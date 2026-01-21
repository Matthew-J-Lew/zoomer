"""Webhook event processing handlers."""

import asyncio
import re
import time
from typing import Any, Dict, Optional

from config import (
    BOT_NAME,
    ECHO_MAX_MESSAGES,
    ECHO_MIN_SECONDS,
    ECHO_TO_CHAT,
    MENTION_RE,
)
from qa_engine import QAEngine
from recall_client import recall_send_chat_message
from schemas import BotDebugState
from store import (
    append_final_utterance,
    get_or_create_meeting,
    remember_participant,
    set_status,
)
from topic_tracker import TopicTracker
from transcript_service import save_transcript_line


# In-memory debug store (echo throttling per bot)
BOT_STATE: Dict[str, BotDebugState] = {}

# Prevent overlapping topic-check LLM calls per bot.
TOPIC_TASK_RUNNING: Dict[str, bool] = {}

# Global instances (initialized on first use)
_qa_engine: Optional[QAEngine] = None
_topic_tracker: Optional[TopicTracker] = None


def get_qa_engine() -> QAEngine:
    """Get or create the QA engine instance."""
    global _qa_engine
    if _qa_engine is None:
        _qa_engine = QAEngine()
    return _qa_engine


def get_topic_tracker() -> TopicTracker:
    """Get or create the topic tracker instance."""
    global _topic_tracker
    if _topic_tracker is None:
        _topic_tracker = TopicTracker()
    return _topic_tracker


def words_to_text(words: list[dict]) -> str:
    """Convert a list of word objects to a text string."""
    return " ".join([w.get("text", "").strip() for w in words]).strip()


def extract_question_from_chat(text: str) -> Optional[str]:
    """Returns the extracted question if the chat message is addressed to the bot.

    We treat messages that contain '@<BOT_NAME>' (or '<BOT_NAME>') as questions.
    """
    t = (text or "").strip()
    if not t:
        return None

    if not MENTION_RE.search(t):
        return None

    # Remove the mention and leading punctuation
    t = MENTION_RE.sub("", t, count=1).strip()
    t = re.sub(r"^[\s:,-]+", "", t).strip()
    if not t:
        return None
    return t


def should_echo(bot_id: str) -> bool:
    """Check if we should echo this message (for debug mode)."""
    st = BOT_STATE.setdefault(bot_id, BotDebugState())
    now = time.time()
    if st.echo_count >= ECHO_MAX_MESSAGES:
        return False
    if now - st.last_echo_ts < ECHO_MIN_SECONDS:
        return False
    st.last_echo_ts = now
    st.echo_count += 1
    return True


def init_bot_state(bot_id: str) -> None:
    """Initialize debug state for a new bot."""
    BOT_STATE[bot_id] = BotDebugState()


async def handle_transcript_event(
    bot_id: str,
    event: str,
    words: list[dict],
    participant: dict,
) -> None:
    """Handle transcript.partial_data and transcript.data events."""
    text = words_to_text(words)
    speaker = participant.get("name") or f"participant:{participant.get('id', 'unknown')}"

    if event == "transcript.partial_data":
        print(f"[partial] ({bot_id}) {speaker}: {text}")
        return

    # transcript.data (finalized)
    print(f"[final] ({bot_id}) {speaker}: {text}")
    append_final_utterance(bot_id, speaker=speaker, text=text, ts=time.time())

    # Update status to in_call when we receive transcript data
    st = get_or_create_meeting(bot_id)
    if st.status == "joining":
        set_status(bot_id, "in_call")
    
    # Track recording start time (first transcript = recording start)
    if st.recording_started_at == 0.0:
        st.recording_started_at = time.time()
        print(f"[recording] Started at {st.recording_started_at} for bot {bot_id}")

    # Save transcript line (per-meeting file)
    save_transcript_line(bot_id, speaker, text, participant, event)

    # Optional echo (debug)
    if ECHO_TO_CHAT and bot_id != "unknown" and text:
        if should_echo(bot_id):
            msg = f"Echo 🧾 {speaker}: {text}"
            if len(msg) > 180:
                msg = msg[:177] + "..."
            await recall_send_chat_message(bot_id, msg)

    # Topic check-in
    if bot_id != "unknown":
        await _maybe_run_topic_check(bot_id, st)


