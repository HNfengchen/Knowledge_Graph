from __future__ import annotations

from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeChatModel(BaseChatModel):
    """按入参返回预置 JSON；可注入异常。"""

    response: str = '{"entities": []}'
    raise_on_call: Optional[Exception] = None

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.raise_on_call:
            raise self.raise_on_call
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response))])

    @property
    def _llm_type(self) -> str:
        return "fake"
