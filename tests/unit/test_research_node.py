# tests/unit/test_research_node.py
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.nodes.research import make_research_node


def test_research_node_with_mock_search(monkeypatch):
    """research_node 在有搜索结果时返回 sources 和 evidences"""
    from deepresearch.tools import SearchResult

    def mock_search(query, max_results):
        return [SearchResult(
            title="Test Page",
            url="https://example.com",
            snippet="A snippet about deep research.",
        )]

    def mock_fetch(url, timeout=10.0):
        return "Deep research agents use multi-step workflows."

    monkeypatch.setattr("deepresearch.nodes.research.search_web", mock_search)
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", mock_fetch)

    evidence_json = '{"evidences": [{"claim": "test claim", "quote": "test quote", "confidence": 0.9}]}'
    llm = FakeChatModel(default_response=evidence_json)

    node = make_research_node(llm)

    state = {
        "user_query": "test",
        "research_plan": {
            "research_goal": "test",
            "sub_questions": [
                {
                    "id": "q1",
                    "question": "test question",
                    "priority": 1,
                    "search_queries": ["test query"],
                }
            ],
            "expected_sections": [],
            "success_criteria": [],
        },
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": None,
        "critique_result": None,
        "final_report": None,
        "iteration": 0,
        "max_iterations": 2,
        "status": "planned",
        "errors": [],
    }

    result = node(state)
    assert len(result["sources"]) > 0
    assert len(result["evidences"]) > 0
    assert result["status"] == "researched"


def test_research_node_handles_no_plan():
    """没有 research_plan 时不报错"""
    llm = FakeChatModel()
    node = make_research_node(llm)

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
        "status": "initialized",
        "errors": [],
    }

    result = node(state)
    assert result["status"] == "error"
    assert len(result["errors"]) > 0
