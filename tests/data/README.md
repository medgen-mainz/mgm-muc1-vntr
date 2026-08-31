# Test fixtures

Everything here is stored via Git LFS and negated by name in `.gitignore`, so adding a
fixture is always a deliberate act. A checkout without `git lfs` installed leaves pointer
files behind and any test that opens one will fail.

## Coordinates

MUC1 gene spans, derived as the minimum exon start and maximum exon end across every
RefSeq transcript of the gene, so each interval covers all annotated isoforms. Annotation
coordinates are 0-based half-open; the regions below are the same bounds used as 1-based
inclusive `samtools` regions, which keeps one extra base of flank at the 5' end.

| build | contig | region | length | transcripts |
| --- | --- | --- | --- | --- |
| GRCh37 | `1` | `1:155158299-155162768` | 4,470 bp | 57 |
| GRCh38 | `chr1` | `chr1:155185823-155192915` | 7,093 bp | 38 |

Both contain the VNTR interval hardcoded in `src/mgm_muc1_vntr/common.py`. The GRCh38 span
is the wider of the two because that annotation carries more extended isoforms; this is
not an error.

## `NA24149_MUC1_SRS.bam`, `.bam.bai`

The MUC1 gene sliced from **NA24149**, also known as **HG003**, the father of the Genome in
a Bottle Ashkenazi trio. A public reference sample, which is what makes it publishable
here. The read group is preserved, so the file identifies itself as `SM:NA24149_N02`.

Short reads from an exome with spike-in, aligned to GRCh37 with bwa-mem. Not WGS, so
coverage over MUC1 is a property of the capture: 23,102 reads, mean depth 428x across the
gene and 2,072x across the VNTR interval.

```bash
samtools view -b -o NA24149_MUC1_SRS.bam "$SRC_BAM" 1:155158299-155162768
samtools index NA24149_MUC1_SRS.bam
```

## `GRCh37_1_MUC1_masked.fa.gz`, `GRCh38_chr1_MUC1_masked.fa.gz`

One contig each, at its **full original length**, with every base outside the MUC1 region
set to `N`. Keeping the full length is the point: reference coordinates stay valid, so a
BAM aligned against the real reference can be read against these without any translation.

They are **bgzip** compressed, not plain gzip. `pysam.FastaFile` and `samtools faidx`
refuse a plain-gzip FASTA outright, and bgzip output is still a valid `.gz`, so this costs
about 26% in size and buys direct random access. The `.fai` and `.gzi` indexes are derived
and gitignored; regenerate with `samtools faidx <file>`.

To rebuild, take the region from a full reference for the matching build, then re-emit the
contig with the region in place and `N` everywhere else, preserving the contig name and
length. Verify by fetching the region back out and comparing it to the source reference.
