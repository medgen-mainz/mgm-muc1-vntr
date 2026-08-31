"""End-to-end test for the short-read analysis on the GRCh37 fixture.

Runs :func:`short_read_analysis` against the committed NA24149 slice and asserts
properties of what comes back, rather than merely that it does not crash. See
`tests/data/README.md` for the provenance of the fixtures.
"""

import pathlib
import xml.etree.ElementTree as ElementTree

import pytest
from syrupy.assertion import SnapshotAssertion

from mgm_muc1_vntr.srs_analysis import (
    PILEUP_ADVANCE_EM,
    Config,
    ShortReadResult,
    short_read_analysis,
)

DATA_DIR = pathlib.Path(__file__).parent / "data"
BAM_PATH = DATA_DIR / "NA24149_MUC1_SRS.bam"
REFERENCE_PATH = DATA_DIR / "GRCh37_1_MUC1_masked.fa.gz"

#: Knob values the CLI defaults to, so the test exercises the configuration users get.
DEFAULT_MIN_SUPPORT_VAR = 3
DEFAULT_MIN_SUPPORT_CONSENSUS = 2
DEFAULT_TRIM_FLANK = 150

#: Support counts per ``min_support_var``, and how many of those calls have a length that
#: is not a multiple of three. Measured against this fixture. The point of the table is
#: that the absence of a frameshifting call is a consequence of the support filter and not
#: a property of the sample: at a threshold of two, two of them survive.
SUPPORT_THRESHOLD_TABLE = [
    (1, 22, 14),
    (2, 4, 2),
    (3, 1, 0),
    (4, 0, 0),
]


def make_config(
    *,
    min_support_var: int = DEFAULT_MIN_SUPPORT_VAR,
    pileup_svg_path: pathlib.Path | None = None,
) -> Config:
    """Build a configuration pointing at the committed GRCh37 fixtures."""
    return Config(
        input_bam=BAM_PATH,
        genome_release="GRCh37",
        reference_genome=REFERENCE_PATH,
        min_support_var=min_support_var,
        trim_flank=DEFAULT_TRIM_FLANK,
        min_support_consensus=DEFAULT_MIN_SUPPORT_CONSENSUS,
        pileup_svg_path=pileup_svg_path,
    )


@pytest.fixture
def results() -> list[ShortReadResult]:
    """Run the analysis once at the CLI defaults and hand back the results."""
    return short_read_analysis(config=make_config())


def test_support_accounting_is_consistent(results: list[ShortReadResult]) -> None:
    """Each result's support figures agree with its flank groups.

    These are invariants of the analysis rather than facts about this fixture, so they
    should hold whatever data is thrown at it.
    """
    assert results, "expected at least one call to assert against"
    for result in results:
        counts = [group.count for group in result.flank_groups]
        assert result.flank_groups, "a result must come from at least one flank group"
        assert result.support >= DEFAULT_MIN_SUPPORT_VAR
        assert result.support <= result.raw_support
        assert result.support == max(counts)
        assert sum(counts) == result.raw_support
        for group in result.flank_groups:
            assert group.count == len(group.contexts)


def test_variant_sequences_are_plain_dna(results: list[ShortReadResult]) -> None:
    """Every reported call carries a non-empty ACGT sequence."""
    for result in results:
        sequence = result.repeat_variation.sequence
        assert sequence
        assert set(sequence) <= set("ACGT"), f"unexpected characters in {sequence!r}"


def test_results_are_ordered_by_descending_support(results: list[ShortReadResult]) -> None:
    """The analysis documents itself as returning the best-supported call first."""
    supports = [result.support for result in results]
    assert supports == sorted(supports, reverse=True)


def test_no_frameshifting_call_at_the_default_threshold(results: list[ShortReadResult]) -> None:
    """No call clearing the default support threshold shifts the reading frame.

    NA24149 is a healthy public reference genome, so this is the expected outcome. The
    analysis has no notion of a frameshift, so it is derived here from the call length.

    The threshold matters and is part of the claim: this fixture does carry
    frameshifting calls at lower thresholds, see
    :func:`test_call_counts_per_support_threshold`. This is not the same as saying the
    sample contains none.
    """
    frameshifting = [result.repeat_variation for result in results if len(result.repeat_variation.sequence) % 3 != 0]
    assert (
        not frameshifting
    ), f"expected no frameshifting call at min_support_var={DEFAULT_MIN_SUPPORT_VAR}, got {frameshifting}"


@pytest.mark.parametrize(("min_support_var", "expected_calls", "expected_frameshifting"), SUPPORT_THRESHOLD_TABLE)
def test_call_counts_per_support_threshold(
    min_support_var: int,
    expected_calls: int,
    expected_frameshifting: int,
) -> None:
    """The support filter shapes the call set as measured against this fixture.

    This documents the noise structure of the locus and would catch a change in the
    support or grouping logic that the single-threshold assertions cannot see.
    """
    results = short_read_analysis(config=make_config(min_support_var=min_support_var))
    frameshifting = [result for result in results if len(result.repeat_variation.sequence) % 3 != 0]
    assert len(results) == expected_calls
    assert len(frameshifting) == expected_frameshifting


