"""Code for SRS analysis of MUC1 VNTR."""

import os
import pathlib
import sys
import typing
from collections import Counter

import pydantic
import pysam
from loguru import logger

from mgm_muc1_vntr.common import VNTR_INTERVALS, GenomeRelease, VariantType, revcomp


class Config(pydantic.BaseModel):
    """Configuration for SRS analysis of MUC1 VNTR."""

    #: Path to input BAM file.
    input_bam: pathlib.Path
    #: Genome release to use
    genome_release: GenomeRelease = "GRCh37"
    #: Path to reference genome in FASTA format.
    reference_genome: pathlib.Path
    #: Path to output directory.
    output_dir: pathlib.Path
    #: Minimum support for variant calls.
    min_support_var: int
    #: Flanking region to trim.
    trim_flank: int
    #: Minimum support for consensus calls.
    min_support_consensus: int
    #: Path to write pileup SVG file (optional).
    pileup_svg_path: pathlib.Path | None = None


class RepeatVariation(pydantic.BaseModel):
    """Describe variation in repeat."""

    model_config = pydantic.ConfigDict(frozen=True)

    #: The variation type.
    var_type: VariantType
    #: The inserted/deleted sequence.
    sequence: str


class ContextInformation(pydantic.BaseModel):
    """Collect information about flanks per read."""

    model_config = pydantic.ConfigDict(frozen=True)

    #: Read name.
    read_name: str
    #: Repeat variation.
    repeat_variation: RepeatVariation
    #: The left flank sequence.
    left_flank: str
    #: The right flank sequence.
    right_flank: str


def _new_context_list() -> list["ContextInformation"]:
    """Typed default factory for FlankGroup.contexts."""
    return []


class FlankGroup(pydantic.BaseModel):
    """Group information for reads with similar flanking sequences."""

    model_config = pydantic.ConfigDict(frozen=False)

    #: Number of reads in this group.
    count: int = 0
    #: Longest left flanking sequence seen in this group.
    longest_left: str = ""
    #: Longest right flanking sequence seen in this group.
    longest_right: str = ""
    #: Consensus left flanking sequence (built from the right end, min support 2 per column).
    consensus_left: str = ""
    #: Consensus right flanking sequence (built from the left end, min support 2 per column).
    consensus_right: str = ""
    #: Example read name from this group.
    example_read: str = ""
    #: Contexts that belong to this group (for alignment printing).
    contexts: list[ContextInformation] = pydantic.Field(default_factory=_new_context_list)


class ShortReadResult(pydantic.BaseModel):

    model_config = pydantic.ConfigDict(frozen=True)

    #: Path to BAM file.
    path_bam: str
    #: Repeat variation found.
    repeat_variation: RepeatVariation
    #: Supporting read count.
    raw_support: int
    #: Largest supporting flanking group.
    support: int
    #: Flank groups for this result.
    flank_groups: list[FlankGroup]

    def ref_sequence(self, *, group_idx: int = 0, trim_flank: int) -> str:
        """Get the reference marker sequence for this result for first group.

        When constructed in the code below, will be group with highest support.

        Args:
            trim_flank: If given, trim left/right flanking sequence length.
        """
        return self._seq_helper(is_ref=True, group_idx=group_idx, trim_flank=trim_flank)

    def alt_sequence(self, *, group_idx: int = 0, trim_flank: int) -> str:
        """Get the alternative marker sequence for this result for first group.

        When constructed in the code below, will be group with highest support.

        Args:
            trim_flank: If given, trim left/right flanking sequence length.
        """
        return self._seq_helper(is_ref=False, group_idx=group_idx, trim_flank=trim_flank)

    def _seq_helper(self, *, is_ref: bool, group_idx: int, trim_flank: int | None) -> str:
        # Prefer consensus if available, otherwise fall back to longest.
        left_flank = self.flank_groups[group_idx].consensus_left or self.flank_groups[group_idx].longest_left
        right_flank = self.flank_groups[group_idx].consensus_right or self.flank_groups[group_idx].longest_right
        if trim_flank:
            left_flank = left_flank[-trim_flank:]
            right_flank = right_flank[:trim_flank]
        if is_ref == (self.repeat_variation.var_type == VariantType.INSERTION):
            return f"{left_flank}{right_flank}"
        else:
            ref_seq = self.repeat_variation.sequence
            return f"{left_flank}{ref_seq}{right_flank}"


