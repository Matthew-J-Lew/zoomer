import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, HttpUrl

# Optional signature verification (Svix-style headers)
from svix.webhooks import Webhook, WebhookVerificationError

from qa_engine import QAEngine
from store import append_final_utterance, get_or_create_meeting, remember_participant, set_agenda
from topic_tracker import TopicTracker

app = FastAPI(title="Gen-Z Meeting Moderator (MVP: Topic Check-ins)")

RECALL_API_KEY = os.getenv("RECALL_API_KEY", "")
RECALL_BASE_URL = os.getenv("RECALL_BASE_URL", "https://us-west-2.recall.ai").rstrip("/")

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
RECALL_WEBHOOK_SECRET = os.getenv("RECALL_WEBHOOK_SECRET", "")

# Echo mode (debug)
ECHO_TO_CHAT = os.getenv("ECHO_TO_CHAT", "false").lower() == "true"
ECHO_MIN_SECONDS = float(os.getenv("ECHO_MIN_SECONDS", "4"))
ECHO_MAX_MESSAGES = int(os.getenv("ECHO_MAX_MESSAGES", "20"))

TRANSCRIPT_OUTFILE = os.getenv("TRANSCRIPT_OUTFILE", "transcript.final.jsonl")

BOT_NAME = os.getenv("BOT_NAME", "Meeting Moderator").strip() or "Meeting Moderator"

# Optional extra strings that should count as "mentioning" the bot in chat.
# Example: BOT_MENTION_ALIASES="Meeting Moderator (Recall),Moderator"
BOT_MENTION_ALIASES = [s.strip() for s in os.getenv("BOT_MENTION_ALIASES", "").split(",") if s.strip()]

qa_engine = QAEngine()

topic_tracker = TopicTracker()

# Prevent overlapping topic-check LLM calls per bot.
TOPIC_TASK_RUNNING: Dict[str, bool] = {}


class StartMeetingBotRequest(BaseModel):
    meeting_url: HttpUrl
    agenda: Optional[str] = None


class StartMeetingBotResponse(BaseModel):
    bot_id: str
    webhook_url: str
    note: str


class SetAgendaRequest(BaseModel):
    agenda: str


class QARequest(BaseModel):
    bot_id: str
    question: str


class QAResponse(BaseModel):
    bot_id: str
    question: str
    answer: str
    confidence: float


@dataclass
class BotDebugState:
    last_echo_ts: float = 0.0
    echo_count: int = 0


# In-memory debug store (echo throttling per bot)
BOT_STATE: Dict[str, BotDebugState] = {}


def _auth_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Token {RECALL_API_KEY}" if not RECALL_API_KEY.startswith("Token ") else RECALL_API_KEY,
        "accept": "application/json",
        "content-type": "application/json",
    }


async def recall_create_bot(meeting_url: str, webhook_url: str) -> Dict[str, Any]:
    if not RECALL_API_KEY:
        raise RuntimeError("Missing RECALL_API_KEY")
    if not PUBLIC_BASE_URL:
        raise RuntimeError("Missing PUBLIC_BASE_URL (needed to build webhook URL)")

    url = f"{RECALL_BASE_URL}/api/v1/bot/"

    body = {
        "meeting_url": meeting_url,
        "bot_name": BOT_NAME,
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {
                        "mode": "prioritize_low_latency",
                        "language_code": "en",
                    }
                }
            },
            "realtime_endpoints": [
                {
                    "type": "webhook",
                    "url": webhook_url,
                    "events": [
                        "transcript.partial_data",
                        "transcript.data",
                        "participant_events.chat_message",
                        "participant_events.join",
                    ],
                }
            ],
        },
        "chat": {
            "on_bot_join": {
                "send_to": "everyone",
                "message": "👋 I’m here. I’ll be quietly judging… and taking notes.",
            }
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=_auth_headers(), json=body)
        if resp.status_code >= 300:
            raise HTTPException(
                status_code=resp.status_code,
                detail={"error": "Recall create bot failed", "body": resp.text},
            )
        return resp.json()


