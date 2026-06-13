# tests/integration/test_workflow.py
"""Integration tests for the full DeepResearch Agent workflow.

Uses SmartFakeLLM to simulate per-node LLM responses and monkeypatch
to replace network-bound search/fetch calls so the entire graph can
execute deterministically without external dependencies.
"""

from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.graph import build_graph
from deepresearch.state import AgentState

# ── Fake LLM responses matching each node's prompt tag ──────────────

PLAN_JSON = (
    '{"research_goal":"test",'
    '"sub_questions":[{"id":"q1","question":"q","priority":1,"search_queries":["q"]}],'
    '"expected_sections":[],"success_criteria":[]}'
)
EVIDENCE_JSON = '{"evidences":[]}'
CRITIQUE_PASS = (
    '{"pass":true,"score":0.9,"issues":[],"new_search_queries":[]}'
)
CRITIQUE_FAIL = (
    '{"pass":false,"score":0.4,'
    '"issues":[{"type":"gap","severity":"high","description":"missing","suggested_action":"search"}],'
    '"new_search_queries":["more"]}'
)
SUMMARY = "## 阶段总结\n\n测试内容"
FINAL_REPORT = "# 最终报告\n\n测试完成"


class SmartFakeLLM(FakeChatModel):
    """根据 prompt 内容返回不同响应的 Fake LLM。"""

    def _generate(self, messages, stop=None, **kwargs):
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatResult, ChatGeneration

        content = str(messages[0].content) if messages else ""

        if "研究规划 Agent" in content:
            text = PLAN_JSON
        elif "研究资料分析 Agent" in content:
            text = EVIDENCE_JSON
        elif "研究总结 Agent" in content:
            text = SUMMARY
        elif "研究审稿 Agent" in content:
            text = CRITIQUE_PASS
        elif "技术报告写作 Agent" in content:
            text = FINAL_REPORT
        else:
            text = '{"status": "ok"}'

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


# ── Shared initial state ────────────────────────────────────────────

_BASE_STATE: AgentState = {
    "user_query": "测试问题",
    "research_plan": None,
    "search_results": [],
    "sources": [],
    "evidences": [],
    "draft_summary": None,
    "critique_result": None,
    "final_report": None,
    "iteration": 0,
    "max_iterations": 1,
    "status": "initialized",
    "errors": [],
    # v1 初始值
    "citations": [],
    "iteration_metrics": [],
    "checkpoint_ref": None,
}


def _mock_search(monkeypatch):
    """Replace network-dependent search/fetch with trivial stubs."""
    from deepresearch.tools import SearchResult

    monkeypatch.setattr(
        "deepresearch.nodes.research.search_web",
        lambda q, max_results: [SearchResult(title="T", url="https://x.com", snippet="S")],
    )
    monkeypatch.setattr(
        "deepresearch.nodes.research.fetch_content",
        lambda url, timeout=10.0: "content",
    )


def _build_compiled_graph():
    """Create and compile a graph wired to SmartFakeLLM."""
    llm = SmartFakeLLM()
    graph = build_graph(llm=llm)
    return graph.compile()


# ── Tests ───────────────────────────────────────────────────────────


def test_full_workflow_with_mock(monkeypatch):
    """Mock LLM + Mock 搜索 → 全流程跑通"""
    _mock_search(monkeypatch)
    app = _build_compiled_graph()

    result = app.invoke(dict(_BASE_STATE))

    # 验证完整流程走完
    assert result["final_report"] is not None
    assert "最终报告" in result["final_report"]
    assert result["research_plan"] is not None
    assert result["status"] == "completed"
    # v1 状态验证
    assert "citations" in result
    assert "iteration_metrics" in result


def test_workflow_output_files(monkeypatch, tmp_path):
    """验证 intermediate artifacts 保存到 session 目录"""
    _mock_search(monkeypatch)
    app = _build_compiled_graph()

    import deepresearch.output

    monkeypatch.setattr(deepresearch.output.settings, "output_dir", str(tmp_path))

    result = app.invoke(dict(_BASE_STATE))

    session_dir = deepresearch.output.init_session_dir()
    deepresearch.output.save_all(result, session_dir)

    assert (session_dir / "plan.json").exists()
    assert (session_dir / "final_report.md").exists()
    content = (session_dir / "final_report.md").read_text(encoding="utf-8")
    assert "最终报告" in content


def test_workflow_iteration_cap(monkeypatch):
    """max_iterations=1 时即使 critique fail 也不死循环"""
    _mock_search(monkeypatch)

    # 使用一直返回 fail 的 LLM
    class AlwaysFailLLM(SmartFakeLLM):
        def _generate(self, messages, stop=None, **kwargs):
            from langchain_core.messages import AIMessage
            from langchain_core.outputs import ChatResult, ChatGeneration

            content = str(messages[0].content) if messages else ""

            if "研究规划 Agent" in content:
                text = PLAN_JSON
            elif "研究审稿 Agent" in content:
                text = CRITIQUE_FAIL  # always fail
            elif "技术报告写作 Agent" in content:
                text = FINAL_REPORT
            else:
                text = SUMMARY
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    llm = AlwaysFailLLM()
    graph = build_graph(llm=llm)
    app = graph.compile()

    initial_state: AgentState = dict(_BASE_STATE)
    initial_state["user_query"] = "test"

    result = app.invoke(initial_state)

    # 即使 critique 一直 fail，max_iterations=1 也应强制走到 final
    assert result["final_report"] is not None
    assert result["iteration"] <= result["max_iterations"]
