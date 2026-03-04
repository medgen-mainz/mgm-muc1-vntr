import os
import pathlib

import pydantic
import pysam
from Bio import Align
from loguru import logger

from mgm_muc1_vntr.common import VNTR_INTERVALS, GenomeRelease, VariantType, revcomp
from mgm_muc1_vntr.srs_analysis import ShortReadResult


class Config(pydantic.BaseModel):
    """Configuration for LRS analysis of MUC1 VNTR."""

    #: Path to input BAM file with long reads.
    input_bam: pathlib.Path
    #: Genome release to use
    genome_release: GenomeRelease = "GRCh38"
    #: Path to reference genome in FASTA format.
    reference_genome: pathlib.Path
    #: Path to output directory.
    output_dir: pathlib.Path
    #: Flanking region to trim.
    trim_flank: int
    #: Required anchor length for spanning reads.
    anchor_length: int = 50


class LongReadResult(pydantic.BaseModel):
    """Result of long read analysis."""

    model_config = pydantic.ConfigDict(frozen=True)

    #: Path to BAM file.
    path_bam: str
    #: Flanking trim length use.
    trim_flank: int | None
    #: Total read count.
    total_read_count: int
    #: Reads spanning over target region.
    spanning_read_count: int
    #: Reads supporting the variant.
    alt_read_count: int
    #: IDs of alt reads.
    alt_read_names: list[str]


ALIGNER = Align.PairwiseAligner(
    mode="global",
    match_score=2.0,
    mismatch_score=-1.0,
    open_internal_insertion_score=-10,
    extend_internal_insertion_score=-0.5,
    open_left_insertion_score=0,
    extend_left_insertion_score=0,
    open_right_insertion_score=0,
    extend_right_insertion_score=0,
    open_internal_deletion_score=-10,
    extend_internal_deletion_score=-0.5,
    open_left_deletion_score=0,
    extend_left_deletion_score=0,
    open_right_deletion_score=0,
    extend_right_deletion_score=0,
)


def long_read_analysis(
    *,
    config: Config,
    short_read_result: ShortReadResult,
) -> LongReadResult:
    """Perform long-read analysis for MUC1 VNTR.

    Args:
        config: Configuration for analysis.
        short_read_result: Result from short read analysis to use as reference.

    Returns:
        Long read analysis result.
    """
    logger.info("Starting long-read analysis...")
    logger.debug("Using configuration: {config}", config=config.model_dump_json(indent=2))

    debug = os.getenv("DEBUG", "").lower() in ["1", "true"]

    bamfile = pysam.AlignmentFile(str(config.input_bam), mode="rb", reference_filename=str(config.reference_genome))
    ref_marker = short_read_result.ref_sequence(trim_flank=config.trim_flank)
    alt_marker = short_read_result.alt_sequence(trim_flank=config.trim_flank)

    # Build consensus variant allele sequence for alignment
    group = short_read_result.flank_groups[0] if short_read_result.flank_groups else None
    if group:
        cons_left = group.consensus_left or group.longest_left
        cons_right = group.consensus_right or group.longest_right
        rep_var = short_read_result.repeat_variation
        if rep_var.var_type == VariantType.INSERTION:
            variant_consensus = cons_left + rep_var.sequence + cons_right
        else:
            variant_consensus = cons_left + cons_right
    else:
        variant_consensus = alt_marker

    if debug:
        print(str(config.input_bam))
    # For each read, count number of reference and alternative marker sequences.
    total_read_count = 0
    spanning_read_count = 0
    alt_read_count = 0
    alt_read_names: list[str] = []
    interval = VNTR_INTERVALS[config.genome_release]
    for line in bamfile.fetch(contig=interval.contig, start=interval.start, end=interval.end):
        total_read_count += 1

        # Check if read is spanning and anchored.
        reference_start = line.reference_start + 1
        reference_end = line.reference_start + (line.reference_length or 0)
        if (
            reference_start < interval.start - config.anchor_length
            and reference_end > interval.end + config.anchor_length
        ):
            spanning_read_count += 1
            # as_motifs = spanning_to_motifs(line.query_sequence or "")
            # print(f"# {line.query_name} spanning, motifs: {' '.join(as_motifs)}")

        read_sequence = line.query_sequence
        assert read_sequence, f"Read sequence of {line.query_name} is empty"
        alt_read_count += 1
        alt_read_names.append(line.query_name or "")
        # Pairwise alignment (Biopython) between long read and variant consensus
        # gap open 10, gap extend 0.5, no terminal gap penalty
        alignments = ALIGNER.align(read_sequence, variant_consensus)
        # Print best alignment for each long read
        if alignments:
            best = alignments[0]
            print(f"###------- BEGIN ALIGN {line.query_name} --------###")
            print(best)
            print(f"###------- END ALIGN {line.query_name}   --------###")

    if debug:
        print("# --\n")

    # if alt_read_count:
    print(f"#### ref_marker = -e '{ref_marker}' -e '{revcomp(ref_marker)}'")
    print(f"#### alt_marker = -e '{alt_marker}' -e '{revcomp(alt_marker)}'")

    logger.info("Long-read analysis completed.")
    return LongReadResult(
        path_bam=str(config.input_bam),
        trim_flank=config.trim_flank,
        total_read_count=total_read_count,
        spanning_read_count=spanning_read_count,
        alt_read_count=alt_read_count,
        alt_read_names=alt_read_names,
    )


def print_long_read_result_header():
    """Print header for long read results."""
    print(
        ",".join(
            [
                "Filename",
                "Total_Reads",
                "Spanning_Reads",
                "Alt_Reads",
                "Full_Path",
            ]
        )
    )


def print_long_read_result(long_read_result: LongReadResult):
    """Print long read result in CSV format."""
    print(
        ",".join(
            map(
                str,
                [
                    os.path.basename(long_read_result.path_bam),
                    long_read_result.total_read_count,
                    long_read_result.spanning_read_count,
                    long_read_result.alt_read_count,
                    long_read_result.path_bam,
                ],
            )
        )
    )


def print_long_read_details(long_read_result: LongReadResult):
    """Print detailed long read analysis results."""
    print(
        f"## total_reads={long_read_result.total_read_count}"
        f", spanning_reads={long_read_result.spanning_read_count}"
        f", alt_reads={long_read_result.alt_read_count}"
    )
    for read_name in long_read_result.alt_read_names:
        print(f"####  {read_name}")
