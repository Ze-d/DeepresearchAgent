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
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_ref": None,
        "agent_outputs": [],
        "merge_summary": None,
        "human_review": None,
    }


def run_workflow(query: str, max_iterations: int = 2) -> dict:
    """同步执行 DeepResearch workflow，返回最终 AgentState dict。

    供 CLI run 命令和 FastAPI server 共享使用。
    """
    initial_state = _make_initial_state(query, max_iterations)

    from deepresearch.output import init_session_dir, save_all
    from deepresearch.checkpoint.manager import CheckpointManager

    graph = build_graph()
    session_dir = init_session_dir()
    cm = CheckpointManager(session_dir)
    app_graph = graph.compile(checkpointer=cm.saver)
    config = {"configurable": {"thread_id": session_dir.name}}

    result = app_graph.invoke(initial_state, config)

    save_all(result, session_dir)
    cm.save(result, "final")

    # v1 额外输出
    from deepresearch.output import save_json
    metrics = result.get("iteration_metrics", [])
    if metrics:
        save_json(metrics, session_dir / "iteration_metrics.json")
    citations = result.get("citations", [])
    if citations:
        save_json(citations, session_dir / "citations.json")

    logger.info("Workflow completed: iteration=%d, status=%s",
                result.get("iteration", 0), result.get("status"))
    return result


@app.command()
def run(
    query: str = typer.Argument(..., help="研究问题"),
    max_iterations: int = typer.Option(2, "--max-iterations", "-n", help="最大研究迭代次数"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="启用 DEBUG 级别日志"),
    log_file: str | None = typer.Option(None, "--log-file", help="日志文件路径"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="启用/禁用实时 streaming 展示"),
):
    """运行 DeepResearch Agent 完成研究任务。"""
    cfg = Settings()
    log_level = "DEBUG" if verbose else cfg.log_level
    resolved_log_file = log_file or cfg.log_file
    setup_logging(level=log_level, log_file=resolved_log_file)

    if not stream:
        import deepresearch.config as config_module
        config_module.settings.stream_enabled = False

    logger.info("Starting DeepResearch Agent")
    logger.debug("Query: %s", query)
    logger.debug("Max iterations: %d, Log level: %s", max_iterations, log_level)

    initial_state = _make_initial_state(query, max_iterations)

    session_dir: Path | None = None
    if stream:
        # ——— 实时 streaming 模式 ———
        graph = build_graph()

        from deepresearch.output import init_session_dir, save_all
        session_dir = init_session_dir()
        from deepresearch.checkpoint.manager import CheckpointManager
        cm = CheckpointManager(session_dir)
        app_graph = graph.compile(checkpointer=cm.saver)

        typer.echo(f"🔍 开始研究: {query}")
        typer.echo(f"   最大迭代次数: {max_iterations}")

        from deepresearch.streaming.renderer import stream_with_rich
        config = {"configurable": {"thread_id": session_dir.name}}
        result = stream_with_rich(app_graph, initial_state, config)

        final = result.get("final_report") or ""
        typer.echo("\n" + "=" * 60)
        typer.echo(final)
        typer.echo("=" * 60)

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(final, encoding="utf-8")
            typer.echo(f"\n📄 报告已保存到: {out_path}")

        # v1 outputs
        save_all(result, session_dir)
        from deepresearch.output import save_json
        metrics = result.get("iteration_metrics", [])
        if metrics:
            save_json(metrics, session_dir / "iteration_metrics.json")
        citations = result.get("citations", [])
        if citations:
            save_json(citations, session_dir / "citations.json")
        cm.save(result, "final")

        # v1 stats
        typer.echo(f"\n📊 迭代次数: {result.get('iteration', 0)}")
        plan = result.get("research_plan")
        if plan:
            typer.echo(f"   子问题数: {len(plan.get('sub_questions', []))}")
        critique = result.get("critique_result")
        if critique:
            typer.echo(f"   Critique 评分: {critique.get('overall_score', critique.get('score', 'N/A'))}")
        iteration_metrics_list = result.get("iteration_metrics", [])
        if iteration_metrics_list:
            last_metrics = iteration_metrics_list[-1]
            fix_rate = last_metrics.get("fix_rate")
            if fix_rate is not None:
                typer.echo(f"   Issues 修复率: {fix_rate * 100:.0f}%")
        sources = result.get("sources", [])
        evidences = result.get("evidences", [])
        typer.echo(f"   来源数: {len(sources)}, 证据数: {len(evidences)}")
        typer.echo(f"   输出目录: {session_dir}")

        errors = result.get("errors", [])
        if errors:
            typer.echo(f"   ⚠️  错误: {len(errors)} 个")
            for e in errors:
                logger.error("Workflow error: %s", e)

        logger.info("DeepResearch Agent completed")
        typer.echo("✅ 研究完成")
    else:
        # ——— 非 streaming 模式：使用共享 run_workflow ———
        result = run_workflow(query, max_iterations)

        final = result.get("final_report") or ""
        typer.echo("\n" + "=" * 60)
        typer.echo(final)
        typer.echo("=" * 60)

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(final, encoding="utf-8")
            typer.echo(f"\n📄 报告已保存到: {out_path}")

        # v1 stats
        typer.echo(f"\n📊 迭代次数: {result.get('iteration', 0)}")
        plan = result.get("research_plan")
        if plan:
            typer.echo(f"   子问题数: {len(plan.get('sub_questions', []))}")
        critique = result.get("critique_result")
        if critique:
            typer.echo(f"   Critique 评分: {critique.get('overall_score', critique.get('score', 'N/A'))}")
        iteration_metrics_list = result.get("iteration_metrics", [])
        if iteration_metrics_list:
            last_metrics = iteration_metrics_list[-1]
            fix_rate = last_metrics.get("fix_rate")
            if fix_rate is not None:
                typer.echo(f"   Issues 修复率: {fix_rate * 100:.0f}%")
        sources = result.get("sources", [])
        evidences = result.get("evidences", [])
        typer.echo(f"   来源数: {len(sources)}, 证据数: {len(evidences)}")

        errors = result.get("errors", [])
        if errors:
            typer.echo(f"   ⚠️  错误: {len(errors)} 个")
            for e in errors:
                logger.error("Workflow error: %s", e)

        logger.info("DeepResearch Agent completed")
        typer.echo("✅ 研究完成")


