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


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> Dict[str, Any]:
    """
    Attempts to parse a JSON object from a model response.
    Supports:
      - pure JSON
      - JSON wrapped in text
    """
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = _JSON_OBJECT_RE.search(text)
        if not m:
            raise ValueError(f"Model did not return JSON. Raw: {text[:400]}")
        return json.loads(m.group(0))


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
    """
    OpenAI-compatible Chat Completions client.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
        self.timeout_s = float(os.getenv("LLM_TIMEOUT_S", "20"))

        if not self.api_key:
            raise RuntimeError("Missing LLM_API_KEY (set in .env)")

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

        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }

        # If supported by the provider, request JSON mode (harmless if ignored)
        payload["response_format"] = {"type": "json_object"}

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
            obj = _extract_json_object(content)

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
