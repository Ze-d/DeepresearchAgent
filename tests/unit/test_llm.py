# tests/unit/test_llm.py
import pytest
from deepresearch.llm import build_llm


def test_build_llm_missing_api_key(monkeypatch):
    """未配置 API key 时抛出明确错误"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        build_llm()


def test_build_llm_with_api_key(monkeypatch):
    """有 API key 时返回 ChatDeepSeek 实例"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")

    from langchain_deepseek import ChatDeepSeek

    llm = build_llm()
    assert isinstance(llm, ChatDeepSeek)
    assert llm.model_name == "deepseek-chat"


def test_build_llm_custom_model(monkeypatch):
    """可以通过环境变量切换模型"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    llm = build_llm()
    assert llm.model_name == "deepseek-reasoner"


def test_build_llm_respects_temperature(monkeypatch):
    """temperature 参数传递正确"""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("TEMPERATURE", "0.7")

    llm = build_llm()
    assert llm.temperature == 0.7
