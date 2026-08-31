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

These are the regions the real fixtures are sliced to. The masked references retain a block
derived from them and not the span itself, which for GRCh37 is wider; see the table under
the masked references below.

## What each fixture is

Sizes and counts are of the committed files. "Reference" is what the reads were aligned
against, which is not the same thing as what a test reads them back with: the analysis only
needs a reference whose coordinates agree, which is the whole point of the masked ones.

| fixture | bytes | records | read length | build | contig | mapped | aligned against |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `NA24149_MUC1_SRS.bam` | 3,640,753 | 23,102 | 150 bp | GRCh37 | `1`, 84 `@SQ` | 85.70% | a full GRCh37, bwa-mem 0.7.17-r1188 |
| `HG003_MUC1_GRCh37_ONT.bam` | 33,572 | 8 | 3,038 to 5,010 bp | GRCh37 | `1`, 86 `@SQ` | 100.00% | a full GRCh37 (`hs37d5`), minimap2 2.17-r941 |
| `HG003_MUC1_GRCh38_ONT.bam` | 68,608 | 8 | 1,482 to 11,932 bp | GRCh38 | `chr1`, 195 `@SQ` | 100.00% | a full GRCh38, minimap2 2.17-r941 |
| `synth_insCCCC.bam` | 563,794 | 20,000 | 150 bp | GRCh37 | `1`, 1 `@SQ` | 100.00% | `GRCh37_1_MUC1_masked.fa.gz`, bwa-mem 0.7.19-r1273 |
| `synth_insCCC_benign.bam` | 561,800 | 20,000 | 150 bp | GRCh37 | `1`, 1 `@SQ` | 100.00% | `GRCh37_1_MUC1_masked.fa.gz`, bwa-mem 0.7.19-r1273 |
| `synth_dupC.bam` | 560,533 | 20,000 | 150 bp | GRCh37 | `1`, 1 `@SQ` | 100.00% | `GRCh37_1_MUC1_masked.fa.gz`, bwa-mem 0.7.19-r1273 |
| `GRCh37_1_MUC1_masked.fa.gz` | 938,666 | contig `1`, 249,250,621 bp | | GRCh37 | `1` | | |
| `GRCh38_chr1_MUC1_masked.fa.gz` | 928,311 | contig `chr1`, 248,956,422 bp | | GRCh38 | `chr1` | | |

Read lengths are over primary records; the real fixtures also carry secondary and
supplementary alignments, whose clipped `SEQ` is shorter.

No committed file records a path from the machine that made it. The synthetic BAMs would:
`bwa` and `samtools` write their command line verbatim into `@PG`, so
`make_synthetic_fixtures.sh` rewrites those to bare file names before the BAM lands here.
Check with `samtools view -H --no-PG <bam> | grep /` after regenerating anything.

## `NA24149_MUC1_SRS.bam`, `.bam.bai`

The MUC1 gene sliced from **NA24149**, also known as **HG003**, the father of the Genome in
a Bottle Ashkenazi trio. A public reference sample, which is what makes it publishable
here. The read group is preserved, so the file identifies itself as `SM:NA24149_N02`.

Short reads from an exome with spike-in, aligned to a full GRCh37 with bwa-mem before
slicing, so the header keeps all 84 `@SQ` lines and 14.30% of the records are unmapped
mates. Not WGS, so coverage over MUC1 is a property of the capture: 23,102 reads, mean
depth 428x across the gene and 2,072x across the VNTR interval.

The cut is the GRCh37 gene span from the table above, taken from the donor's aligned BAM
with no filtering and no re-alignment:

```bash
samtools view -b -o NA24149_MUC1_SRS.bam "$SRC_BAM" 1:155158299-155162768
samtools index NA24149_MUC1_SRS.bam
```

## `GRCh37_1_MUC1_masked.fa.gz`, `GRCh38_chr1_MUC1_masked.fa.gz`

One contig each, at its **full original length**, with every base outside the retained
block set to `N`. Keeping the full length is the point: reference coordinates stay valid,
so a BAM aligned against the real reference can be read against these without any
translation.

| file | contig | length | retained | header |
| --- | --- | --- | --- | --- |
| `GRCh37_1_MUC1_masked.fa.gz` | `1` | 249,250,621 bp | `1:155148299-155172768`, 24,470 bp | `>1 masked: only 1:155148299-155172768 (MUC1) retained, remainder set to N` |
| `GRCh38_chr1_MUC1_masked.fa.gz` | `chr1` | 248,956,422 bp | `chr1:155185823-155192915`, 7,093 bp | `>chr1 masked: only chr1:155185823-155192915 (MUC1) retained, remainder set to N` |

