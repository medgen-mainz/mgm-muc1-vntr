"""Shared fixtures.

Everything here builds real objects and real files. There are no stubs in this suite: a
BAM the code reads is a BAM `pysam` wrote, and a `ShortReadResult` is the pydantic model
itself, which is plain data and cheaper to construct than to fake.
"""

import pathlib
from collections.abc import Callable

import pysam
import pytest
from loguru import logger

from mgm_muc1_vntr.common import VNTR_INTERVALS, GenomeRelease, VariantType
from mgm_muc1_vntr.lrs_analysis import Config as LrsConfig
from mgm_muc1_vntr.srs_analysis import (
    Config,
    ContextInformation,
    FlankGroup,
    RepeatVariation,
    ShortReadResult,
)

DATA = pathlib.Path(__file__).parent / "data"

#: The committed short-read fixture and the reference it was aligned against.
SRS_BAM = DATA / "NA24149_MUC1_SRS.bam"
SRS_REFERENCE = DATA / "GRCh37_1_MUC1_masked.fa.gz"

#: One masked reference per build, both committed.
REFERENCES: dict[GenomeRelease, pathlib.Path] = {
    "GRCh37": SRS_REFERENCE,
    "GRCh38": DATA / "GRCh38_chr1_MUC1_masked.fa.gz",
}

#: The downsampled GIAB HG003 ONT-UL slices, see `data/README.md`.
ONT_BAMS: dict[GenomeRelease, pathlib.Path] = {
    "GRCh37": DATA / "HG003_MUC1_GRCh37_ONT.bam",
    "GRCh38": DATA / "HG003_MUC1_GRCh38_ONT.bam",
}


@pytest.fixture(autouse=True)
def _reset_loguru():
    """Drop log handlers after every test.

    `setup_loguru` binds a handler to whatever `sys.stderr` is live when it runs. Once a
    `CliRunner` invocation returns, that stream is closed, and every later log from any
    test raises `ValueError: I/O operation on closed file` inside loguru. Noisy rather
    than failing, but it buries real output.
    """
    yield
    logger.remove()


@pytest.fixture
def srs_config(tmp_path) -> Callable[..., Config]:
    """Build an SRS `Config` on the committed fixture, at the CLI's own defaults."""

    def _make(**overrides) -> Config:
        kwargs = {
            "input_bam": SRS_BAM,
            "reference_genome": SRS_REFERENCE,
            "genome_release": "GRCh37",
            "output_dir": tmp_path,
            "min_support_var": 3,
            "min_support_consensus": 2,
            "trim_flank": 150,
        }
        kwargs.update(overrides)
        return Config(**kwargs)

    return _make


@pytest.fixture
def make_short_read_result() -> Callable[..., ShortReadResult]:
    """Build a `ShortReadResult` by hand, with flanks long enough to survive trimming."""

    def _make(
        *,
        var_type: VariantType = VariantType.DELETION,
        sequence: str = "GGG",
        groups: list[FlankGroup] | None = None,
    ) -> ShortReadResult:
        repeat_variation = RepeatVariation(var_type=var_type, sequence=sequence)
        if groups is None:
            groups = [
                FlankGroup(
                    count=2,
                    longest_left="ACGT" * 40,
                    longest_right="TGCA" * 40,
                    consensus_left="ACGT" * 30,
                    consensus_right="TGCA" * 30,
                    example_read="read1",
                    contexts=[
                        ContextInformation(
                            read_name="read1",
                            repeat_variation=repeat_variation,
                            left_flank="ACGT" * 40,
                            right_flank="TGCA" * 40,
                        ),
                        ContextInformation(
                            read_name="read2",
                            repeat_variation=repeat_variation,
                            left_flank="ACGT" * 20,
                            right_flank="TGCA" * 20,
                        ),
                    ],
                )
            ]
        return ShortReadResult(
            path_bam="/somewhere/sample.bam",
            repeat_variation=repeat_variation,
            raw_support=2,
            support=max((group.count for group in groups), default=0),
            flank_groups=groups,
        )

    return _make


@pytest.fixture
def ont_bams() -> dict[GenomeRelease, pathlib.Path]:
    """The downsampled GIAB HG003 ONT-UL slices, one per build."""
    return ONT_BAMS


@pytest.fixture
def lrs_config(tmp_path) -> Callable[..., LrsConfig]:
    """Build an LRS `Config` against the masked reference for the chosen build."""

    def _make(input_bam: pathlib.Path, genome_release: GenomeRelease = "GRCh38", **overrides) -> LrsConfig:
        kwargs = {
            "input_bam": input_bam,
            "genome_release": genome_release,
            "reference_genome": REFERENCES[genome_release],
            "output_dir": tmp_path,
            "trim_flank": 100,
            "anchor_length": 50,
        }
        kwargs.update(overrides)
        return LrsConfig(**kwargs)

    return _make


@pytest.fixture
def make_lrs_bam(tmp_path) -> Callable[..., pathlib.Path]:
    """Write and index a real BAM whose reads are cut from a committed masked reference.

    The caller states each read as `(name, reference_start, length)`, which is what makes
    this worth having next to the real ONT fixtures: it decides which reads clear
    `anchor_length` on both sides, so `spanning_read_count` has a known expected value
    instead of whatever a sample happens to contain.
    """

    def _make(
        reads: list[tuple[str, int, int]],
        *,
        genome_release: GenomeRelease = "GRCh38",
        name: str = "lrs.bam",
    ) -> pathlib.Path:
        path = tmp_path / name
        contig = VNTR_INTERVALS[genome_release].contig
        reference = pysam.FastaFile(str(REFERENCES[genome_release]))
        header = {
            "HD": {"VN": "1.6", "SO": "coordinate"},
            "SQ": [{"SN": contig, "LN": reference.get_reference_length(contig)}],
        }
        with pysam.AlignmentFile(str(path), "wb", header=header) as out:
            # The header declares SO:coordinate and `samtools index` enforces it, so sort
            # here rather than making every caller list its reads in position order.
            for read_name, start, length in sorted(reads, key=lambda read: (read[1], read[0])):
                segment = pysam.AlignedSegment()
                segment.query_name = read_name
                segment.query_sequence = reference.fetch(contig, start, start + length).upper()
                segment.flag = 0
                segment.reference_id = 0
                segment.reference_start = start
                segment.mapping_quality = 60
                segment.cigartuples = [(pysam.CMATCH, length)]
                segment.query_qualities = pysam.qualitystring_to_array("I" * length)
                out.write(segment)
        pysam.index(str(path))
        return path

    return _make
