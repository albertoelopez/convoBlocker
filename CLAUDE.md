# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ConvoBlocker is an AI-powered Chrome extension for real-time conversation moderation. It contains **two independent implementations** in the same repo:

- **`claude_version/`** — YouTube Live Chat Blocker (batch-processing, LangChain agent, SQLite persistence)
- **`codex_version/`** — Social Feed Filter (multi-platform, DSPy/DeepAgents, stateless)

Each version has its own backend (Python/FastAPI) and extension (Chrome Manifest V3, vanilla JS). They do not share code.

## Running the Backends

Both backends require Python 3.12+ with their own virtual environments.

```bash
# Claude version (YouTube)
cd claude_version/backend
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Codex version (Social feeds)
cd codex_version/agent_service
source .venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

Install dependencies with `pip install -r requirements.txt` in each backend directory. The codex version also needs `cp .env.example .env` with API keys configured.

## Loading the Extensions

Open `chrome://extensions`, enable Developer mode, click "Load unpacked", and select the relevant `extension/` directory. No build step is needed — both extensions are vanilla JavaScript.

## Architecture

### Claude Version Pipeline

Content script (`content.js`) watches YouTube live chat via MutationObserver, batches up to 15 messages (3-second flush interval), and sends `ANALYZE_BATCH` messages to the background service worker. The background script forwards batches to `POST /analyze` on the FastAPI backend. The backend runs a multi-step agent pipeline:

1. **Pattern Detection** (`tools/pattern_detector.py`) — free heuristics (URLs, caps, emoji density, length)
2. **Message Classification** (`tools/message_classifier.py`) — DSPy + LLM sentiment/category classification
3. **User History** (`tools/user_history.py`) — SQLite lookup of past messages
4. **Decision Making** (`tools/decision_maker.py`) — chain-of-thought final decision (block/allow/watch)

Results are cached in-memory with a 5-minute TTL keyed by username. Block decisions trigger native YouTube block actions via DOM automation in the content script.

The agent (`agent.py`) tries DeepAgents first, falls back to LangChain's `create_react_agent`. Supports Gemini 2.0 Flash or local Ollama models.

### Codex Version Pipeline

Content script detects feed items across platforms (Twitter/X, Reddit, YouTube) using CSS selectors, extracts text, and optionally sends it to the background worker → `POST /filter`. The backend returns `{hide, reason, confidence, label}`. Content is hidden by collapsing or removing DOM elements.

Supports two runtimes via `FILTER_RUNTIME` env var: `dspy` (default, multi-provider) or `deepagents` (OpenAI only).

### Message Passing

Both versions use Chrome Runtime messaging (`chrome.runtime.sendMessage`) from content script → background service worker → HTTP to backend. Message types include: `ANALYZE_BATCH`, `GET_STATS`, `GET_BLOCK_LOG`, `SAVE_SETTINGS`, `GET_SETTINGS`, `HEALTH_CHECK`, `UNBLOCK_USER`, `GET_OLLAMA_MODELS`, `RUN_AGENT_FILTER`.

### Storage

- **Claude version**: `chrome.storage.local` for extension settings; aiosqlite (`db.py`) for user history, decisions, and stats on the backend; `config.json` for runtime settings
- **Codex version**: `chrome.storage.sync` for all settings (syncs across devices); stateless backend

### Error Handling Philosophy

Both versions fail safe: on backend errors, the claude version returns "allow" decisions (don't disrupt chat), and the codex version keeps content visible (don't hide by accident).

## Key API Endpoints

### Claude version (`server.py`)
- `POST /analyze` — batch message analysis
- `GET /stats` — moderation statistics
- `GET /block-log` — decision history
- `POST /settings` / `GET /settings` — configuration
- `POST /unblock/{username}` — remove from cache
- `GET /ollama-models` — list local Ollama models

### Codex version (`app.py`)
- `POST /filter` — content filtering decision
- `GET /health` — health check with runtime info

## AI Provider Configuration

Both versions support multiple AI providers: Gemini, OpenAI, Groq, Ollama (local). Provider/model selection is done through the extension UI (popup for claude_version, options page for codex_version). API keys are stored in extension storage and passed to the backend via settings endpoints or environment variables.
