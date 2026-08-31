"""Machine-readable JSON result document for the short-read analysis.

This is the contract a downstream consumer ingests instead of scraping stdout. It carries
the numbers and the per-read alignment evidence, and nothing derived from them: no
frame-shift flag, no verdict, no rendered pileup. The effective thresholds are emitted so
a consumer can apply them itself.

The pileup that ``--print-pileups`` renders is derivable from this document:
:func:`mgm_muc1_vntr.srs_analysis.print_short_read_pileups` pads by ``max()`` over the
consensus and the flanks and orders reads by ``(-len(left_flank), read_name)``, all of
which is here. The reverse does not hold, which is why the groups go out as data.
"""

import pathlib

import pydantic

from mgm_muc1_vntr import __version__
from mgm_muc1_vntr.common import GenomeRelease, VariantType, revcomp
from mgm_muc1_vntr.srs_analysis import Config, LocusReadCounts, ShortReadResult

#: Version of the document below, for a consumer to gate on. Bumped when a field is
#: removed or its meaning changes; adding a field does not bump it.
SCHEMA_VERSION = 1


class JsonRead(pydantic.BaseModel):
    """The flanks one supporting read contributed, in the orientation analysed."""

    model_config = pydantic.ConfigDict(frozen=True)

    #: Read name, as in the BAM.
    read_name: str
    #: Read sequence left of the variation.
    left_flank: str
    #: Read sequence right of the variation.
    right_flank: str


class JsonFlankGroup(pydantic.BaseModel):
    """One group of reads sharing the four bases either side of the variation."""

    model_config = pydantic.ConfigDict(frozen=True)

    #: Number of reads in this group.
    count: int
    #: Consensus left flank, empty when no column cleared ``min_support_consensus``.
    consensus_left: str
    #: Consensus right flank, empty when no column cleared ``min_support_consensus``.
    consensus_right: str
    #: Longest left flank seen in this group.
    longest_left: str
    #: Longest right flank seen in this group.
    longest_right: str
    #: Name of the read with the longest left flank.
    example_read: str
    #: Every read in this group.
    reads: list[JsonRead]


class JsonResult(pydantic.BaseModel):
    """One called variation and the evidence for it."""

    model_config = pydantic.ConfigDict(frozen=True)

    #: Insertion or deletion.
    var_type: VariantType
    #: Inserted or deleted sequence, in the orientation the analysis produced it.
    sequence: str
    #: The same sequence in transcript orientation, which is what the CSV row prints.
    sequence_transcript: str
    #: Length of the variation; orientation-invariant, emitted so a consumer need not
    #: re-derive it to compute ``length % 3``.
    length: int
    #: Reads carrying this variation.
    raw_support: int
    #: Reads in the largest flank group.
    support: int
    #: Every flank group, including those below ``min_support_consensus``: that threshold
    #: is a display choice and it is emitted for the consumer to apply.
    flank_groups: list[JsonFlankGroup]


class JsonDocument(pydantic.BaseModel):
    """The complete short-read analysis result."""

    model_config = pydantic.ConfigDict(frozen=True)

    #: Version of this document's schema, see :data:`SCHEMA_VERSION`.
    schema_version: int = SCHEMA_VERSION
    #: Version of the tool that produced it.
    tool_version: str = __version__
    #: Genome release the analysis ran against, which fixes the VNTR interval.
    genome_release: GenomeRelease
    #: Path to the analysed BAM, as passed.
    input_bam: str
    #: Effective minimum support for a variation to reach ``results``.
    min_support_var: int
    #: Effective minimum support per consensus column.
    min_support_consensus: int
    #: Effective flank length.
    trim_flank: int
    #: Reads fetched over the VNTR interval, whether or not they carry a variation. Zero
    #: means no coverage, which an empty ``results`` alone does not distinguish.
    locus_read_count: int
    #: Of those, the reads carrying an indel of at least two bases, which is all the
    #: analysis looks at. At least ``sum(raw_support)``: variations below
    #: ``min_support_var`` are dropped from ``results`` but still counted here.
    indel_read_count: int
    #: The called variations, sorted by ``support`` descending.
    results: list[JsonResult]


def build_json_document(
    *,
    config: Config,
    short_read_results: list[ShortReadResult],
    locus_read_counts: LocusReadCounts,
) -> JsonDocument:
    """Assemble the document from an analysis run and its read counts."""
    return JsonDocument(
        genome_release=config.genome_release,
        input_bam=str(config.input_bam),
        min_support_var=config.min_support_var,
        min_support_consensus=config.min_support_consensus,
        trim_flank=config.trim_flank,
        locus_read_count=locus_read_counts.locus_read_count,
        indel_read_count=locus_read_counts.indel_read_count,
        results=[
            JsonResult(
                var_type=result.repeat_variation.var_type,
                sequence=result.repeat_variation.sequence,
                sequence_transcript=revcomp(result.repeat_variation.sequence),
                length=len(result.repeat_variation.sequence),
                raw_support=result.raw_support,
                support=result.support,
                flank_groups=[
                    JsonFlankGroup(
                        count=group.count,
                        consensus_left=group.consensus_left,
                        consensus_right=group.consensus_right,
                        longest_left=group.longest_left,
                        longest_right=group.longest_right,
                        example_read=group.example_read,
                        reads=[
                            JsonRead(
                                read_name=context.read_name,
                                left_flank=context.left_flank,
                                right_flank=context.right_flank,
                            )
                            for context in group.contexts
                        ],
                    )
                    for group in result.flank_groups
                ],
            )
            for result in short_read_results
        ],
    )


def write_json_document(*, document: JsonDocument, output_path: pathlib.Path) -> None:
    """Write ``document`` to ``output_path`` as one JSON object."""
    output_path.write_text(document.model_dump_json(indent=2) + "\n", encoding="utf-8")