@app.command()
def resume(
    session_dir: str = typer.Argument(..., help="Session 目录路径"),
):
    """从中断 session 恢复执行。"""
    from pathlib import Path
    from deepresearch.output import save_all

    sd = Path(session_dir)
    if not sd.exists():
        typer.echo(f"❌ Session 目录不存在: {session_dir}")
        raise typer.Exit(code=1)

    from deepresearch.checkpoint.manager import CheckpointManager
    cm = CheckpointManager(sd)
    checkpoints = cm.list_checkpoints()
    if not checkpoints:
        typer.echo("❌ 未找到 checkpoint")
        raise typer.Exit(code=1)

    latest = checkpoints[-1]
    state = cm.load(latest["id"])
    if state is None:
        typer.echo(f"❌ 无法加载 checkpoint: {latest['id']}")
        raise typer.Exit(code=1)

    typer.echo(f"📂 从 checkpoint 恢复: {latest['id']}")
    typer.echo(f"   状态: {state.get('status', 'unknown')}")
    typer.echo(f"   迭代: {state.get('iteration', 0)}")

    graph = build_graph()
    app_graph = graph.compile(checkpointer=cm.saver)
    config = {"configurable": {"thread_id": sd.name}}

    from deepresearch.streaming.renderer import stream_with_rich
    result = stream_with_rich(app_graph, state, config)

    save_all(result, sd)
    cm.save(result, "final")
    typer.echo("✅ 恢复执行完成")


@app.command()
def checkpoints(
    session_dir: str = typer.Argument(..., help="Session 目录路径"),
):
    """列出 session 的 checkpoint。"""
    from pathlib import Path
    sd = Path(session_dir)
    if not sd.exists():
        typer.echo(f"❌ Session 目录不存在: {session_dir}")
        raise typer.Exit(code=1)

    from deepresearch.checkpoint.manager import CheckpointManager
    cm = CheckpointManager(sd)
    cps = cm.list_checkpoints()

    if not cps:
        typer.echo("(无 checkpoint)")
        return

    typer.echo(f"Checkpoints ({len(cps)}):")
    for cp in cps:
        typer.echo(f"  {cp['id']} — {cp['size_bytes']} bytes")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="服务器绑定的 IP"),
    port: int = typer.Option(8620, "--port", "-p", help="服务器端口"),
    reload: bool = typer.Option(False, "--reload", help="启用热重载（开发模式）"),
):
    """启动 Web 服务器（FastAPI + Vue 前端）。"""
    import sys
    import uvicorn

    # 确保 server 包可被导入（项目根目录可能不在已安装的 package 路径中）
    _project_root = str(Path(__file__).resolve().parent.parent)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    # 覆盖配置
    import deepresearch.config as config_module
    config_module.settings.server_host = host
    config_module.settings.server_port = port

    typer.echo("🚀 DeepResearch Agent Web Server")
    typer.echo(f"   地址: http://{host}:{port}")
    typer.echo(f"   API 文档: http://{host}:{port}/docs")

    web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if not web_dist.exists():
        typer.echo("   ⚠️  前端未构建（web/dist/ 不存在）")
        typer.echo("   请先运行: cd web && npm install && npm run build")

    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