# Group by 4bp flanks, then build consensus sequences per group (min support 2 per column)
def build_left_consensus(config: Config, left_flanks: list[str]) -> str:
    if not left_flanks:
        return ""
    max_len = max(len(s) for s in left_flanks)
    consensus_rev: list[str] = []  # building from indel outward (right->left)
    for k in range(1, max_len + 1):
        bases: list[str] = []
        for s in left_flanks:
            if len(s) >= k:
                bases.append(s[-k])
        assert bases, "the longest flank contributes a base for every k <= max_len"
        cnt = Counter(bases)
        base, freq = cnt.most_common(1)[0]
        if freq >= config.min_support_consensus:
            consensus_rev.append(base)
        else:
            break
    return "".join(reversed(consensus_rev))


def build_right_consensus(config: Config, right_flanks: list[str]) -> str:
    if not right_flanks:
        return ""
    max_len = max(len(s) for s in right_flanks)
    consensus: list[str] = []  # building from indel outward (left->right)
    for k in range(0, max_len):
        bases: list[str] = []
        for s in right_flanks:
            if len(s) > k:
                bases.append(s[k])
        assert bases, "the longest flank contributes a base for every k <= max_len"
        cnt = Counter(bases)
        base, freq = cnt.most_common(1)[0]
        if freq >= config.min_support_consensus:
            consensus.append(base)
        else:
            break
    return "".join(consensus)


