# deepresearch/nodes/merge.py
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from deepresearch.state import AgentState

logger = logging.getLogger(__name__)


def _dedup_sources_by_url(sources: list[dict]) -> list[dict]:
    """按 URL 去重 sources，保留首次出现的条目。"""
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for src in sources:
        url = src.get("url", "")
        if url not in seen_urls:
            seen_urls.add(url)
            deduped.append(src)
    return deduped


def _dedup_evidences(evidences: list[dict], llm: BaseChatModel) -> list[dict]:
    """对 evidences 进行语义去重（延迟 import 以支持测试 monkeypatch）。"""
    from deepresearch.evidence.dedup import deduplicate_evidences

    return deduplicate_evidences(evidences, llm)


def _rank_sources(sources: list[dict]) -> list[dict]:
    """对 sources 进行权威度评分排序（延迟 import 以支持测试 monkeypatch）。"""
    from deepresearch.evidence.ranking import rank_sources

    return rank_sources(sources)


def _build_merge_summary(
    sources: list[dict],
    evidences: list[dict],
) -> dict[str, Any]:
    """构建 merge_summary 元数据字典。"""
    # 按 source_agent 统计 unique_findings
    agent_counts: dict[str, int] = {}
    for ev in evidences:
        agent = ev.get("source_agent", "unknown")
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    return {
        "total_sources": len(sources),
        "total_evidences": len(evidences),
        "cross_validated_count": 0,  # Phase 1 — placeholder
        "unique_findings_per_agent": agent_counts,
        "conflicts": [],  # Phase 1 — placeholder
        "source_bias_warnings": [],
        "coverage_gaps": [],
    }


def make_merge_node(llm: BaseChatModel):
    """创建 merge_node（闭包注入 LLM）。

    Phase 1 — Simple Collect + Dedup + Rank:
    1. 收集所有 Agent 的 sources 和 evidences
    2. 对 sources 按 URL 去重
    3. 对 evidences 做 LLM 语义去重
    4. 对 sources 做权威度评分排序
    5. 生成 merge_summary 摘要
    """

    def merge_node(state: AgentState) -> dict:
        sources = list(state.get("sources", []))
        evidences = list(state.get("evidences", []))

        logger.info(
            "Merge: %d sources, %d evidences before dedup",
            len(sources),
            len(evidences),
        )

        # 1) 按 URL 去重 sources
        sources = _dedup_sources_by_url(sources)

        # 2) LLM 语义去重 evidences
        if evidences:
            evidences = _dedup_evidences(evidences, llm)

        # 3) 权威度评分排序
        if sources:
            sources = _rank_sources(sources)

        # 4) 构建 merge_summary
        merge_summary = _build_merge_summary(sources, evidences)

        logger.info(
            "Merge done: %d sources, %d evidences after dedup",
            len(sources),
            len(evidences),
        )

        return {
            "sources": sources,
            "evidences": evidences,
            "merge_summary": merge_summary,
            "status": "merged",
        }

    return merge_node


# Backward-compatible module-level alias for __init__.py / graph.py
def merge_node(state: AgentState) -> dict:
    """Backward-compatible entry point (uses default LLM from build_llm())."""
    from deepresearch.llm import build_llm

    llm = build_llm()
    return make_merge_node(llm)(state)
