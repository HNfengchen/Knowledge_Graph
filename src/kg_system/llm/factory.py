from __future__ import annotations

from typing import Literal

from langchain_core.language_models import BaseChatModel

from kg_system.core.config import get_settings
from kg_system.core.exceptions import ConfigError

Provider = Literal["openai", "anthropic", "local"]


def get_chat_model(provider: Provider | None = None) -> BaseChatModel:
    """provider=None 时使用 settings.LLM_DEFAULT_PROVIDER。"""
    s = get_settings()
    p: str = provider or s.LLM_DEFAULT_PROVIDER

    if p == "openai":
        from langchain_openai import ChatOpenAI

        if not s.OPENAI_API_KEY:
            raise ConfigError("OPENAI_API_KEY is empty")
        return ChatOpenAI(
            api_key=s.OPENAI_API_KEY,
            base_url=s.OPENAI_BASE_URL,
            model=s.OPENAI_MODEL,
            temperature=s.OPENAI_TEMPERATURE,
            max_tokens=s.OPENAI_MAX_TOKENS,
            timeout=s.OPENAI_TIMEOUT,
        )

    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not s.ANTHROPIC_API_KEY:
            raise ConfigError("ANTHROPIC_API_KEY is empty")
        return ChatAnthropic(
            api_key=s.ANTHROPIC_API_KEY,
            base_url=s.ANTHROPIC_BASE_URL,
            model=s.ANTHROPIC_MODEL,
            temperature=s.ANTHROPIC_TEMPERATURE,
            max_tokens=s.ANTHROPIC_MAX_TOKENS,
        )

    if p == "local":
        # 走 OpenAI 兼容协议，base_url 指向本地 vLLM/Ollama
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=s.LOCAL_LLM_API_KEY,
            base_url=s.LOCAL_LLM_BASE_URL,
            model=s.LOCAL_LLM_MODEL,
            temperature=s.LOCAL_LLM_TEMPERATURE,
            max_tokens=s.LOCAL_LLM_MAX_TOKENS,
        )

    raise ConfigError(f"unknown LLM provider: {p}")