def short_read_analysis(
    *,
    config: Config,
) -> list[ShortReadResult]:
    """Perform short-read analysis for MUC1 VNTR.

    Args:
        config: Configuration for analysis.

    Returns:
        List of results found.
    """
    logger.info("Starting short-read analysis...")
    logger.debug("Using configuration: {config}", config=config.model_dump_json(indent=2))

    rep_var_counter: dict[RepeatVariation, int] = {}
    context_infos: dict[str, list[ContextInformation]] = {}

    logger.debug("Opening BAM file {bam}", bam=config.input_bam)
    with pysam.AlignmentFile(
        str(config.input_bam), mode="rb", reference_filename=str(config.reference_genome)
    ) as bamfile:
        interval = VNTR_INTERVALS[config.genome_release]
        logger.debug("Fetching reads from {itv}", itv=interval)
        for line in bamfile.fetch(contig=interval.contig, start=interval.start, end=interval.end):
            # Skip all but those having indel >= 2
            is_indel_geq_2 = False
            for operation, length in line.cigartuples or []:
                if operation in (pysam.CINS, pysam.CDEL) and length >= 2:
                    is_indel_geq_2 = True
                    break
            else:
                logger.trace("Skipping read {read} without indel >=2", read=line.query_name or "")
                continue  # skip
            assert is_indel_geq_2, "otherwise, skipped above"
            ref_seq = line.get_reference_sequence()
            qry_seq = line.query_sequence
            assert qry_seq is not None, "query sequence must be present"

            # Extract all indel sequences
            ref_pos = 0
            read_pos = 0
            insertions: list[str] = []
            deletions: list[str] = []
            for operation, length in line.cigartuples or []:
                if operation == 1:  # Insertion (I)
                    insertion_seq = qry_seq[read_pos : read_pos + length]
                    insertions.append(insertion_seq)
                    read_pos += length
                elif operation == 2:  # Deletion (D)
                    deletion_seq = ref_seq[ref_pos : ref_pos + length]
                    deletions.append(deletion_seq)
                    ref_pos += length
                elif operation in [
                    pysam.CMATCH,
                    pysam.CREF_SKIP,
                    pysam.CHARD_CLIP,
                    pysam.CSOFT_CLIP,
                ]:
                    read_pos += length if operation in [0, 4, 5] else 0
                    ref_pos += length if operation in [0, 2, 3, 5] else 0

            # Find the position of the indel in the read sequence
            read_pos_at_indel = 0
            for operation, length in line.cigartuples or []:
                if operation == 1:  # Insertion (I)
                    break  # Found the indel position
                elif operation == 2:  # Deletion (D)
                    break  # Found the indel position
                elif operation in [pysam.CMATCH, pysam.CSOFT_CLIP]:
                    read_pos_at_indel += length

            # Extract flanking sequences from the read
            flank_length = config.trim_flank
            left_flank_start = max(0, read_pos_at_indel - flank_length)
            left_flank_end = read_pos_at_indel
            right_flank_start = read_pos_at_indel
            if insertions:  # For insertions, skip the inserted sequence
                right_flank_start += len(insertions[0])
            right_flank_end = min(len(qry_seq), right_flank_start + flank_length)

            left_flank = qry_seq[left_flank_start:left_flank_end]
            right_flank = qry_seq[right_flank_start:right_flank_end]

            # Count the variation.
            if insertions:
                rep_var = RepeatVariation(var_type=VariantType.INSERTION, sequence=insertions[0])
            else:
                rep_var = RepeatVariation(var_type=VariantType.DELETION, sequence=deletions[0])
            rep_var_counter[rep_var] = rep_var_counter.get(rep_var, 0) + 1

            # Collect context information
            context_info = ContextInformation(
                read_name=line.query_name or "",
                repeat_variation=rep_var,
                left_flank=left_flank,
                right_flank=right_flank,
            )
            logger.trace("Found variant {var}", var=context_info.model_dump_json(indent=2))

            # Store context information grouped by variation sequence
            var_key = f"{rep_var.var_type.value}:{rep_var.sequence}"
            if var_key not in context_infos:
                context_infos[var_key] = []
            context_infos[var_key].append(context_info)
    logger.debug("Found {num_vars} unique repeat variations", num_vars=len(rep_var_counter))

    # Build result for all variations with count >= min_support.
    logger.info("Building results for variants with sufficient support...")
    result: list[ShortReadResult] = []
    for rep_var, count in rep_var_counter.items():
        if count >= config.min_support_var:
            # Dump context information for this variant
            var_key = f"{rep_var.var_type.value}:{rep_var.sequence}"
            if var_key in context_infos:
                contexts = context_infos[var_key]
                contexts.sort(key=lambda x: (x.left_flank, x.read_name))
                # First accumulate contexts per group key
                grouped_contexts: dict[tuple[str, str], list[ContextInformation]] = {}
                for ctx in contexts:
                    left_flank_short = ctx.left_flank[-4:]
                    right_flank_short = ctx.right_flank[:4]
                    flank_key = (left_flank_short, right_flank_short)
                    grouped_contexts.setdefault(flank_key, []).append(ctx)
                # Build FlankGroup objects with consensus sequences
                flank_groups: dict[tuple[str, str], FlankGroup] = {}
                for flank_key, ctxs in grouped_contexts.items():
                    lefts = [c.left_flank for c in ctxs]
                    rights = [c.right_flank for c in ctxs]
                    # Determine longest flanks and example read (from longest left)
                    longest_left_ctx = max(ctxs, key=lambda c: len(c.left_flank))
                    longest_right_ctx = max(ctxs, key=lambda c: len(c.right_flank))
                    group = FlankGroup(
                        count=len(ctxs),
                        longest_left=longest_left_ctx.left_flank,
                        longest_right=longest_right_ctx.right_flank,
                        consensus_left=build_left_consensus(config, lefts),
                        consensus_right=build_right_consensus(config, rights),
                        example_read=longest_left_ctx.read_name,
                        contexts=list(ctxs),
                    )
                    flank_groups[flank_key] = group
                short_read_result = ShortReadResult(
                    path_bam=str(config.input_bam),
                    repeat_variation=rep_var,
                    raw_support=count,
                    support=max([group.count for group in flank_groups.values()]),
                    flank_groups=list(flank_groups.values()),
                )
                logger.trace("Built short-read result {res}", res=short_read_result.model_dump_json(indent=2))
                result.append(short_read_result)

    result.sort(
        key=lambda x: x.support,
        reverse=True,
    )
    logger.debug("Found {num_results} results with sufficient support", num_results=len(result))

    # Generate SVG pileup if path is provided
    if config.pileup_svg_path:
        logger.info("Generating SVG pileup visualization...")
        generate_pileup_svg(
            short_read_results=result,
            min_support_consensus=config.min_support_consensus,
            output_path=config.pileup_svg_path,
        )

    logger.info("Short-read analysis completed.")
    return result


def print_short_read_result_header():
    print(
        ",".join(
            [
                "Filename",
                "Variant_Type",
                "Variant_Sequence",
                "Raw_Support",
                "Support",
                "Full_Path",
            ]
        )
    )


