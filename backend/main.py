"""Zoomer API - FastAPI application with meeting bot endpoints."""

from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette import status
from svix.webhooks import Webhook, WebhookVerificationError

# Config
from config import (
    PUBLIC_BASE_URL,
    RECALL_API_KEY,
    RECALL_WEBHOOK_SECRET,
    WEBHOOK_TOKEN,
)

# Schemas
from schemas import (
    QARequest,
    QAResponse,
    SetAgendaRequest,
    StartMeetingBotRequest,
    StartMeetingBotResponse,
    TranscriptsListResponse,
    TranslateFileRequest,
)

# Services
from llm_client import LLMClient
from recall_client import (
    recall_create_bot,
    recall_fetch_recording_url,
    recall_leave_call,
)
from store import get_or_create_meeting, set_agenda, set_status
from transcript_service import (
    list_transcript_files,
    load_transcript_from_file,
    translate_file_with_cache,
)
from webhook_handlers import (
    get_qa_engine,
    handle_bot_status_change,
    handle_chat_message,
    handle_participant_join,
    handle_transcript_event,
    init_bot_state,
)


# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Zoomer API")

# CORS (needed for Next.js dev server calling FastAPI from the browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---------------------------------------------------------------------------
# Transcript Endpoints
# ---------------------------------------------------------------------------

@app.get("/transcripts", response_model=TranscriptsListResponse)
async def list_transcripts():
    """List available transcripts from the transcripts directory."""
    transcripts = list_transcript_files()
    return TranscriptsListResponse(transcripts=transcripts)


# ---------------------------------------------------------------------------
# Q&A Endpoint
# ---------------------------------------------------------------------------

@app.post("/qa", response_model=QAResponse)
async def qa(req: QARequest):
    """Web (private) Q&A endpoint.

    The frontend can call this with a bot_id + question and get a short answer.
    Loads transcript from file if not in memory (for historical transcripts).
    """
    load_transcript_from_file(req.bot_id)

    st = get_or_create_meeting(req.bot_id)
    qa_engine = get_qa_engine()
    res = await qa_engine.answer(st, req.question, post_meeting=req.post_meeting)
    if res is None:
        raise HTTPException(400, "QA is disabled")
    return QAResponse(
        bot_id=req.bot_id,
        question=req.question,
        answer=res.answer,
        confidence=res.confidence,
    )


# ---------------------------------------------------------------------------
# Meeting Bot Endpoints
# ---------------------------------------------------------------------------

@app.post("/start-meeting-bot", response_model=StartMeetingBotResponse)
async def start_meeting_bot(req: StartMeetingBotRequest):
    """Start a new meeting bot."""
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
    init_bot_state(bot_id)
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
    """Update the meeting agenda."""
    st = set_agenda(bot_id, req.agenda)
    return {"bot_id": bot_id, "agenda": st.agenda}


@app.get("/meeting/{bot_id}/topic")
async def get_topic(bot_id: str):
    """Return the current topic for a meeting."""
    st = get_or_create_meeting(bot_id)
    return {
        "bot_id": bot_id,
        "topic": st.current_topic,
        "last_updated": st.last_topic_check_ts,
    }


@app.get("/meeting/{bot_id}/status")
async def get_status(bot_id: str):
    """Return the current status of the bot.

    Status values: "joining", "in_call", "done", "error"
    """
    load_transcript_from_file(bot_id)
    
    st = get_or_create_meeting(bot_id)
    
    # For historical/done transcripts without recording URL, try to fetch it
    if st.status == "done" and not st.recording_url and st.transcript_history:
        try:
            recording_url = await recall_fetch_recording_url(bot_id)
            if recording_url:
                st.recording_url = recording_url
        except Exception as e:
            print(f"[get_status] Error fetching recording URL: {repr(e)}")
    
    return {
        "bot_id": bot_id,
        "status": st.status,
        "topic": st.current_topic,
        "status_updated_at": st.status_updated_at,
        "recording_url": st.recording_url,
    }


@app.get("/meeting/{bot_id}/transcript")
async def get_transcript(bot_id: str):
    """Return the full transcript for a meeting."""
    load_transcript_from_file(bot_id)
    
    st = get_or_create_meeting(bot_id)
    transcript = [
        {
            "ts": u.ts,
            "speaker": u.speaker,
            "text": u.text,
        }
        for u in st.transcript_history
    ]
    return {
        "bot_id": bot_id,
        "recording_started_at": st.recording_started_at,
        "transcript": transcript,
    }


@app.get("/meeting/{bot_id}/summary")
async def get_summary(bot_id: str):
    """Generate a meeting summary using Gemini."""
    load_transcript_from_file(bot_id)
    
    st = get_or_create_meeting(bot_id)
    
    if not st.transcript_history:
        return {
            "bot_id": bot_id,
            "summary": "*No transcript available to summarize.*",
            "confidence": 0.0,
        }
    
    # Format transcript as text for LLM
    transcript_lines = [f"{u.speaker}: {u.text}" for u in st.transcript_history]
    transcript_text = "\n".join(transcript_lines)
    
    # Get meeting date from first utterance
    meeting_date = ""
    if st.transcript_history:
        first_ts = st.transcript_history[0].ts
        meeting_date = datetime.fromtimestamp(first_ts).strftime("%B %d, %Y")
    
    try:
        llm = LLMClient()
        result = await llm.generate_summary(
            transcript_text=transcript_text,
            meeting_date=meeting_date,
        )
        return {
            "bot_id": bot_id,
            "summary": result.summary,
            "confidence": result.confidence,
        }
    except Exception as e:
        print(f"[summary] Error: {repr(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}",
        )


@app.post("/meeting/{bot_id}/leave")
async def leave_meeting(bot_id: str):
    """Tell the bot to leave the meeting."""
    await recall_leave_call(bot_id)
    set_status(bot_id, "done")
    return {"bot_id": bot_id, "status": "done"}


# ---------------------------------------------------------------------------
# Translation Endpoint
# ---------------------------------------------------------------------------

@app.post("/translate-file")
async def translate_file(req: TranslateFileRequest):
    """Translate a transcript file, with caching."""
    return await translate_file_with_cache(req.filename, req.target_lang)


# ---------------------------------------------------------------------------
# Webhook Endpoints
# ---------------------------------------------------------------------------

@app.post("/recall/webhook/realtime/", status_code=status.HTTP_204_NO_CONTENT)
async def recall_webhook_realtime(request: Request):
    """Handle realtime events from Recall.ai (transcript, chat, etc.)."""
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
        await handle_transcript_event(bot_id, event, words, participant)
        return

    # Participant events: join
    if event == "participant_events.join":
        inner = (payload.get("data") or {}).get("data") or {}
        participant = inner.get("participant") or {}
        await handle_participant_join(bot_id, participant)
        return

    # Participant events: chat messages
    if event == "participant_events.chat_message":
        inner = (payload.get("data") or {}).get("data") or {}
        participant = inner.get("participant") or {}
        data = inner.get("data") or {}
        await handle_chat_message(bot_id, participant, data)
        return

    return


@app.post("/recall/webhook/bot_status/", status_code=status.HTTP_204_NO_CONTENT)
async def recall_webhook_bot_status(request: Request):
    """Handle bot status change webhooks from Recall.ai."""
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

    event = payload.get("event", "")
    data = payload.get("data") or {}
    bot_id = data.get("bot_id") or (data.get("bot") or {}).get("id") or "unknown"

    await handle_bot_status_change(bot_id, event, data)
    return
