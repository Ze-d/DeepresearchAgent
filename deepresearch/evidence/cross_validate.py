"""交叉验证与冲突检测模块。

提供两个函数：
- cross_validate_evidences: 跨 Agent 批量语义聚类，提升多源确认的 confidence
- detect_conflicts: 批量检测同一 cluster 内不同 Agent 的矛盾
"""

import json
import logging
import re
import time

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

_BATCH_CLUSTER_PROMPT = """你是一个交叉验证助手。请将以下证据按语义聚类——表达相同核心信息的归入同一组。

证据列表（JSON）：
{evidences_json}

要求：
1. 只比较 claim 字段的核心语义，忽略措辞差异。
2. 每个 cluster 包含表达相同信息的证据 ID 列表。
3. 不与任何其他证据相同的证据不需要单独列出。
4. 严格返回 JSON，no extra text。

返回格式：
{{"clusters": [["id1", "id3"], ["id2", "id5"], ...]}}"""

_BATCH_CONFLICT_PROMPT = """你是一个矛盾检测助手。以下是按语义聚类分组的多条证据——每组内的证据来自不同来源，声称相同事实。

请检测每组内是否存在矛盾。

聚类列表（JSON）：
{clusters_json}

返回格式：
{{"conflicts": [{{"cluster_index": 0, "severity": "major"}}, ...]}}

- cluster_index: 出现矛盾的组序号（从0开始）
- severity: major（根本矛盾）或 minor（轻微不一致）
- 没有矛盾的组不需要列出"""

_MAX_EVIDENCES = 50
_MAX_CONFIDENCE_BOOST = 0.2
_BOOST_PER_AGENT = 0.05
_MAX_CONFIDENCE = 1.0

# Rich console for progress output
_console = None


def _get_console():
    global _console
    if _console is None:
        from rich.console import Console
        _console = Console()
    return _console


def _batch_cluster(evidences: list[dict], llm: BaseChatModel) -> list[list[str]]:
    """用一次批量 LLM 调用将所有 evidence 聚类。"""
    ev_list = []
    for i, ev in enumerate(evidences):
        ev_list.append({
            "index": i,
            "id": ev.get("id", ""),
            "agent": ev.get("source_agent", "unknown"),
            "claim": ev.get("claim", "")[:300],
        })

    prompt = _BATCH_CLUSTER_PROMPT.format(
        evidences_json=json.dumps(ev_list, ensure_ascii=False)
    )

    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        text = str(response.content) if hasattr(response, "content") else str(response)

        # 提取 JSON
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        data = json.loads(text)
        raw_clusters: list[list[str]] = data.get("clusters", [])
    except Exception:
        logger.warning("Batch clustering LLM call failed", exc_info=True)
        # Fallback: 每条 evidence 独立成簇
        return [[ev["id"]] for ev in evidences]

    # 验证并重建 clusters（确保所有 ID 都存在）
    valid_ids = {ev["id"] for ev in evidences}
    clusters: list[list[str]] = []
    seen_in_clusters: set[str] = set()
    for cluster_ids in raw_clusters:
        clean = [cid for cid in cluster_ids if cid in valid_ids]
        if len(clean) >= 2:
            clusters.append(clean)
            seen_in_clusters.update(clean)

    # 未被任何 cluster 包含的 evidence 单独成簇
    for ev in evidences:
        if ev["id"] not in seen_in_clusters:
            clusters.append([ev["id"]])

    return clusters