async def _maybe_run_topic_check(bot_id: str, st) -> None:
    """Run topic check if conditions are met."""
    import os
    
    topic_tracker = get_topic_tracker()
    
    if not topic_tracker.should_check(st) or TOPIC_TASK_RUNNING.get(bot_id):
        return
    
    # Mark as running and advance the timer immediately
    TOPIC_TASK_RUNNING[bot_id] = True
    st.last_topic_check_ts = time.time()

    async def _run_topic_check() -> None:
        try:
            topic_result = await topic_tracker.infer_topic(st)
            if not topic_result:
                return

            print(
                "[topic_check]",
                {
                    "topic": topic_result.topic,
                    "conf": topic_result.confidence,
                    "reason": topic_result.reason,
                    "prev": st.current_topic,
                },
            )

            if topic_result.confidence >= float(os.getenv("TOPIC_MIN_CONFIDENCE", "0.5")):
                if topic_tracker.is_changed_enough(st.current_topic, topic_result.topic):
                    st.current_topic = topic_result.topic
                    msg = topic_tracker.format_chat_message(topic_result.topic)
                    await recall_send_chat_message(bot_id, msg)
        except Exception as e:
            print("[topic_check] error:", repr(e))
        finally:
            TOPIC_TASK_RUNNING.pop(bot_id, None)

    asyncio.create_task(_run_topic_check())


async def handle_participant_join(bot_id: str, participant: dict) -> None:
    """Handle participant_events.join events."""
    name = participant.get("name") or ""
    pid = participant.get("id") or ""
    if bot_id != "unknown":
        remember_participant(bot_id, name=name, pid=str(pid))


async def handle_chat_message(
    bot_id: str,
    participant: dict,
    data: dict,
) -> None:
    """Handle participant_events.chat_message events."""
    text = (data.get("text") or "").strip()
    to_field = (data.get("to") or "").strip()
    speaker = participant.get("name") or f"participant:{participant.get('id', 'unknown')}"

    # Debug visibility: log every chat message event we receive.
    print(f"[chat_event] ({bot_id}) {speaker} -> {to_field or 'unknown_to'}: {text}")

    # Prevent loops: ignore the bot's own messages
    if speaker.strip().lower() == BOT_NAME.lower():
        return

    question = extract_question_from_chat(text)
    # Fallback: some platforms format mentions oddly, but still set `to`.
    if not question and to_field:
        if BOT_NAME.lower() in to_field.lower() or "bot" in to_field.lower():
            question = re.sub(r"^@\S+\s+", "", text).strip() or text
    if not question:
        return

    print(f"[chat_question] ({bot_id}) {speaker}: {question}")

    async def _handle_question() -> None:
        if bot_id == "unknown":
            return
        qa_engine = get_qa_engine()
        st = get_or_create_meeting(bot_id)
        res = await qa_engine.answer(st, question)
        if res is None:
            return
        # Public reply (Zoom chat is used for public questions)
        msg = f"🤖 {speaker}: {res.answer}"
        if len(msg) > 380:
            msg = msg[:377] + "..."
        await recall_send_chat_message(bot_id, msg)

    asyncio.create_task(_handle_question())


async def handle_bot_status_change(bot_id: str, event: str, data: dict) -> None:
    """Handle bot status change events."""
    from recall_client import recall_fetch_recording_url
    
    print(f"[bot_status] event={event} bot_id={bot_id}")

    # Map Recall events to our status values
    status_map = {
        "bot.joining_call": "joining",
        "bot.in_call_not_recording": "in_call",
        "bot.in_call_recording": "in_call",
        "bot.in_waiting_room": "joining",
        "bot.call_ended": "done",
        "bot.done": "done",
        "bot.fatal": "error",
    }

    new_status = status_map.get(event)
    if new_status and bot_id != "unknown":
        set_status(bot_id, new_status)
        print(f"[bot_status] Updated {bot_id} status to {new_status}")

        # When meeting ends, fetch the recording URL
        if new_status == "done":
            async def _fetch_recording():
                try:
                    await asyncio.sleep(2)
                    recording_url = await recall_fetch_recording_url(bot_id)
                    if recording_url:
                        st = get_or_create_meeting(bot_id)
                        st.recording_url = recording_url
                        print(f"[bot_status] Stored recording URL for {bot_id}")
                except Exception as e:
                    print(f"[bot_status] Error fetching recording: {repr(e)}")

            asyncio.create_task(_fetch_recording())
