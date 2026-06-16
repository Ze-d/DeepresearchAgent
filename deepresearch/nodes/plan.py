# deepresearch/nodes/plan.py
import json
import logging
import re
import time

from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError

from deepresearch.state import ResearchPlan
from deepresearch.state import AgentState
from deepresearch.prompts import build_planner_messages

logger = logging.getLogger(__name__)


def _parse_plan_json(raw: str) -> dict | None:
    """从 LLM 原始输出中解析 ResearchPlan JSON。

    兼容：
    - 纯 JSON
    - ```json ... ``` 包裹的 JSON
    """
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse plan JSON: %s", raw[:200])
        return None

    if not isinstance(data, dict):
        logger.warning("Plan JSON must be an object. Got: %s", type(data).__name__)
        return None

    required = {"research_goal", "sub_questions", "expected_sections", "success_criteria"}
    if not required.issubset(data.keys()):
        logger.warning("Plan JSON missing required fields. Got: %s", list(data.keys()))
        return None

    try:
        plan = ResearchPlan.model_validate(data).model_dump()
    except ValidationError as exc:
        logger.warning("Plan JSON failed schema validation: %s", exc)
        return None

    # Ensure every sub_question has source_types with valid fallback
    valid_types = {"paper", "github", "blog", "docs"}
    for sq in plan.get("sub_questions", []):
        if "source_types" not in sq:
            sq["source_types"] = ["blog"]
        sq["source_types"] = [t for t in sq["source_types"] if t in valid_types] or ["blog"]
    return plan


def _run_planner(user_query: str, llm: BaseChatModel, max_retries: int = 2) -> dict | None:
    """调用 LLM 生成 ResearchPlan，支持 JSON 解析失败重试。"""
    messages = build_planner_messages(user_query)

    for attempt in range(max_retries + 1):
        response = llm.invoke(messages)
        raw = str(response.content) if hasattr(response, "content") else str(response)

        plan = _parse_plan_json(raw)
        if plan is not None:
            return plan

        logger.warning("Plan JSON parse failed (attempt %d/%d)", attempt + 1, max_retries + 1)

    return None


def make_plan_node(llm: BaseChatModel):
    """创建 plan_node（闭包注入 LLM）。"""

    def plan_node(state: AgentState) -> dict:
        user_query = state["user_query"]
        t0 = time.perf_counter()
        logger.info("[plan] 开始: %s", user_query[:80])
        print("\n📋 Plan: 正在生成研究计划...")

        plan = _run_planner(user_query, llm)

        if plan is None:
            elapsed = time.perf_counter() - t0
            logger.error("[plan] 失败 (%.1fs)", elapsed)
            return {
                "status": "error",
                "errors": ["Plan generation failed: unable to parse LLM output as valid JSON."],
            }

        elapsed = time.perf_counter() - t0
        sq_count = len(plan.get("sub_questions", []))
        logger.info("[plan] 完成: %d 个子问题 (%.1fs)", sq_count, elapsed)
        print(f"📋 Plan: 完成 → {sq_count} 个子问题, {plan.get('expected_sections', [])}")

        return {
            "research_plan": plan,
            "status": "planned",
        }

    return plan_node
