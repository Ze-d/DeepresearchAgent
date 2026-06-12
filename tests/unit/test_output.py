# tests/unit/test_output.py
import json
from deepresearch.output import init_session_dir, save_json, save_markdown, save_all


def test_init_session_dir_creates_directory(monkeypatch, tmp_path):
    monkeypatch.setattr("deepresearch.output.settings.output_dir", str(tmp_path))
    session_dir = init_session_dir()
    assert session_dir.exists()
    assert session_dir.name.startswith("session_")


def test_save_json(tmp_path):
    path = tmp_path / "test.json"
    save_json({"key": "value"}, path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["key"] == "value"


def test_save_markdown(tmp_path):
    path = tmp_path / "test.md"
    save_markdown("# Title\n\ncontent", path)
    assert path.exists()
    assert "# Title" in path.read_text(encoding="utf-8")


def test_save_all(monkeypatch, tmp_path):
    monkeypatch.setattr("deepresearch.output.settings.output_dir", str(tmp_path))
    session_dir = init_session_dir()

    state = {
        "user_query": "test",
        "research_plan": {"research_goal": "goal"},
        "search_results": [{"q": "test"}],
        "sources": [{"id": "s1", "title": "T", "url": "https://x.com"}],
        "evidences": [{"id": "e1", "claim": "c"}],
        "draft_summary": "## Draft",
        "critique_result": {"pass": True, "score": 0.9, "issues": [], "new_search_queries": []},
        "final_report": "# Final Report",
        "iteration": 1,
        "max_iterations": 2,
        "status": "completed",
        "errors": [],
    }

    save_all(state, session_dir)

    assert (session_dir / "plan.json").exists()
    assert (session_dir / "search_results.json").exists()
    assert (session_dir / "sources.json").exists()
    assert (session_dir / "evidences.json").exists()
    assert (session_dir / "draft_summary.md").exists()
    assert (session_dir / "critique.json").exists()
    assert (session_dir / "final_report.md").exists()