def print_short_read_result(
    *, short_read_result: ShortReadResult, min_support_consensus: int, file: typing.TextIO | None = None
):
    # Resolved per call: as a default it would bind the `sys.stdout` live at import time.
    file = file or sys.stdout
    print(
        ",".join(
            map(
                str,
                [
                    os.path.basename(short_read_result.path_bam),
                    short_read_result.repeat_variation.var_type.value,
                    # Sequence is in transcript orientation (revcomp).
                    revcomp(short_read_result.repeat_variation.sequence),
                    short_read_result.raw_support,
                    short_read_result.support,
                    short_read_result.path_bam,
                ],
            )
        ),
        file=file,
    )


def print_short_read_pileups(
    *, short_read_result: ShortReadResult, min_support_consensus: int, file: typing.TextIO | None = None
):
    # Resolved per call: as a default it would bind the `sys.stdout` live at import time.
    file = file or sys.stdout
    for group_idx, group in enumerate(short_read_result.flank_groups):
        _ = group_idx
        if group.count >= min_support_consensus:
            rep_var = short_read_result.repeat_variation
            # Header summary line
            print(
                (
                    f"#  {group.example_read} {group.count:4} | "
                    f"{(group.consensus_left or group.longest_left)} "
                    f"[ {rep_var.sequence} ] "
                    f"{(group.consensus_right or group.longest_right)}"
                ),
                file=file,
            )

            # Render alignment with consensus on top and reads below.
            cons_left = group.consensus_left or group.longest_left
            cons_right = group.consensus_right or group.longest_right

            # Left side: right-align at the variant boundary
            max_left = max([len(cons_left)] + [len(ctx.left_flank) for ctx in group.contexts])
            # Right side: left-align at the variant boundary
            max_right = max([len(cons_right)] + [len(ctx.right_flank) for ctx in group.contexts])

            def pad_left(max_left: int, s: str) -> str:
                return " " * (max_left - len(s)) + s

            def pad_right(max_right: int, s: str) -> str:
                return s + " " * (max_right - len(s))

            def highlight_left(max_left: int, s: str, consensus: str) -> str:
                # Right-align, compare from right
                s_pad = s.rjust(max_left)
                cons_pad = consensus.rjust(max_left)
                out: list[str] = []
                for base, cons_base in zip(s_pad, cons_pad, strict=False):
                    if base == " ":
                        out.append(" ")
                    elif base.upper() == cons_base.upper():
                        out.append(base.upper())
                    else:
                        # Dark gray ANSI for deviation
                        out.append(f"\033[90m{base.lower()}\033[0m")
                return "".join(out)

            def highlight_right(max_right: int, s: str, consensus: str) -> str:
                # Left-align, compare from left
                s_pad = s.ljust(max_right)
                cons_pad = consensus.ljust(max_right)
                out: list[str] = []
                for base, cons_base in zip(s_pad, cons_pad, strict=False):
                    if base == " ":
                        out.append(" ")
                    elif base.upper() == cons_base.upper():
                        out.append(base.upper())
                    else:
                        # Dark gray ANSI for deviation
                        out.append(f"\033[90m{base.lower()}\033[0m")
                return "".join(out)

            # Consensus line
            print(
                (
                    "## CONS "
                    + pad_left(max_left, cons_left)
                    + f" [ {rep_var.sequence} ] "
                    + pad_right(max_right, cons_right)
                ),
                file=file,
            )

            # Each read line, sorted so that leading whitespace increases from top to bottom
            sorted_contexts = sorted(
                group.contexts,
                key=lambda c: (-len(c.left_flank), c.read_name),
            )
            for ctx in sorted_contexts:
                print(
                    "##   r  "
                    + highlight_left(max_left, ctx.left_flank, cons_left)
                    + f" [ {rep_var.sequence} ] "
                    + highlight_right(max_right, ctx.right_flank, cons_right),
                    file=file,
                )


#: Font stack for the pileup SVG. Every family listed advances 0.6 em per glyph, which is
#: what cairo's "Courier" resolved to, so the glyph grid is unchanged.
PILEUP_FONT_FAMILY = "DejaVu Sans Mono, Liberation Mono, Courier New, Courier, monospace"

#: Advance width per character, in ems, for every family in :data:`PILEUP_FONT_FAMILY`.
PILEUP_ADVANCE_EM = 0.6


