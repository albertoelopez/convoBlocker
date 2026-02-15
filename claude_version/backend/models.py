from pydantic import BaseModel


class ChatMessage(BaseModel):
    username: str
    text: str


class AnalyzeRequest(BaseModel):
    messages: list[ChatMessage]
    settings: dict | None = None


class MessageDecision(BaseModel):
    username: str
    decision: str  # "block", "allow", or "watch"
    reason: str


class AnalyzeResponse(BaseModel):
    decisions: list[MessageDecision]


class HealthResponse(BaseModel):
    status: str
    agent: str


class StatsResponse(BaseModel):
    messages_analyzed: int
    users_blocked: int
    cache_hits: int


class BlockLogEntry(BaseModel):
    username: str
    decision: str
    reason: str
    categories: list[str]
    timestamp: str


class SettingsModel(BaseModel):
    enabled: bool = True
    gemini_api_key: str = ""
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ai_provider: str = "gemini"
    categories: dict[str, bool] = {
        "spam": True,
        "trolls": True,
        "off_topic": True,
        "hate_speech": True,
        "self_promo": True,
    }
    custom_prompt: str = ""
