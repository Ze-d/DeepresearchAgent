import logging
import time
from collections.abc import Mapping
from typing import Any, cast

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from deepresearch.config import settings
from deepresearch.state import AgentState

logger = logging.getLogger(__name__)

_NODE_LABELS = {
    "plan": "Plan",
    "research": "Research",
    "summary": "Summary",
    "critique": "Critique",
    "final": "Final",
}


class StreamRenderer:
    """用 Rich 渲染 LangGraph streaming 输出。"""

    def __init__(self, console: Console | None = None, enabled: bool | None = None):
        self.console = console or Console()
        self._enabled = enabled if enabled is not None else settings.stream_enabled
        self._start_times: dict[str, float] = {}
        self._completed: dict[str, dict[str, Any]] = {}

    def _build_table(self) -> Table:
        """构建进度表格。"""
        table = Table(show_header=False, expand=True, box=None)
        table.add_column("status", width=3)
        table.add_column("node", width=12)
        table.add_column("detail")

        nodes_order = ["plan", "research", "summary", "critique", "final"]
        for node in nodes_order:
            label = _NODE_LABELS.get(node, node)
            if node in self._completed:
                elapsed = time.perf_counter() - self._start_times.get(node, time.perf_counter())
                table.add_row("✅", label, f"已完成 ({elapsed:.1f}s)")
            elif node in self._start_times and node not in self._completed:
                # 正在执行中
                elapsed = time.perf_counter() - self._start_times[node]
                table.add_row("⏳", label, f"进行中... ({elapsed:.0f}s)")
            else:
                table.add_row("⬜", label, "等待中")
        return table

    def render_node_start(self, node_name: str) -> None:
        """标记 node 开始，立即输出提示。"""
        if not self._enabled:
            return
        self._start_times[node_name] = time.perf_counter()
        label = _NODE_LABELS.get(node_name, node_name)
        self.console.print(f"⏳ {label} 开始执行...")

    def render_node_done(self, node_name: str, result: dict[str, Any]) -> None:
        """标记 node 完成。"""
        if not self._enabled:
            return
        self._completed[node_name] = result
        elapsed = time.perf_counter() - self._start_times.get(node_name, time.perf_counter())
        label = _NODE_LABELS.get(node_name, node_name)
        self.console.print(f"✅ {label} 完成 ({elapsed:.1f}s)")

    def render_summary(self, result: Mapping[str, Any]) -> None:
        """打印最终摘要。"""
        if not self._enabled:
            return
        iteration = result.get("iteration", 0)
        metrics = result.get("iteration_metrics", [])
        self.console.print(f"\n📊 迭代次数: {iteration}")
        if metrics:
            last = metrics[-1]
            self.console.print(f"   Critique 评分: {last.get('overall_score', 'N/A')}")
            fix_rate = last.get("fix_rate")
            if fix_rate is not None:
                self.console.print(f"   Issues 修复率: {fix_rate * 100:.0f}%")
        sources_count = len(result.get("sources", []))
        evidences_count = len(result.get("evidences", []))
        self.console.print(f"   来源数: {sources_count}, 证据数: {evidences_count}")


def stream_with_rich(graph, initial_state: AgentState, config: dict[str, Any]) -> AgentState:
    """逐个渲染 LangGraph stream 执行过程，实时显示进度。

    使用 graph.stream(stream_mode="updates") 在每个 node 完成时输出，
    同时 research_node 内部通过 console.print 输出子步骤进度。
    """
    if not settings.stream_enabled:
        return cast(AgentState, graph.invoke(initial_state, config))

    console = Console()
    renderer = StreamRenderer(console)

    console.print(Panel(
        f"问题: {initial_state.get('user_query', '')}",
        title="🔍 DeepResearch Agent v1",
        border_style="blue",
    ))

    last_result = initial_state
    for chunk in graph.stream(initial_state, config, stream_mode="updates"):
        for node_name, node_result in chunk.items():
            renderer.render_node_start(node_name)
            # node 执行完成才到这里（stream_mode="updates" 的特性）
            # 内部的 console.print 已经实时输出了进度
            renderer.render_node_done(node_name, node_result)
            last_result = cast(AgentState, {**last_result, **node_result})

    renderer.render_summary(last_result)
    return last_result
