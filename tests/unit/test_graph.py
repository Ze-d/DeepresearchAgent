# tests/unit/test_graph.py
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.graph import build_graph, route_after_critique, route_after_plan
from deepresearch.state import AgentState

PLAN_JSON = '{"research_goal":"test","sub_questions":[{"id":"q1","question":"q","priority":1,"search_queries":["q"]}],"expected_sections":[],"success_criteria":[]}'


def test_graph_compiles():
    llm = FakeChatModel(default_response=PLAN_JSON)
    graph = build_graph(llm=llm)
    app = graph.compile()
    assert app is not None


def test_graph_nodes_registered():
    llm = FakeChatModel(default_response=PLAN_JSON)
    graph = build_graph(llm=llm)
    node_names = set(graph.nodes.keys())
    assert node_names == {"plan", "research_agent", "merge", "human_review", "summary", "critique", "final"}


def test_graph_run_mock_full_flow():
    from deepresearch.tools import SearchResult

    llm = FakeChatModel(default_response=PLAN_JSON)
    graph = build_graph(llm=llm)
    app = graph.compile()

    # Need to mock search to avoid real network calls
    import deepresearch.nodes.research_agent as ra_mod
    ra_mod.search_web = lambda q, max_results=5, **kw: [SearchResult(title="T", url="https://x.com", snippet="S")]
    ra_mod.fetch_content = lambda url, **kw: "content"

    initial_state: AgentState = {
        "user_query": "测试问题",
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
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_ref": None,
        "agent_outputs": [],
        "merge_summary": None,
        "human_review": None,
        "agent_profile": None,
        "sub_question": None,
    }

    result = app.invoke(initial_state)

    assert result["final_report"] is not None
    assert result["status"] == "completed"


def test_graph_stops_when_planning_fails():
    llm = FakeChatModel(default_response="not json")
    graph = build_graph(llm=llm)
    app = graph.compile()

    initial_state: AgentState = {
        "user_query": "测试问题",
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
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_ref": None,
        "agent_outputs": [],
        "merge_summary": None,
        "human_review": None,
        "agent_profile": None,
        "sub_question": None,
    }

    result = app.invoke(initial_state)

    assert result["status"] == "error"
    assert result["final_report"] is None
    assert result["research_plan"] is None


def test_graph_routes_to_end_when_plan_errors():
    state_error: AgentState = {
        "user_query": "test", "research_plan": None, "search_results": [],
        "sources": [], "evidences": [], "draft_summary": None,
        "critique_result": None, "final_report": None, "iteration": 0,
        "max_iterations": 2, "status": "error", "errors": ["bad plan"],
    }
    assert route_after_plan(state_error) == "end"


def test_build_graph_has_v2_1_nodes():
    """v2.1 graph 包含 research_agent 和 merge，不含 research"""
    from deepresearch.graph import build_graph
    from tests.fixtures.mock_llm import FakeChatModel
    llm = FakeChatModel()
    graph = build_graph(llm=llm)
    node_names = list(graph.nodes.keys())
    assert "research_agent" in node_names
    assert "merge" in node_names
    assert "research" not in node_names


def test_fanout_creates_sends():
    """fanout_to_agents 根据 source_types 创建 Send"""
    from deepresearch.graph import fanout_to_agents
    from langgraph.types import Send
    state: AgentState = {
        "user_query": "test", "research_plan": {
            "research_goal": "test",
            "sub_questions": [
                {"id": "q1", "question": "q", "priority": 1,
                 "search_queries": ["q"], "source_types": ["paper", "blog"]},
            ],
            "expected_sections": [], "success_criteria": [],
        },
        "search_results": [], "sources": [], "evidences": [],
        "draft_summary": None, "critique_result": None, "final_report": None,
        "iteration": 0, "max_iterations": 2, "status": "planned", "errors": [],
        "citations": [], "iteration_metrics": [], "checkpoint_ref": None,
        "agent_outputs": [], "merge_summary": None, "human_review": None,
        "agent_profile": None, "sub_question": None,
    }
    sends = fanout_to_agents(state)
    assert len(sends) == 2, f"Expected 2 Sends (paper+blog), got {len(sends)}"
    assert all(isinstance(s, Send) for s in sends)


# Keep the route tests (they don't need llm)
def test_graph_conditional_route_to_final_when_critique_passes():
    state_pass: AgentState = {
        "user_query": "test", "research_plan": None, "search_results": [],
        "sources": [], "evidences": [], "draft_summary": None,
        "critique_result": {"pass": True, "score": 0.9, "issues": [], "new_search_queries": []},
        "final_report": None, "iteration": 0, "max_iterations": 2,
        "status": "running", "errors": [],
    }
    assert route_after_critique(state_pass) == "final"


def test_graph_conditional_route_to_research_when_critique_fails():
    state_fail: AgentState = {
        "user_query": "test", "research_plan": None, "search_results": [],
        "sources": [], "evidences": [], "draft_summary": None,
        "critique_result": {"pass": False, "score": 0.4, "issues": [], "new_search_queries": ["more"]},
        "final_report": None, "iteration": 0, "max_iterations": 2,
        "status": "running", "errors": [],
    }
    assert route_after_critique(state_fail) == "research_agent"


def test_graph_conditional_route_exceeds_max_iterations():
    state_max: AgentState = {
        "user_query": "test", "research_plan": None, "search_results": [],
        "sources": [], "evidences": [], "draft_summary": None,
        "critique_result": {"pass": False, "score": 0.4, "issues": [], "new_search_queries": []},
        "final_report": None, "iteration": 2, "max_iterations": 2,
        "status": "running", "errors": [],
    }
    assert route_after_critique(state_max) == "final"


def test_graph_compiles_with_checkpointer():
    """Graph 可以编译为带 checkpointer 的 app"""
    from deepresearch.checkpoint.manager import CheckpointManager
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        session_dir = Path(tmp) / "test_session"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)

        llm = FakeChatModel(default_response='{"research_goal":"test","sub_questions":[],"expected_sections":[],"success_criteria":[]}')
        graph = build_graph(llm=llm)
        app = graph.compile(checkpointer=cm.saver)
        assert app is not None
        # Close SQLite connection to release Windows file lock
        if cm._saver is not None:
            cm._saver.conn.close()
