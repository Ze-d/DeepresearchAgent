"""Tests for the DeepResearch Agent command-line interface."""

from typer.testing import CliRunner

from deepresearch.cli import app


def test_cli_help_succeeds() -> None:
    """The packaged CLI entry point should expose a working help command."""
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "DeepResearch Agent" in result.output
