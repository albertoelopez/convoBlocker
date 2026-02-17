"""FastAPI server for YouTube Live Chat AI Blocker."""

import json
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent import create_moderation_agent, run_agent
from config import Settings, load_settings, save_settings
from db import (
    cleanup_old_messages,
    close as close_db,
    get_block_log,
    get_stats,
    init_db,
    store_decision,
    update_stats,
)
from dspy_modules import configure_dspy
from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    BlockLogEntry,
    HealthResponse,
    MessageDecision,
    SettingsModel,
    StatsResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
_agent = None
_settings: Settings | None = None
_decision_cache: dict[str, tuple[str, float]] = {}  # username -> (decision, timestamp)
CACHE_TTL = 300  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent, _settings

    # Startup
    await init_db()
    _settings = load_settings()

    # Configure DSPy
    try:
        configure_dspy({
            "gemini_api_key": _settings.gemini_api_key,
            "groq_api_key": _settings.groq_api_key,
            "ollama_model": f"ollama_chat/{_settings.ollama_model}",
            "ollama_base_url": _settings.ollama_endpoint,
        })
    except Exception as e:
        logger.warning("DSPy configuration failed: %s", e)

    # Create agent
    _agent = create_moderation_agent(_settings)
    if _agent:
        logger.info("Moderation agent initialized successfully")
    else:
        logger.warning("Agent not ready — configure an AI provider in settings")

    # Cleanup old messages
    removed = await cleanup_old_messages()
    if removed:
        logger.info("Cleaned up %d old messages", removed)

    yield

    # Shutdown
    await close_db()


