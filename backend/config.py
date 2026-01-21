"""Configuration and environment variables for the Zoomer backend."""

import os
import re
from typing import List

# Directory for transcript files
TRANSCRIPTS_DIR = "transcripts"
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

# Recall.ai API settings
RECALL_API_KEY = os.getenv("RECALL_API_KEY", "")
RECALL_BASE_URL = os.getenv("RECALL_BASE_URL", "https://us-west-2.recall.ai").rstrip("/")

# Public URL for webhooks (ngrok URL in dev)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# Webhook authentication
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")
RECALL_WEBHOOK_SECRET = os.getenv("RECALL_WEBHOOK_SECRET", "")

# Echo mode (debug)
ECHO_TO_CHAT = os.getenv("ECHO_TO_CHAT", "false").lower() == "true"
ECHO_MIN_SECONDS = float(os.getenv("ECHO_MIN_SECONDS", "4"))
ECHO_MAX_MESSAGES = int(os.getenv("ECHO_MAX_MESSAGES", "20"))

# Legacy setting (kept for compatibility)
TRANSCRIPT_OUTFILE = os.getenv("TRANSCRIPT_OUTFILE", "transcript.final.jsonl")

# Bot identity
BOT_NAME = os.getenv("BOT_NAME", "Meeting Moderator").strip() or "Meeting Moderator"

# Optional extra strings that should count as "mentioning" the bot in chat.
# Example: BOT_MENTION_ALIASES="Meeting Moderator (Recall),Moderator"
BOT_MENTION_ALIASES: List[str] = [
    s.strip() for s in os.getenv("BOT_MENTION_ALIASES", "").split(",") if s.strip()
]


def _build_mention_re() -> re.Pattern:
    """Build a regex that matches any configured bot name alias."""
    names = [BOT_NAME] + BOT_MENTION_ALIASES
    # Sort longer first to avoid partial matches
    names = sorted({n for n in names if n.strip()}, key=len, reverse=True)
    if not names:
        names = ["bot"]
    alts = "|".join(re.escape(n) for n in names)
    return re.compile(r"@?\s*(?:" + alts + r")\b", re.IGNORECASE)


# Pre-compiled mention regex
MENTION_RE = _build_mention_re()
