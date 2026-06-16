"""Shared pytest fixtures for DeepResearch Agent tests."""
import sys
import os

# Ensure project root is on sys.path so tests/ is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Allow OTel tests to replace the global TracerProvider
os.environ.setdefault("OTEL_PYTHON_TRACER_PROVIDER", "sdk_tracer_provider")
