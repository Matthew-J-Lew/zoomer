# App Features: Gen-Z AI Meeting Moderator

This application is an AI-powered meeting assistant designed to moderate discussions, specifically focusing on keeping meetings on track via tangent detection. It is composed of a FastAPI backend and a Next.js frontend.

## Core Features

### 1. AI Meeting Bot (Backend)
-   **Integration**: Uses [Recall.ai](https://recall.ai/) to spawn a bot that joins video meetings (Zoom, Google Meet, Microsoft Teams, etc.).
-   **Real-time Transcription**: Receives real-time transcript data via webhooks.
-   **Chat Interaction**: The bot can send messages to the meeting chat to intervene or provide feedback.

### 2. Tangent Detection System
The core logic resides in the backend to ensure meetings stick to their agenda.
-   **Agenda Monitoring**: Compares the live conversation against a pre-defined agenda.
-   **LLM Analysis**: Uses an OpenAI-compatible LLM (e.g., GPT-4o-mini) to classify recent conversation segments as "on-topic" or "off-topic".
-   **Strike System**:
    -   Accumulates "strikes" when confident off-topic diversions are detected.
    -   Triggers an intervention after 2 strikes within a short window (default 20s).
-   **Cool-down**: Prevents spamming by enforcing a cool-down period (default 45s) after an intervention.

### 3. Debugging & Developer Tools
-   **Echo Mode**: Optional feature to echo finalized transcript lines back into the meeting chat for verification (`ECHO_TO_CHAT`).
-   **Transcript Logging**: Saves finalized transcript lines to a local JSONL file (`transcript.final.jsonl`) for review.
-   **Health Check**: Simple `/healthz` endpoint to verify backend status.

## Frontend Features (Next.js)
*Currently in early development/scaffold stage.*
-   **Tech Stack**: Next.js 16 (App Router), React 19, Tailwind CSS 4.
-   **Purpose**: Intended to provide a UI for:
    -   Starting the bot (`/start-meeting-bot`).
    -   Setting/updating the meeting agenda.
    -   Monitoring meeting status and debug logs.

## Configuration
Controlled via `backend/.env` (and potentially `frontend/.env` in future).
-   **Recall.ai**: API keys and webhook secrets.
-   **LLM**: API keys for the tangent detector.
-   **Toggles**: Enable/disable tangent detection, adjust thresholds, and set operational modes.
