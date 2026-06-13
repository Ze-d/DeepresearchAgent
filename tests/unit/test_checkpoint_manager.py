from deepresearch.checkpoint.manager import CheckpointManager
from deepresearch.state import AgentState


def _make_state(**overrides) -> AgentState:
    state: AgentState = {
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
        "citations": [],
        "iteration_metrics": [],
        "checkpoint_ref": None,
    }
    state.update(overrides)
    return state


class TestCheckpointManager:
    def test_init_creates_db(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        assert cm.db_path.exists()
        assert cm.db_path.name == "checkpoint.db"

    def test_save_returns_checkpoint_id(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        state = _make_state(status="planned")
        cp_id = cm.save(state, "plan")
        assert cp_id is not None
        assert isinstance(cp_id, str)
        assert len(cp_id) > 0

    def test_list_checkpoints(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        cm.save(_make_state(status="planned"), "plan")
        cm.save(_make_state(status="researched"), "research")

        checkpoints = cm.list_checkpoints()
        assert len(checkpoints) >= 2

    def test_disabled_skips_save(self, tmp_path, monkeypatch):
        import deepresearch.checkpoint.manager as cm_mod
        monkeypatch.setattr(cm_mod.settings, "checkpoint_enabled", False)
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        state = _make_state()
        cp_id = cm.save(state, "plan")
        assert cp_id == ""

    def test_save_and_restore(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        state = _make_state(user_query="restore test", status="researched", iteration=1)
        cp_id = cm.save(state, "research")

        restored = cm.load(cp_id)
        assert restored is not None
        assert restored["user_query"] == "restore test"
        assert restored["status"] == "researched"
        assert restored["iteration"] == 1

    def test_load_nonexistent_returns_none(self, tmp_path):
        session_dir = tmp_path / "session_test"
        session_dir.mkdir()
        cm = CheckpointManager(session_dir)
        assert cm.load("nonexistent") is None
