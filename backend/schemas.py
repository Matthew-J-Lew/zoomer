"""Pydantic models and dataclasses for API request/response schemas."""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, HttpUrl


# --- Transcript Models ---

class TranscriptInfo(BaseModel):
    bot_id: str
    filename: str
    created_at: str
    utterance_count: int


class TranscriptsListResponse(BaseModel):
    transcripts: list[TranscriptInfo]


# --- Meeting Bot Models ---

class StartMeetingBotRequest(BaseModel):
    meeting_url: HttpUrl
    agenda: Optional[str] = None


class StartMeetingBotResponse(BaseModel):
    bot_id: str
    webhook_url: str
    note: str


class SetAgendaRequest(BaseModel):
    agenda: str


# --- Q&A Models ---

class QARequest(BaseModel):
    bot_id: str
    question: str
    post_meeting: bool = False  # True when asking from post-meeting page


class QAResponse(BaseModel):
    bot_id: str
    question: str
    answer: str
    confidence: float


# --- Translation Models ---

class TranslateFileRequest(BaseModel):
    filename: str
    target_lang: str


# --- Internal State ---

@dataclass
class BotDebugState:
    """Debug state for echo throttling per bot."""
    last_echo_ts: float = 0.0
    echo_count: int = 0
