"""Command-line interface for DeepResearch Agent."""

import typer

app = typer.Typer(help="DeepResearch Agent command-line interface.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run the DeepResearch Agent CLI."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
