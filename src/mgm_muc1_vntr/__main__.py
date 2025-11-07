"""Command-line interface for seqsensei2glims."""

import pathlib
import sys
from typing import Annotated, Literal

import typer
from loguru import logger

from mgm_muc1_vntr import __version__
from mgm_muc1_vntr.srs_analysis import Config as SrsConfig
from mgm_muc1_vntr.srs_analysis import (
    print_short_read_pileups,
    print_short_read_result,
    print_short_read_result_header,
    short_read_analysis,
)


def setup_loguru(verbose: int = 0):
    logger.remove()  # Remove default handler to reconfigure
    if verbose >= 2:
        level = "TRACE"
    elif verbose == 1:
        level = "DEBUG"
    elif verbose == -1:
        level = "WARNING"
    else:
        level = "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )


app = typer.Typer(
    name="mgm-muc1-vntr",
    help="SRS and LRS analysis for MUC1 VNTR",
    add_completion=False,
    no_args_is_help=True,
)


@app.command()
def run(
    short_read_bam: Annotated[pathlib.Path, typer.Option(help="Path to BAM file with SRS data")],
    short_read_reference: Annotated[
        pathlib.Path, typer.Option(help="Path to reference genome FASTA file for SRS data")
    ],
    short_read_release: Annotated[
        Literal["GRCh37", "GRCh38"], typer.Option(help="Genome release for SRS data")
    ] = "GRCh37",
    output_dir: Annotated[pathlib.Path, typer.Option(help="Output directory")] = pathlib.Path("."),
    min_support_var: Annotated[int, typer.Option(help="Minimum number of reads supporting a variant")] = 3,
    min_support_consensus: Annotated[int, typer.Option(help="Minimum number of reads supporting a consensus")] = 2,
    short_read_analysis_trim_flank: Annotated[int, typer.Option(help="Trim flank size for short read analysis")] = 150,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True)] = 0,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output")] = False,
    print_pileups: Annotated[bool, typer.Option(help="Print pileups")] = False,
    pileup_svg_path: Annotated[
        pathlib.Path | None, typer.Option(help="Path to write pileup visualization as SVG file")
    ] = None,
) -> None:
    """Run SRS (and optional LRS) analysis."""
    setup_loguru(verbose=-1 if quiet else verbose)

    logger.info("MGM-MUC1-VNTR startup")

    short_read_results = short_read_analysis(
        config=SrsConfig(
            input_bam=short_read_bam,
            genome_release=short_read_release,
            reference_genome=short_read_reference,
            output_dir=output_dir,
            min_support_var=min_support_var,
            min_support_consensus=min_support_consensus,
            trim_flank=short_read_analysis_trim_flank,
            pileup_svg_path=pileup_svg_path,
        )
    )

    for no, short_read_result in enumerate(short_read_results):
        if no == 0:
            print_short_read_result_header()
        print_short_read_result(
            short_read_result=short_read_result,
            min_support_consensus=min_support_consensus,
        )
        if print_pileups:
            print_short_read_pileups(short_read_result=short_read_result, min_support_consensus=min_support_consensus)

    logger.info("All done. Have a nice day!")


@app.command()
def version() -> None:
    """Show the version of mgm-muc1-vntr."""
    typer.echo(__version__)


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
