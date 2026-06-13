# deepresearch/nodes/plan.py
import json
import logging
import re

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
        return ResearchPlan.model_validate(data).model_dump()
    except ValidationError as exc:
        logger.warning("Plan JSON failed schema validation: %s", exc)
        return None


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
        logger.info("Plan node: generating research plan for: %s", user_query)

        plan = _run_planner(user_query, llm)

        if plan is None:
            return {
                "status": "error",
                "errors": ["Plan generation failed: unable to parse LLM output as valid JSON."],
            }

        return {
            "research_plan": plan,
            "status": "planned",
        }

    return plan_node
