import logging
import time
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from deepresearch.config import settings

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

    def _build_table(self, current_node: str | None = None) -> Table:
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
            else:
                table.add_row("⬜", label, "等待中")
        return table

    def render_node_start(self, node_name: str) -> None:
        """标记 node 开始。"""
        if not self._enabled:
            return
        self._start_times[node_name] = time.perf_counter()

    def render_node_done(self, node_name: str, result: dict[str, Any]) -> None:
        """标记 node 完成。"""
        if not self._enabled:
            return
        self._completed[node_name] = result

    def render_summary(self, result: dict[str, Any]) -> None:
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


def stream_with_rich(graph, initial_state: dict, config: dict) -> dict:
    """使用 Rich Live 逐个渲染 LangGraph stream 执行过程。"""
    if not settings.stream_enabled:
        return graph.invoke(initial_state, config)

    console = Console()
    renderer = StreamRenderer(console)

    panel = Panel(
        renderer._build_table(),
        title=f"🔍 DeepResearch: {initial_state.get('user_query', '')}",
        border_style="blue",
    )

    with Live(panel, console=console, refresh_per_second=4, transient=False) as live:
        last_result = initial_state
        for chunk in graph.stream(initial_state, config, stream_mode="updates"):
            for node_name, node_result in chunk.items():
                renderer.render_node_start(node_name)
                renderer.render_node_done(node_name, node_result)
                last_result = {**last_result, **node_result}
                live.update(renderer._build_table())

    renderer.render_summary(last_result)
    return last_result
