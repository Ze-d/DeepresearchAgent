# deepresearch/cli.py
import logging
from pathlib import Path

import typer

from deepresearch.config import Settings
from deepresearch.graph import build_graph
from deepresearch.logging import setup_logging
from deepresearch.state import AgentState

app = typer.Typer(help="DeepResearch Agent — LangGraph-based research workflow")
logger = logging.getLogger(__name__)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """DeepResearch Agent CLI."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _make_initial_state(query: str, max_iterations: int) -> AgentState:
    """创建初始 AgentState。"""
    return {
        "user_query": query,
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "status": "initialized",
        "errors": [],
    }


@app.command()
def run(
    query: str = typer.Argument(..., help="研究问题"),
    max_iterations: int = typer.Option(2, "--max-iterations", "-n", help="最大研究迭代次数"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用 DEBUG 级别日志"),
    log_file: str | None = typer.Option(None, "--log-file", help="日志文件路径"),
):
    """运行 DeepResearch Agent 完成研究任务。"""
    cfg = Settings()
    log_level = "DEBUG" if verbose else cfg.log_level
    resolved_log_file = log_file or cfg.log_file
    setup_logging(level=log_level, log_file=resolved_log_file)

    logger.info("Starting DeepResearch Agent")
    logger.debug("Query: %s", query)
    logger.debug("Max iterations: %d, Log level: %s", max_iterations, log_level)

    initial_state = _make_initial_state(query, max_iterations)

    graph = build_graph()
    app_graph = graph.compile()

    typer.echo(f"🔍 开始研究: {query}")
    typer.echo(f"   最大迭代次数: {max_iterations}")

    result = app_graph.invoke(initial_state)

    final = result.get("final_report", "")
    typer.echo("\n" + "=" * 60)
    typer.echo(final)
    typer.echo("=" * 60)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(final, encoding="utf-8")
        typer.echo(f"\n📄 报告已保存到: {out_path}")

    plan = result.get("research_plan")
    critique = result.get("critique_result")
    typer.echo(f"\n📊 迭代次数: {result.get('iteration', 0)}")
    if plan:
        typer.echo(f"   子问题数: {len(plan.get('sub_questions', []))}")
    if critique:
        typer.echo(f"   Critique 评分: {critique.get('score', 'N/A')}")

    errors = result.get("errors", [])
    if errors:
        typer.echo(f"   ⚠️  错误: {len(errors)} 个")
        for e in errors:
            logger.error("Workflow error: %s", e)

    logger.info("DeepResearch Agent completed")
    typer.echo("✅ 研究完成")
