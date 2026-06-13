# deepresearch/config.py
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 强制 .env 覆盖系统环境变量（避免机器上残留的全局 key 干扰）
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)


class Settings(BaseSettings):
    """DeepResearch Agent 全局配置。"""

    # 不设 env_file：.env 值已通过 load_dotenv(override=True) 注入环境变量。
    # 这确保 pydantic-settings 只读环境变量，monkeypatch 可在测试中正常覆盖。

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # 搜索
    search_provider: str = "duckduckgo"
    tavily_api_key: str = ""

    # 工作流
    max_iterations: int = 2
    max_search_results: int = 5

    # 输出
    output_dir: str = "outputs"

    # 日志
    log_level: str = "INFO"
    log_file: str | None = None

    # v1: Evidence 质量
    dedup_enabled: bool = True
    dedup_max_calls_per_run: int = 20
    source_ranking_enabled: bool = True

    # v1: Checkpoint
    checkpoint_enabled: bool = True

    # v1: Streaming
    stream_enabled: bool = True

    # v1: Observability
    metrics_enabled: bool = True

    # LLM 调用参数
    temperature: float = 0.0
    max_retries: int = 2


# 全局单例
settings = Settings()
