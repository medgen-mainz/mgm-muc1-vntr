"""End-to-end tests for the short-read analysis on the synthetic MucOneUp fixtures.

Each fixture carries a MUC1 variant that is known by construction, so these tests assert
what the analysis should find rather than characterising whatever it happens to emit. See
`tests/data/README.md` for provenance and `tests/data/make_synthetic_fixtures.sh` for the
recipe.
"""

import pathlib

import pysam
import pytest

from mgm_muc1_vntr.common import VNTR_INTERVALS
from mgm_muc1_vntr.srs_analysis import Config, ShortReadResult, short_read_analysis

DATA_DIR = pathlib.Path(__file__).parent / "data"
REFERENCE_PATH = DATA_DIR / "GRCh37_1_MUC1_masked.fa.gz"

#: Knob values the CLI defaults to.
DEFAULT_MIN_SUPPORT_VAR = 3
DEFAULT_MIN_SUPPORT_CONSENSUS = 2
DEFAULT_TRIM_FLANK = 150

#: fixture, variant type, call length, called sequence, support, shifts the frame.
#:
#: The called sequences are the reverse complement of what MucOneUp inserts, `GGGG` for an
#: inserted `CCCC`, because MUC1 sits on the minus strand and the analysis reports in
#: reference orientation.
DETECTED_CASES = [
    ("synth_insCCCC", "ins", 4, "GGGG", 63, True),
    ("synth_insCCC_benign", "ins", 3, "GGG", 57, False),
]

#: Fixtures whose variant the analysis is expected to find nothing for; see
#: :func:`test_dupc_is_in_the_bam_but_never_reported`.
UNDETECTED_CASES = ["synth_dupC"]

ALL_CASES = [case[0] for case in DETECTED_CASES] + UNDETECTED_CASES


def make_config(
    fixture: str,
    *,
    min_support_var: int = DEFAULT_MIN_SUPPORT_VAR,
) -> Config:
    """Build a configuration for one synthetic fixture."""
    return Config(
        input_bam=DATA_DIR / f"{fixture}.bam",
        genome_release="GRCh37",
        reference_genome=REFERENCE_PATH,
        min_support_var=min_support_var,
        trim_flank=DEFAULT_TRIM_FLANK,
        min_support_consensus=DEFAULT_MIN_SUPPORT_CONSENSUS,
    )


@pytest.mark.parametrize(("fixture", "var_type", "length", "sequence", "support", "shifts_frame"), DETECTED_CASES)
def test_expected_variant_is_called(
    fixture: str,
    var_type: str,
    length: int,
    sequence: str,
    support: int,
    shifts_frame: bool,
) -> None:
    """The analysis finds exactly the variant the fixture was built to carry."""
    results = short_read_analysis(config=make_config(fixture))

    assert len(results) == 1
    (result,) = results
    assert result.repeat_variation.var_type.value == var_type
    assert result.repeat_variation.sequence == sequence
    assert len(result.repeat_variation.sequence) == length
    assert result.support == support
    assert result.raw_support == support
    assert (len(result.repeat_variation.sequence) % 3 != 0) is shifts_frame


@pytest.mark.parametrize(("fixture", "shifts_frame"), [(c[0], c[5]) for c in DETECTED_CASES])
def test_frameshift_status_matches_the_construction(fixture: str, shifts_frame: bool) -> None:
    """A frameshifting fixture yields a frameshifting call, an in-frame one does not.

    This is the assertion that matters clinically, stated separately from the exact call so
    a failure says which of the two went wrong.
    """
    results = short_read_analysis(config=make_config(fixture))
    frameshifting = [r for r in results if len(r.repeat_variation.sequence) % 3 != 0]

    assert bool(frameshifting) is shifts_frame


def test_dupc_is_in_the_bam_but_never_reported() -> None:
    """The pathogenic dupC allele is present in the reads and reported by nothing.

    This pins a known limitation rather than desired behaviour. `short_read_analysis`
    skips any read without an indel of at least 2 bp, and dupC is a single base insertion,
    so every supporting read is discarded before its variation is counted. The pathogenic
    ADTKD-MUC1 allele is exactly this variant.

    When the filter is fixed, this test is meant to fail. Replace it with an assertion that
    the insertion is found.
    """
    interval = VNTR_INTERVALS["GRCh37"]
    with pysam.AlignmentFile(str(DATA_DIR / "synth_dupC.bam")) as bam:
        single_base_insertions = [
            read
            for read in bam.fetch(contig=interval.contig, start=interval.start, end=interval.end)
            if (pysam.CINS, 1) in (read.cigartuples or [])
        ]
    assert len(single_base_insertions) == 60, "fixture should carry the dupC reads"
    assert not any(
        length >= 2
        for read in single_base_insertions
        for operation, length in read.cigartuples or []
        if operation in (pysam.CINS, pysam.CDEL)
    ), "no dupC read carries another indel, so all of them fail the >= 2 read filter"

    for min_support_var in (1, DEFAULT_MIN_SUPPORT_VAR):
        results = short_read_analysis(config=make_config("synth_dupC", min_support_var=min_support_var))
        assert results == [], f"known limitation, nothing is reported at {min_support_var=}"


@pytest.mark.parametrize("fixture", ALL_CASES)
def test_support_accounting_is_consistent(fixture: str) -> None:
    """The invariants asserted for the real fixture hold for the synthetic ones too."""
    results: list[ShortReadResult] = short_read_analysis(config=make_config(fixture))

    for result in results:
        counts = [group.count for group in result.flank_groups]
        assert result.flank_groups
        assert result.support >= DEFAULT_MIN_SUPPORT_VAR
        assert result.support <= result.raw_support
        assert result.support == max(counts)
        assert sum(counts) == result.raw_support
        assert set(result.repeat_variation.sequence) <= set("ACGT")
        for group in result.flank_groups:
            assert group.count == len(group.contexts)
