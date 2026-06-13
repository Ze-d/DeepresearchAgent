import json
import logging
import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from deepresearch.state import AgentState
from deepresearch.config import settings

logger = logging.getLogger(__name__)


class CheckpointManager:
    """管理 LangGraph checkpoint 持久化和恢复。"""

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.db_path = session_dir / "checkpoint.db"
        self._saver: SqliteSaver | None = None
        # Ensure the db file exists on disk
        self.db_path.touch()

    @property
    def saver(self) -> SqliteSaver | None:
        if not settings.checkpoint_enabled:
            return None
        if self._saver is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._saver = SqliteSaver(conn)
        return self._saver

    def save(self, state: AgentState, step: str) -> str:
        """将当前 state 以 JSON 快照形式持久化。

        SqliteSaver 由 LangGraph 自动管理，此方法保存显式 JSON 快照副本。

        Returns:
            快照文件名（不带扩展名），用作 checkpoint ID。
        """
        if not settings.checkpoint_enabled:
            return ""

        ts = len(list(self.session_dir.glob("snapshot_*.json"))) + 1
        cp_id = f"snapshot_{ts:03d}"

        serializable = dict(state)
        safe: dict = {}
        for k, v in serializable.items():
            try:
                json.dumps(v, ensure_ascii=False, default=str)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = str(v)

        snapshot_path = self.session_dir / f"{cp_id}.json"
        snapshot_path.write_text(
            json.dumps(safe, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.debug("Checkpoint saved: %s (step=%s)", cp_id, step)
        return cp_id

    def load(self, checkpoint_id: str) -> AgentState | None:
        """从快照恢复 state。"""
        snapshot_path = self.session_dir / f"{checkpoint_id}.json"
        if not snapshot_path.exists():
            logger.warning("Checkpoint not found: %s", snapshot_path)
            return None

        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        logger.info("Checkpoint loaded: %s", checkpoint_id)
        return data  # type: ignore[return-value]

    def list_checkpoints(self) -> list[dict]:
        """列出所有 checkpoint 快照。"""
        snapshots = sorted(self.session_dir.glob("snapshot_*.json"))
        result = []
        for sp in snapshots:
            stat = sp.stat()
            result.append({
                "id": sp.stem,
                "path": str(sp),
                "size_bytes": stat.st_size,
                "created": stat.st_ctime,
            })
        return result
