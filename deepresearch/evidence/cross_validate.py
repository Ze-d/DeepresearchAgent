"""交叉验证与冲突检测模块。

提供两个函数：
- cross_validate_evidences: 跨 Agent 交叉验证，聚类相似 claim 并提升 confidence
- detect_conflicts: 检测同一 cluster 内不同 Agent 的矛盾
"""
import json
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

logger = logging.getLogger(__name__)

_CROSS_VALIDATE_PROMPT = """你是一个事实交叉验证助手。判断以下两条 evidence 是否表达相同的核心信息。

Evidence A:
claim: "{claim_a}"
quote: "{quote_a}"

Evidence B:
claim: "{claim_b}"
quote: "{quote_b}"

只回答 YES 或 NO。如果两条 evidence 的核心信息一致（即使措辞不同），回答 YES。"""

_CONFLICT_DETECT_PROMPT = """你是一个矛盾检测助手。以下是一组来自不同来源的 evidence，判断它们之间是否存在矛盾。

Claims:
{claims_text}

请分析这些 claim 之间是否存在矛盾。只返回 JSON 格式：
{{"conflict": true/false, "severity": "major"/"minor"/"none"}}

- conflict: 是否存在矛盾
- severity: major（根本性矛盾）, minor（轻微不一致）, none（无矛盾）"""

_MAX_CONFIDENCE_BOOST = 0.2
_BOOST_PER_AGENT = 0.05
_MAX_CONFIDENCE = 1.0


def _are_same_claim(ev_a: dict, ev_b: dict, llm: BaseChatModel) -> bool:
    """用 LLM 判断两条 evidence 是否表达相同的核心信息。"""
    prompt = _CROSS_VALIDATE_PROMPT.format(
        claim_a=ev_a.get("claim", ""),
        quote_a=ev_a.get("quote", ""),
        claim_b=ev_b.get("claim", ""),
        quote_b=ev_b.get("quote", ""),
    )
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        text = str(response.content).strip().upper() if hasattr(response, "content") else ""
        return "YES" in text
    except Exception:
        logger.warning("Cross-validate LLM call failed, treating as different claims", exc_info=True)
        return False


def _cluster_evidences(evidences: list[dict], llm: BaseChatModel) -> list[list[dict]]:
    """将语义相同的 evidence 聚类。O(n²) 逐对比较。"""
    clusters: list[list[dict]] = []
    assigned: set[str] = set()

    for i, ev_a in enumerate(evidences):
        if ev_a["id"] in assigned:
            continue
        cluster = [ev_a]
        assigned.add(ev_a["id"])
        for ev_b in evidences[i + 1:]:
            if ev_b["id"] in assigned:
                continue
            if _are_same_claim(ev_a, ev_b, llm):
                cluster.append(ev_b)
                assigned.add(ev_b["id"])
        clusters.append(cluster)

    return clusters


def cross_validate_evidences(evidences: list[dict], llm: BaseChatModel) -> list[dict]:
    """交叉验证入口：聚类 -> 跨 Agent 验证 -> 更新 confidence 和标记。

    对每个语义 cluster：
    - 若包含 >= 2 个不同 Agent：按 Agent 数量提升 confidence（每个 Agent +0.05，最多 +0.2），
      标记 cross_validated=True，记录 confirming_agents
    - 若仅有 1 个 Agent：标记 cross_validated=False, source_bias=True

    Args:
        evidences: evidence 字典列表，每项须包含 id, claim, source_agent, source_id
        llm: 用于判断的 LLM 实例

    Returns:
        更新后的 evidence 列表（原位修改，原顺序不变）
    """
    if not evidences:
        return []

    # 少于 2 条时无法交叉验证
    if len(evidences) < 2:
        for ev in evidences:
            ev["cross_validated"] = False
            ev["source_bias"] = True
        return evidences

    clusters = _cluster_evidences(evidences, llm)

    for cluster in clusters:
        agents = {ev.get("source_agent", "") for ev in cluster if ev.get("source_agent")}
        if len(agents) >= 2:
            boost = min(_BOOST_PER_AGENT * len(agents), _MAX_CONFIDENCE_BOOST)
            for ev in cluster:
                ev["confidence"] = min(ev.get("confidence", 0) + boost, _MAX_CONFIDENCE)
                ev["cross_validated"] = True
                ev["confirming_agents"] = sorted(agents)
        else:
            for ev in cluster:
                ev["cross_validated"] = False
                ev["source_bias"] = True

    return evidences


def detect_conflicts(clusters: list[list[dict]], llm: BaseChatModel) -> list[dict]:
    """冲突检测入口：对包含 >= 2 个不同 Agent 的 cluster 做矛盾分析。

    每个符合条件的 cluster 调用 LLM 判断 claim 间是否存在矛盾，
    解析 JSON 裁决 `{{"conflict": bool, "severity": "major"/"minor"/"none"}}`。

    Args:
        clusters: 聚类后的 evidence 分组列表
        llm: 用于判断的 LLM 实例

    Returns:
        冲突列表，每项包含:
        - topic: 代表该 cluster 的 claim
        - positions: dict[source_agent -> claim]
        - severity: "major" | "minor"
    """
    conflicts: list[dict] = []

    for cluster in clusters:
        agents = {ev.get("source_agent", "") for ev in cluster if ev.get("source_agent")}
        if len(agents) < 2:
            continue

        claims_text = "\n".join(
            f"- [{ev.get('source_agent', 'unknown')}]: {ev.get('claim', '')}"
            for ev in cluster
        )
        prompt = _CONFLICT_DETECT_PROMPT.format(claims_text=claims_text)

        try:
            response = llm.invoke([SystemMessage(content=prompt)])
            text = str(response.content).strip() if hasattr(response, "content") else ""
            if not text:
                logger.warning("Conflict detection LLM returned empty response, skipping cluster")
                continue
            verdict = json.loads(text)
            if verdict.get("conflict") and verdict.get("severity", "none") != "none":
                conflicts.append({
                    "topic": cluster[0].get("claim", ""),
                    "positions": {ev.get("source_agent", ""): ev.get("claim", "") for ev in cluster},
                    "severity": verdict["severity"],
                })
        except json.JSONDecodeError:
            logger.warning("Conflict detection: failed to parse LLM response as JSON: %s", text)
            continue
        except Exception:
            logger.warning("Conflict detection LLM call failed for cluster", exc_info=True)
            continue

    return conflicts
