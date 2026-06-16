# deepresearch/llm.py
from langchain_deepseek import ChatDeepSeek
from langchain_core.language_models import BaseChatModel

from deepresearch.config import Settings


def build_llm() -> BaseChatModel:
    """创建 DeepSeek Chat 实例。

    每次调用时从环境变量重新读取配置，便于测试时通过 monkeypatch 修改。

    Raises:
        ValueError: 未配置 DEEPSEEK_API_KEY 时抛出。
    """
    cfg = Settings()
    if not cfg.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY not set. Copy .env.example to .env and fill in your key."
        )
    return ChatDeepSeek(
        model=cfg.deepseek_model,
        temperature=cfg.temperature,
        max_retries=cfg.max_retries,
        request_timeout=cfg.llm_request_timeout,
    )
