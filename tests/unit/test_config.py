# tests/unit/test_config.py
from deepresearch.config import Settings


def test_settings_from_env(monkeypatch):
    """从环境变量加载配置"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    monkeypatch.setenv("MAX_ITERATIONS", "3")
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "10")
    monkeypatch.setenv("OUTPUT_DIR", "my_outputs")
    monkeypatch.setenv("TEMPERATURE", "0.5")
    monkeypatch.setenv("MAX_RETRIES", "3")
    monkeypatch.setenv("SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "sk-tavily-test")

    s = Settings()

    assert s.deepseek_api_key == "sk-test-key"
    assert s.deepseek_model == "deepseek-reasoner"
    assert s.max_iterations == 3
    assert s.max_search_results == 10
    assert s.output_dir == "my_outputs"
    assert s.temperature == 0.5
    assert s.max_retries == 3
    assert s.search_provider == "tavily"
    assert s.tavily_api_key == "sk-tavily-test"


def test_settings_defaults(monkeypatch):
    """未设置环境变量时使用默认值"""
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "MAX_ITERATIONS",
                "MAX_SEARCH_RESULTS", "OUTPUT_DIR", "TEMPERATURE", "MAX_RETRIES",
                "SEARCH_PROVIDER", "TAVILY_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    s = Settings()

    assert s.deepseek_api_key == ""
    assert s.deepseek_model == "deepseek-chat"
    assert s.max_iterations == 2
    assert s.max_search_results == 5
    assert s.output_dir == "outputs"
    assert s.temperature == 0.0
    assert s.max_retries == 2
    assert s.search_provider == "duckduckgo"
    assert s.tavily_api_key == ""


def test_settings_from_dotenv(monkeypatch, tmp_path):
    """从 .env 文件加载配置"""
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=sk-from-file\nMAX_ITERATIONS=4\n")

    for key in ("DEEPSEEK_API_KEY", "MAX_ITERATIONS"):
        monkeypatch.delenv(key, raising=False)

    s = Settings(_env_file=str(env_file), _env_file_encoding="utf-8")

    assert s.deepseek_api_key == "sk-from-file"
    assert s.max_iterations == 4
