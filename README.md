# Zoomer — AI Meeting Assistant

An accessible AI-powered meeting assistant that provides real-time transcription, topic tracking, AI-generated summaries, transcript translation, and post-meeting Q&A.

---

## Features

### 🎙️ Real-time Meeting Bot
- Integrates with [Recall.ai](https://recall.ai/) to join video meetings (Zoom, Google Meet, Microsoft Teams, etc.)
- Real-time transcription via webhooks
- Topic tracking with periodic updates sent to meeting chat

### 📝 Post-Meeting Recap
- **Video playback** with synced transcript navigation (click transcript to seek)
- **AI-generated summaries** using Gemini
- **Transcript translation** to 10+ languages (Spanish, French, German, Portuguese, Chinese, Japanese, Korean, Hindi, Arabic)
- **Q&A interface** — ask questions about the meeting content
- **PDF export** of meeting summaries

### 📚 Meeting History
- Browse and load previous meeting transcripts
- View past recordings and regenerate summaries

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI, Python 3.9+ |
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript |
| **Styling** | Tailwind CSS 4 |
| **AI/LLM** | OpenAI-compatible API (GPT-4o-mini), Google Gemini |
| **Translation** | deep-translator |
| **Meeting Bot** | Recall.ai |

---

## Prerequisites

- **Python 3.9+**
- **Node.js 18+** (20+ recommended)
- **ngrok** installed + logged in (`ngrok config add-authtoken ...`)
- A **Recall.ai API key**
- An **LLM API key** (OpenAI-compatible) for topic tracking and Q&A
- A **Google Gemini API key** for summaries

---

## Project Structure

```
zoomer/
├── backend/
│   ├── main.py              # FastAPI app with all endpoints
│   ├── llm_client.py        # OpenAI/Gemini LLM integration
│   ├── qa_engine.py         # Q&A engine for post-meeting questions
│   ├── topic_tracker.py     # Real-time topic detection
│   ├── tangent_detector.py  # Meeting tangent detection
│   ├── translate.py         # Translation utilities
│   ├── store.py             # In-memory meeting state
│   ├── transcripts/         # Saved transcript files (JSONL)
│   ├── requirements.txt
│   └── .env                  # Backend config (do not commit)
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Home page (start meeting / view history)
│   │   ├── meeting/         # Live meeting view
│   │   └── post-meeting/    # Recap page (video, transcript, summary, Q&A)
│   ├── components/ui/       # Reusable UI components
│   └── package.json
├── .gitignore
└── README.md
```

---

## Setup

### 1. Backend Setup

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend/.env`:

```env
# Recall.ai
RECALL_API_KEY=YOUR_RECALL_KEY
RECALL_BASE_URL=https://us-west-2.recall.ai

# Public URL for webhooks (set after starting ngrok)
PUBLIC_BASE_URL=

# Webhook token auth
WEBHOOK_TOKEN=dev-secret-token

# Topic tracking
TOPIC_TRACKER_ENABLED=true
TOPIC_CHECK_INTERVAL_S=60

# LLM (OpenAI-compatible) — for topic tracking and Q&A
LLM_API_KEY=YOUR_LLM_KEY
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1

# Gemini — for meeting summaries
GEMINI_API_KEY=YOUR_GEMINI_KEY
```

### 2. Frontend Setup

```powershell
cd frontend
npm install
```

### 3. Start ngrok

```powershell
ngrok http 8000
```

Copy the forwarding URL (e.g., `https://xxxxxx.ngrok-free.dev`) and update `PUBLIC_BASE_URL` in `backend/.env`.

---

## Running the App

### Terminal A — Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000 --env-file .env
```

Verify: http://localhost:8000/healthz → `{"ok": true}`

### Terminal B — Frontend

```powershell
cd frontend
npm run dev
```

Open: http://localhost:3000

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/healthz` | Health check |
| `GET` | `/transcripts` | List saved transcripts |
| `POST` | `/start-meeting-bot` | Start a bot to join a meeting |
| `POST` | `/meeting/{bot_id}/agenda` | Set/update meeting agenda |
| `GET` | `/meeting/{bot_id}/topic` | Get current meeting topic |
| `GET` | `/meeting/{bot_id}/status` | Get bot status + recording URL |
| `GET` | `/meeting/{bot_id}/transcript` | Get full transcript |
| `GET` | `/meeting/{bot_id}/summary` | Generate AI summary |
| `POST` | `/meeting/{bot_id}/leave` | Tell bot to leave meeting |
| `POST` | `/qa` | Ask a question about a meeting |
| `POST` | `/translate-file` | Translate transcript to another language |
| `POST` | `/recall/webhook/realtime/` | Webhook for real-time transcripts |
| `POST` | `/recall/webhook/bot-status/` | Webhook for bot status changes |

---

## Usage

### Start a New Meeting

1. Open http://localhost:3000
2. Enter your meeting link (Zoom, Google Meet, etc.)
3. Optionally add a meeting topic/context
4. Click **Connect Assistant**
5. The bot will join and start transcribing

### View Meeting Recap

After the meeting ends (or select a previous meeting from the home page):

- **Transcript tab**: View/translate the full transcript, click to seek video
- **Summary tab**: AI-generated meeting summary with PDF export
- **Questions tab**: Ask questions about the meeting content

---

## Common Issues

### Bot joins but no transcript appears
- Ensure ngrok is running and `PUBLIC_BASE_URL` is set correctly
- Restart the backend after editing `.env`
- Check that webhook URLs include `?token=...` matching `WEBHOOK_TOKEN`

### Recording not available
- Recording processing can take a few minutes after the meeting ends
- The post-meeting page will poll for up to 2 minutes

### Translation not working
- Ensure `deep-translator` is installed (`pip install deep-translator`)
- Check that the backend has internet access

---

## .gitignore

```
backend/.env
backend/.venv/
backend/__pycache__/
backend/transcripts/
frontend/node_modules/
frontend/.next/
```