async def recall_send_chat_message(bot_id: str, message: str) -> None:
    url = f"{RECALL_BASE_URL}/api/v1/bot/{bot_id}/send_chat_message/"
    body = {"message": message}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=_auth_headers(), json=body)
        print("[send_chat_message] status:", resp.status_code, "body:", resp.text[:300])
        if resp.status_code >= 300:
            print("[send_chat_message] failed:", resp.status_code, resp.text)


def words_to_text(words: list[dict]) -> str:
    return " ".join([w.get("text", "").strip() for w in words]).strip()


def _build_mention_re() -> re.Pattern:
    # Build a forgiving regex that matches any configured alias.
    names = [BOT_NAME] + BOT_MENTION_ALIASES
    # Sort longer first to avoid partial matches
    names = sorted({n for n in names if n.strip()}, key=len, reverse=True)
    if not names:
        names = ["bot"]
    alts = "|".join(re.escape(n) for n in names)
    return re.compile(r"@?\s*(?:" + alts + r")\b", re.IGNORECASE)


_MENTION_RE = _build_mention_re()


def extract_question_from_chat(text: str) -> Optional[str]:
    """Returns the extracted question if the chat message is addressed to the bot.

    We treat messages that contain '@<BOT_NAME>' (or '<BOT_NAME>') as questions.
    """

    t = (text or "").strip()
    if not t:
        return None

    if not _MENTION_RE.search(t):
        return None

    # Remove the mention and leading punctuation
    t = _MENTION_RE.sub("", t, count=1).strip()
    t = re.sub(r"^[\s:,-]+", "", t).strip()
    if not t:
        return None
    return t


def should_echo(bot_id: str) -> bool:
    st = BOT_STATE.setdefault(bot_id, BotDebugState())
    now = time.time()
    if st.echo_count >= ECHO_MAX_MESSAGES:
        return False
    if now - st.last_echo_ts < ECHO_MIN_SECONDS:
        return False
    st.last_echo_ts = now
    st.echo_count += 1
    return True


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/qa", response_model=QAResponse)
async def qa(req: QARequest):
    """Web (private) Q&A endpoint.

    The frontend can call this with a bot_id + question and get a short answer.
    """

    st = get_or_create_meeting(req.bot_id)
    res = await qa_engine.answer(st, req.question)
    if res is None:
        raise HTTPException(400, "QA is disabled")
    return QAResponse(
        bot_id=req.bot_id,
        question=req.question,
        answer=res.answer,
        confidence=res.confidence,
    )


@app.post("/start-meeting-bot", response_model=StartMeetingBotResponse)
async def start_meeting_bot(req: StartMeetingBotRequest):
    if not PUBLIC_BASE_URL:
        raise HTTPException(500, "PUBLIC_BASE_URL not set (ngrok URL in dev).")
    if not RECALL_API_KEY:
        raise HTTPException(500, "RECALL_API_KEY not set.")

    webhook_url = f"{PUBLIC_BASE_URL}/recall/webhook/realtime/"
    if WEBHOOK_TOKEN:
        webhook_url = f"{webhook_url}?token={WEBHOOK_TOKEN}"

    data = await recall_create_bot(str(req.meeting_url), webhook_url)
    bot_id = data.get("id")
    if not bot_id:
        raise HTTPException(500, {"error": "Unexpected Recall response (missing bot id)", "data": data})

    # Initialize meeting state
    BOT_STATE[bot_id] = BotDebugState()
    get_or_create_meeting(bot_id)

    # If agenda provided up front, store it now
    if req.agenda:
        set_agenda(bot_id, req.agenda)

    return StartMeetingBotResponse(
        bot_id=bot_id,
        webhook_url=webhook_url,
        note=(
            "Bot created. Transcript will stream to webhook. "
            "Every ~30s, the bot infers the current topic from recent transcript and posts an update if it changes."
        ),
    )


