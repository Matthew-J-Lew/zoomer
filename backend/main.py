import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, HttpUrl

# Optional signature verification (Svix-style headers)
from svix.webhooks import Webhook, WebhookVerificationError

from store import append_final_line, get_or_create_meeting, set_agenda
from tangent_detector import TangentDetector

app = FastAPI(title="Gen-Z Meeting Moderator (MVP Increment 2: Tangent Detection)")

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

detector = TangentDetector()


class StartMeetingBotRequest(BaseModel):
    meeting_url: HttpUrl
    agenda: Optional[str] = None


class StartMeetingBotResponse(BaseModel):
    bot_id: str
    webhook_url: str
    note: str


class SetAgendaRequest(BaseModel):
    agenda: str


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
                    "events": ["transcript.partial_data", "transcript.data"],
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
            "Tangent detection runs on finalized transcript.data when agenda is set."
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
    if event not in ("transcript.partial_data", "transcript.data"):
        return

    inner = (payload.get("data") or {}).get("data") or {}
    words = inner.get("words") or []
    participant = inner.get("participant") or {}
    bot = (payload.get("data") or {}).get("bot") or {}
    bot_id = bot.get("id") or "unknown"

    text = words_to_text(words)
    speaker = participant.get("name") or f"participant:{participant.get('id', 'unknown')}"

    if event == "transcript.partial_data":
        print(f"[partial] ({bot_id}) {speaker}: {text}")
        return

    # transcript.data (finalized)
    print(f"[final] ({bot_id}) {speaker}: {text}")

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

    # Keep rolling transcript buffer for tangent detection
    append_final_line(bot_id, f"{speaker}: {text}")

    # Optional echo (debug)
    if ECHO_TO_CHAT and bot_id != "unknown" and text:
        if should_echo(bot_id):
            msg = f"Echo 🧾 {speaker}: {text}"
            if len(msg) > 180:
                msg = msg[:177] + "..."
            await recall_send_chat_message(bot_id, msg)

    # Tangent detection (Option B)
    if bot_id != "unknown":
        st = get_or_create_meeting(bot_id)

        if detector.should_check(st):
            result = await detector.classify(st)
            if result:
                print("[tangent_check]", {"on_topic": result.on_topic, "conf": result.confidence, "reason": result.reason})

                if detector.register_strike_and_should_intervene(st, result):
                    if result.message:
                        await recall_send_chat_message(bot_id, result.message)

    return
