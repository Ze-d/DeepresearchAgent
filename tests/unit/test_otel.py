"""OpenTelemetry 集成单元测试。

使用 opentelemetry-sdk 的 InMemorySpanExporter 验证 span 创建和属性。
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

# ——— OTel test helpers ———


@pytest.fixture(scope="module")
def in_memory_exporter():
    """创建 InMemorySpanExporter 并设为全局 TracerProvider（module scope）。

    使用 module scope 因为 OTel SDK 禁止在同一进程中多次替换
    TracerProvider。
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry import trace as otel_trace

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel_trace.set_tracer_provider(provider)

    yield exporter

    exporter.clear()


@pytest.fixture
def otel_handler(in_memory_exporter):
    """创建 OTelCallbackHandler（已连接到 InMemoryExporter）。"""
    from deepresearch.observability.otel_callback import OTelCallbackHandler

    handler = OTelCallbackHandler()
    return handler


@pytest.fixture(autouse=True)
def _reset_otel_state(in_memory_exporter, monkeypatch):
    """重置应用层 OTel 状态标志，并清空 exporter。

    每个测试独立启用 OTel（覆盖 conftest.py 中的全局禁用）。
    """
    import deepresearch.observability.otel as otel_mod
    import deepresearch.observability.otel_callback as cb_mod

    # 对本模块所有测试启用 OTel
    monkeypatch.setattr("deepresearch.config.settings.otel_enabled", True)
    monkeypatch.setattr("deepresearch.config.settings.otel_console_export", False)
    monkeypatch.setattr("deepresearch.config.settings.otel_file_export", None)

    otel_mod._initialized = False
    otel_mod._tools_patched = False
    cb_mod._trace = None
    cb_mod._Tracer = None
    cb_mod._Span = None
    cb_mod._StatusCode = None

    in_memory_exporter.clear()

    yield

    otel_mod._initialized = False
    otel_mod._tools_patched = False
    cb_mod._trace = None
    cb_mod._Tracer = None
    cb_mod._Span = None
    cb_mod._StatusCode = None


# ——— mock_llm_result helper ———


