# tests/unit/test_plan_node.py
import json
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.nodes.plan import _parse_plan_json, _run_planner, make_plan_node


PLAN_JSON = json.dumps({
    "research_goal": "调研 Deep Research Agent",
    "sub_questions": [
        {
            "id": "q1",
            "question": "主流架构有哪些?",
            "priority": 1,
            "search_queries": ["architecture survey"],
        },
    ],
    "expected_sections": ["架构", "项目"],
    "success_criteria": ["覆盖 2 种架构"],
}, ensure_ascii=False)


class TestParsePlanJson:
    def test_parse_valid_json(self):
        result = _parse_plan_json(PLAN_JSON)
        assert result["research_goal"] == "调研 Deep Research Agent"
        assert len(result["sub_questions"]) == 1

    def test_parse_json_with_markdown_fence(self):
        raw = f"```json\n{PLAN_JSON}\n```"
        result = _parse_plan_json(raw)
        assert result["research_goal"] == "调研 Deep Research Agent"

    def test_parse_invalid_json_returns_none(self):
        result = _parse_plan_json("not json at all")
        assert result is None

    def test_parse_missing_field_returns_none(self):
        result = _parse_plan_json('{"research_goal": "only goal"}')
        assert result is None

    def test_parse_non_object_json_returns_none(self):
        result = _parse_plan_json('["not", "an", "object"]')
        assert result is None

    def test_parse_invalid_schema_returns_none(self):
        result = _parse_plan_json(json.dumps({
            "research_goal": "bad shape",
            "sub_questions": "not a list",
            "expected_sections": [],
            "success_criteria": [],
        }))
        assert result is None


class TestRunPlanner:
    def test_run_planner_success(self):
        """LLM 返回合法 JSON 时成功解析"""
        llm = FakeChatModel(default_response=PLAN_JSON)
        result = _run_planner("测试问题", llm)
        assert result is not None
        assert result["research_goal"] == "调研 Deep Research Agent"

    def test_run_planner_retry_on_bad_json(self):
        """第一次返回非法 JSON，第二次返回合法时重试成功"""
        call_count = [0]
        responses = ["bad json!!", PLAN_JSON]
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatResult, ChatGeneration

        class RetryLLM(FakeChatModel):
            def _generate(self, messages, **kwargs):
                idx = call_count[0]
                call_count[0] += 1
                text = responses[min(idx, len(responses) - 1)]
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

        llm = RetryLLM(response_map={})
        result = _run_planner("test", llm, max_retries=1)
        assert result is not None
        assert result["research_goal"] == "调研 Deep Research Agent"

    def test_run_planner_all_retries_fail(self):
        """所有重试都失败时返回 None"""
        llm = FakeChatModel(default_response="garbage")
        result = _run_planner("test", llm, max_retries=0)
        assert result is None


class TestPlanNode:
    def test_plan_node_updates_state(self):
        """plan_node 正确更新 state"""
        llm = FakeChatModel(default_response=PLAN_JSON)
        node = make_plan_node(llm)

        state = {
            "user_query": "测试",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "initialized",
            "errors": [],
        }

        result = node(state)
        assert result["research_plan"] is not None
        assert result["status"] == "planned"

    def test_plan_node_handles_llm_failure(self):
        """LLM 完全失败时状态标记 error"""
        llm = FakeChatModel(default_response="garbage")
        node = make_plan_node(llm)

        state = {
            "user_query": "测试",
            "research_plan": None,
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": None,
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "initialized",
            "errors": [],
        }

        result = node(state)
        assert result["status"] == "error"
        assert len(result["errors"]) > 0
