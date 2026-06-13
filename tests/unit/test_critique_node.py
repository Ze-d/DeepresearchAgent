# tests/unit/test_critique_node.py
import json
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.nodes.critique import make_critique_node, compute_fix_rate

CRITIQUE_PASS = json.dumps({
    "pass": True, "overall_score": 0.85,
    "dimensions": {
        "fact_check": {"score": 0.9, "issues": [], "status": "pass"},
        "logic_coherence": {"score": 0.85, "issues": [], "status": "pass"},
        "coverage": {"score": 0.8, "issues": [], "status": "pass"},
    },
    "issues": [],
    "new_search_queries": [],
}, ensure_ascii=False)

CRITIQUE_FAIL = json.dumps({
    "pass": False, "overall_score": 0.55,
    "dimensions": {
        "fact_check": {"score": 0.8, "issues": [], "status": "pass"},
        "logic_coherence": {"score": 0.5, "issues": ["矛盾"], "status": "fail"},
        "coverage": {"score": 0.4, "issues": ["遗漏"], "status": "fail"},
    },
    "issues": [{"type": "insufficient_evidence", "severity": "high", "description": "缺少引用", "suggested_action": "补充来源"}],
    "new_search_queries": ["more search"],
}, ensure_ascii=False)


class TestComputeFixRate:
    def test_first_iteration_none(self):
        assert compute_fix_rate(None, 3, 0) is None

    def test_all_fixed(self):
        assert compute_fix_rate(3, 0, 1) == 1.0

    def test_partial_fix(self):
        assert compute_fix_rate(3, 1, 1) == 0.67

    def test_none_fixed(self):
        assert compute_fix_rate(3, 3, 1) == 0.0


class TestCritiqueNode:
    def _make_state(self, **overrides):
        state = {
            "user_query": "test",
            "research_plan": {"research_goal": "test", "sub_questions": [], "expected_sections": [], "success_criteria": []},
            "search_results": [],
            "sources": [],
            "evidences": [],
            "draft_summary": "draft content",
            "critique_result": None,
            "final_report": None,
            "iteration": 0,
            "max_iterations": 2,
            "status": "summarized",
            "errors": [],
            "citations": [],
            "iteration_metrics": [],
            "checkpoint_ref": None,
        }
        state.update(overrides)
        return state

    def test_critique_pass(self):
        llm = FakeChatModel(default_response=CRITIQUE_PASS)
        node = make_critique_node(llm)
        result = node(self._make_state())
        assert result["critique_result"]["pass"] is True
        assert result["critique_result"]["overall_score"] == 0.85
        assert len(result["iteration_metrics"]) == 1
        assert result["iteration_metrics"][0]["fix_rate"] is None
        assert result["iteration_metrics"][0]["iteration"] == 1

    def test_critique_fail(self):
        llm = FakeChatModel(default_response=CRITIQUE_FAIL)
        node = make_critique_node(llm)
        result = node(self._make_state())
        assert result["critique_result"]["pass"] is False
        assert result["iteration"] == 1

    def test_critique_json_fallback(self):
        llm = FakeChatModel(default_response="not valid json at all")
        node = make_critique_node(llm)
        result = node(self._make_state())
        assert result["critique_result"]["pass"] is True

    def test_fix_rate_second_iteration(self):
        llm = FakeChatModel(default_response=CRITIQUE_PASS)
        node = make_critique_node(llm)
        state = self._make_state(
            iteration=0,
            iteration_metrics=[{
                "iteration": 1, "overall_score": 0.55,
                "dimensions": {}, "issues_count": 3,
                "fix_rate": None, "tokens_used": 0, "latency_ms": 0,
            }],
        )
        result = node(state)
        assert len(result["iteration_metrics"]) == 2
        assert result["iteration_metrics"][1]["fix_rate"] == 1.0
