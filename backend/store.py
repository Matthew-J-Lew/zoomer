from __future__ import annotations

import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional


# Minimal stopwords for a cheap inverted index.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
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
    "it",
    "this",
    "that",
    "we",
    "you",
    "i",
}


def _index_tokens(s: str) -> List[str]:
    s = (s or "").lower()
    tokens = re.findall(r"[a-z0-9]+", s)
    out: List[str] = []
    for t in tokens:
        if len(t) <= 2:
            continue
        if t in _STOPWORDS:
            continue
        out.append(t)
    return out


@dataclass
class TranscriptUtterance:
    ts: float
    speaker: str
    text: str


@dataclass
class MeetingState:
    bot_id: str
    agenda: str = ""

    # Short rolling buffer for near-real-time checks (topic/tangent)
    recent_finals: Deque[str] = field(default_factory=lambda: deque(maxlen=10))

    # Append-only transcript in memory (for Q&A across the full meeting)
    transcript_history: List[TranscriptUtterance] = field(default_factory=list)

    # Cheap inverted index: token -> list of utterance indices
    token_index: Dict[str, List[int]] = field(default_factory=dict)

    # Participant lookup (useful for future DM replies on Zoom)
    participant_name_to_id: Dict[str, str] = field(default_factory=dict)

    # Optional memory cap (0 = unlimited). If set, we keep only the most recent N utterances.
    transcript_max_utterances: int = 0

    # Topic tracking
    current_topic: str = ""
    last_topic_check_ts: float = 0.0

    # Rate limiting / spam guard
    last_llm_check_ts: float = 0.0
    cooldown_until_ts: float = 0.0

    # Two-strike logic
    strike_count: int = 0
    strike_expires_ts: float = 0.0

    # Bot lifecycle status: "joining", "in_call", "done", "error"
    status: str = "joining"
    status_updated_at: float = 0.0


# In-memory meeting state store
MEETINGS: Dict[str, MeetingState] = {}


def get_or_create_meeting(bot_id: str) -> MeetingState:
    st = MEETINGS.get(bot_id)
    if st is None:
        st = MeetingState(bot_id=bot_id)
        try:
            st.transcript_max_utterances = int(os.getenv("TRANSCRIPT_MAX_UTTERANCES", "0"))
        except Exception:
            st.transcript_max_utterances = 0
        MEETINGS[bot_id] = st
    return st


def set_agenda(bot_id: str, agenda: str) -> MeetingState:
    st = get_or_create_meeting(bot_id)
    st.agenda = (agenda or "").strip()
    return st


def set_status(bot_id: str, status: str) -> MeetingState:
    """Update the bot lifecycle status."""
    st = get_or_create_meeting(bot_id)
    st.status = status
    st.status_updated_at = time.time()
    return st


def _rebuild_index(st: MeetingState) -> None:
    st.token_index = {}
    for idx, u in enumerate(st.transcript_history):
        for tok in _index_tokens(u.text):
            st.token_index.setdefault(tok, []).append(idx)


def append_final_utterance(
    bot_id: str,
    speaker: str,
    text: str,
    ts: Optional[float] = None,
) -> MeetingState:
    """Append a finalized utterance to both the rolling buffer and the full transcript.

    This powers:
    - Topic / tangent checks (rolling buffer)
    - Q&A retrieval over the whole meeting (append-only transcript + index)
    """

    st = get_or_create_meeting(bot_id)

    sp = (speaker or "unknown").strip() or "unknown"
    tx = (text or "").strip()
    if not tx:
        return st

    ts_val = ts if ts is not None else time.time()

    # Rolling buffer for near-real-time checks
    st.recent_finals.append(f"{sp}: {tx}")

    # Append-only transcript
    idx = len(st.transcript_history)
    st.transcript_history.append(TranscriptUtterance(ts=ts_val, speaker=sp, text=tx))

    # Update cheap index
    for tok in _index_tokens(tx):
        st.token_index.setdefault(tok, []).append(idx)

    # Optional memory cap (rarely used in hackathon MVP; safe guard for very long meetings)
    if st.transcript_max_utterances and len(st.transcript_history) > st.transcript_max_utterances:
        st.transcript_history = st.transcript_history[-st.transcript_max_utterances :]
        _rebuild_index(st)

    return st


def append_final_line(bot_id: str, line: str) -> MeetingState:
    """Backwards-compatible helper: accepts a single formatted line.

    If the line looks like 'Speaker: text', we'll parse it.
    Otherwise we store it under speaker='unknown'.
    """

    st = get_or_create_meeting(bot_id)
    line = (line or "").strip()
    if not line:
        return st

    speaker = "unknown"
    text = line
    m = re.match(r"^([^:]{1,64}):\s+(.*)$", line)
    if m:
        speaker = m.group(1).strip() or "unknown"
        text = (m.group(2) or "").strip()

    return append_final_utterance(bot_id, speaker=speaker, text=text)


def remember_participant(bot_id: str, name: str, pid: str) -> "MeetingState":
    st = get_or_create_meeting(bot_id)
    name = (name or "").strip()
    pid = (pid or "").strip()
    if name and pid:
        st.participant_name_to_id[name] = pid
    return st


def append_utterance(bot_id: str, speaker: str, text: str, ts=None) -> "MeetingState":
    """Backward-compatible alias used by older code paths."""
    return append_final_utterance(bot_id, speaker=speaker, text=text, ts=ts)


def now_ts() -> float:
    return time.time()