def _make_llm_result(
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> object:
    """创建模拟的 LLMResult 对象。"""
    from langchain_core.outputs import LLMResult, Generation

    return LLMResult(
        generations=[[Generation(text="test response")]],
        llm_output={
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        },
    )


# ——— Tests ————————————————————————————————————————————————————————


class TestOTelCallbackHandler:
    """OTelCallbackHandler 单元测试。"""

    def test_llm_lifecycle_creates_span(
        self, otel_handler, in_memory_exporter
    ):
        """on_llm_start → on_llm_end 创建并结束 span。"""
        run_id = uuid.uuid4()
        otel_handler.on_llm_start(
            serialized={"kwargs": {"model": "deepseek-chat"}},
            prompts=["Hello"],
            run_id=run_id,
        )
        otel_handler.on_llm_end(
            response=_make_llm_result(10, 20),
            run_id=run_id,
        )

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "llm:invoke"

    def test_span_has_genai_attributes(
        self, otel_handler, in_memory_exporter
    ):
        """Span 包含 gen_ai 语义约定属性。"""
        run_id = uuid.uuid4()
        otel_handler.on_llm_start(
            serialized={"kwargs": {"model": "deepseek-chat"}},
            prompts=["Test"],
            run_id=run_id,
        )
        otel_handler.on_llm_end(
            response=_make_llm_result(15, 30),
            run_id=run_id,
        )

        spans = in_memory_exporter.get_finished_spans()
        span = spans[0]
        attrs = {k: v for k, v in span.attributes.items()}
        assert attrs["gen_ai.system"] == "deepseek"
        assert attrs["gen_ai.request.model"] == "deepseek-chat"
        assert attrs["gen_ai.usage.input_tokens"] == 15
        assert attrs["gen_ai.usage.output_tokens"] == 30

    def test_token_fallback_keys(self, otel_handler, in_memory_exporter):
        """兼容 input_tokens/output_tokens 替代键名。"""
        from langchain_core.outputs import LLMResult, Generation

        run_id = uuid.uuid4()
        otel_handler.on_llm_start(
            serialized={"kwargs": {"model": "test"}},
            prompts=["Test"],
            run_id=run_id,
        )
        # DeepSeek 可能返回不同 key 名
        resp = LLMResult(
            generations=[[Generation(text="test response")]],
            llm_output={
                "token_usage": {
                    "input_tokens": 5,
                    "output_tokens": 10,
                }
            },
        )
        otel_handler.on_llm_end(response=resp, run_id=run_id)

        spans = in_memory_exporter.get_finished_spans()
        attrs = {k: v for k, v in spans[0].attributes.items()}
        assert attrs["gen_ai.usage.input_tokens"] == 5
        assert attrs["gen_ai.usage.output_tokens"] == 10

    def test_llm_error_records_exception(
        self, otel_handler, in_memory_exporter
    ):
        """on_llm_error 应该结束 span 并记录异常。"""
        run_id = uuid.uuid4()
        otel_handler.on_llm_start(
            serialized={"kwargs": {"model": "deepseek-chat"}},
            prompts=["Test"],
            run_id=run_id,
        )
        otel_handler.on_llm_error(
            error=ValueError("API error"),
            run_id=run_id,
        )

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        # 异常通过 record_exception 记录在 span events 中
        assert len(spans[0].events) >= 1

    def test_missing_token_usage_no_crash(
        self, otel_handler, in_memory_exporter
    ):
        """LLM 返回无 token_usage 时不应崩溃。"""
        from langchain_core.outputs import LLMResult, Generation

        run_id = uuid.uuid4()
        otel_handler.on_llm_start(
            serialized={"kwargs": {"model": "deepseek-chat"}},
            prompts=["Test"],
            run_id=run_id,
        )
        # No token_usage at all
        resp = LLMResult(
            generations=[[Generation(text="test response")]],
            llm_output={},
        )
        otel_handler.on_llm_end(response=resp, run_id=run_id)

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        # No gen_ai.usage.* attributes
        attrs = {k: v for k, v in spans[0].attributes.items()}
        assert "gen_ai.usage.input_tokens" not in attrs

    def test_unknown_model_is_handled(self, otel_handler, in_memory_exporter):
        """serialized 中没有 model 信息时的回退。"""
        run_id = uuid.uuid4()
        otel_handler.on_llm_start(
            serialized={},  # No kwargs
            prompts=["Test"],
            run_id=run_id,
        )
        otel_handler.on_llm_end(
            response=_make_llm_result(),
            run_id=run_id,
        )

        spans = in_memory_exporter.get_finished_spans()
        attrs = {k: v for k, v in spans[0].attributes.items()}
        assert attrs["gen_ai.request.model"] == "unknown"


class TestTraceNode:
    """_trace_node 包装器测试。"""

    def test_wraps_node_function(self, in_memory_exporter):
        """_trace_node 创建 node span 并返回原函数结果。"""
        from deepresearch.observability.otel_callback import _trace_node

        wrapped = _trace_node("plan", lambda state: {"status": "planned"})
        result = wrapped({})

        assert result == {"status": "planned"}
        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "node:plan"
        attrs = {k: v for k, v in spans[0].attributes.items()}
        assert attrs["deepresearch.node.name"] == "plan"
        assert attrs["deepresearch.node.status"] == "planned"

    def test_node_error_is_recorded(self, in_memory_exporter):
        """node 抛异常时应记录到 span。"""
        from deepresearch.observability.otel_callback import _trace_node

        wrapped = _trace_node("failing", lambda state: (_ for _ in ()).throw(ValueError("boom")))

        with pytest.raises(ValueError, match="boom"):
            wrapped({})

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1


class TestPatchTools:
    """_patch_tools 测试。"""

    def test_patches_search_web(self, in_memory_exporter, monkeypatch):
        """_patch_tools 后 search_web 产生 tool span。"""
        from deepresearch.observability.otel import _patch_tools, setup_otel
        import deepresearch.tools as tools_mod

        # 保存原始函数
        orig_search = tools_mod.search_web

        # 先用 monkeypatch 替换为快速 stub（避免网络调用）
        from deepresearch.tools import SearchResult

        def stub_search(query, max_results=5, site_filter=None):
            return [SearchResult(title="T", url="https://x.com", snippet="S")]

        monkeypatch.setattr(tools_mod, "search_web", stub_search)
        _patch_tools()

        # 调用 patched 版本
        result = tools_mod.search_web("test query", max_results=3, site_filter="arxiv.org")
        assert len(result) == 1

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "tool:search_web"
        attrs = {k: v for k, v in spans[0].attributes.items()}
        assert attrs["tool.name"] == "search_web"
        assert attrs["tool.query"] == "test query"
        assert attrs["tool.site_filter"] == "arxiv.org"
        assert attrs["tool.result_count"] == 1

        # 恢复
        tools_mod.search_web = orig_search

    def test_patches_fetch_content(self, in_memory_exporter, monkeypatch):
        """_patch_tools 后 fetch_content 产生 tool span。"""
        from deepresearch.observability.otel import _patch_tools
        import deepresearch.tools as tools_mod

        orig_fetch = tools_mod.fetch_content

        def stub_fetch(url, timeout=8.0):
            return "test content"

        monkeypatch.setattr(tools_mod, "fetch_content", stub_fetch)
        _patch_tools()

        result = tools_mod.fetch_content("https://example.com")
        assert result == "test content"

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "tool:fetch_content"
        attrs = {k: v for k, v in spans[0].attributes.items()}
        assert attrs["tool.name"] == "fetch_content"
        assert attrs["tool.url"] == "https://example.com"

        tools_mod.fetch_content = orig_fetch

    def test_patch_tools_is_idempotent(self, monkeypatch):
        """重复调用 _patch_tools 不重复包装。"""
        from deepresearch.observability.otel import _patch_tools
        import deepresearch.tools as tools_mod

        orig_search = tools_mod.search_web

        def stub_search(query, max_results=5, site_filter=None):
            from deepresearch.tools import SearchResult
            return [SearchResult(title="T", url="https://x.com", snippet="S")]

        monkeypatch.setattr(tools_mod, "search_web", stub_search)
        _patch_tools()
        first = tools_mod.search_web
        _patch_tools()
        second = tools_mod.search_web

        # 第二次调用不应再次包装
        assert first is second

        tools_mod.search_web = orig_search


class TestSetupOtel:
    """setup_otel 测试。"""

    def test_setup_otel_idempotent(self, monkeypatch):
        """setup_otel 多次调用应幂等。"""
        from deepresearch.observability.otel import setup_otel
        import deepresearch.observability.otel as otel_mod

        # 伪造已初始化的状态
        monkeypatch.setattr(otel_mod, "_initialized", True)
        monkeypatch.setattr("deepresearch.config.settings.otel_enabled", True)

        # 幂等：第二次调用返回 True 且不抛异常
        result = setup_otel()
        assert result is True

    def test_setup_otel_disabled_when_flag_off(self, monkeypatch):
        """otel_enabled=False 时 setup_otel 返回 False。"""
        from deepresearch.observability.otel import setup_otel
        import deepresearch.observability.otel as otel_mod

        monkeypatch.setattr(otel_mod, "_initialized", False)
        monkeypatch.setattr("deepresearch.config.settings.otel_enabled", False)

        result = setup_otel()
        assert result is False


class TestWorkflowSpan:
    """workflow_span 上下文管理器测试。"""

    def test_creates_root_span(self, in_memory_exporter):
        """workflow_span 创建 workflow:deepresearch 根 span。

        TracerProvider 已由 in_memory_exporter fixture 配置。
        """
        from deepresearch.observability.otel import workflow_span
        import deepresearch.observability.otel as otel_mod

        # 让 workflow_span 知道 OTel 已初始化
        otel_mod._initialized = True

        with workflow_span("test query") as span:
            assert span is not None

        spans = in_memory_exporter.get_finished_spans()
        root_spans = [s for s in spans if s.name == "workflow:deepresearch"]
        assert len(root_spans) == 1
        attrs = {k: v for k, v in root_spans[0].attributes.items()}
        assert attrs["gen_ai.operation.name"] == "deepresearch"
        assert attrs["deepresearch.query"] == "test query"

    def test_workflow_span_disabled(self, monkeypatch):
        """OTel 未启用时 workflow_span 静默返回 None。"""
        from deepresearch.observability.otel import workflow_span
        import deepresearch.observability.otel as otel_mod

        otel_mod._initialized = False
        monkeypatch.setattr("deepresearch.config.settings.otel_enabled", False)

        with workflow_span("test") as span:
            assert span is None
