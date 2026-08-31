"""Unit and integration tests for `mgm_muc1_vntr.lrs_analysis`.

Two kinds of BAM appear here on purpose. The synthetic one is cut from a committed masked
reference by `make_lrs_bam`, so the test decides which reads span the interval and
`spanning_read_count` has a known expected value. The ONT fixtures are real GIAB HG003
ultralong reads, which carry a real error profile and real CIGARs that no synthetic read
reproduces. Neither is a stub.

`long_read_analysis` prints a full pairwise alignment per read, so every call here
redirects stdout. `make test` runs with `-s`, and the ONT fixtures produce about 200 kB.
"""

import contextlib
import io

import pytest

from mgm_muc1_vntr.common import VNTR_INTERVALS, VariantType
from mgm_muc1_vntr.lrs_analysis import (
    LongReadResult,
    long_read_analysis,
    print_long_read_details,
    print_long_read_result,
    print_long_read_result_header,
)

ANCHOR_LENGTH = 50


def run_quietly(**kwargs) -> tuple[LongReadResult, str]:
    """Call the analysis with stdout captured rather than dumped into the test log."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = long_read_analysis(**kwargs)
    return result, buffer.getvalue()


@pytest.fixture
def synthetic_bam(make_lrs_bam):
    """Six reads: two that span the VNTR with the anchor on both sides, four that do not."""
    interval = VNTR_INTERVALS["GRCh38"]
    span = interval.end - interval.start
    return make_lrs_bam(
        [
            ("spans_wide", interval.start - 500, span + 1000),
            ("spans_just", interval.start - ANCHOR_LENGTH - 2, span + 2 * ANCHOR_LENGTH + 4),
            ("left_only", interval.start - 200, 400),
            ("right_only", interval.end - 100, 500),
            ("inside", interval.start + 100, 200),
            ("short_left_anchor", interval.start - ANCHOR_LENGTH + 10, span + 100),
        ],
        genome_release="GRCh38",
    )


def test_counts_spanning_reads_by_the_anchor_rule(synthetic_bam, make_short_read_result, lrs_config):
    result, _ = run_quietly(
        config=lrs_config(synthetic_bam),
        short_read_result=make_short_read_result(),
    )
    assert result.total_read_count == 6
    assert result.spanning_read_count == 2, "only the two reads clearing the anchor on both sides"


def test_every_fetched_read_is_reported_for_inspection(synthetic_bam, make_short_read_result, lrs_config):
    """`alt_read_count` counts reads presented for review, not reads carrying the variant.

    This is intended, not an oversight. The module is a review aid: it prints the full
    alignment of every read so a person can look at the locus and decide. No automated
    call is possible here, which is a conclusion from practice and reproducible on the
    fixtures (#27): an exact match of either marker is found in none of the ONT reads at a
    5% per-base error rate, and ref against alt alignment scores differ by 1.5 to 13 points
    on a scale of about 200, which is a coin flip.

    So this assertion is a real invariant, not a pinned defect.
    """
    result, _ = run_quietly(
        config=lrs_config(synthetic_bam),
        short_read_result=make_short_read_result(),
    )
    assert result.alt_read_count == result.total_read_count
    assert len(result.alt_read_names) == result.total_read_count


@pytest.mark.parametrize("var_type", [VariantType.INSERTION, VariantType.DELETION])
def test_variant_consensus_is_built_for_either_variant_type(
    synthetic_bam, make_short_read_result, lrs_config, var_type
):
    """An insertion splices the variant into the consensus, a deletion joins the flanks."""
    result, output = run_quietly(
        config=lrs_config(synthetic_bam),
        short_read_result=make_short_read_result(var_type=var_type),
    )
    assert result.total_read_count == 6
    assert "#### ref_marker" in output
    assert "#### alt_marker" in output


def test_result_records_the_bam_path_and_trim_flank(synthetic_bam, make_short_read_result, lrs_config):
    config = lrs_config(synthetic_bam)
    result, _ = run_quietly(config=config, short_read_result=make_short_read_result())
    assert result.path_bam == str(synthetic_bam)
    assert result.trim_flank == 100


def test_debug_env_var_prints_the_bam_path(synthetic_bam, make_short_read_result, lrs_config, monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    _, output = run_quietly(
        config=lrs_config(synthetic_bam),
        short_read_result=make_short_read_result(),
    )
    assert str(synthetic_bam) in output


@pytest.mark.parametrize("genome_release", ["GRCh37", "GRCh38"])
def test_real_ont_reads(genome_release, make_short_read_result, lrs_config, ont_bams):
    """GIAB HG003 ultralong ONT, the same donor as the short-read fixture.

    Downsampled to six spanning and two partial reads, see `data/README.md`. This is the
    only test that reads `GRCh38_chr1_MUC1_masked.fa.gz` and the `chr1` arm of
    `VNTR_INTERVALS` against real data.
    """
    result, output = run_quietly(
        config=lrs_config(ont_bams[genome_release], genome_release),
        short_read_result=make_short_read_result(),
    )
    assert result.total_read_count == 8
    assert result.spanning_read_count == 6
    assert result.alt_read_count == 8, "every fetched read is reported for inspection"
    assert output.count("###------- BEGIN ALIGN") == 8


def test_print_result_header(capsys):
    print_long_read_result_header()
    assert capsys.readouterr().out.strip().split(",") == [
        "Filename",
        "Total_Reads",
        "Spanning_Reads",
        "Alt_Reads",
        "Full_Path",
    ]


def test_print_result_reports_the_basename_and_the_full_path(capsys):
    print_long_read_result(
        LongReadResult(
            path_bam="/somewhere/sample.bam",
            trim_flank=100,
            total_read_count=8,
            spanning_read_count=6,
            alt_read_count=8,
            alt_read_names=["r1"],
        )
    )
    fields = capsys.readouterr().out.strip().split(",")
    assert fields[0] == "sample.bam"
    assert fields[1:4] == ["8", "6", "8"]
    assert fields[-1] == "/somewhere/sample.bam"


def test_print_details_lists_every_alt_read(capsys):
    print_long_read_details(
        LongReadResult(
            path_bam="/somewhere/sample.bam",
            trim_flank=100,
            total_read_count=2,
            spanning_read_count=1,
            alt_read_count=2,
            alt_read_names=["r1", "r2"],
        )
    )
    output = capsys.readouterr().out
    assert "## total_reads=2, spanning_reads=1, alt_reads=2" in output
    assert output.count("####  ") == 2
