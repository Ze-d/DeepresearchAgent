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
