import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NodeMetrics:
    """单个 node 的执行指标。"""

    node_name: str
    start_time: float
    end_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def latency_ms(self) -> float:
        return round((self.end_time - self.start_time) * 1000, 0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class MetricsCollector:
    """汇总整个 run 的指标。"""

    def __init__(self):
        self.node_metrics: dict[str, NodeMetrics] = {}

    def record_node(self, name: str, metrics: NodeMetrics) -> None:
        """记录一个 node 的指标（多次调用合并）。"""
        if name in self.node_metrics:
            existing = self.node_metrics[name]
            existing.end_time = metrics.end_time
            existing.input_tokens += metrics.input_tokens
            existing.output_tokens += metrics.output_tokens
            existing.llm_calls += metrics.llm_calls
            existing.errors.extend(metrics.errors)
        else:
            self.node_metrics[name] = metrics

    def summary(self) -> dict[str, Any]:
        """生成汇总 dict（用于输出 metrics.json）。"""
        nodes = {}
        total_tokens = 0
        total_latency_ms = 0.0

        for name, m in self.node_metrics.items():
            nodes[name] = {
                "tokens": m.total_tokens,
                "latency_ms": m.latency_ms,
                "llm_calls": m.llm_calls,
                "errors": len(m.errors),
            }
            total_tokens += m.total_tokens
            total_latency_ms += m.latency_ms

        return {
            "total_tokens": total_tokens,
            "total_latency_ms": round(total_latency_ms, 0),
            "nodes": nodes,
        }
