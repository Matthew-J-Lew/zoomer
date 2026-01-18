from __future__ import annotations

import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Set, Tuple

from llm_client import LLMClient, QAResult
from store import MeetingState, TranscriptUtterance


_STOPWORDS: Set[str] = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "so",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "at",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "this",
    "that",
    "we",
    "you",
    "i",
    "they",
    "he",
    "she",
    "them",
    "us",
    "our",
    "your",
    "my",
    "me",
    "as",
    "from",
    "into",
    "about",
    "can",
    "could",
    "should",
    "would",
    "will",
    "just",
    "like",
}


def _tokenize(s: str) -> Set[str]:
    s = (s or "").lower()
    tokens = re.findall(r"[a-z0-9]+", s)
    out: Set[str] = set()
    for t in tokens:
        if t in _STOPWORDS:
            continue
        if len(t) <= 2:
            continue
        out.add(t)
    return out


def _similarity(a: str, b: str) -> float:
    """Loose similarity in [0,1]."""
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0

    ta = _tokenize(a)
    tb = _tokenize(b)
    jaccard = 0.0
    if ta or tb:
        jaccard = len(ta & tb) / max(1, len(ta | tb))

    seq = SequenceMatcher(None, a, b).ratio()
    return 0.65 * jaccard + 0.35 * seq


def _score_utterance(question: str, u: TranscriptUtterance) -> float:
    # Keyword overlap + light string similarity
    base = _similarity(question, u.text)

    # If the utterance explicitly contains some key tokens, boost
    qt = _tokenize(question)
    ut = _tokenize(u.text)
    if qt and ut:
        overlap = len(qt & ut) / max(1, len(qt))
        base = max(base, overlap)

    return base


def _format_excerpts(excerpts: List[TranscriptUtterance], max_chars: int = 2200) -> str:
    # Most recent last
    lines: List[str] = []
    for u in excerpts:
        lines.append(f"{u.speaker}: {u.text}")

    joined = "\n".join(lines)
    if len(joined) <= max_chars:
        return joined

    # Trim from the front until within budget
    while lines and len("\n".join(lines)) > max_chars:
        lines.pop(0)
    return "\n".join(lines)


@dataclass
class QAResponse:
    answer: str
    confidence: float
    used_excerpts: List[str]


class QAEngine:
    """Answer questions from the meeting transcript.

    - Zoom public questions: detected from chat_message events when people @-mention the bot.
    - Web private questions: served by POST /qa.
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("QA_ENABLED", "true").lower() == "true"
        self.max_excerpts = int(os.getenv("QA_MAX_EXCERPTS", "8"))
        self.min_score = float(os.getenv("QA_MIN_SCORE", "0.18"))
        self.min_context_chars = int(os.getenv("QA_MIN_CONTEXT_CHARS", "40"))

        self._client: Optional[LLMClient] = None

    def _client_or_none(self) -> Optional[LLMClient]:
        if self._client is not None:
            return self._client
        try:
            self._client = LLMClient()
            return self._client
        except Exception:
            return None

    def retrieve(self, st: MeetingState, question: str) -> List[TranscriptUtterance]:
        question = (question or "").strip()
        if not question:
            return []

        history = list(getattr(st, "transcript_history", []))
        if not history:
            return []

        # --- Indexed candidate selection (cheap) ---
        # If we have an inverted index on the meeting state, use it to avoid
        # scanning the entire transcript for every question.
        candidates: List[Tuple[int, TranscriptUtterance]] = []
        index = getattr(st, "token_index", None)
        qt = _tokenize(question)
        if isinstance(index, dict) and qt:
            idxs: Set[int] = set()
            for tok in qt:
                for i in index.get(tok, [])[-300:]:
                    idxs.add(int(i))
            # If the index yields nothing, fall back to full scan.
            if idxs:
                # Keep candidates in chronological order
                for i in sorted(idxs):
                    if 0 <= i < len(history):
                        candidates.append((i, history[i]))
        if not candidates:
            # No index / no matches: consider everything
            candidates = list(enumerate(history))

        scored: List[Tuple[float, int, TranscriptUtterance]] = []
        for idx, u in candidates:
            s = _score_utterance(question, u)
            if s <= 0.0:
                continue
            scored.append((s, idx, u))

        if not scored:
            # Fallback: last few utterances
            return history[-min(10, len(history)) :]

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [u for (s, _, u) in scored[: self.max_excerpts] if s >= self.min_score]

        if not top:
            # Fallback: last few utterances
            return history[-min(10, len(history)) :]

        # Keep in chronological order
        top_set = set((u.ts, u.speaker, u.text) for u in top)
        chrono = [u for u in history if (u.ts, u.speaker, u.text) in top_set]
        return chrono

    async def answer(self, st: MeetingState, question: str) -> Optional[QAResponse]:
        if not self.enabled:
            return None

        client = self._client_or_none()
        if client is None:
            return QAResponse(
                answer="LLM isn't configured yet (set LLM_API_KEY).",
                confidence=0.0,
                used_excerpts=[],
            )

        excerpts = self.retrieve(st, question)
        excerpts_text = _format_excerpts(excerpts)
        if len(excerpts_text.strip()) < self.min_context_chars:
            return QAResponse(
                answer="I haven't heard enough yet to answer that. Try again after a bit more context.",
                confidence=0.1,
                used_excerpts=[],
            )

        res: QAResult = await client.answer_question(
            agenda=st.agenda,
            current_topic=st.current_topic,
            question=question,
            transcript_excerpts=excerpts_text,
        )

        used_lines = [f"{u.speaker}: {u.text}" for u in excerpts]
        answer = (res.answer or "").strip()
        if not answer:
            answer = "I don't have a clean answer yet based on what I've heard so far."

        return QAResponse(answer=answer, confidence=res.confidence, used_excerpts=used_lines)
