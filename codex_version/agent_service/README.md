# Autonomous Filter Agent Service

Local API used by the Chrome extension for autonomous filtering.

## Setup
1. Create a virtualenv and install dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
2. Set env vars:
   - `cp .env.example .env`
   - Fill the key for the provider you plan to use (`OPENAI_API_KEY` or `GEMINI_API_KEY` or `GROQ_API_KEY`)
3. Run API:
   - `uvicorn app:app --host 127.0.0.1 --port 8000 --reload`

## Runtime selection
- `FILTER_RUNTIME=deepagents` uses https://github.com/langchain-ai/deepagents
- `FILTER_RUNTIME=dspy` uses https://github.com/stanfordnlp/dspy
- Default is `dspy`

Example:
- `FILTER_RUNTIME=dspy uvicorn app:app --host 127.0.0.1 --port 8000 --reload`

## Provider selection (DSPy runtime)
Send these fields in `POST /filter`:
- `provider`: `openai` | `gemini` | `groq` | `ollama`
- `provider_model`: model id
- `provider_base_url`: optional (used for Ollama/custom base URL)
- `api_keys`: optional object with `openai`, `gemini`, `groq`, `ollama`

Expected keys by provider:
- `openai`: `OPENAI_API_KEY`
- `gemini`: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- `groq`: `GROQ_API_KEY`
- `ollama`: no cloud key required (defaults to `OLLAMA_BASE_URL=http://127.0.0.1:11434/v1`)

## API
- `POST /filter`
- Request body:
  - `content`: content snippet from page
  - `page_url`: current URL
  - `page_title`: current page title
  - `system_prompt`: your high-level policy
  - `preferences`: list of user preference lines
- `provider`: model provider
- `provider_model`: model name/id
- `provider_base_url`: optional base URL
- `api_keys`: optional key map from extension settings

Response:
- `hide`: boolean
- `reason`: short explanation
- `confidence`: 0..1
- `label`: `hide` or `keep`

## Note
This runs locally so your prompt and preferences stay under your control.
