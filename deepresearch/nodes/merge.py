# deepresearch/nodes/merge.py
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from deepresearch.evidence.cross_validate import (
    cross_validate_evidences,
    detect_conflicts,
)
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


def _build_clusters_from_evidence(evidences: list[dict]) -> list[list[dict]]:
    """从交叉验证后的 evidences 构建 clusters，用于冲突检测。

    将具有相同 confirming_agents 集合的 evidence 归入同一 cluster。
    每个 solo finding（无 confirming_agents 或未交叉验证）单独成簇。

    Args:
        evidences: 交叉验证后的 evidence 列表

    Returns:
        cluster 列表，每个 cluster 包含一组 related evidence
    """
    clusters: list[list[dict]] = []
    used: set[int] = set()

    for i, ev in enumerate(evidences):
        if i in used:
            continue
        agent_set = frozenset(ev.get("confirming_agents", []))
        if not agent_set:
            # Solo finding — 单独成簇
            clusters.append([ev])
            used.add(i)
        else:
            # 与具有相同 confirming_agents 的其他 evidence 归组
            cluster = [ev]
            used.add(i)
            for j in range(i + 1, len(evidences)):
                if j in used:
                    continue
                other_set = frozenset(evidences[j].get("confirming_agents", []))
                if other_set and other_set == agent_set:
                    cluster.append(evidences[j])
                    used.add(j)
            clusters.append(cluster)

    return clusters


def _build_merge_summary(
    sources: list[dict],
    evidences: list[dict],
    conflicts: list[dict] | None = None,
) -> dict[str, Any]:
    """构建 merge_summary 元数据字典。"""
    # 按 source_agent 统计 unique_findings
    agent_counts: dict[str, int] = {}
    for ev in evidences:
        agent = ev.get("source_agent", "unknown")
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    # 交叉验证统计
    cross_validated_count = sum(
        1 for ev in evidences if ev.get("cross_validated")
    )
    total = len(evidences)
    solo_count = total - cross_validated_count

    source_bias_warnings: list[str] = []
    if total > 0 and (solo_count / total) > 0.5:
        source_bias_warnings.append(
            f"{solo_count}/{total} evidences are solo findings (single source)"
        )

    return {
        "total_sources": len(sources),
        "total_evidences": total,
        "cross_validated_count": cross_validated_count,
        "unique_findings_per_agent": agent_counts,
        "conflicts": conflicts or [],
        "source_bias_warnings": source_bias_warnings,
        "coverage_gaps": [],
    }


def make_merge_node(llm: BaseChatModel):
    """创建 merge_node（闭包注入 LLM）。

    Phase 2 — Three-stage pipeline with cross-validation:
    Stage 1: Collect & Normalize
    Stage 2: Dedup & Cross-Validate
      - 2a: Source URL dedup
      - 2b: Evidence semantic dedup
      - 2c: Cross-validation via cross_validate_evidences()
      - 2d: Conflict detection via detect_conflicts()
      - 2e: Source ranking
    Stage 3: Quality Report (enhanced merge_summary)
    """

    def merge_node(state: AgentState) -> dict:
        sources = list(state.get("sources", []))
        evidences = list(state.get("evidences", []))

        logger.info(
            "Merge: %d sources, %d evidences before dedup",
            len(sources),
            len(evidences),
        )

        # Stage 2a: 按 URL 去重 sources
        sources = _dedup_sources_by_url(sources)

        # Stage 2b: LLM 语义去重 evidences
        if evidences:
            evidences = _dedup_evidences(evidences, llm)

        # Stage 2c: 交叉验证 — 仅当 evidences 来自 >=2 个不同 source_agent
        distinct_agents = {ev.get("source_agent") for ev in evidences if ev.get("source_agent")}
        conflicts: list[dict] = []
        if evidences and len(distinct_agents) >= 2:
            evidences = cross_validate_evidences(evidences, llm)
            # Stage 2d: 冲突检测
            clusters = _build_clusters_from_evidence(evidences)
            conflicts = detect_conflicts(clusters, llm)

        # Stage 2e: 权威度评分排序
        if sources:
            sources = _rank_sources(sources)

        # Stage 3: 构建增强的 merge_summary
        merge_summary = _build_merge_summary(sources, evidences, conflicts=conflicts)

        logger.info(
            "Merge done: %d sources, %d evidences after dedup, "
            "%d conflicts detected",
            len(sources),
            len(evidences),
            len(conflicts),
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
