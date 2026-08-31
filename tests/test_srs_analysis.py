"""Unit and integration tests for `mgm_muc1_vntr.srs_analysis`.

The end-to-end assertions on the NA24149 fixture live in `test_srs_analysis_e2e.py`.
What is here is the layer below: the pure functions, the model helpers, the printers, and
`generate_pileup_svg` driven directly rather than through an analysis run.
"""

import io
import xml.etree.ElementTree as ElementTree

import pytest

from mgm_muc1_vntr.common import VariantType
from mgm_muc1_vntr.srs_analysis import (
    FlankGroup,
    build_left_consensus,
    build_right_consensus,
    generate_pileup_svg,
    print_short_read_pileups,
    print_short_read_result,
    print_short_read_result_header,
)


def test_flank_group_defaults_to_an_empty_context_list():
    """`_new_context_list` is the `default_factory` and has no other caller."""
    group = FlankGroup()
    assert group.contexts == []
    assert FlankGroup().contexts is not group.contexts


@pytest.mark.parametrize("var_type", [VariantType.INSERTION, VariantType.DELETION])
@pytest.mark.parametrize("trim_flank", [0, 10])
def test_ref_and_alt_sequences_differ_by_the_variant(make_short_read_result, var_type, trim_flank):
    """`_seq_helper` puts the variant sequence on exactly one of the two markers.

    Which one flips with `var_type`, so the four combinations here are the full truth
    table of `is_ref == (var_type == INSERTION)`.
    """
    result = make_short_read_result(var_type=var_type, sequence="GGG")
    ref = result.ref_sequence(trim_flank=trim_flank)
    alt = result.alt_sequence(trim_flank=trim_flank)

    with_variant, without_variant = (alt, ref) if var_type == VariantType.INSERTION else (ref, alt)
    assert len(with_variant) == len(without_variant) + 3
    assert "GGG" in with_variant


def test_trimming_shortens_both_flanks(make_short_read_result):
    result = make_short_read_result()
    assert len(result.ref_sequence(trim_flank=10)) == 10 + 10 + len("GGG")
    assert len(result.ref_sequence(trim_flank=0)) > len(result.ref_sequence(trim_flank=10))


def test_seq_helper_prefers_consensus_over_longest(make_short_read_result):
    group = FlankGroup(count=1, longest_left="AAAA", longest_right="TTTT", consensus_left="CC", consensus_right="GG")
    result = make_short_read_result(groups=[group])
    assert result.alt_sequence(trim_flank=0) == "CCGG"


def test_seq_helper_falls_back_to_longest_without_a_consensus(make_short_read_result):
    group = FlankGroup(count=1, longest_left="AAAA", longest_right="TTTT")
    result = make_short_read_result(groups=[group])
    assert result.alt_sequence(trim_flank=0) == "AAAATTTT"


@pytest.mark.parametrize("build", [build_left_consensus, build_right_consensus])
def test_consensus_of_no_flanks_is_empty(srs_config, build):
    assert build(srs_config(), []) == ""


def test_left_consensus_builds_from_the_indel_outwards(srs_config):
    """Columns are numbered from the right, so the shared suffix is what survives."""
    assert build_left_consensus(srs_config(min_support_consensus=2), ["TTACGT", "GGACGT"]) == "ACGT"


def test_right_consensus_builds_from_the_indel_outwards(srs_config):
    assert build_right_consensus(srs_config(min_support_consensus=2), ["ACGTTT", "ACGTGG"]) == "ACGT"


def test_consensus_stops_at_the_first_column_below_support(srs_config):
    """One flank alone cannot reach a support of 2, so nothing is called."""
    assert build_left_consensus(srs_config(min_support_consensus=2), ["ACGT"]) == ""


def test_consensus_of_a_single_flank_at_support_one(srs_config):
    assert build_left_consensus(srs_config(min_support_consensus=1), ["ACGT"]) == "ACGT"
    assert build_right_consensus(srs_config(min_support_consensus=1), ["ACGT"]) == "ACGT"


def test_ragged_flanks_extend_past_the_shorter_one(srs_config):
    """Past the short flank's end only the long one votes, so support drops to 1."""
    config = srs_config(min_support_consensus=1)
    assert build_left_consensus(config, ["GT", "ACGT"]) == "ACGT"
    assert build_right_consensus(config, ["AC", "ACGT"]) == "ACGT"


