# tests/unit/test_summary_node.py
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.nodes.summary import make_summary_node


def test_summary_node_generates_draft():
    llm = FakeChatModel(default_response="## 阶段总结\n\n测试内容。")
    node = make_summary_node(llm)

    state = {
        "user_query": "test",
        "research_plan": {"research_goal": "test", "sub_questions": [], "expected_sections": [], "success_criteria": []},
        "search_results": [],
        "sources": [],
        "evidences": [{"claim": "test"}],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "researched",
        "errors": [],
    }

    result = node(state)
    assert result["draft_summary"] is not None
    assert "阶段总结" in result["draft_summary"]
    assert result["status"] == "summarized"


def test_summary_node_handles_no_evidences():
    llm = FakeChatModel(default_response="无证据可用。")
    node = make_summary_node(llm)

    state = {
        "user_query": "test",
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "researched",
        "errors": [],
    }

    result = node(state)
    assert result["draft_summary"] is not None
    assert result["status"] == "summarized"
