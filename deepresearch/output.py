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
    if state.get("research_plan"):
        save_json(state["research_plan"], session_dir / "plan.json")
        count += 1
    if state.get("search_results"):
        save_json(state["search_results"], session_dir / "search_results.json")
        count += 1
    if state.get("sources"):
        save_json(state["sources"], session_dir / "sources.json")
        count += 1
    if state.get("evidences"):
        save_json(state["evidences"], session_dir / "evidences.json")
        count += 1
    if state.get("draft_summary"):
        save_markdown(state["draft_summary"], session_dir / "draft_summary.md")
        count += 1
    if state.get("critique_result"):
        save_json(state["critique_result"], session_dir / "critique.json")
        count += 1
    if state.get("final_report"):
        save_markdown(state["final_report"], session_dir / "final_report.md")
        count += 1
    logger.info("Saved %d artifacts to %s", count, session_dir)
