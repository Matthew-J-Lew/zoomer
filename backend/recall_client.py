"""Recall.ai API client functions."""

from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from config import BOT_NAME, RECALL_API_KEY, RECALL_BASE_URL


def _auth_headers() -> Dict[str, str]:
    """Build authentication headers for Recall.ai API."""
    return {
        "Authorization": f"Token {RECALL_API_KEY}" if not RECALL_API_KEY.startswith("Token ") else RECALL_API_KEY,
        "accept": "application/json",
        "content-type": "application/json",
    }


async def recall_create_bot(meeting_url: str, webhook_url: str) -> Dict[str, Any]:
    """Create a new bot via Recall.ai API."""
    if not RECALL_API_KEY:
        raise RuntimeError("Missing RECALL_API_KEY")

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
            "video_mixed_mp4": {},  # Enable MP4 recording
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
                "message": "👋 I'm here. I'll be taking notes and am open to answering any questions you may have.",
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
    """Send a chat message via the bot."""
    url = f"{RECALL_BASE_URL}/api/v1/bot/{bot_id}/send_chat_message/"
    body = {"message": message}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=_auth_headers(), json=body)
        print("[send_chat_message] status:", resp.status_code, "body:", resp.text[:300])
        if resp.status_code >= 300:
            print("[send_chat_message] failed:", resp.status_code, resp.text)


async def recall_fetch_recording_url(bot_id: str) -> Optional[str]:
    """Fetch the recording download URL from Recall.ai after meeting ends."""
    url = f"{RECALL_BASE_URL}/api/v1/bot/{bot_id}/"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=_auth_headers())
            if resp.status_code >= 300:
                print(f"[fetch_recording] failed: {resp.status_code} {resp.text}")
                return None
            
            data = resp.json()
            recordings = data.get("recordings") or []
            if not recordings:
                print(f"[fetch_recording] No recordings found for bot {bot_id}")
                return None
            
            # Get the first recording's video_mixed download URL
            media_shortcuts = recordings[0].get("media_shortcuts") or {}
            video_mixed = media_shortcuts.get("video_mixed") or {}
            video_data = video_mixed.get("data") or {}
            download_url = video_data.get("download_url")
            
            if download_url:
                print(f"[fetch_recording] Got recording URL for bot {bot_id}")
            else:
                print(f"[fetch_recording] Recording not ready yet for bot {bot_id}")
            
            return download_url
    except Exception as e:
        print(f"[fetch_recording] error: {repr(e)}")
        return None


async def recall_leave_call(bot_id: str) -> None:
    """Tell the bot to leave the meeting."""
    if not RECALL_API_KEY:
        raise HTTPException(500, "RECALL_API_KEY not set.")

    url = f"{RECALL_BASE_URL}/api/v1/bot/{bot_id}/leave_call/"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=_auth_headers())
        if resp.status_code >= 300:
            print(f"[leave_call] failed: {resp.status_code} {resp.text}")
            raise HTTPException(
                status_code=resp.status_code,
                detail={"error": "Failed to leave call", "body": resp.text},
            )
