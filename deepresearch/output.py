# deepresearch/output.py
import json
import logging
from datetime import datetime
from pathlib import Path

from deepresearch.config import settings
from deepresearch.state import AgentState

logger = logging.getLogger(__name__)


def init_session_dir() -> Path:
    """创建 session 输出目录。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = Path(settings.output_dir) / f"session_{ts}"
    session_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Session output dir: %s", session_dir)
    return session_dir


def save_json(data: dict | list, path: Path) -> None:
    """保存 JSON 文件。"""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("Saved JSON: %s", path.name)


def save_markdown(content: str, path: Path) -> None:
    """保存 Markdown 文件。"""
    path.write_text(content, encoding="utf-8")
    logger.debug("Saved Markdown: %s", path.name)


def save_all(state: AgentState, session_dir: Path) -> None:
    """保存所有中间产物到 session 目录。"""
    count = 0
    research_plan = state.get("research_plan")
    if research_plan:
        save_json(research_plan, session_dir / "plan.json")
        count += 1
    search_results = state.get("search_results")
    if search_results:
        save_json(search_results, session_dir / "search_results.json")
        count += 1
    sources = state.get("sources")
    if sources:
        save_json(sources, session_dir / "sources.json")
        count += 1
    evidences = state.get("evidences")
    if evidences:
        save_json(evidences, session_dir / "evidences.json")
        count += 1
    draft_summary = state.get("draft_summary")
    if draft_summary:
        save_markdown(draft_summary, session_dir / "draft_summary.md")
        count += 1
    critique_result = state.get("critique_result")
    if critique_result:
        save_json(critique_result, session_dir / "critique.json")
        count += 1
    final_report = state.get("final_report")
    if final_report:
        save_markdown(final_report, session_dir / "final_report.md")
        count += 1
    # v1 新增输出
    citations = state.get("citations")
    if citations:
        save_json(citations, session_dir / "citations.json")
        count += 1
    iteration_metrics = state.get("iteration_metrics")
    if iteration_metrics:
        save_json(iteration_metrics, session_dir / "iteration_metrics.json")
        count += 1
    logger.info("Saved %d artifacts to %s", count, session_dir)
