"""Decision-making tool using DSPy chain-of-thought reasoning."""

import json

from langchain_core.tools import tool

from ..dspy_modules import DecisionMaker


@tool
def make_decision(
    username: str,
    message_analysis: str,
    sentiment: str,
    pattern_flags: str,
    user_history: str,
    custom_instructions: str = "",
) -> str:
    """Decide whether to block, allow, or watch a YouTube chat user.

    Aggregates all analysis results and uses DSPy chain-of-thought reasoning
    to produce a final decision.

    Args:
        username: The username being evaluated.
        message_analysis: JSON string from classify_message tool.
        sentiment: Sentiment label (positive/neutral/negative/hostile).
        pattern_flags: JSON string from detect_patterns tool.
        user_history: JSON string from get_user_history tool.
        custom_instructions: Optional additional instructions from the streamer.

    Returns:
        JSON string with decision and reasoning.
    """
    maker = DecisionMaker()

    result = maker(
        username=username,
        message_analysis=message_analysis,
        sentiment=sentiment,
        pattern_flags=pattern_flags,
        user_history=user_history,
        custom_instructions=custom_instructions or "No custom instructions provided.",
    )

    decision = result.decision
    if isinstance(decision, str):
        decision = decision.strip().lower()
    if decision not in ("block", "allow", "watch"):
        decision = "watch"

    output = {
        "username": username,
        "decision": decision,
        "reasoning": result.reasoning,
    }
    return json.dumps(output)
