"""Deep Agent orchestrator for YouTube chat moderation."""

import json
import logging

from config import Settings

logger = logging.getLogger(__name__)

# Tool imports
from tools import classify_message, detect_patterns, get_user_history, make_decision


def _build_system_prompt(settings: Settings) -> str:
    active_categories = [k for k, v in settings.categories.items() if v]
    categories_str = ", ".join(active_categories) if active_categories else "none"

    custom_section = ""
    if settings.custom_prompt.strip():
        custom_section = f"""

CUSTOM MODERATION RULES (from the streamer):
{settings.custom_prompt.strip()}
"""

    return f"""You are an autonomous YouTube Live Chat moderation agent. Your job is to analyze
batches of chat messages and decide which users should be blocked.

ACTIVE MODERATION CATEGORIES: {categories_str}
{custom_section}
WORKFLOW for each message in the batch:
1. Run detect_patterns first — it's fast and free (no LLM cost).
2. If patterns are suspicious (has_urls, excessive_caps, repeated_chars, excessive_emojis, too_long)
   OR the message seems potentially problematic:
   → Run classify_message with criteria="{categories_str}" and check_user_history.
3. If the classification shows severity "medium" or "high", or categories are violated:
   → Run make_decision for the final verdict.
4. If the message is short, normal, and patterns are clean:
   → Allow it without further analysis.

IMPORTANT RULES:
- Always err on the side of ALLOWING when uncertain.
- Only block users who clearly violate the active categories.
- Short friendly messages like "hi", "lol", "gg" should always be allowed.
- A single borderline message should result in "watch", not "block".
- Consider user history: repeat offenders deserve stricter treatment.

OUTPUT FORMAT:
Return a JSON array. Each element must have exactly these keys:
  - "username": the username
  - "decision": one of "block", "allow", or "watch"
  - "reason": brief explanation

Example:
[
  {{"username": "spammer123", "decision": "block", "reason": "Repeated spam links detected"}},
  {{"username": "friendly_viewer", "decision": "allow", "reason": "Normal chat message"}}
]

Process ALL messages in the batch. Do not skip any."""


def _build_agent_with_deepagents(model, tools, system_prompt):
    """Try using deepagents library."""
    from deepagents import create_deep_agent

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )


def _build_agent_with_langgraph(model, tools, system_prompt):
    """Fallback: use langgraph's create_react_agent."""
    from langgraph.prebuilt import create_react_agent

    return create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )


def _get_model(settings: Settings):
    """Initialize the LLM based on settings."""
    from langchain.chat_models import init_chat_model

    if settings.ai_provider == "gemini" and settings.gemini_api_key:
        return init_chat_model(
            "gemini-2.0-flash",
            model_provider="google_genai",
            api_key=settings.gemini_api_key,
        )
    elif settings.ai_provider == "groq" and settings.groq_api_key:
        return init_chat_model(
            "llama-3.3-70b-versatile",
            model_provider="groq",
            api_key=settings.groq_api_key,
        )
    else:
        return init_chat_model(
            settings.ollama_model,
            model_provider="ollama",
            base_url=settings.ollama_endpoint,
        )


def create_moderation_agent(settings: Settings):
    """Create and return the moderation agent with all tools.

    Tries deepagents first, falls back to langgraph react agent.
    Returns None if no AI provider is configured.
    """
    if settings.ai_provider == "gemini" and not settings.gemini_api_key:
        logger.warning("Gemini selected but no API key configured")
        return None
    if settings.ai_provider == "groq" and not settings.groq_api_key:
        logger.warning("Groq selected but no API key configured")
        return None

    system_prompt = _build_system_prompt(settings)
    tools = [classify_message, detect_patterns, get_user_history, make_decision]

    try:
        model = _get_model(settings)
    except Exception as e:
        logger.error("Failed to initialize LLM: %s", e)
        return None

    # Try deepagents first, fall back to langgraph
    for builder in [_build_agent_with_deepagents, _build_agent_with_langgraph]:
        try:
            agent = builder(model, tools, system_prompt)
            logger.info("Agent created using %s", builder.__name__)
            return agent
        except ImportError as e:
            logger.warning("%s not available: %s", builder.__name__, e)
            continue
        except Exception as e:
            logger.warning("Failed with %s: %s", builder.__name__, e)
            continue

    logger.error("No agent framework available. Install deepagents or langgraph.")
    return None


async def run_agent(agent, messages: list[dict]) -> list[dict]:
    """Invoke the agent on a batch of messages and parse the result.

    Args:
        agent: The moderation agent instance.
        messages: List of {"username": ..., "text": ...} dicts.

    Returns:
        List of {"username": ..., "decision": ..., "reason": ...} dicts.
    """
    if not messages:
        return []

    batch_text = "\n".join(
        f"[{m['username']}]: {m['text']}" for m in messages
    )
    prompt = f"Analyze the following YouTube live chat messages:\n\n{batch_text}"

    try:
        # Both deepagents and langgraph agents support invoke/ainvoke
        if hasattr(agent, "ainvoke"):
            result = await agent.ainvoke({"messages": [("user", prompt)]})
        else:
            import asyncio
            result = await asyncio.to_thread(agent.invoke, {"messages": [("user", prompt)]})

        # Extract the text content from the agent's response
        response_text = _extract_response_text(result)
        decisions = _parse_decisions(response_text, messages)
        return decisions

    except Exception as e:
        logger.error("Agent invocation failed: %s", e)
        # Safe fallback: allow all messages
        return [
            {"username": m["username"], "decision": "allow", "reason": f"Agent error: {e}"}
            for m in messages
        ]


def _extract_response_text(result) -> str:
    """Extract text from various agent result formats."""
    if isinstance(result, dict):
        # langgraph format: {"messages": [...]}
        if "messages" in result:
            msgs = result["messages"]
            if msgs:
                last = msgs[-1]
                if hasattr(last, "content"):
                    return last.content
                if isinstance(last, dict):
                    return last.get("content", str(last))
        # deepagents may return {"output": "..."}
        if "output" in result:
            return result["output"]
    if isinstance(result, str):
        return result
    return str(result)


def _parse_decisions(text: str, messages: list[dict]) -> list[dict]:
    """Parse the JSON decision array from the agent's response text."""
    # Try to find JSON array in the response
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            decisions = json.loads(text[start : end + 1])
            if isinstance(decisions, list):
                # Validate and clean up
                valid = []
                for d in decisions:
                    if isinstance(d, dict) and "username" in d:
                        valid.append({
                            "username": d.get("username", ""),
                            "decision": d.get("decision", "allow"),
                            "reason": d.get("reason", ""),
                        })
                return valid
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse agent decisions, defaulting to allow")
    return [
        {"username": m["username"], "decision": "allow", "reason": "Parse error — defaulting to allow"}
        for m in messages
    ]