def cross_validate_evidences(evidences: list[dict], llm: BaseChatModel) -> list[dict]:
    """交叉验证入口：批量语义聚类 → 跨 Agent 验证 → 更新 confidence。

    使用单次批量 LLM 调用对所有 evidence 进行语义聚类（O(1) API 调用），
    然后对每个多 Agent 确认的 cluster 提升 confidence。

    Args:
        evidences: evidence 字典列表
        llm: LLM 实例

    Returns:
        更新后的 evidence 列表（原位修改）
    """
    if not evidences:
        return []

    if len(evidences) < 2:
        for ev in evidences:
            ev["cross_validated"] = False
            ev["source_bias"] = True
        return evidences

    t0 = time.perf_counter()

    # 限制参与聚类的 evidence 数量（取 confidence 最高的前 N 条）
    sorted_evs = sorted(evidences, key=lambda e: e.get("confidence", 0), reverse=True)

    if len(sorted_evs) > _MAX_EVIDENCES:
        _get_console().print(
            f"   ⚠️  交叉验证: {len(sorted_evs)} 条过多 → 取前 {_MAX_EVIDENCES} 条高置信度 evidence"
        )
        to_validate = sorted_evs[:_MAX_EVIDENCES]
        rest = sorted_evs[_MAX_EVIDENCES:]
        # 未参与验证的标记为 solo
        for ev in rest:
            ev["cross_validated"] = False
            ev["source_bias"] = True
    else:
        to_validate = sorted_evs
        rest = []

    # 一次批量 LLM 调用进行语义聚类
    _get_console().print(f"   🔬 交叉验证: {len(to_validate)} 条批量聚类中...")
    clusters = _batch_cluster(to_validate, llm)

    # 应用 confidence 调整
    for cluster_ids in clusters:
        cluster_evs = [ev for ev in to_validate if ev["id"] in cluster_ids]
        if not cluster_evs:
            continue

        agents = {ev.get("source_agent", "") for ev in cluster_evs if ev.get("source_agent")}
        if len(agents) >= 2:
            boost = min(_BOOST_PER_AGENT * len(agents), _MAX_CONFIDENCE_BOOST)
            for ev in cluster_evs:
                ev["confidence"] = min(ev.get("confidence", 0) + boost, _MAX_CONFIDENCE)
                ev["cross_validated"] = True
                ev["confirming_agents"] = sorted(agents)
        else:
            for ev in cluster_evs:
                ev["cross_validated"] = False
                ev["source_bias"] = True

    # 合并回完整列表
    result = to_validate + rest

    # 统计
    cv_count = sum(1 for ev in result if ev.get("cross_validated"))
    elapsed = time.perf_counter() - t0
    logger.info(
        "Cross-validate: %d/%d cross-validated in %d clusters (%.1fs)",
        cv_count, len(result), len(clusters), elapsed,
    )
    _get_console().print(
        f"   ✅ 交叉验证完成: {cv_count}/{len(result)} validated, {len(clusters)} clusters ({elapsed:.1f}s)"
    )

    return result


def detect_conflicts(clusters: list[list[dict]], llm: BaseChatModel) -> list[dict]:
    """冲突检测入口：批量检测所有 cluster 中的矛盾。

    使用单次批量 LLM 调用检测所有符合条件的 cluster，
    而非逐 cluster 调用。

    Args:
        clusters: 聚类后的 evidence 分组列表
        llm: LLM 实例

    Returns:
        冲突列表
    """
    # 筛选出含 >=2 个不同 Agent 的 cluster
    multi_agent_clusters = []
    for cluster in clusters:
        agents = {ev.get("source_agent", "") for ev in cluster if ev.get("source_agent")}
        if len(agents) >= 2:
            multi_agent_clusters.append(cluster)

    if not multi_agent_clusters:
        return []

    t0 = time.perf_counter()

    # 构建批量 prompt
    cluster_list = []
    for ci, cluster in enumerate(multi_agent_clusters):
        cluster_list.append({
            "cluster_index": ci,
            "claims": [
                {"agent": ev.get("source_agent", "unknown"), "claim": ev.get("claim", "")[:200]}
                for ev in cluster
            ],
        })

    prompt = _BATCH_CONFLICT_PROMPT.format(
        clusters_json=json.dumps(cluster_list, ensure_ascii=False)
    )

    conflicts: list[dict] = []
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        text = str(response.content) if hasattr(response, "content") else str(response)

        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        data = json.loads(text)
        conflict_entries = data.get("conflicts", [])

        for entry in conflict_entries:
            ci = entry.get("cluster_index", -1)
            if 0 <= ci < len(multi_agent_clusters):
                cluster = multi_agent_clusters[ci]
                conflicts.append({
                    "topic": cluster[0].get("claim", ""),
                    "positions": {
                        ev.get("source_agent", ""): ev.get("claim", "")
                        for ev in cluster
                    },
                    "severity": entry.get("severity", "minor"),
                })
    except json.JSONDecodeError:
        logger.warning("Conflict detection: failed to parse LLM response as JSON")
    except Exception:
        logger.warning("Conflict detection LLM call failed", exc_info=True)

    elapsed = time.perf_counter() - t0
    if conflicts:
        logger.info(
            "Conflict detection: %d conflicts in %d clusters (%.1fs)",
            len(conflicts), len(multi_agent_clusters), elapsed,
        )

    return conflicts