GRCh37 retains the gene span **plus 10 kb of flank each side** rather than the gene span
alone. The three `synth_*` fixtures are aligned against this file and MucOneUp emits about
10 kb of flank per haplotype; against the bare gene span that flank had nowhere to map and
roughly 70% of every synthetic read pair went unmapped. With the wider block they map in
full. GRCh38 keeps the bare gene span because nothing is aligned against it.

They are **bgzip** compressed, not plain gzip. `pysam.FastaFile` and `samtools faidx`
refuse a plain-gzip FASTA outright, and bgzip output is still a valid `.gz`, so this costs
about 26% in size and buys direct random access. The `.fai` and `.gzi` indexes are derived
and gitignored; regenerate with `samtools faidx <file>`.

To rebuild, take the retained region out of a full reference for the matching build, such
as `hs37d5.fa` for GRCh37, then re-emit the contig with the region in place and `N`
everywhere else, at the original contig name and length, 60 bases per line, and compress
with `bgzip`. Verify by fetching the region back out and comparing it to the source
reference; when replacing an existing file, also compare the block it already retained,
which has to come back byte-identical.

## `HG003_MUC1_{GRCh37,GRCh38}_ONT.bam`, `.bam.bai`

Long reads for the **same donor** as the short-read fixture: HG003, also NA24149. From the
GIAB `UCSC_Ultralong_OxfordNanopore_Promethion` release,
`HG003_{GRCh37,GRCh38}_ONT-UL_UCSC_20200508.bam`. PromethION R9.4.1, basecalled with guppy
3.2.5; the read groups are preserved, so the files identify themselves as `SM:HG003`.

One per build, because they are the only fixtures that exercise the GRCh38 arm of
`VNTR_INTERVALS` and `GRCh38_chr1_MUC1_masked.fa.gz` against real data.

They are **remote slices, not downloads**. The sources are about 330 GB each, so fetch only
the published `.bai` and let `samtools view -X` read the regions over HTTPS. The regions are
the MUC1 spans from the table above:

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

The downsampling rule, in full: of the records overlapping the VNTR interval that carry a
sequence, rank every one by `(query length, query name)`, then keep the 6 shortest that
span the interval with the default 50 bp anchor on both sides and the 2 shortest that
overlap without spanning. Both arms of the spanning test are therefore real reads. The
`(length, name)` rank is a total order over the input, so the output is byte-reproducible.
The script is `tests/data/make_ont_fixture.py`:

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
samtools then dies with `libncurses.so.5: cannot open shared object file`. Any conda-family
front end will do; an ad hoc one-off environment such as
`pixi exec --spec bwa -c bioconda -c conda-forge -- bwa ...` also works and creates no
project environment or second lockfile.

**Versions behind the committed fixtures.** A mutable tag is not provenance, so the commit
is recorded alongside it:

| tool | version |
| --- | --- |
| MucOneUp | 0.44.4, commit `7db048f226392ed25cacb732ca5c1d88d4343350` |
| bwa | 0.7.19-r1273 |
| wgsim | 1.19.2 |
| samtools | 1.19.2, htslib 1.19 |

### How they are generated

**Haplotypes.** MucOneUp simulates a diploid pair from the `config.json` in its own
repository, which carries the MUC1 repeat units and the flanks and ships only in the git
tree, not in the wheel, so the tag is cloned as well as installed. Both haplotypes get
`--fixed-lengths 60`, 60 VNTR repeats each, on `--reference-assembly hg19` flanks.
`--mutation-name normal,<mutation>` writes the pair as one normal member and one mutated
member, and `--mutation-targets 1,25` puts the mutation on haplotype 1, repeat 25, leaving
haplotype 2 untouched. Every fixture is therefore heterozygous, which is what the real
allele is. Repeat 25 is chosen because it is an `X` unit and these mutations are only
defined on that unit. The simulator seed is `7`.

**Reads.** `wgsim` draws 10,000 read pairs of 150 bp per end from the mutated haplotype
file, seed `42`, with `-e 0 -r 0 -R 0 -X 0`: no base error, no wgsim-injected substitutions,
no wgsim-injected indels. That is the point of the fixture. With error switched on, an indel
in the BAM could come from read noise instead of the simulated haplotype and the expected
support count would stop being derivable by construction.

**Alignment.** `bwa mem -t 4` against `GRCh37_1_MUC1_masked.fa.gz`, gunzipped, then
`samtools sort` and `samtools index`. The `@PG` command lines are rewritten to bare file
names before the BAM is written into this directory.

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
