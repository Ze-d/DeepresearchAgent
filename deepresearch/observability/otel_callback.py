"""OpenTelemetry LangChain Callback Handler。

为每个 LLM 调用创建 ``llm:invoke`` span，记录模型名和 token 用量。
与现有 ``ObservabilityCallback`` 独立共存——LangChain 支持多个 callback。
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from deepresearch.config import settings

logger = logging.getLogger(__name__)

# ——— 延迟 import，避免 otel 未安装时崩溃 ———
_trace: Any = None
_Tracer: Any = None
_Span: Any = None
_StatusCode: Any = None


def _ensure_otel():
    """延迟加载 OTel API，失败时返回 False。"""
    global _trace, _Tracer, _Span, _StatusCode
    if _trace is not None:
        return True
    try:
        from opentelemetry import trace as _trace_mod
        from opentelemetry.trace import Tracer as _Tracer_mod
        from opentelemetry.trace import Span as _Span_mod
        from opentelemetry.trace import StatusCode as _StatusCode_mod

        _trace = _trace_mod
        _Tracer = _Tracer_mod
        _Span = _Span_mod
        _StatusCode = _StatusCode_mod
        return True
    except ImportError:
        logger.warning("OpenTelemetry packages not installed; spans will not be created.")
        return False


class OTelCallbackHandler(BaseCallbackHandler):
    """LangChain callback，将 LLM 调用转为 OpenTelemetry span。

    每个 ``on_llm_start`` 创建 span，对应的 ``on_llm_end`` 或
    ``on_llm_error`` 结束 span 并记录属性。

    Span attributes 遵循 GenAI 语义约定：
    - ``gen_ai.system``: ``"deepseek"``
    - ``gen_ai.request.model``: 模型名
    - ``gen_ai.usage.input_tokens`` / ``gen_ai.usage.output_tokens``
    """

    def __init__(self) -> None:
        super().__init__()
        self._spans: dict[str, Any] = {}

    def _get_tracer(self) -> Any:
        """获取 OTel tracer 实例。"""
        if not _ensure_otel():
            return None
        return _trace.get_tracer(settings.otel_service_name)

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        tracer = self._get_tracer()
        if tracer is None:
            return

        model_name = (
            serialized.get("kwargs", {}).get("model", "unknown")
            if isinstance(serialized, dict)
            else "unknown"
        )
        span = tracer.start_span(
            "llm:invoke",
            attributes={
                "gen_ai.system": "deepseek",
                "gen_ai.request.model": str(model_name),
            },
        )
        self._spans[str(run_id)] = span

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        span = self._spans.pop(str(run_id), None)
        if span is None:
            return

        # 提取 token 用量，兼容多种 key 名格式
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            if isinstance(usage, dict):
                input_tokens = (
                    usage.get("prompt_tokens")
                    or usage.get("input_tokens")
                    or usage.get("input")
                    or 0
                )
                output_tokens = (
                    usage.get("completion_tokens")
                    or usage.get("output_tokens")
                    or usage.get("output")
                    or 0
                )
                span.set_attribute("gen_ai.usage.input_tokens", int(input_tokens))
                span.set_attribute("gen_ai.usage.output_tokens", int(output_tokens))

        span.end()

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        **kwargs: Any,
    ) -> None:
        span = self._spans.pop(str(run_id), None)
        if span is None:
            return
        span.record_exception(error)
        if _ensure_otel() and _StatusCode is not None:
            span.set_status(_StatusCode.ERROR, str(error))
        span.end()


# ——— Node Span 包装器 ———


def _trace_node(name: str, func: Callable[..., Any]) -> Callable[..., Any]:
    """包装 LangGraph node 函数，为其创建 ``node:{name}`` span。

    Args:
        name: Node 名称（如 ``"plan"``、``"summary"``）。
        func: 原始 node 函数，签名为 ``(state: AgentState) -> dict``。

    Returns:
        包装后的函数，签名不变。
    """

    @functools.wraps(func)
    def wrapper(state: Any) -> dict[str, Any]:
        if not _ensure_otel():
            return func(state)

        tracer = _trace.get_tracer(settings.otel_service_name)
        with tracer.start_as_current_span(f"node:{name}") as span:
            span.set_attribute("deepresearch.node.name", name)
            try:
                result = func(state)
                if isinstance(result, dict):
                    span.set_attribute(
                        "deepresearch.node.status",
                        str(result.get("status", "")),
                    )
                return result
            except Exception:
                span.record_exception(
                    Exception("node execution failed"),
                )
                if _StatusCode is not None:
                    span.set_status(_StatusCode.ERROR, "node execution failed")
                raise

    return wrapper
