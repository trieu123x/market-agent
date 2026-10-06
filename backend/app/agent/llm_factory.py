"""Tạo chat model LangChain theo model_id (OpenAI / Anthropic / Gemini)."""
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.core.config import get_settings


class LLMConfigError(RuntimeError):
    """model_id không hỗ trợ hoặc thiếu API key của provider."""


_PROVIDER_PREFIXES = {
    "openai": ("gpt-", "o1", "o3", "o4", "chatgpt-"),
    "anthropic": ("claude-",),
    "google": ("gemini-",),
}


def provider_for(model_id: str) -> str:
    for provider, prefixes in _PROVIDER_PREFIXES.items():
        if model_id.startswith(prefixes):
            return provider
    raise LLMConfigError(f"Không xác định được provider cho model '{model_id}'")


def provider_configured(provider: str) -> bool:
    """Provider đã có API key chưa (để UI ẩn/khóa model không gọi được)."""
    s = get_settings()
    return bool({"openai": s.openai_api_key, "anthropic": s.anthropic_api_key, "google": s.google_api_key}.get(provider))


def _require_key(value: str, env_name: str) -> str:
    if not value:
        raise LLMConfigError(f"{env_name} trống – không gọi được model này")
    return value


@lru_cache
def get_chat_model(model_id: str) -> BaseChatModel:
    s = get_settings()
    provider = provider_for(model_id)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_id,
            api_key=_require_key(s.openai_api_key, "OPENAI_API_KEY"),
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
            stream_usage=True,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_id,
            api_key=_require_key(s.anthropic_api_key, "ANTHROPIC_API_KEY"),
            temperature=s.llm_temperature,
            max_tokens=s.llm_max_tokens,
        )
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model_id,
        google_api_key=_require_key(s.google_api_key, "GOOGLE_API_KEY"),
        temperature=s.llm_temperature,
        max_output_tokens=s.llm_max_tokens,
    )


def message_text(message: BaseMessage) -> str:
    """Lấy phần text của message/chunk (Gemini/Anthropic có thể trả content dạng list block)."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
        if isinstance(block, str) or block.get("type") == "text"
    )
