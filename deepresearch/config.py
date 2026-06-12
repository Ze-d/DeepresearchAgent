# deepresearch/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """DeepResearch Agent 全局配置，从 .env 和环境变量加载。"""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

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

    # LLM 调用参数
    temperature: float = 0.0
    max_retries: int = 2


# 全局单例
settings = Settings()
