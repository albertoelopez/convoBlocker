import json
from pathlib import Path

from pydantic import BaseModel

_CONFIG_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _CONFIG_DIR / "config.json"


class Settings(BaseModel):
    enabled: bool = True
    gemini_api_key: str = ""
    groq_api_key: str = ""
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


def load_settings() -> Settings:
    """Load settings from config.json, returning defaults if file is missing."""
    if _CONFIG_PATH.exists():
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return Settings(**data)
    return Settings()


def save_settings(settings: Settings) -> None:
    """Persist settings to config.json."""
    _CONFIG_PATH.write_text(
        settings.model_dump_json(indent=2),
        encoding="utf-8",
    )


# Singleton instance -- import and use directly; call reload() after edits.
settings = load_settings()


def reload() -> None:
    """Re-read config.json into the singleton."""
    global settings
    settings = load_settings()
