# tests/unit/test_cli.py
from typer.testing import CliRunner
from tests.fixtures.mock_llm import FakeChatModel
from deepresearch.cli import app

runner = CliRunner()

PLAN_JSON = '{"research_goal":"test","sub_questions":[{"id":"q1","question":"q","priority":1,"search_queries":["q"]}],"expected_sections":[],"success_criteria":[]}'


def test_cli_help(monkeypatch):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "DeepResearch" in result.stdout


def test_cli_run_mock(monkeypatch):
    """用 FakeChatModel 跑 CLI，不依赖真实 API"""
    from deepresearch.tools import SearchResult

    # Mock search
    monkeypatch.setattr("deepresearch.nodes.research.search_web", lambda q, max_results: [SearchResult(title="T", url="https://x.com", snippet="S")])
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", lambda url, timeout=10.0: "content")
    # Mock LLM
    monkeypatch.setattr("deepresearch.graph.build_llm", lambda: FakeChatModel(default_response=PLAN_JSON))
    # Disable checkpoint to avoid SQLite cross-thread issues with CliRunner
    monkeypatch.setattr("deepresearch.checkpoint.manager.settings.checkpoint_enabled", False)

    result = runner.invoke(app, ["run", "测试问题", "--max-iterations", "1"])
    assert result.exit_code == 0
    assert "完成" in result.stdout or "研究报告" in result.stdout or "==" in result.stdout


def test_cli_run_with_iterations(monkeypatch):
    from deepresearch.tools import SearchResult
    monkeypatch.setattr("deepresearch.nodes.research.search_web", lambda q, max_results: [SearchResult(title="T", url="https://x.com", snippet="S")])
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", lambda url, timeout=10.0: "content")
    monkeypatch.setattr("deepresearch.graph.build_llm", lambda: FakeChatModel(default_response=PLAN_JSON))
    monkeypatch.setattr("deepresearch.checkpoint.manager.settings.checkpoint_enabled", False)

    result = runner.invoke(app, ["run", "测试问题", "--max-iterations", "1"])
    assert result.exit_code == 0


def test_cli_resume_invalid_dir():
    """resume 不存在的目录报错"""
    result = runner.invoke(app, ["resume", "outputs/nonexistent/"])
    assert result.exit_code == 1


def test_cli_checkpoints_empty(tmp_path):
    """空 session 目录的 checkpoints 输出"""
    session_dir = tmp_path / "empty_session"
    session_dir.mkdir()
    result = runner.invoke(app, ["checkpoints", str(session_dir)])
    assert result.exit_code == 0


def test_run_workflow_exists():
    """run_workflow 可从 CLI 模块导入"""
    from deepresearch.cli import run_workflow
    assert callable(run_workflow)


def test_run_workflow_returns_state(monkeypatch, tmp_path):
    """run_workflow 用 mock LLM + mock search 返回完整 state"""
    from deepresearch.cli import run_workflow
    from tests.fixtures.mock_llm import FakeChatModel
    from deepresearch.tools import SearchResult
    import json

    # Mock search
    def mock_search(query, max_results):
        return [SearchResult(title="T", url="https://example.com", snippet="S")]

    def mock_fetch(url, timeout=8.0):
        return "Test content for evidence extraction."

    monkeypatch.setattr("deepresearch.nodes.research.search_web", mock_search)
    monkeypatch.setattr("deepresearch.nodes.research.fetch_content", mock_fetch)

    # Disable checkpoint to avoid SQLite issues
    monkeypatch.setattr("deepresearch.checkpoint.manager.settings.checkpoint_enabled", False)

    # Redirect output to tmp_path
    from deepresearch.config import settings
    monkeypatch.setattr(settings, "output_dir", str(tmp_path / "outputs"))

    PLAN = json.dumps({
        "research_goal": "test",
        "sub_questions": [{"id": "q1", "question": "q", "priority": 1, "search_queries": ["q"]}],
        "expected_sections": ["s1"],
        "success_criteria": ["c1"],
    }, ensure_ascii=False)

    llm = FakeChatModel(default_response=PLAN)

    # Inject mock LLM into graph
    monkeypatch.setattr("deepresearch.graph.build_llm", lambda: llm)

    result = run_workflow("test query", max_iterations=1)
    assert result["user_query"] == "test query"
    assert result["status"] == "completed"
    assert result["final_report"] is not None
