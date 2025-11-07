"""Command-line interface for seqsensei2glims."""

import typer

from mgm_muc1_vntr import __version__

app = typer.Typer(
    name="mgm-muc1-vntr",
    help="SRS and LRS analysis for MUC1 VNTR",
    add_completion=False,
    no_args_is_help=True,
)


@app.command()
def run() -> None:
    """Run SRS (and optional LRS) analysis."""
    typer.echo("Not implemented yet.")


@app.command()
def version() -> None:
    """Show the version of mgm-muc1-vntr."""
    typer.echo(__version__)


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
