"""DeepResearch Agent OpenTelemetry 初始化模块。

提供：
- ``setup_otel()`` — 初始化 TracerProvider + 导出器链（幂等）
- ``workflow_span()`` — 包裹单次 workflow 调用的根 span 上下文管理器
- ``_patch_tools()`` — 工具函数追踪包装（替换模块属性）
"""

from __future__ import annotations

import atexit
import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from deepresearch.config import settings

logger = logging.getLogger(__name__)

_initialized: bool = False
_tools_patched: bool = False


# ——— 优雅降级：OTel 未安装时不影响运行 ———


def _import_otel():
    """延迟导入 OTel 包，失败时返回 None 元组。"""
    try:
        from opentelemetry import trace  # noqa: F401
        from opentelemetry.sdk.trace import TracerProvider  # noqa: F401
        from opentelemetry.sdk.trace.export import (  # noqa: F401
            BatchSpanProcessor,
            SimpleSpanProcessor,
            ConsoleSpanExporter,
            SpanExporter,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: F401
            OTLPSpanExporter,
        )

        return True
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. "
            "Install with: uv pip install deepresearch-agent[otel]"
        )
        return False


# ——— 自定义 FileSpanExporter ———


class _FileSpanExporter:
    """将 span 写为 JSON Lines 文件的简单导出器。"""

    def __init__(self, path: str) -> None:
        import json

        self._json = json
        self._file = open(path, "a", encoding="utf-8")  # noqa: SIM115

    def export(self, spans: list[Any]) -> None:
        for span in spans:
            try:
                self._file.write(span.to_json() + "\n")
            except Exception:
                logger.debug("Failed to export span to file", exc_info=True)
        self._file.flush()

    def shutdown(self) -> None:
        self._file.close()


# ——— 工具函数追踪包装 ———


def _patch_tools() -> None:
    """用 OTel 追踪包装替换 ``deepresearch.tools`` 模块中的工具函数。

    幂等：多次调用不会重复包装。

    要求调用方已通过 ``from deepresearch import tools as _tools``
    方式引用工具模块（而非 ``from deepresearch.tools import search_web``），
    以便在调用时查找模块属性，看到 patched 后的函数。
    """
    global _tools_patched
    if _tools_patched:
        return

    if not _import_otel():
        return

    from opentelemetry import trace as trace_mod

    tracer = trace_mod.get_tracer(settings.otel_service_name)

    import deepresearch.tools as tools_module

    # ——— 包装 search_web ———
    _original_search = tools_module.search_web

    @functools.wraps(_original_search)
    def _traced_search(
        query: str,
        max_results: int = 5,
        site_filter: str | None = None,
    ) -> list[Any]:
        with tracer.start_as_current_span("tool:search_web") as span:
            span.set_attribute("tool.name", "search_web")
            span.set_attribute("tool.query", query[:200])
            if site_filter:
                span.set_attribute("tool.site_filter", site_filter)
            t0 = time.perf_counter()
            result = _original_search(query, max_results, site_filter)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            span.set_attribute("tool.result_count", len(result))
            span.set_attribute("tool.latency_ms", round(elapsed_ms, 1))
            return result

    # ——— 包装 fetch_content ———
    _original_fetch = tools_module.fetch_content

    @functools.wraps(_original_fetch)
    def _traced_fetch(url: str, timeout: float = 8.0) -> str:
        with tracer.start_as_current_span("tool:fetch_content") as span:
            span.set_attribute("tool.name", "fetch_content")
            span.set_attribute("tool.url", url[:500])
            t0 = time.perf_counter()
            result = _original_fetch(url, timeout)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            span.set_attribute("tool.content_length", len(result))
            span.set_attribute("tool.latency_ms", round(elapsed_ms, 1))
            return result

    tools_module.search_web = _traced_search  # type: ignore[assignment]
    tools_module.fetch_content = _traced_fetch  # type: ignore[assignment]

    _tools_patched = True
    logger.debug("Tools patched for OTel tracing")


# ——— 初始化 ———


def setup_otel() -> bool:
    """初始化 OpenTelemetry TracerProvider 和导出器链（幂等）。

    导出器链：
    1. OTLP HTTP → 远端 collector（Jaeger/Tempo/Grafana Cloud）
    2. Console → 开发调试时终端输出
    3. File → JSON Lines 文件（CI/无 collector 环境）

    Returns:
        True 表示初始化成功；False 表示 OTel 未安装或已禁用。
    """
    global _initialized
    if _initialized:
        return True

    if not settings.otel_enabled:
        return False

    if not _import_otel():
        logger.warning(
            "otel_enabled=True but OpenTelemetry packages not installed. "
            "Install with: uv pip install deepresearch-agent[otel]"
        )
        return False

    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    provider = TracerProvider()

    # 1. OTLP HTTP 导出器（生产）
    try:
        otlp = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp))
        logger.info("OTel: OTLP exporter configured → %s", settings.otel_endpoint)
    except Exception:
        logger.warning(
            "OTel: Failed to create OTLP exporter for %s", settings.otel_endpoint,
            exc_info=True,
        )

    # 2. Console 导出器（开发）
    if settings.otel_console_export:
        provider.add_span_processor(
            SimpleSpanProcessor(ConsoleSpanExporter())
        )
        logger.info("OTel: Console exporter enabled")

    # 3. File 导出器（CI/无 collector）
    if settings.otel_file_export:
        file_exporter = _FileSpanExporter(settings.otel_file_export)
        provider.add_span_processor(SimpleSpanProcessor(file_exporter))
        atexit.register(file_exporter.shutdown)
        logger.info("OTel: File exporter → %s", settings.otel_file_export)

    trace.set_tracer_provider(provider)

    # 工具函数追踪
    _patch_tools()

    _initialized = True
    logger.info(
        "OTel initialized: service=%s",
        settings.otel_service_name,
    )
    return True


# ——— Context Manager ———


@contextmanager
def workflow_span(query: str) -> Iterator[Any]:
    """包裹单次 workflow 执行的根 span。

    Usage::

        if settings.otel_enabled:
            with workflow_span(query):
                result = graph.invoke(state, config)
        else:
            result = graph.invoke(state, config)
    """
    if not _initialized and not setup_otel():
        yield None
        return

    from opentelemetry import trace

    tracer = trace.get_tracer(settings.otel_service_name)
    with tracer.start_as_current_span("workflow:deepresearch") as span:
        span.set_attribute("gen_ai.operation.name", "deepresearch")
        span.set_attribute("deepresearch.query", query[:500])
        yield span