@app.post("/meeting/{bot_id}/agenda")
async def update_agenda(bot_id: str, req: SetAgendaRequest):
    st = set_agenda(bot_id, req.agenda)
    return {"bot_id": bot_id, "agenda": st.agenda}


@app.post("/recall/webhook/realtime/", status_code=status.HTTP_204_NO_CONTENT)
async def recall_webhook_realtime(request: Request):
    raw = await request.body()
    headers = dict(request.headers)

    if RECALL_WEBHOOK_SECRET:
        try:
            wh = Webhook(RECALL_WEBHOOK_SECRET)
            payload: Dict[str, Any] = wh.verify(raw, headers)  # type: ignore
        except WebhookVerificationError:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        token = request.query_params.get("token")
        if WEBHOOK_TOKEN and token != WEBHOOK_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid token")
        payload = await request.json()

    event = payload.get("event")

    bot = (payload.get("data") or {}).get("bot") or {}
    bot_id = bot.get("id") or "unknown"

    # Transcript events
    if event in ("transcript.partial_data", "transcript.data"):
        inner = (payload.get("data") or {}).get("data") or {}
        words = inner.get("words") or []
        participant = inner.get("participant") or {}
        text = words_to_text(words)
        speaker = participant.get("name") or f"participant:{participant.get('id', 'unknown')}"

        if event == "transcript.partial_data":
            print(f"[partial] ({bot_id}) {speaker}: {text}")
            return

        # transcript.data (finalized)
        print(f"[final] ({bot_id}) {speaker}: {text}")
        append_final_utterance(bot_id, speaker=speaker, text=text, ts=time.time())

        
# Save transcript line
        line = {
            "ts": time.time(),
            "bot_id": bot_id,
            "speaker": speaker,
            "participant": participant,
            "text": text,
            "raw_event": event,
        }
        with open(TRANSCRIPT_OUTFILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

        # Keep rolling buffers

        # Optional echo (debug)
        if ECHO_TO_CHAT and bot_id != "unknown" and text:
            if should_echo(bot_id):
                msg = f"Echo 🧾 {speaker}: {text}"
                if len(msg) > 180:
                    msg = msg[:177] + "..."
                await recall_send_chat_message(bot_id, msg)

        # Topic check-in (new scope)
        if bot_id != "unknown":
            st = get_or_create_meeting(bot_id)

            if topic_tracker.should_check(st) and not TOPIC_TASK_RUNNING.get(bot_id):
                # Mark as running and advance the timer immediately so we don't queue a burst.
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
                        # Never break the webhook loop due to LLM issues.
                        print("[topic_check] error:", repr(e))
                    finally:
                        TOPIC_TASK_RUNNING.pop(bot_id, None)

                asyncio.create_task(_run_topic_check())

        return

    # Participant events: join
    if event == "participant_events.join":
        inner = (payload.get("data") or {}).get("data") or {}
        participant = inner.get("participant") or {}
        name = participant.get("name") or ""
        pid = participant.get("id") or ""
        if bot_id != "unknown":
            remember_participant(bot_id, name=name, pid=str(pid))
        return

    # Participant events: chat messages
    if event == "participant_events.chat_message":
        inner = (payload.get("data") or {}).get("data") or {}
        participant = inner.get("participant") or {}
        data = inner.get("data") or {}
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
            # If the message is directed at the bot (DM or reply), treat it as a question.
            # We keep this forgiving to avoid missing queries.
            if BOT_NAME.lower() in to_field.lower() or "bot" in to_field.lower():
                # Strip a leading @mention if present
                question = re.sub(r"^@\S+\s+", "", text).strip() or text
        if not question:
            return

        print(f"[chat_question] ({bot_id}) {speaker}: {question}")

        async def _handle_question() -> None:
            if bot_id == "unknown":
                return
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
        return

    return