def test_print_result_header(capsys):
    print_short_read_result_header()
    assert capsys.readouterr().out.strip().split(",") == [
        "Filename",
        "Variant_Type",
        "Variant_Sequence",
        "Raw_Support",
        "Support",
        "Full_Path",
    ]


def test_print_result_reports_the_basename_and_the_full_path(make_short_read_result):
    out = io.StringIO()
    print_short_read_result(short_read_result=make_short_read_result(), min_support_consensus=2, file=out)
    fields = out.getvalue().strip().split(",")
    assert fields[0] == "sample.bam"
    assert fields[-1] == "/somewhere/sample.bam"


def test_print_result_revcomps_the_variant_sequence(make_short_read_result):
    """The CSV reports transcript orientation, the model stores reference orientation."""
    out = io.StringIO()
    print_short_read_result(
        short_read_result=make_short_read_result(sequence="AAGG"), min_support_consensus=2, file=out
    )
    assert out.getvalue().strip().split(",")[2] == "CCTT"


def test_print_pileups_renders_consensus_and_one_line_per_read(make_short_read_result):
    out = io.StringIO()
    print_short_read_pileups(short_read_result=make_short_read_result(), min_support_consensus=2, file=out)
    lines = out.getvalue().splitlines()
    assert sum(line.startswith("## CONS") for line in lines) == 1
    assert sum(line.startswith("##   r") for line in lines) == 2


def test_print_pileups_skips_groups_below_support(make_short_read_result):
    group = FlankGroup(count=1, longest_left="AAAA", longest_right="TTTT", example_read="lonely")
    out = io.StringIO()
    print_short_read_pileups(
        short_read_result=make_short_read_result(groups=[group]), min_support_consensus=2, file=out
    )
    assert out.getvalue() == ""


def test_generate_pileup_svg_writes_nothing_without_results(tmp_path):
    output_path = tmp_path / "pileup.svg"
    generate_pileup_svg(short_read_results=[], min_support_consensus=2, output_path=output_path)
    assert not output_path.exists()


def test_generate_pileup_svg_from_hand_built_results(make_short_read_result, tmp_path):
    """Driven directly, so the SVG is covered without an analysis run in front of it.

    The second group sits below `min_support_consensus` and must be left out, which is
    what distinguishes this from the end-to-end SVG test.
    """
    supported = make_short_read_result().flank_groups[0]
    below_support = FlankGroup(count=1, longest_left="AAAA", longest_right="TTTT", example_read="lonely")

    with_both = tmp_path / "both.svg"
    generate_pileup_svg(
        short_read_results=[make_short_read_result(groups=[supported, below_support])],
        min_support_consensus=2,
        output_path=with_both,
    )
    only_supported = tmp_path / "one.svg"
    generate_pileup_svg(
        short_read_results=[make_short_read_result(groups=[supported])],
        min_support_consensus=2,
        output_path=only_supported,
    )

    assert with_both.stat().st_size > 0
    assert ElementTree.parse(with_both).getroot().tag.endswith("svg")
    # The group below support must contribute nothing, so the two renders are identical.
    assert with_both.read_bytes() == only_supported.read_bytes()
    assert below_support.example_read not in with_both.read_text()


def test_generate_pileup_svg_fits_a_long_header_inside_the_canvas(make_short_read_result, tmp_path):
    """A read name longer than the widest alignment line must still fit the canvas.

    `Example_Read` is the only line whose length is not bounded by the flanks, so it is
    the one that used to be laid out past the declared `width` and clipped there.
    """
    result = make_short_read_result()
    result.flank_groups[0].example_read = "R" * 400

    output_path = tmp_path / "pileup.svg"
    generate_pileup_svg(short_read_results=[result], min_support_consensus=2, output_path=output_path)

    root = ElementTree.parse(output_path).getroot()
    width = float(root.attrib["width"])
    overflowing = [
        text.text
        for text in root.iter("{http://www.w3.org/2000/svg}text")
        if float(text.attrib["x"]) + float(text.attrib["textLength"]) > width
    ]
    assert overflowing == []
