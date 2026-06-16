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

    monkeypatch.setattr("deepresearch.tools.search_web", mock_search)
    monkeypatch.setattr("deepresearch.tools.fetch_content", mock_fetch)

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


def test_research_node_uses_critique_follow_up_queries(monkeypatch):
    """critique 失败重试时优先使用 critique 提供的补充查询。"""
    from deepresearch.tools import SearchResult

    searched_queries = []

    def mock_search(query, max_results):
        searched_queries.append(query)
        return [SearchResult(title="Follow-up", url="https://example.com", snippet="S")]

    monkeypatch.setattr("deepresearch.tools.search_web", mock_search)
    monkeypatch.setattr("deepresearch.tools.fetch_content", lambda url, timeout=10.0: "content")

    llm = FakeChatModel(default_response='{"evidences": []}')
    node = make_research_node(llm)

    state = {
        "user_query": "test",
        "research_plan": {
            "research_goal": "test",
            "sub_questions": [
                {
                    "id": "q1",
                    "question": "original question",
                    "priority": 1,
                    "search_queries": ["original query"],
                }
            ],
            "expected_sections": [],
            "success_criteria": [],
        },
        "search_results": [],
        "sources": [],
        "evidences": [],
        "draft_summary": "draft",
        "critique_result": {
            "pass": False,
            "score": 0.4,
            "issues": [],
            "new_search_queries": ["targeted follow-up"],
        },
        "final_report": None,
        "iteration": 1,
        "max_iterations": 2,
        "status": "critiqued",
        "errors": [],
    }

    node(state)

    assert searched_queries == ["targeted follow-up"]


def test_research_node_does_not_call_dedup(monkeypatch):
    """v2.1: research_node 不再调用 dedup — dedup 已移至 merge 节点统一处理"""
    def mock_search(query, max_results):
        from deepresearch.tools import SearchResult
        return [SearchResult(title="T", url="https://x.com", snippet="S")]

    def mock_fetch(url, timeout=10.0):
        return "content"

    monkeypatch.setattr("deepresearch.tools.search_web", mock_search)
    monkeypatch.setattr("deepresearch.tools.fetch_content", mock_fetch)

    dedup_called = []
    def mock_dedup(evidences, llm):
        dedup_called.append(True)
        return evidences

    monkeypatch.setattr("deepresearch.evidence.dedup.deduplicate_evidences", mock_dedup)

    evidence_json = '{"evidences": [{"claim": "test", "quote": "test", "confidence": 0.9}]}'
    from tests.fixtures.mock_llm import FakeChatModel
    llm = FakeChatModel(default_response=evidence_json)

    from deepresearch.nodes.research import make_research_node
    node = make_research_node(llm)

    state = {
        "user_query": "test",
        "research_plan": {
            "research_goal": "test",
            "sub_questions": [
                {"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}
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
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_ref": None,
    }

    node(state)
    assert len(dedup_called) == 0, "v2.1: research_node should NOT call dedup — merge handles it"


def test_research_node_calls_ranking(monkeypatch):
    """research_node 执行后调用 rank_sources"""
    def mock_search(query, max_results):
        return []

    def mock_fetch(url, timeout=10.0):
        return ""

    monkeypatch.setattr("deepresearch.tools.search_web", mock_search)
    monkeypatch.setattr("deepresearch.tools.fetch_content", mock_fetch)

    ranking_called = []
    def mock_ranking(sources):
        ranking_called.append(True)
        return sources

    monkeypatch.setattr("deepresearch.evidence.ranking.rank_sources", mock_ranking)

    from tests.fixtures.mock_llm import FakeChatModel
    llm = FakeChatModel(default_response='{"evidences":[]}')

    from deepresearch.nodes.research import make_research_node
    node = make_research_node(llm)

    state = {
        "user_query": "test",
        "research_plan": {
            "research_goal": "test",
            "sub_questions": [
                {"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}
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
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_ref": None,
    }

    node(state)
    assert len(ranking_called) > 0
