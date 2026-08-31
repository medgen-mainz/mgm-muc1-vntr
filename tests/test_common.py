"""Unit tests for `mgm_muc1_vntr.common`."""

import pytest

from mgm_muc1_vntr.common import VNTR_INTERVALS, revcomp


@pytest.mark.parametrize(
    "sequence,expected",
    [
        ("", ""),
        ("A", "T"),
        ("ACGT", "ACGT"),
        ("AAGG", "CCTT"),
        ("GGTGGAGCCCGGGGCCGG", "CCGGCCCCGGGCTCCACC"),
    ],
)
def test_revcomp(sequence: str, expected: str):
    assert revcomp(sequence) == expected


def test_revcomp_is_an_involution():
    sequence = "GGTGGAGCCCGGGGCCGG"
    assert revcomp(revcomp(sequence)) == sequence


@pytest.mark.parametrize("genome_release", ["GRCh37", "GRCh38"])
def test_vntr_intervals_are_well_formed(genome_release):
    interval = VNTR_INTERVALS[genome_release]
    assert interval.start < interval.end
    assert interval.contig == ("1" if genome_release == "GRCh37" else "chr1")
