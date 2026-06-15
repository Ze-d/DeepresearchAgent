# tests/unit/test_human_review.py
import pytest
import inspect


def test_human_review_node_uses_interrupt():
    """human_review 节点函数调用 LangGraph interrupt()"""
    from deepresearch.nodes.human_review import make_human_review_node
    from tests.fixtures.mock_llm import FakeChatModel

    llm = FakeChatModel()
    node = make_human_review_node(llm)
    assert callable(node)

    source = inspect.getsource(node)
    assert "interrupt" in source, "human_review_node must call LangGraph interrupt()"


def test_human_review_node_skips_when_disabled(monkeypatch):
    """human_review 被禁用时不调用 interrupt，直接返回 approved"""
    from deepresearch.nodes.human_review import make_human_review_node
    from tests.fixtures.mock_llm import FakeChatModel

    monkeypatch.setattr("deepresearch.config.settings.human_review_enabled", False)

    llm = FakeChatModel()
    node = make_human_review_node(llm)

    state = {
        "user_query": "test", "research_plan": None,
        "search_results": [], "sources": [], "evidences": [],
        "draft_summary": None, "critique_result": None, "final_report": None,
        "iteration": 1, "max_iterations": 2, "status": "merged", "errors": [],
        "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
        "agent_outputs": [], "merge_summary": None, "human_review": None,
        "agent_profile": None, "sub_question": None,
    }

    result = node(state)
    assert result["human_review"]["action"] == "approved"
    assert "auto" in result["human_review"]["notes"]