app = FastAPI(title="YouTube Chat AI Blocker", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cache_get(username: str) -> str | None:
    """Get cached decision if still valid."""
    if username in _decision_cache:
        decision, ts = _decision_cache[username]
        if time.time() - ts < CACHE_TTL:
            return decision
        del _decision_cache[username]
    return None


def _cache_set(username: str, decision: str):
    """Cache a decision."""
    _decision_cache[username] = (decision, time.time())


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_messages(request: AnalyzeRequest):
    """Analyze a batch of chat messages and return block/allow/watch decisions."""
    global _agent, _settings

    if not _settings or not _settings.enabled:
        return AnalyzeResponse(
            decisions=[
                MessageDecision(username=m.username, decision="allow", reason="Moderation disabled")
                for m in request.messages
            ]
        )

    # Check cache first
    cached_decisions = []
    uncached_messages = []
    cache_hits = 0

    for msg in request.messages:
        cached = _cache_get(msg.username)
        if cached:
            cached_decisions.append(
                MessageDecision(username=msg.username, decision=cached, reason="Cached decision")
            )
            cache_hits += 1
        else:
            uncached_messages.append({"username": msg.username, "text": msg.text})

    # Update cache hit stats
    if cache_hits:
        await update_stats(cache_hits=cache_hits)

    # If all cached, return early
    if not uncached_messages:
        await update_stats(messages_analyzed=len(request.messages))
        return AnalyzeResponse(decisions=cached_decisions)

    # Run agent on uncached messages
    if _agent:
        try:
            raw_decisions = await run_agent(_agent, uncached_messages)
        except Exception as e:
            logger.error("Agent error: %s", e)
            raw_decisions = [
                {"username": m["username"], "decision": "allow", "reason": f"Error: {e}"}
                for m in uncached_messages
            ]
    else:
        raw_decisions = [
            {"username": m["username"], "decision": "allow", "reason": "Agent not configured"}
            for m in uncached_messages
        ]

    # Process decisions
    new_decisions = []
    blocks = 0
    for d in raw_decisions:
        decision = d.get("decision", "allow")
        username = d.get("username", "")
        reason = d.get("reason", "")

        # Cache the decision
        _cache_set(username, decision)

        new_decisions.append(
            MessageDecision(username=username, decision=decision, reason=reason)
        )

        # Store block/watch decisions in DB
        if decision in ("block", "watch"):
            await store_decision(username, decision, reason)
            if decision == "block":
                blocks += 1

    await update_stats(
        messages_analyzed=len(request.messages),
        users_blocked=blocks,
    )

    return AnalyzeResponse(decisions=cached_decisions + new_decisions)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check backend health and agent status."""
    agent_status = "ready" if _agent else "not_configured"
    return HealthResponse(status="ok", agent=agent_status)


@app.get("/ollama-models")
async def list_ollama_models():
    """Fetch locally installed Ollama models by querying the Ollama API."""
    endpoint = _settings.ollama_endpoint if _settings else "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{endpoint}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                size_bytes = m.get("size", 0)
                size_gb = round(size_bytes / (1024 ** 3), 1) if size_bytes else None
                models.append({
                    "name": name,
                    "size": f"{size_gb}GB" if size_gb else None,
                    "modified_at": m.get("modified_at", ""),
                    "family": m.get("details", {}).get("family", ""),
                    "parameter_size": m.get("details", {}).get("parameter_size", ""),
                })
            return {"models": models, "endpoint": endpoint}
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Ollama at {endpoint}. Is it running?")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama API error: {e}")


@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    """Get moderation statistics."""
    stats = await get_stats()
    return StatsResponse(**stats)


@app.get("/block-log", response_model=list[BlockLogEntry])
async def get_block_log_endpoint():
    """Get the block/decision log."""
    entries = await get_block_log()
    result = []
    for entry in entries:
        result.append(BlockLogEntry(
            username=entry["username"],
            decision=entry["decision"],
            reason=entry["reason"],
            categories=entry.get("categories", []),
            timestamp=str(entry["timestamp"]),
        ))
    return result


@app.post("/unblock/{username}")
async def unblock_user(username: str):
    """Remove a user from the block cache and log."""
    # Clear from cache
    if username in _decision_cache:
        del _decision_cache[username]

    # Note: we don't delete from decisions table to keep audit trail,
    # but we cache "allow" so they won't be re-blocked immediately
    _cache_set(username, "allow")

    return {"status": "ok", "username": username, "message": f"User '{username}' unblocked"}


@app.get("/settings", response_model=SettingsModel)
async def get_settings():
    """Get current settings."""
    s = _settings or load_settings()
    return SettingsModel(**s.model_dump())


@app.post("/settings", response_model=SettingsModel)
async def update_settings(new_settings: SettingsModel):
    """Update settings and recreate agent if AI config changed."""
    global _agent, _settings

    old_settings = _settings
    _settings = Settings(**new_settings.model_dump())
    save_settings(_settings)

    # Reconfigure DSPy and recreate agent if AI settings changed
    ai_changed = (
        old_settings is None
        or old_settings.ai_provider != _settings.ai_provider
        or old_settings.gemini_api_key != _settings.gemini_api_key
        or old_settings.groq_api_key != _settings.groq_api_key
        or old_settings.ollama_endpoint != _settings.ollama_endpoint
        or old_settings.ollama_model != _settings.ollama_model
        or old_settings.categories != _settings.categories
        or old_settings.custom_prompt != _settings.custom_prompt
    )

    if ai_changed:
        try:
            configure_dspy({
                "gemini_api_key": _settings.gemini_api_key,
                "groq_api_key": _settings.groq_api_key,
                "ollama_model": f"ollama_chat/{_settings.ollama_model}",
                "ollama_base_url": _settings.ollama_endpoint,
            })
        except Exception as e:
            logger.warning("DSPy reconfiguration failed: %s", e)

        _agent = create_moderation_agent(_settings)
        if _agent:
            logger.info("Agent recreated with updated settings")
        else:
            logger.warning("Agent creation failed after settings update")

        # Clear decision cache on settings change
        _decision_cache.clear()

    return SettingsModel(**_settings.model_dump())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
