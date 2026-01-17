# Hackville — Gen‑Z AI Meeting Moderator (Recall.ai + Next.js)

This repo is split into two apps:

- **backend/**: FastAPI server that creates a Recall.ai bot, receives real‑time transcript webhooks, runs tangent detection, and sends chat messages.
- **frontend/**: Next.js UI to start/monitor meetings (you’ll build this next).

---

## 0) Prereqs

- **Python 3.9+**
- **Node.js 18+** (20+ recommended)
- **ngrok** installed + logged in (`ngrok config add-authtoken ...`)
- A **Recall.ai API key**
- (For tangent detection) an **LLM API key** (OpenAI‑compatible)

---

## 1) Repo structure

Recommended layout:

```
Hackville/
  backend/
    main.py
    store.py
    tangent_detector.py
    llm_client.py
    requirements.txt
    .env            # backend only (do not commit)
    .venv/          # backend only (do not commit)
  frontend/
    ...Next.js app...
  .gitignore
  README.md
```

> Tip: keep `.env`, `.venv`, and `__pycache__` inside `backend/` and gitignore them.

---

## 2) Create the Next.js frontend (from repo root)

### Using npm (recommended)

```bash
mkdir frontend
cd frontend
npm create next-app@latest .
```

When prompted, a good default setup is:
- TypeScript: **Yes**
- ESLint: **Yes**
- Tailwind: **Yes**
- App Router: **Yes**
- src/ directory: **Yes** (optional; either is fine)
- Import alias: **Yes** (e.g. `@/*`)

Then start the frontend dev server:

```bash
npm run dev
```

The app will run at:

- http://localhost:3000

---

## 3) Backend setup

### 3.1 Create & activate venv (Windows PowerShell)

From repo root:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3.2 Create `.env` (backend/.env)

Create `backend/.env` with:

```env
# Recall
RECALL_API_KEY=YOUR_RECALL_KEY
RECALL_BASE_URL=https://us-west-2.recall.ai

# Public URL for webhooks (set after ngrok)
PUBLIC_BASE_URL=

# Webhook token auth (you choose)
WEBHOOK_TOKEN=dev-secret-token

# Debug (optional): echo finalized transcript lines back into Zoom chat
ECHO_TO_CHAT=true
ECHO_MIN_SECONDS=4
ECHO_MAX_MESSAGES=20

# Transcript file output
TRANSCRIPT_OUTFILE=transcript.final.jsonl

# Tangent detection toggles
TANGENT_DETECTOR_ENABLED=true
TANGENT_CHECK_EVERY_S=5
TANGENT_CONFIDENCE_THRESHOLD=0.7
TANGENT_COOLDOWN_S=45
TANGENT_STRIKE_WINDOW_S=20

# LLM (OpenAI-compatible). Required for tangent detection.
LLM_API_KEY=YOUR_LLM_KEY
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_TIMEOUT_S=20
```

> If `LLM_API_KEY` is missing, tangent detection will safely skip.

---

## 4) Run everything (local dev)

You will run **three terminals**:

### Terminal A — Backend (FastAPI)

From repo root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000 --env-file .env
```

Sanity check:

- http://localhost:8000/healthz  → `{"ok": true}`

### Terminal B — ngrok (public webhook tunnel)

```powershell
ngrok http 8000
```

Copy the forwarding URL, for example:

- `https://xxxxxx.ngrok-free.dev`

Put it into `backend/.env`:

```env
PUBLIC_BASE_URL=https://xxxxxx.ngrok-free.dev
```

Then **restart Terminal A** (Ctrl+C then run uvicorn again) so the backend reloads `.env`.

### Terminal C — Start the bot (join Zoom)

Start a bot and provide an agenda (agenda is required for tangent detection):

```powershell
$body = @{
  meeting_url = "https://YOUR_ZOOM_LINK_HERE"
  agenda = "Decide MVP scope, assign tasks, and agree on the demo plan."
} | ConvertTo-Json

$response = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/start-meeting-bot" -ContentType "application/json" -Body $body
$response
```

Copy the returned `bot_id`.

Optional: set/update agenda later:

```powershell
$botId = $response.bot_id
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/meeting/$botId/agenda" -ContentType "application/json" -Body (@{ agenda="Updated agenda text" } | ConvertTo-Json)
```

---

## 5) Verify it works

### Transcript
When people talk, backend logs should show:

- `[partial] (...) Speaker: ...`
- `[final] (...) Speaker: ...`

### Chat messages
- If `ECHO_TO_CHAT=true`, the bot will post “Echo …” messages to Zoom chat (throttled).
- For tangent detection, after sustained off-topic conversation, you should see:
  - `[tangent_check] ...` in logs
  - A single “back on track” message in Zoom chat (cooldown prevents spam).

### Transcript file
Backend writes finalized transcript lines to:

- `backend/transcript.final.jsonl`

---

## 6) Common issues

### Bot joins but chat messages don’t appear
This is usually Zoom meeting settings:
- Chat set to “Host only” or restricted.
- Enable chat for “Everyone”.

### No webhook traffic arrives
- Ensure ngrok is running and `PUBLIC_BASE_URL` is updated correctly.
- Ensure you restarted uvicorn after editing `.env`.
- Ensure your webhook URL includes `?token=...` and `WEBHOOK_TOKEN` matches.

### Tangent detector never runs
- Ensure `agenda` is set (via start-meeting-bot request or the agenda endpoint).
- Ensure `LLM_API_KEY` is set.
- Check logs for `[tangent_check]`.

---

## 7) Next.js frontend ↔ backend connection (dev)

In development, you can call the backend directly from Next.js:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

If you hit CORS issues later, add FastAPI CORS middleware, or proxy via Next.js route handlers.

---

## Useful endpoints

- `GET  /healthz`
- `POST /start-meeting-bot`
- `POST /meeting/{bot_id}/agenda`
- `POST /recall/webhook/realtime/` (called by Recall via ngrok)

---

## Suggested .gitignore additions

```
backend/.env
backend/.venv/
backend/__pycache__/
backend/*.jsonl
frontend/node_modules/
frontend/.next/
```
