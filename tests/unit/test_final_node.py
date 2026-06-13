# tests/unit/test_final_node.py
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.nodes.final import make_final_node


def test_final_node_generates_report():
    llm = FakeChatModel(default_response="# 最终报告\n\n测试内容。")
    node = make_final_node(llm)

    state = {
        "user_query": "test",
        "research_plan": None,
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": "draft",
        "critique_result": {"pass": True, "score": 0.9, "issues": [], "new_search_queries": []},
        "final_report": None,
        "iteration": 1,
        "max_iterations": 2,
        "status": "critiqued",
        "errors": [],
    }

    result = node(state)
    assert result["final_report"] is not None
    assert "最终报告" in result["final_report"]
    assert result["status"] == "completed"
