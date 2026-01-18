from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


@dataclass
class TangentResult:
    on_topic: bool
    confidence: float
    reason: str
    message: str


@dataclass
class TopicResult:
    topic: str
    confidence: float
    reason: str


@dataclass
class QAResult:
    answer: str
    confidence: float


@dataclass
class SummaryResult:
    summary: str  # Markdown formatted summary
    confidence: float


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _normalize_json_object(obj: Any) -> Dict[str, Any]:
    """Normalize model JSON output to a dict.

    Some models may return a JSON array (e.g. [{...}]) even when asked for a
    single JSON object. We normalize to the first dict when possible.
    """

    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj[0]
    raise ValueError(f"Expected JSON object, got: {type(obj).__name__}")


def _extract_json_object(text: str) -> Dict[str, Any]:
    """
    Attempts to parse a JSON object from a model response.
    Supports:
      - pure JSON
      - JSON wrapped in text
    """
    text = text.strip()
    try:
        return _normalize_json_object(json.loads(text))
    except Exception:
        m = _JSON_OBJECT_RE.search(text)
        if not m:
            raise ValueError(f"Model did not return JSON. Raw: {text[:400]}")
        return _normalize_json_object(json.loads(m.group(0)))


def _clamp01(x: Any) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


class LLMClient:
    """LLM client with pluggable providers.

    Supported providers:
    - openai: OpenAI-compatible /chat/completions API
    - gemini: Google Generative Language API (generateContent)
    """

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        self.timeout_s = float(os.getenv("LLM_TIMEOUT_S", "20"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "500"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))

        if self.provider == "gemini":
            # Prefer GEMINI_API_KEY but allow LLM_API_KEY as fallback.
            self.api_key = (os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip())
            self.model = os.getenv("LLM_MODEL", "gemini-2.0-flash").strip()
            # Base URL is fixed for Gemini.
            self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        else:
            # OpenAI-compatible
            self.api_key = os.getenv("LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
            self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            self.model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

        if not self.api_key:
            raise RuntimeError(
                "Missing API key. Set LLM_API_KEY (openai) or GEMINI_API_KEY (gemini) in .env"
            )

    async def _chat_json(self, system: str, user: str) -> Dict[str, Any]:
        """Call the configured provider and return a parsed JSON object."""
        if self.provider == "gemini":
            return await self._chat_json_gemini(system=system, user=user)
        return await self._chat_json_openai(system=system, user=user)

    async def _chat_json_openai(self, system: str, user: str) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 300:
                raise RuntimeError(f"LLM error {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_json_object(content)

    async def _chat_json_gemini(self, system: str, user: str) -> Dict[str, Any]:
        # Gemini doesn't have a separate system role in this REST API; we prepend.
        prompt = f"{system}\n\n{user}".strip()
        url = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self.api_key}
        payload: Dict[str, Any] = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]},
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, params=params, json=payload)
            if resp.status_code >= 300:
                raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text[:500]}")
            data = resp.json()

            # Typical shape: candidates[0].content.parts[0].text
            try:
                parts = data["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            except Exception:
                raise RuntimeError(f"Unexpected Gemini response: {str(data)[:500]}")

            # Remove code fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
            return _extract_json_object(text)

    async def classify_tangent(self, agenda: str, recent_context: str) -> TangentResult:
        system = (
            "You are a meeting moderator. Your job is to keep discussion aligned to the agenda."
        )
        user = (
            "Agenda:\n"
            f"{agenda}\n\n"
            "Recent transcript (most recent last):\n"
            f"{recent_context}\n\n"
            "Return JSON only:\n"
            '{\n'
            '  "on_topic": true/false,\n'
            '  "confidence": number 0..1,\n'
            '  "reason": "short reason",\n'
            '  "message": "If off-topic, 1 short chat message. If on-topic, empty string."\n'
            '}\n'
            "Rules:\n"
            "- Mark on_topic = true if discussion is still related to agenda, even if loosely.\n"
            "- Only mark off-topic if clearly unrelated for >10 seconds.\n"
            "- Keep message <= 160 characters.\n"
            "- Avoid personal insults, slurs, or harassment.\n"
        )

        obj = await self._chat_json(system=system, user=user)

        on_topic = bool(obj.get("on_topic", True))
        confidence = _clamp01(obj.get("confidence", 0.0))
        reason = str(obj.get("reason", "") or "").strip()
        message = str(obj.get("message", "") or "").strip()

        if on_topic:
            message = ""

        # Enforce <= 160 chars
        if len(message) > 160:
            message = message[:157] + "..."

        return TangentResult(
            on_topic=on_topic,
            confidence=confidence,
            reason=reason,
            message=message,
        )

    async def detect_topic(self, meeting_context: str, recent_context: str) -> TopicResult:
        """Infer the current meeting topic from recent transcript.

        Returns a short topic label (not a full sentence).
        """
        system = "You summarize meeting conversation into a short current topic label for chat check-ins."
        user = (
            "Meeting context (agenda / goal). This may be empty:\n"
            f"{(meeting_context or '').strip()}\n\n"
            "Recent transcript (most recent last):\n"
            f"{recent_context}\n\n"
            "Return JSON only:\n"
            "{\n"
            "  \"topic\": \"short topic label\",\n"
            "  \"confidence\": number 0..1,\n"
            "  \"reason\": \"brief reason\"\n"
            "}\n"
            "Rules:\n"
            "- Output a topic label, a couple sentences.\n"
            "- If the transcript is too thin/unclear, lower confidence.\n"
        )

        obj = await self._chat_json(system=system, user=user)

        topic = str(obj.get("topic", "") or "").strip()
        confidence = _clamp01(obj.get("confidence", 0.0))
        reason = str(obj.get("reason", "") or "").strip()

        # Hard limits
        if len(topic) > 80:
            topic = topic[:77] + "..."

        return TopicResult(topic=topic, confidence=confidence, reason=reason)

    async def answer_question(
        self,
        agenda: str,
        current_topic: str,
        question: str,
        transcript_excerpts: str,
    ) -> QAResult:
        """Answer a question using only provided transcript excerpts.

        The caller is responsible for retrieving relevant excerpts.
        """

        system = (
            "You are a sarcastic-but-helpful Gen-Z meeting assistant. "
            "Answer questions using ONLY the provided transcript excerpts. "
            "If the answer is not in the excerpts, say you haven't heard it yet."
        )

        user = (
            "Meeting agenda/goal (may be empty):\n"
            f"{(agenda or '').strip()}\n\n"
            "Current inferred topic (may be empty):\n"
            f"{(current_topic or '').strip()}\n\n"
            "Question:\n"
            f"{(question or '').strip()}\n\n"
            "Transcript excerpts (most recent last):\n"
            f"{transcript_excerpts}\n\n"
            "Return JSON only:\n"
            "{\n"
            "  \"answer\": \"2 sentences max\",\n"
            "  \"confidence\": number 0..1\n"
            "}\n"
            "Rules:\n"
            "- Keep the answer to ~2 sentences.\n"
            "- Don't invent details; if it's not in the excerpts, say you haven't heard it yet.\n"
            "- Avoid targeting individuals; keep tone constructive.\n"
        )

        obj = await self._chat_json(system=system, user=user)

        answer = str(obj.get("answer", "") or "").strip()
        confidence = _clamp01(obj.get("confidence", 0.0))

        # Light hard limits for chat usability
        if len(answer) > 350:
            answer = answer[:347] + "..."

        return QAResult(answer=answer, confidence=confidence)

    def _chunk_transcript(self, transcript_text: str, max_chars: int = 25000) -> list[str]:
        """Split transcript into chunks that fit within context limits."""
        if len(transcript_text) <= max_chars:
            return [transcript_text]

        chunks = []
        lines = transcript_text.split("\n")
        current_chunk = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            if current_len + line_len > max_chars and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = line_len
            else:
                current_chunk.append(line)
                current_len += line_len

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    async def _summarize_chunk(self, chunk: str, chunk_num: int, total_chunks: int) -> str:
        """Summarize a single transcript chunk."""
        system = (
            "You are a professional meeting assistant. "
            "Summarize the meeting transcript excerpt provided. "
            "Extract key points, decisions, and action items mentioned."
        )
        user = (
            f"This is part {chunk_num} of {total_chunks} of a meeting transcript.\n\n"
            "Transcript:\n"
            f"{chunk}\n\n"
            "Return JSON only:\n"
            "{\n"
            "  \"key_points\": [\"point 1\", \"point 2\"],\n"
            "  \"action_items\": [\"action 1\", \"action 2\"],\n"
            "  \"decisions\": [\"decision 1\"],\n"
            "  \"discussion_summary\": \"Brief summary of what was discussed\"\n"
            "}\n"
        )

        obj = await self._chat_json(system=system, user=user)
        return json.dumps(obj)

    async def generate_summary(
        self,
        transcript_text: str,
        meeting_date: str = "",
    ) -> SummaryResult:
        """Generate a markdown meeting summary from transcript.

        Handles long transcripts by chunking and combining summaries.
        """
        if not transcript_text.strip():
            return SummaryResult(
                summary="*No transcript available to summarize.*",
                confidence=0.0,
            )

        chunks = self._chunk_transcript(transcript_text)
        print(f"[summary] Processing {len(chunks)} chunk(s)")

        # Summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks, 1):
            try:
                summary = await self._summarize_chunk(chunk, i, len(chunks))
                chunk_summaries.append(summary)
            except Exception as e:
                print(f"[summary] Chunk {i} failed: {repr(e)}")
                chunk_summaries.append("{}")

        # Combine chunk summaries into final summary
        combined_context = "\n---\n".join(chunk_summaries)

        system = (
            "You are a professional meeting assistant. "
            "Create a well-structured meeting summary in Markdown format. "
            "Combine the provided chunk summaries into a cohesive document."
        )
        user = (
            "Combine these meeting summary excerpts into a final meeting summary:\n\n"
            f"{combined_context}\n\n"
            f"Meeting date: {meeting_date or 'Not specified'}\n\n"
            "Return JSON with a single field:\n"
            "{\n"
            "  \"markdown\": \"Full markdown summary\",\n"
            "  \"confidence\": number 0..1\n"
            "}\n\n"
            "The markdown should follow this structure:\n"
            "# Meeting Summary\n"
            "**Date:** [date]\n\n"
            "## Key Points\n"
            "- point 1\n"
            "- point 2\n\n"
            "## Action Items\n"
            "- [ ] Action 1\n"
            "- [ ] Action 2\n\n"
            "## Decisions Made\n"
            "- Decision 1\n\n"
            "## Discussion Topics\n"
            "Brief narrative of what was discussed.\n\n"
            "Rules:\n"
            "- Be concise but comprehensive\n"
            "- Use bullet points for clarity\n"
            "- Use checkboxes for action items\n"
            "- Combine duplicate items from different chunks\n"
        )

        try:
            obj = await self._chat_json(system=system, user=user)
            markdown = str(obj.get("markdown", "") or "").strip()
            confidence = _clamp01(obj.get("confidence", 0.7))

            if not markdown:
                markdown = "*Failed to generate summary. Please try again.*"
                confidence = 0.0

            return SummaryResult(summary=markdown, confidence=confidence)
        except Exception as e:
            print(f"[summary] Final combination failed: {repr(e)}")
            return SummaryResult(
                summary="*Error generating summary. Please try again.*",
                confidence=0.0,
            )

