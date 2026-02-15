import json
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import dspy
except ImportError:  # pragma: no cover
    dspy = None

try:
    from deepagents import create_deep_agent
except ImportError:  # pragma: no cover
    create_deep_agent = None


MODEL_NAME = os.getenv("FILTER_MODEL", "gpt-4.1-mini")
FILTER_RUNTIME = os.getenv("FILTER_RUNTIME", "dspy").strip().lower()

DEFAULT_PROVIDER_MODELS = {
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.1:8b",
}


class FilterRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    page_url: str = ""
    page_title: str = ""
    system_prompt: str = ""
    preferences: list[str] = Field(default_factory=list)
    provider: Literal["openai", "gemini", "groq", "ollama"] = "openai"
    provider_model: str = ""
    provider_base_url: str = ""
    api_keys: dict[str, str] = Field(default_factory=dict)


class FilterResponse(BaseModel):
    hide: bool
    reason: str
    confidence: float
    label: Literal["hide", "keep"]


app = FastAPI(title="Autonomous Filter Agent Service", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_deep_agent():
    if create_deep_agent is None:
        raise RuntimeError("deepagents is required for FILTER_RUNTIME=deepagents")

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "langchain-openai is required for FILTER_RUNTIME=deepagents"
        ) from exc

    llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
    return create_deep_agent(
        model=llm,
        tools=[],
        system_prompt=(
            "You are a deep autonomous feed-filtering agent. "
            "Given user preferences and a content snippet, decide if it should be hidden. "
            "Output only JSON with keys: hide (bool), reason (string), confidence (0..1), label ('hide'|'keep')."
        ),
    )


def _build_dspy_predictor():
    if dspy is None:
        raise RuntimeError("dspy is required for FILTER_RUNTIME=dspy")

    class FilterSignature(dspy.Signature):
        """Return strict JSON with keys: hide(bool), reason(str), confidence(0..1), label('hide'|'keep')."""

        system_prompt: str = dspy.InputField()
        preferences: str = dspy.InputField()
        page_title: str = dspy.InputField()
        page_url: str = dspy.InputField()
        content: str = dspy.InputField()
        output_json: str = dspy.OutputField()

    return dspy.Predict(FilterSignature)


def _key_from_request_or_env(api_keys: dict[str, str], request_key: str, *env_names: str) -> str:
    request_value = api_keys.get(request_key, "").strip()
    if request_value:
        return request_value
    for env_name in env_names:
        env_value = os.getenv(env_name, "").strip()
        if env_value:
            return env_value
    return ""


def _build_dspy_lm(
    provider: str, provider_model: str, provider_base_url: str, api_keys: dict[str, str]
):
    if dspy is None:
        raise RuntimeError("dspy is required for FILTER_RUNTIME=dspy")

    if provider == "openai":
        api_key = _key_from_request_or_env(api_keys, "openai", "OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Provide openai API key in settings or set OPENAI_API_KEY")
        return dspy.LM(f"openai/{provider_model}", api_key=api_key)

    if provider == "gemini":
        api_key = _key_from_request_or_env(api_keys, "gemini", "GEMINI_API_KEY", "GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("Provide gemini API key in settings or set GEMINI_API_KEY/GOOGLE_API_KEY")
        return dspy.LM(f"gemini/{provider_model}", api_key=api_key)

    if provider == "groq":
        api_key = _key_from_request_or_env(api_keys, "groq", "GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Provide groq API key in settings or set GROQ_API_KEY")
        return dspy.LM(f"groq/{provider_model}", api_key=api_key)

    if provider == "ollama":
        base_url = provider_base_url.strip() or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        api_key = _key_from_request_or_env(api_keys, "ollama", "OLLAMA_API_KEY") or "ollama"
        return dspy.LM(f"openai/{provider_model}", api_base=base_url, api_key=api_key)

    raise RuntimeError("Unsupported provider. Use one of: openai, gemini, groq, ollama")


def _parse_agent_json(raw_text: str) -> dict:
    cleaned = (raw_text or "").replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = {
            "hide": False,
            "reason": "Agent output was not parseable JSON.",
            "confidence": 0.0,
            "label": "keep",
        }

    hide = bool(parsed.get("hide", False))
    return {
        "hide": hide,
        "reason": str(parsed.get("reason", ""))[:240],
        "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.0)))),
        "label": "hide" if hide else "keep",
    }


deep_agent = None
dspy_predictor = None

if FILTER_RUNTIME == "deepagents":
    deep_agent = _build_deep_agent()
elif FILTER_RUNTIME == "dspy":
    dspy_predictor = _build_dspy_predictor()
else:
    raise RuntimeError("FILTER_RUNTIME must be one of: deepagents, dspy")


@app.post("/filter", response_model=FilterResponse)
async def filter_content(req: FilterRequest):
    preference_block = "\n".join(f"- {line}" for line in req.preferences) or "- (none provided)"
    final_system = req.system_prompt.strip() or "Use preferences strictly and prefer hiding low-value content."

    if FILTER_RUNTIME == "deepagents":
        if req.provider != "openai":
            raise HTTPException(
                status_code=400,
                detail="FILTER_RUNTIME=deepagents currently supports provider=openai only. Use FILTER_RUNTIME=dspy for provider switching.",
            )

        user_prompt = (
            "Apply the user's filtering policy.\n\n"
            f"SYSTEM POLICY:\n{final_system}\n\n"
            f"PREFERENCES:\n{preference_block}\n\n"
            f"PAGE TITLE: {req.page_title}\n"
            f"PAGE URL: {req.page_url}\n\n"
            "CONTENT TO EVALUATE:\n"
            f"{req.content}\n\n"
            "Return strict JSON only."
        )
        result = deep_agent.invoke({"messages": [{"role": "user", "content": user_prompt}]})
        raw_text = ""
        for message in reversed(result.get("messages", [])):
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                raw_text = content.strip()
                break
            if isinstance(content, list):
                parts = [
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                text = "\n".join(p for p in parts if p).strip()
                if text:
                    raw_text = text
                    break
    else:
        provider = req.provider.strip().lower()
        model = (req.provider_model or DEFAULT_PROVIDER_MODELS.get(provider, "")).strip()
        if not model:
            raise HTTPException(status_code=400, detail="provider_model is required")

        try:
            lm = _build_dspy_lm(provider, model, req.provider_base_url, req.api_keys)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        dspy.configure(lm=lm)
        result = dspy_predictor(
            system_prompt=final_system,
            preferences=preference_block,
            page_title=req.page_title,
            page_url=req.page_url,
            content=req.content,
        )
        raw_text = getattr(result, "output_json", "")

    parsed = _parse_agent_json(raw_text)
    return FilterResponse(**parsed)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "runtime": FILTER_RUNTIME,
        "providers": ["openai", "gemini", "groq", "ollama"],
    }
