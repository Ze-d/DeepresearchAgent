"""Shared pytest fixtures for DeepResearch Agent tests."""
import sys
import os

# Ensure project root is on sys.path so tests/ is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── OTel isolation: block user .env from leaking OTEL_ENABLED=true into tests ──
# deepresearch/config.py uses load_dotenv(override=True) which overwrites
# os.environ with .env values. We reset these AFTER collection (when .env has
# already been loaded) so non-OTel tests never trigger tracing.
# OTel tests enable it per-test via monkeypatch.
os.environ.setdefault("OTEL_PYTHON_TRACER_PROVIDER", "sdk_tracer_provider")


def pytest_sessionstart(session):
    """Force-disable OTel for all tests after .env has been loaded."""
    os.environ["OTEL_ENABLED"] = "false"
    os.environ["OTEL_CONSOLE_EXPORT"] = "false"
    # Also mutate the already-created settings singleton
    try:
        from deepresearch.config import settings
        settings.otel_enabled = False
        settings.otel_console_export = False
    except Exception:
        pass
