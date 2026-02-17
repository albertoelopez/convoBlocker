# Repository Guidelines

## Project Structure & Module Organization
This repository contains two parallel implementations of the same idea:
- `claude_version/`: YouTube live-chat blocker.
- `codex_version/`: Multi-platform feed filter (X/Reddit/YouTube).

Each implementation is split into:
- `extension/`: Chrome Manifest V3 client (`manifest.json`, `content.js`, `background.js`, popup/options UI files).
- Backend service folder (`claude_version/backend/`, `codex_version/agent_service/`) with FastAPI entrypoints and AI logic.

Shared visuals live in `assets/` (for example `assets/hero.svg`). Keep new assets here unless they are extension-specific.

## Build, Test, and Development Commands
Run commands from the relevant implementation directory.

- `python -m venv .venv && source .venv/bin/activate`
Creates and activates a local virtual environment.
- `pip install -r requirements.txt`
Installs backend dependencies.
- `uvicorn server:app --host 0.0.0.0 --port 8000 --reload` (Claude backend)
Runs the YouTube moderation API.
- `uvicorn app:app --host 127.0.0.1 --port 8000 --reload` (Codex backend)
Runs the feed-filter API.

Extension dev loop: load unpacked extension from `chrome://extensions`, then reload extension and refresh target tabs after code changes.

## Coding Style & Naming Conventions
- Python: follow PEP 8, 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes.
- JavaScript: 2-4 spaces consistently per file (preserve existing style), `camelCase` for variables/functions, `UPPER_SNAKE_CASE` for constants.
- Keep files focused: platform DOM logic in `content.js`, messaging/network flow in `background.js`, UI state in popup/options scripts.

## Testing Guidelines
There is currently no committed automated test suite. Before opening a PR:
- Manually verify backend health and key API path (`POST /filter` where applicable).
- Manually verify extension behavior on at least one supported site.
- Validate failure paths (API unavailable, invalid key, disabled filtering).
If you add tests, place backend tests under `*/backend/tests/` or `*/agent_service/tests/` and use `test_*.py`.

## Commit & Pull Request Guidelines
Current history favors short, imperative commit subjects (for example: `Fix AI provider init...`, `Add README...`).
- Keep subject lines concise and action-first.
- Group related code + docs updates in the same commit.

PRs should include:
- Clear summary of behavior changes.
- Affected implementation (`claude_version` and/or `codex_version`).
- Manual test steps and results.
- Screenshots/GIFs for popup/options UI changes.

## Security & Configuration Tips
- Never commit API keys or filled `.env` files.
- Keep provider keys in local environment or extension settings only.
- Review `manifest.json` permission changes carefully and document why each new permission is required.