def test_single_expected_call(results: list[ShortReadResult]) -> None:
    """Characterise the current output on this fixture.

    Deliberately exact, as a regression guard. Note the one call that clears the filter
    has support exactly equal to the threshold, and nothing clears a threshold of four,
    so this is knife-edge by construction: any change to read filtering, grouping or
    support counting will move it. A failure here means the numbers moved, which is
    worth a look, not that the test is broken.
    """
    assert len(results) == 1
    (result,) = results
    assert pathlib.Path(result.path_bam).name == BAM_PATH.name
    assert result.repeat_variation.var_type.value == "del"
    assert result.repeat_variation.sequence == "GGTGGAGCCCGGGGCCGG"
    assert len(result.repeat_variation.sequence) == 18
    assert result.raw_support == 3
    assert result.support == 3
    assert len(result.flank_groups) == 1
    assert result.flank_groups[0].count == 3


def test_results_match_snapshot(results: list[ShortReadResult], snapshot: SnapshotAssertion) -> None:
    """Pin the full result payload, including consensus sequences and read contexts.

    Those are laborious to assert by hand and this is where a change shows up in detail.
    Refresh with ``make test-snapshot`` when the numbers legitimately move.

    ``path_bam`` is reduced to its file name first. The analysis records the path it was
    handed, which is absolute and therefore differs between a developer checkout and CI,
    so snapshotting it verbatim would pin one machine's layout. The path is asserted
    separately in :func:`test_single_expected_call`.
    """
    payload = []
    for result in results:
        dumped = result.model_dump(mode="json")
        dumped["path_bam"] = pathlib.Path(dumped["path_bam"]).name
        payload.append(dumped)

    assert payload == snapshot


def test_pileup_svg_is_written(tmp_path: pathlib.Path) -> None:
    """The pileup SVG is the only file the analysis writes.

    Only structure is asserted. The size and exact content shift for purely cosmetic
    layout reasons, so neither is pinned.
    """
    svg_path = tmp_path / "pileup.svg"
    short_read_analysis(config=make_config(pileup_svg_path=svg_path))

    assert svg_path.exists()
    assert svg_path.stat().st_size > 0
    root = ElementTree.parse(svg_path).getroot()
    assert root.tag.rpartition("}")[2] == "svg"


def test_no_pileup_svg_without_a_path(tmp_path: pathlib.Path) -> None:
    """Nothing is written when no SVG path is configured.

    The pileup SVG is the only file the analysis writes and ``pileup_svg_path`` is the
    only thing that names it, so leaving it unset has to leave the directory the sibling
    tests write their SVG into empty.
    """
    short_read_analysis(config=make_config())

    assert list(tmp_path.iterdir()) == []


def test_pileup_svg_preserves_alignment_padding(tmp_path: pathlib.Path) -> None:
    """Every pileup line keeps the padding that aligns its columns.

    This is the regression guard for the SVG writer (#24). The layout is carried
    entirely by the ``rjust``/``ljust`` padding inside each line, and SVG collapses
    leading and repeated spaces unless ``xml:space="preserve"`` is set. Dropping that
    attribute still produces a valid, plausible-looking SVG in which every line is
    flush left and the pileup means nothing, so structural assertions do not catch it.
    """
    svg_path = tmp_path / "pileup.svg"
    short_read_analysis(config=make_config(pileup_svg_path=svg_path))

    root = ElementTree.parse(svg_path).getroot()
    texts = root.iter("{http://www.w3.org/2000/svg}text")
    padded = [t for t in texts if (t.text or "").startswith(" ") or "  " in (t.text or "")]

    assert padded, "expected at least one line to carry alignment padding"
    for element in padded:
        space = element.get("{http://www.w3.org/XML/1998/namespace}space")
        assert space == "preserve", f"padding would collapse on line {element.text!r}"


def test_pileup_svg_lines_sit_on_the_character_grid(tmp_path: pathlib.Path) -> None:
    """Each line's declared length is its character count times the advance width.

    Pins the relationship between ``PILEUP_ADVANCE_EM`` and the ``textLength`` the
    writer emits, so changing the font family without changing the advance is a test
    failure rather than a silent column drift.
    """
    svg_path = tmp_path / "pileup.svg"
    short_read_analysis(config=make_config(pileup_svg_path=svg_path))

    root = ElementTree.parse(svg_path).getroot()
    group = root.find("{http://www.w3.org/2000/svg}g")
    assert group is not None
    advance = float(group.get("font-size", "0")) * PILEUP_ADVANCE_EM
    assert advance > 0

    lines = list(group.iter("{http://www.w3.org/2000/svg}text"))
    assert lines, "expected the fixture to produce at least one line"
    for element in lines:
        expected = len(element.text or "") * advance
        assert float(element.get("textLength", "-1")) == pytest.approx(expected)
