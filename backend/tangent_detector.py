from __future__ import annotations

import os
from typing import Optional

from llm_client import LLMClient, TangentResult
from store import MeetingState, now_ts


class TangentDetector:
    def __init__(self) -> None:
        self.enabled = os.getenv("TANGENT_DETECTOR_ENABLED", "true").lower() == "true"
        self.conf_threshold = float(os.getenv("TANGENT_CONFIDENCE_THRESHOLD", "0.7"))
        self.check_every_s = float(os.getenv("TANGENT_CHECK_EVERY_S", "5"))
        self.cooldown_s = float(os.getenv("TANGENT_COOLDOWN_S", "45"))
        self.strike_window_s = float(os.getenv("TANGENT_STRIKE_WINDOW_S", "20"))

        self._client: Optional[LLMClient] = None

    def _client_or_none(self) -> Optional[LLMClient]:
        if self._client is not None:
            return self._client
        try:
            self._client = LLMClient()
            return self._client
        except Exception:
            # If no LLM key set, we just won’t run detection (safe for dev)
            return None

    def should_check(self, st: MeetingState) -> bool:
        if not self.enabled:
            return False
        if not st.agenda.strip():
            return False

        now = now_ts()
        if now - st.last_llm_check_ts < self.check_every_s:
            return False

        return True

    def _recent_context_text(self, st: MeetingState) -> str:
        # Most recent last
        return "\n".join(list(st.recent_finals)[-10:])

    async def classify(self, st: MeetingState) -> Optional[TangentResult]:
        client = self._client_or_none()
        if client is None:
            return None

        st.last_llm_check_ts = now_ts()
        recent_context = self._recent_context_text(st)
        return await client.classify_tangent(st.agenda, recent_context)

    def register_strike_and_should_intervene(self, st: MeetingState, result: TangentResult) -> bool:
        now = now_ts()

        # Cooldown guard
        if now < st.cooldown_until_ts:
            return False

        # Only act on confident off-topic
        if result.on_topic or result.confidence < self.conf_threshold:
            # Reset strikes if on-topic
            st.strike_count = 0
            st.strike_expires_ts = 0.0
            return False

        # Strike window logic
        if st.strike_expires_ts < now:
            st.strike_count = 0

        st.strike_count += 1
        st.strike_expires_ts = now + self.strike_window_s

        if st.strike_count >= 2:
            st.cooldown_until_ts = now + self.cooldown_s
            st.strike_count = 0
            st.strike_expires_ts = 0.0
            return True

        return False
