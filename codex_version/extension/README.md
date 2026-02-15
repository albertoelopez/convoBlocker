# View-Based Feed Filter (Chrome Extension)

This extension hides social content based on your own rules and can call a local LangChain agent for autonomous decisions.

## Features
- Enable/disable quickly from popup
- Set blocked keywords/phrases (one per line)
- Configure a system prompt + preference list
- Use a LangChain agent endpoint for model-based filtering
- Limit filtering to specific domains
- Choose hide behavior: collapse or remove

## Install (Developer mode)
1. Open Chrome and go to `chrome://extensions`.
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `extension/` folder.
4. Open extension options and customize your rules.

## Agent mode (LangChain)
1. Start the local service from `agent_service/` (see `agent_service/README.md`).
2. In extension options:
   - Enable `Use LangChain agent`
   - Keep endpoint as `http://127.0.0.1:8000/filter` (or your own URL)
   - Choose provider: OpenAI / Gemini / Groq / Ollama
   - Set the model name for that provider
   - (Optional) set provider base URL (for Ollama/custom)
   - (Optional) paste provider API key(s) in settings
   - Add your `Agent system prompt`
   - Add `Your preferences` lines
3. Refresh target tabs after saving settings.

## Notes
- Keyword filtering remains as a local fallback when the agent is unavailable.
- Keep your policy clear and specific for better filtering consistency.
- API keys entered in options are stored by the extension in Chrome storage.
