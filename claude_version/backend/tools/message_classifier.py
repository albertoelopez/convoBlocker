"""Message classification tool using DSPy modules."""

import json

from langchain_core.tools import tool

from ..dspy_modules import MessageClassifier, SentimentScorer


@tool
def classify_message(message: str, criteria: str, username: str = "unknown") -> str:
    """Classify a YouTube chat message and analyze its sentiment.

    Uses DSPy MessageClassifier (chain-of-thought) and SentimentScorer
    to evaluate the message against the given blocking criteria.

    Args:
        message: The chat message text to classify.
        criteria: Comma-separated blocking criteria (e.g. "spam,hate,harassment").
        username: The username who sent the message.

    Returns:
        JSON string with classification and sentiment results.
    """
    classifier = MessageClassifier()
    scorer = SentimentScorer()

    classification = classifier(message=message, username=username, criteria=criteria)
    sentiment = scorer(message=message)

    # Parse categories_violated from DSPy output
    categories = classification.categories_violated
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except (json.JSONDecodeError, TypeError):
            categories = [c.strip() for c in categories.split(",") if c.strip()]

    # Parse confidence
    confidence = sentiment.confidence
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            confidence = 0.5

    result = {
        "reasoning": classification.reasoning,
        "categories_violated": categories,
        "severity": classification.severity,
        "sentiment": sentiment.sentiment,
        "sentiment_confidence": confidence,
    }
    return json.dumps(result)
