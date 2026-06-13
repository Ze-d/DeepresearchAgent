# tests/unit/test_critique_node.py
import json
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.nodes.critique import make_critique_node


PASS_JSON = json.dumps({"pass": True, "score": 0.9, "issues": [], "new_search_queries": []})
FAIL_JSON = json.dumps({
    "pass": False,
    "score": 0.5,
    "issues": [{"type": "gap", "severity": "high", "description": "missing", "suggested_action": "search more"}],
    "new_search_queries": ["more search"],
})


def test_critique_node_pass():
    """critique pass=True 时不触发循环"""
    llm = FakeChatModel(default_response=PASS_JSON)
    node = make_critique_node(llm)

    state = {
        "user_query": "test",
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": "some draft",
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "summarized",
        "errors": [],
    }

    result = node(state)
    assert result["critique_result"]["pass"] is True
    assert result["iteration"] == 1


def test_critique_node_fail():
    """critique pass=False 时迭代+1"""
    llm = FakeChatModel(default_response=FAIL_JSON)
    node = make_critique_node(llm)

    state = {
        "user_query": "test",
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": "draft",
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "summarized",
        "errors": [],
    }

    result = node(state)
    assert result["critique_result"]["pass"] is False
    assert len(result["critique_result"]["issues"]) == 1
    assert len(result["critique_result"]["new_search_queries"]) == 1
    assert result["iteration"] == 1


def test_critique_node_handles_bad_json():
    """JSON 解析失败时默认 pass=True 避免死循环"""
    llm = FakeChatModel(default_response="not json at all")
    node = make_critique_node(llm)

    state = {
        "user_query": "test",
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": "draft",
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "summarized",
        "errors": [],
    }

    result = node(state)
    assert result["critique_result"]["pass"] is True
    assert result["status"] == "critiqued"
