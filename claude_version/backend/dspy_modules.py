"""DSPy modules for YouTube chat message analysis and block decisions."""

import dspy


# --- Signatures ---

class MessageClassification(dspy.Signature):
    """Classify a YouTube chat message against blocking criteria."""

    message = dspy.InputField(desc="The YouTube chat message text to classify")
    username = dspy.InputField(desc="The username who sent the message")
    criteria = dspy.InputField(desc="Comma-separated list of blocking criteria to check against")

    reasoning = dspy.OutputField(desc="Step-by-step reasoning for the classification")
    categories_violated = dspy.OutputField(desc="JSON list of criteria categories violated, e.g. [\"spam\", \"hate\"]")
    severity = dspy.OutputField(desc="Severity level: none, low, medium, or high")


class SentimentAnalysis(dspy.Signature):
    """Analyze the sentiment of a YouTube chat message."""

    message = dspy.InputField(desc="The YouTube chat message text to analyze")

    sentiment = dspy.OutputField(desc="One of: positive, neutral, negative, hostile")
    confidence = dspy.OutputField(desc="Confidence score from 0.0 to 1.0")


class BlockDecision(dspy.Signature):
    """Decide whether to block, allow, or watch a YouTube chat user."""

    username = dspy.InputField(desc="The username being evaluated")
    message_analysis = dspy.InputField(desc="JSON classification result from message analysis")
    sentiment = dspy.InputField(desc="Sentiment analysis result")
    pattern_flags = dspy.InputField(desc="JSON dict of detected message pattern flags")
    user_history = dspy.InputField(desc="JSON dict of user history stats")
    custom_instructions = dspy.InputField(desc="Additional custom instructions from the streamer")

    reasoning = dspy.OutputField(desc="Step-by-step reasoning for the decision")
    decision = dspy.OutputField(desc="One of: block, allow, watch")


# --- Modules ---

class MessageClassifier(dspy.Module):
    """Classifies messages using chain-of-thought reasoning."""

    def __init__(self):
        super().__init__()
        self.classify = dspy.ChainOfThought(MessageClassification)

    def forward(self, message: str, username: str, criteria: str):
        return self.classify(message=message, username=username, criteria=criteria)


class SentimentScorer(dspy.Module):
    """Scores message sentiment."""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.Predict(SentimentAnalysis)

    def forward(self, message: str):
        return self.analyze(message=message)


class DecisionMaker(dspy.Module):
    """Makes block/allow/watch decisions using chain-of-thought."""

    def __init__(self):
        super().__init__()
        self.decide = dspy.ChainOfThought(BlockDecision)

    def forward(
        self,
        username: str,
        message_analysis: str,
        sentiment: str,
        pattern_flags: str,
        user_history: str,
        custom_instructions: str,
    ):
        return self.decide(
            username=username,
            message_analysis=message_analysis,
            sentiment=sentiment,
            pattern_flags=pattern_flags,
            user_history=user_history,
            custom_instructions=custom_instructions,
        )


_current_lm = None


def _build_lm(settings: dict):
    """Build a DSPy LM instance from settings."""
    gemini_key = settings.get("gemini_api_key")
    groq_key = settings.get("groq_api_key")
    gemini_model = settings.get("gemini_model", "gemini/gemini-2.0-flash")
    ollama_model = settings.get("ollama_model", "ollama_chat/llama3.2")
    ollama_base_url = settings.get("ollama_base_url", "http://localhost:11434")

    if gemini_key:
        return dspy.LM(gemini_model, api_key=gemini_key)
    elif groq_key:
        return dspy.LM("groq/llama-3.3-70b-versatile", api_key=groq_key)
    else:
        return dspy.LM(ollama_model, api_base=ollama_base_url)


def configure_dspy(settings: dict) -> None:
    """Configure the DSPy language model based on application settings.

    Stores the LM globally and calls dspy.configure. If dspy.configure fails
    due to async context issues, the LM is still stored and can be used via
    dspy.context() in tool functions.
    """
    global _current_lm
    _current_lm = _build_lm(settings)
    try:
        dspy.configure(lm=_current_lm)
    except Exception:
        # Async context mismatch — the LM is stored in _current_lm
        # and DSPy tools can use dspy.context(lm=_current_lm) as needed
        pass


def get_dspy_lm():
    """Return the currently configured DSPy LM."""
    return _current_lm
