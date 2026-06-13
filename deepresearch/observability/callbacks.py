import logging
import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from deepresearch.observability.metrics import NodeMetrics, MetricsCollector

logger = logging.getLogger(__name__)


class ObservabilityCallback(BaseCallbackHandler):
    """LangChain callback，追踪每个 node 的 LLM 调用指标。

    Usage:
        collector = MetricsCollector()
        callback = ObservabilityCallback("plan", collector)
        llm = build_llm().with_config(callbacks=[callback])
    """

    def __init__(self, node_name: str, collector: MetricsCollector):
        super().__init__()
        self.node_name = node_name
        self.collector = collector
        self._start_time: float = 0.0
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._call_count: int = 0
        self._errors: list[str] = []

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        self._start_time = time.perf_counter()
        # 估算输入 token（简化：按字符数 / 2 估算，实际由 on_llm_end 覆盖）
        for p in prompts:
            self._input_tokens += len(p) // 2
        self._call_count += 1

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        end_time = time.perf_counter()
        # 提取实际 token 用量
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            self._input_tokens = usage.get("prompt_tokens", self._input_tokens)
            self._output_tokens = usage.get("completion_tokens", 0)

        metrics = NodeMetrics(
            node_name=self.node_name,
            start_time=self._start_time,
            end_time=end_time,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            llm_calls=self._call_count,
            errors=self._errors,
        )
        self.collector.record_node(self.node_name, metrics)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self._errors.append(str(error))
        logger.error("LLM error in node '%s': %s", self.node_name, error)
