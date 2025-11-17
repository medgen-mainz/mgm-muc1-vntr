"""Command-line interface for seqsensei2glims."""

import pathlib
import sys
from typing import Annotated, Literal

import typer
from loguru import logger

from mainz_muc1_vntr import __version__
from mainz_muc1_vntr.lrs_analysis import Config as LrsConfig
from mainz_muc1_vntr.lrs_analysis import (
    long_read_analysis,
    print_long_read_details,
    print_long_read_result,
    print_long_read_result_header,
)
from mainz_muc1_vntr.srs_analysis import Config as SrsConfig
from mainz_muc1_vntr.srs_analysis import (
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
    name="mainz-muc1-vntr",
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
    long_read_bam: Annotated[
        pathlib.Path | None, typer.Option(help="Path to BAM file with LRS data (optional)")
    ] = None,
    long_read_reference: Annotated[
        pathlib.Path | None, typer.Option(help="Path to reference genome FASTA file for LRS data (optional)")
    ] = None,
    long_read_release: Annotated[
        Literal["GRCh37", "GRCh38"], typer.Option(help="Genome release for LRS data")
    ] = "GRCh38",
    long_read_analysis_trim_flank: Annotated[int, typer.Option(help="Trim flank size for long read analysis")] = 100,
    long_read_anchor_length: Annotated[int, typer.Option(help="Required anchor length for spanning reads")] = 50,
    output_dir: Annotated[pathlib.Path, typer.Option(help="Output directory")] = pathlib.Path("."),
    min_support_var: Annotated[int, typer.Option(help="Minimum number of reads supporting a variant")] = 3,
    min_support_consensus: Annotated[int, typer.Option(help="Minimum number of reads supporting a consensus")] = 2,
    short_read_analysis_trim_flank: Annotated[int, typer.Option(help="Trim flank size for short read analysis")] = 150,
    verbose: Annotated[int, typer.Option("--verbose", "-v", count=True)] = 0,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress output")] = False,
    print_pileups: Annotated[bool, typer.Option(help="Print pileups")] = False,
    print_details: Annotated[bool, typer.Option(help="Print detailed analysis results")] = False,
    pileup_svg_path: Annotated[
        pathlib.Path | None, typer.Option(help="Path to write pileup visualization as SVG file")
    ] = None,
) -> None:
    """Run SRS (and optional LRS) analysis."""
    setup_loguru(verbose=-1 if quiet else verbose)

    logger.info("Mainz-MUC1-VNTR startup")

    # Validate long read parameters if provided
    if long_read_bam and not long_read_reference:
        typer.echo("Error: Long read reference FASTA is required when long read BAM is provided", err=True)
        raise typer.Exit(1)

    if long_read_reference and not long_read_bam:
        typer.echo("Error: Long read BAM is required when long read reference FASTA is provided", err=True)
        raise typer.Exit(1)

    # Run short read analysis
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

    # Output short read results
    for no, short_read_result in enumerate(short_read_results):
        if no == 0:
            print_short_read_result_header()
        print_short_read_result(
            short_read_result=short_read_result,
            min_support_consensus=min_support_consensus,
        )
        if print_pileups:
            print_short_read_pileups(short_read_result=short_read_result, min_support_consensus=min_support_consensus)

    # Run long read analysis if parameters provided
    if long_read_bam and long_read_reference and short_read_results:
        logger.info("Running long read analysis...")

        # Use the first short read result with highest support for long read analysis
        primary_short_result = short_read_results[0]

        long_read_result = long_read_analysis(
            config=LrsConfig(
                input_bam=long_read_bam,
                genome_release=long_read_release,
                reference_genome=long_read_reference,
                output_dir=output_dir,
                trim_flank=long_read_analysis_trim_flank,
                anchor_length=long_read_anchor_length,
            ),
            short_read_result=primary_short_result,
        )

        # Output long read results
        print_long_read_result_header()
        print_long_read_result(long_read_result)

        if print_details:
            print_long_read_details(long_read_result)

    elif long_read_bam or long_read_reference:
        logger.warning("Long read analysis skipped: both BAM and reference files are required")
    elif not short_read_results:
        logger.warning("Long read analysis skipped: no short read results found")

    logger.info("All done. Have a nice day!")


@app.command()
def version() -> None:
    """Show the version of mainz-muc1-vntr."""
    typer.echo(__version__)


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
