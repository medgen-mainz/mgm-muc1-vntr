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

## `HG003_MUC1_{GRCh37,GRCh38}_ONT.bam`, `.bam.bai`

Long reads for the **same donor** as the short-read fixture: HG003, also NA24149. From the
GIAB `UCSC_Ultralong_OxfordNanopore_Promethion` release,
`HG003_{GRCh37,GRCh38}_ONT-UL_UCSC_20200508.bam`. PromethION R9.4.1, basecalled with guppy
3.2.5; the read groups are preserved, so the files identify themselves as `SM:HG003`.

One per build, because they are the only fixtures that exercise the GRCh38 arm of
`VNTR_INTERVALS` and `GRCh38_chr1_MUC1_masked.fa.gz` against real data.

The sources are about 330 GB each, so slice them remotely against the published index
rather than downloading. The regions are the MUC1 spans from the table above:

```bash
URL=https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/data/AshkenazimTrio/HG003_NA24149_father/UCSC_Ultralong_OxfordNanopore_Promethion
curl -sO "$URL/HG003_GRCh37_ONT-UL_UCSC_20200508.bam.bai"
samtools view -b -X -o gene_GRCh37.bam \
  "$URL/HG003_GRCh37_ONT-UL_UCSC_20200508.bam" \
  HG003_GRCh37_ONT-UL_UCSC_20200508.bam.bai "1:155158299-155162768"
```

That takes about 5 seconds per build and yields 5 to 6 MB. It is then **downsampled**,
because the full gene slice is not suite-sized: `long_read_analysis` prints a whole
pairwise alignment per read, and ultralong reads reach 156 kb, so a slice of 231 records
takes 11 seconds and emits 17 MB on stdout.

Downsampling keeps the 6 shortest reads that span the VNTR interval with the default 50 bp
anchor on both sides, plus the 2 shortest that overlap without spanning, so both arms of
the spanning test are real reads. Reads are ranked by `(length, name)`, which makes the
output byte-reproducible. The script is `tests/data/make_ont_fixture.py`:

```bash
python tests/data/make_ont_fixture.py GRCh37 gene_GRCh37.bam HG003_MUC1_GRCh37_ONT.bam
```

| fixture | size | records | `long_read_analysis` |
| --- | --- | --- | --- |
| `HG003_MUC1_GRCh37_ONT.bam` | 33 KB | 8 | 0.05 s |
| `HG003_MUC1_GRCh38_ONT.bam` | 69 KB | 8 | 0.11 s |

Note the GRCh37 gene slice contains a secondary alignment with `SEQ=*`, for which
`query_sequence` is `None` and the `assert read_sequence` in `long_read_analysis` fires. It
lies outside the VNTR interval, so the fetch never reaches it, and the downsampling drops
it along with every other record without a sequence.
## `synth_insCCCC.bam`, `synth_insCCC_benign.bam`, `synth_dupC.bam`

Simulated MUC1 haplotypes with a known variant, so the expected analysis result is known
by construction rather than characterised after the fact. Regenerate with

```
tests/data/make_synthetic_fixtures.sh
```

The tools it needs are not in `uv.lock`. bwa, samtools and wgsim are bioconda-only and have
no PyPI distribution, so the `fixtures` pixi environment that used to supply them went with
pixi in #38. Put them on `PATH` first, from a conda-family environment or your distribution,
and install the simulator:

```
micromamba create -n muc1-fixtures -c conda-forge -c bioconda bwa samtools wgsim
uv tool install git+https://github.com/berntpopp/MucOneUp.git@v0.44.4
```

Channel order is load-bearing: `-c bioconda -c conda-forge` resolves an ancient ncurses and
samtools then dies with `libncurses.so.5: cannot open shared object file`.

`pixi.lock` used to record the simulator commit behind the tag, which a mutable tag does not.
It is `7db048f226392ed25cacb732ca5c1d88d4343350`; check it out explicitly if a regenerated
fixture has to be traceable to an exact MucOneUp version.

Each is heterozygous: MucOneUp mutates haplotype 1 of a diploid pair and leaves haplotype
2 alone. 60 repeats per haplotype, hg19 flanks, 10,000 read pairs of 150 bp from `wgsim`
with error and variant injection switched off, aligned with `bwa mem` against
`GRCh37_1_MUC1_masked.fa.gz`.

| fixture | mutation | Δbp | frameshift | analysis finds it |
| --- | --- | --- | --- | --- |
| `synth_insCCCC` | `insCCCC` | +4 | yes | yes, `ins` of 4 bp, support 63 |
| `synth_insCCC_benign` | `insCCC_benign` | +3 | no | yes, `ins` of 3 bp, support 57 |
| `synth_dupC` | `dupC` | +1 | yes | **no**, see below |

Called sequences are the reverse complement of what MucOneUp inserts, `GGGG` for an
inserted `CCCC`, because MUC1 is on the minus strand and the analysis reports in reference
orientation.

`synth_dupC` documents a limitation rather than a capability. `short_read_analysis` skips
any read without an indel of at least 2 bp, and dupC is a single base insertion, so all 60
supporting reads are discarded before being counted. The pathogenic ADTKD-MUC1 allele is
exactly this variant. The test asserts the current behaviour and is meant to fail when the
filter is fixed.

`bwa` rather than `minimap2`: `NA24149_MUC1_SRS.bam` was aligned with bwa-mem, so the
fixtures share its provenance. On identical reads minimap2 also called a 48 bp deletion
that bwa does not, which would have been baked into expected output. bwa also emits MD
tags by default, which the analysis requires through `pysam`'s
`get_reference_sequence()`.

### MucOneUp

The haplotypes come from MucOneUp, which is not a dependency of this project.

- Repository: <https://github.com/berntpopp/MucOneUp> (MIT), pinned at `v0.44.4`
- Software: Popp B. *MucOneUp*. doi:[10.5281/zenodo.19740405](https://doi.org/10.5281/zenodo.19740405)
- Paper: Popp B, Saei H. *MucOneUp: A Simulation Framework for MUC1-VNTR Variant
  Benchmarking*. bioRxiv, 12 May 2026.
  doi:[10.64898/2026.05.08.723876](https://doi.org/10.64898/2026.05.08.723876)
