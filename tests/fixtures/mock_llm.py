# tests/fixtures/mock_llm.py
"""Fake LLM for tests — returns preset JSON responses without network calls."""
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration


class FakeChatModel(BaseChatModel):
    """返回预设 JSON 字符串的 Fake LLM。

    在测试中通过 `response_map` 控制不同 prompt 的返回值。
    """

    response_map: dict[str, str] = {}
    default_response: str = '{"status": "ok"}'

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs) -> ChatResult:
        key = str(messages[0].content) if messages else ""
        text = self.response_map.get(key, self.default_response)
        message = AIMessage(content=text)
        return ChatResult(generations=[ChatGeneration(message=message)])

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"
