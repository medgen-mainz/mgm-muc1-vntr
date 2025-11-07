import enum
from typing import Literal

import pydantic

type GenomeRelease = Literal["GRCh37", "GRCh38"]

class VariantType(str, enum.Enum):
    """Enumeration for specifying variant type."""

    #: Is insertion of sequence into read.
    INSERTION = "ins"
    #: Is deletion from reference sequence.
    DELETION = "del"


class GenomeInterval(pydantic.BaseModel):
    """Represent a genomic interval."""

    #: Contig name.
    contig: str
    #: Start position (1-based).
    start: int
    #: End position (1-based, exclusive).
    end: int


#: VNTR interval locations
VNTR_INTERVALS: dict[GenomeRelease, GenomeInterval] = {
    "GRCh37": GenomeInterval(contig="1", start=155_161_171, end=155_161_634),
    "GRCh38": GenomeInterval(contig="chr1", start=155_188_946, end=155_191_506),
}


def revcomp(seq: str) -> str:
    """Reverse complement a DNA sequence."""
    complement = str.maketrans("ACGT", "TGCA")
    return seq.translate(complement)[::-1]