def _svg_escape(text: str) -> str:
    """Escape ``text`` for use as XML character data."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generate_pileup_svg(
    *,
    short_read_results: list[ShortReadResult],
    min_support_consensus: int,
    output_path: pathlib.Path,
) -> None:
    """Generate an SVG visualization of pileups for short read results.

    Args:
        short_read_results: List of short read results to visualize.
        min_support_consensus: Minimum support threshold for consensus.
        output_path: Path where SVG file should be written.
    """
    if not short_read_results:
        logger.warning("No short read results to visualize")
        return

    # SVG dimensions and styling
    font_size = 12
    line_height = 16
    margin = 20
    char_width = 8  # Approximate character width for monospace font

    # Calculate total height needed
    total_height = margin
    for result in short_read_results:
        for group in result.flank_groups:
            if group.count >= min_support_consensus:
                # Height for header info (7 lines), gap, consensus line, and each read line
                total_height += line_height * (7 + 1 + 1 + len(group.contexts)) + margin

    # Calculate width needed (find longest line)
    max_width = 0
    for result in short_read_results:
        for group in result.flank_groups:
            if group.count >= min_support_consensus:
                cons_left = group.consensus_left or group.longest_left
                cons_right = group.consensus_right or group.longest_right
                max_left = max([len(cons_left)] + [len(ctx.left_flank) for ctx in group.contexts])
                max_right = max([len(cons_right)] + [len(ctx.right_flank) for ctx in group.contexts])

                # Estimate line width: left + variant + right + extra text
                line_width = max_left + len(result.repeat_variation.sequence) + max_right + 20
                max_width = max(max_width, line_width)

    svg_width = max_width * char_width + 2 * margin
    svg_height = total_height + margin

    advance = font_size * PILEUP_ADVANCE_EM
    lines: list[str] = []

    def emit(text: str, y: float, fill: str) -> None:
        """Append one line of monospace text on the character grid.

        ``xml:space`` is required: the alignment relies on the padding produced by
        ``rjust``/``ljust``, and SVG collapses leading and repeated spaces without it.
        ``textLength`` pins the line to an exact multiple of the advance width so the
        columns survive a viewer substituting a font whose advance is not 0.6 em.
        """
        lines.append(
            f'<text x="{margin}" y="{y:g}" fill="{fill}" '
            f'textLength="{len(text) * advance:g}" lengthAdjust="spacing" '
            f'xml:space="preserve">{_svg_escape(text)}</text>'
        )

    y_pos = margin + font_size

    for result in short_read_results:
        for group in result.flank_groups:
            if group.count >= min_support_consensus:
                rep_var = result.repeat_variation
                cons_left = group.consensus_left or group.longest_left
                cons_right = group.consensus_right or group.longest_right

                # Extract filename from path
                filename = os.path.basename(result.path_bam)

                header_lines = [
                    f"Filename: {filename}",
                    f"Variant_Type: {rep_var.var_type.value}",
                    f"Variant_Sequence: {rep_var.sequence}",
                    f"Raw_Support: {result.raw_support}",
                    f"Support: {result.support}",
                    f"Group_Count: {group.count}",
                    f"Example_Read: {group.example_read}",
                ]

                for header_line in header_lines:
                    emit(header_line, y_pos, "#333333")  # Dark gray
                    y_pos += line_height

                y_pos += line_height // 2  # Small gap before alignment

                # Calculate alignment parameters
                max_left = max([len(cons_left)] + [len(ctx.left_flank) for ctx in group.contexts])
                max_right = max([len(cons_right)] + [len(ctx.right_flank) for ctx in group.contexts])

                # Consensus line
                cons_text = f"CONS {cons_left.rjust(max_left)} [ {rep_var.sequence} ] {cons_right.ljust(max_right)}"
                emit(cons_text, y_pos, "#0000cc")  # Blue for consensus
                y_pos += line_height

                # Read lines
                sorted_contexts = sorted(group.contexts, key=lambda c: (-len(c.left_flank), c.read_name))
                for context in sorted_contexts:
                    read_text = (
                        f"r    {context.left_flank.rjust(max_left)} [ {rep_var.sequence} ] "
                        f"{context.right_flank.ljust(max_right)}"
                    )
                    emit(read_text, y_pos, "#666666")  # Gray for reads
                    y_pos += line_height

                y_pos += margin // 2  # Extra space between groups

    body = "\n".join(lines)
    output_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width:g}" height="{svg_height:g}" '
        f'viewBox="0 0 {svg_width:g} {svg_height:g}">\n'
        f'<g font-family="{PILEUP_FONT_FAMILY}" font-size="{font_size}">\n'
        f"{body}\n"
        "</g>\n"
        "</svg>\n",
        encoding="utf-8",
    )
    logger.info(f"SVG pileup visualization saved to {output_path}")
