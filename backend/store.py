from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional


@dataclass
class MeetingState:
    bot_id: str
    agenda: str = ""
    recent_finals: Deque[str] = field(default_factory=lambda: deque(maxlen=10))

    # Topic tracking (new scope)
    current_topic: str = ""
    last_topic_check_ts: float = 0.0

    # Rate limiting / spam guard
    last_llm_check_ts: float = 0.0
    cooldown_until_ts: float = 0.0

    # Two-strike logic
    strike_count: int = 0
    strike_expires_ts: float = 0.0


# In-memory meeting state store
MEETINGS: Dict[str, MeetingState] = {}


def get_or_create_meeting(bot_id: str) -> MeetingState:
    st = MEETINGS.get(bot_id)
    if st is None:
        st = MeetingState(bot_id=bot_id)
        MEETINGS[bot_id] = st
    return st


def set_agenda(bot_id: str, agenda: str) -> MeetingState:
    st = get_or_create_meeting(bot_id)
    st.agenda = (agenda or "").strip()
    return st


def append_final_line(bot_id: str, line: str) -> MeetingState:
    st = get_or_create_meeting(bot_id)
    line = (line or "").strip()
    if line:
        st.recent_finals.append(line)
    return st


def now_ts() -> float:
    return time.time()
