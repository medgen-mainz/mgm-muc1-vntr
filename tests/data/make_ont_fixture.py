"""Downsample a MUC1 ONT slice to a suite-sized fixture.

Deterministic: reads are ranked by (query length, query name) so the same input always
yields the same fixture. Keeps the 6 shortest reads that span the VNTR interval with the
default 50 bp anchor on both sides, plus the 2 shortest that overlap but do not span, so
both arms of the spanning test are exercised.
"""

import pathlib
import sys

import pysam

from mgm_muc1_vntr.common import VNTR_INTERVALS, GenomeRelease

ANCHOR = 50
N_SPANNING = 6
N_PARTIAL = 2


def main(build: GenomeRelease, src: pathlib.Path, dst: pathlib.Path) -> None:
    interval = VNTR_INTERVALS[build]
    bam = pysam.AlignmentFile(str(src), "rb")
    records = [r for r in bam.fetch(interval.contig, interval.start, interval.end) if r.query_sequence]

    def spans(read: pysam.AlignedSegment) -> bool:
        start = read.reference_start + 1
        end = read.reference_start + (read.reference_length or 0)
        return start < interval.start - ANCHOR and end > interval.end + ANCHOR

    def rank(read: pysam.AlignedSegment) -> tuple[int, str]:
        return (len(read.query_sequence or ""), read.query_name or "")

    spanning = sorted((r for r in records if spans(r)), key=rank)[:N_SPANNING]
    partial = sorted((r for r in records if not spans(r)), key=rank)[:N_PARTIAL]
    keep = sorted(spanning + partial, key=lambda r: (r.reference_start, r.query_name or ""))

    with pysam.AlignmentFile(str(dst), "wb", template=bam) as out:
        for read in keep:
            out.write(read)
    pysam.index(str(dst))
    print(
        f"{dst.name}: {len(spanning)} spanning + {len(partial)} partial = {len(keep)} reads, {dst.stat().st_size} bytes"
    )


if __name__ == "__main__":
    build = sys.argv[1]
    assert build in ("GRCh37", "GRCh38"), f"unknown genome build {build}"
    main(build, pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]))
