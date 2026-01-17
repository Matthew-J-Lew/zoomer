from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from typing import Optional, Set

from llm_client import LLMClient, TopicResult
from store import MeetingState, now_ts


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


def topic_similarity(a: str, b: str) -> float:
    """Returns a similarity score in [0,1]. Higher means more similar."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    # Token overlap (robust for short labels)
    ta = _tokenize(a)
    tb = _tokenize(b)
    jaccard = 0.0
    if ta or tb:
        jaccard = len(ta & tb) / max(1, len(ta | tb))

    # Character-level similarity (helps when topics are phrased similarly)
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()

    # Blend (weighted slightly toward token overlap)
    return 0.6 * jaccard + 0.4 * seq


class TopicTracker:
    """Every N seconds, infer the current topic from recent transcript.

    If the topic changes "enough" compared to the previous topic, returns a message
    you can post in chat.
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("TOPIC_CHECK_ENABLED", "true").lower() == "true"
        self.check_every_s = float(os.getenv("TOPIC_CHECK_EVERY_S", "30"))
        self.sim_threshold = float(os.getenv("TOPIC_SIMILARITY_THRESHOLD", "0.72"))
        self.min_confidence = float(os.getenv("TOPIC_MIN_CONFIDENCE", "0.5"))
        self.min_context_chars = int(os.getenv("TOPIC_MIN_CONTEXT_CHARS", "80"))

        self._client: Optional[LLMClient] = None

    def _client_or_none(self) -> Optional[LLMClient]:
        if self._client is not None:
            return self._client
        try:
            self._client = LLMClient()
            return self._client
        except Exception:
            # If no LLM key set, skip topic checks safely
            return None

    def should_check(self, st: MeetingState) -> bool:
        if not self.enabled:
            return False
        now = now_ts()
        return (now - st.last_topic_check_ts) >= self.check_every_s

    def _recent_context_text(self, st: MeetingState) -> str:
        # Most recent last
        return "\n".join(list(st.recent_finals)[-10:])

    async def infer_topic(self, st: MeetingState) -> Optional[TopicResult]:
        client = self._client_or_none()
        if client is None:
            return None

        st.last_topic_check_ts = now_ts()
        recent_context = self._recent_context_text(st).strip()
        if len(recent_context) < self.min_context_chars:
            return None

        return await client.detect_topic(meeting_context=st.agenda, recent_context=recent_context)

    def is_changed_enough(self, previous: str, new: str) -> bool:
        prev = (previous or "").strip()
        new = (new or "").strip()
        if not new:
            return False
        if not prev:
            return True
        sim = topic_similarity(prev, new)
        return sim < self.sim_threshold

    def format_chat_message(self, topic: str) -> str:
        # Keep it short and readable in Zoom chat
        topic = (topic or "").strip()
        if len(topic) > 120:
            topic = topic[:117] + "..."
        return f"🧠 Topic check: {topic}"
