[![CI](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml/badge.svg)](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml)

# MGM-MUC1-VNTR

MUC1 VNTR analysis for short-read and long-read sequencing data.

- Python: 3.13+
- License: MIT
- Made: with ❤️ at [Limbach Genetics, Medizinische Genetik Mainz](https://www.medgen-mainz.de/)

> **Synthetic test data comes from [MucOneUp](https://github.com/berntpopp/MucOneUp).** The
> `synth_*` fixtures in `tests/data` are simulated MUC1 haplotypes carrying a named variant,
> so their expected result is known by construction rather than characterised after the
> fact. MucOneUp is not a dependency of this project; it produced files committed here. See
> [Test data](#test-data) for the citation.

## Quick start

Every example below runs against files committed to this repository, so there is no
reference genome to fetch and no data to supply. You need `git lfs`, or the fixtures arrive
as pointer files and every run fails with `file does not contain alignment data`.

```
git clone git@github.com:medgen-mainz/mgm-muc1-vntr.git
cd mgm-muc1-vntr
uv run mgm-muc1-vntr run \
    --short-read-bam tests/data/synth_insCCCC.bam \
    --short-read-reference tests/data/GRCh37_1_MUC1_masked.fa.gz \
    --quiet
```

```
Filename,Variant_Type,Variant_Sequence,Raw_Support,Support,Full_Path
synth_insCCCC.bam,ins,CCCC,63,63,tests/data/synth_insCCCC.bam
```

A four base insertion seen in 63 reads. Four is not a multiple of three, so it shifts the
reading frame.

## Worked examples

Real output from the committed fixtures. `--quiet` keeps the logs out of the way; they go to
stderr, so `2>/dev/null` works too.

### A real sample

NA24149, also known as HG003, the father of the Genome in a Bottle Ashkenazi trio:

```
uv run mgm-muc1-vntr run \
    --short-read-bam tests/data/NA24149_MUC1_SRS.bam \
    --short-read-reference tests/data/GRCh37_1_MUC1_masked.fa.gz \
    --quiet
```

```
Filename,Variant_Type,Variant_Sequence,Raw_Support,Support,Full_Path
NA24149_MUC1_SRS.bam,del,CCGGCCCCGGGCTCCACC,3,3,tests/data/NA24149_MUC1_SRS.bam
```

| column | meaning |
| --- | --- |
| `Filename` | basename of the input BAM |
| `Variant_Type` | `ins` or `del`, relative to the reference |
| `Variant_Sequence` | the inserted or deleted bases, in transcript orientation |
| `Raw_Support` | reads carrying this exact repeat variation |
| `Support` | reads in the largest flanking-context group |
| `Full_Path` | the input path as given |

Three things to know before reading a row.

**`Raw_Support` is the filtered column, not `Support`.** `--min-support-var` is compared
against `Raw_Support`. `Support` counts only the reads that additionally agree on the
sequence surrounding the variant, so it is always less than or equal to `Raw_Support` and is
the stronger signal, but it is not what decides whether a row appears at all.

**Orientation.** MUC1 lies on the minus strand. The analysis works in reference orientation
and reports in transcript orientation, so the printed sequence is the reverse complement of
the one that was matched. The deletion above is `GGTGGAGCCCGGGGCCGG` against the reference.

**The reading frame is yours to check.** There is no frameshift column. Take
`len(Variant_Sequence) % 3`: zero is in frame, anything else shifts it. Here 18 divides by
three, so this call is in frame.

Note that both support values equal 3, which is exactly the default `--min-support-var`.
Against roughly 2000x coverage over the VNTR that is an allele fraction well under one
percent. A row appearing does not by itself mean the variant is real.

### Synthetic samples, where the answer is known in advance

These two differ only in the length of the insertion, which is the distinction that matters
clinically:

```
uv run mgm-muc1-vntr run --quiet \
    --short-read-reference tests/data/GRCh37_1_MUC1_masked.fa.gz \
    --short-read-bam tests/data/synth_insCCCC.bam

uv run mgm-muc1-vntr run --quiet \
    --short-read-reference tests/data/GRCh37_1_MUC1_masked.fa.gz \
    --short-read-bam tests/data/synth_insCCC_benign.bam
```

```
synth_insCCCC.bam,ins,CCCC,63,63,tests/data/synth_insCCCC.bam
synth_insCCC_benign.bam,ins,CCC,57,57,tests/data/synth_insCCC_benign.bam
```

Four bases shift the frame, three do not. Both are heterozygous with similar support, so the
support figures do not separate them and the length is what you read.

### The variant this tool cannot see yet

`synth_dupC` carries a single cytosine insertion, the pathogenic ADTKD-MUC1 allele:

```
uv run mgm-muc1-vntr run --quiet \
    --short-read-reference tests/data/GRCh37_1_MUC1_masked.fa.gz \
    --short-read-bam tests/data/synth_dupC.bam
```

```
(no rows)
```

Nothing is reported, at any support threshold. The read filter discards any read whose
largest indel is shorter than 2 bp, so all 60 supporting reads are dropped before they can be
counted.

**Empty output does not mean the sample is negative.** It means either that nothing cleared
`--min-support-var`, or that the variant is of a kind this tool does not yet detect. This
fixture exists to keep that limitation visible rather than buried.

### Long reads alongside short reads

The long-read mode takes the short-read call and shows you the same locus in long reads.
Short reads here are GRCh37 and long reads GRCh38, which the defaults already assume:

```
uv run mgm-muc1-vntr run --quiet \
    --short-read-bam tests/data/NA24149_MUC1_SRS.bam \
    --short-read-reference tests/data/GRCh37_1_MUC1_masked.fa.gz \
    --long-read-bam tests/data/HG003_MUC1_GRCh38_ONT.bam \
    --long-read-reference tests/data/GRCh38_chr1_MUC1_masked.fa.gz \
    > run.txt
```

```
Filename,Variant_Type,Variant_Sequence,Raw_Support,Support,Full_Path
NA24149_MUC1_SRS.bam,del,CCGGCCCCGGGCTCCACC,3,3,tests/data/NA24149_MUC1_SRS.bam
Filename,Total_Reads,Spanning_Reads,Alt_Reads,Full_Path
HG003_MUC1_GRCh38_ONT.bam,8,6,8,tests/data/HG003_MUC1_GRCh38_ONT.bam
```

Both fixtures are the same donor, which is what makes the pairing meaningful.

| column | meaning |
| --- | --- |
| `Total_Reads` | reads fetched over the VNTR interval |
| `Spanning_Reads` | reads crossing the whole interval with the anchor clear on both sides |
| `Alt_Reads` | reads presented for inspection |

**`Alt_Reads` is not a variant call, and always equals `Total_Reads`.** The long-read mode is
a review aid: it prints a full pairwise alignment for every read so that a person can look at
the locus and decide. At nanopore error rates no automatic call is reliable. An exact match
of the variant marker occurs in none of these reads, and comparing alignment scores against
the reference and variant sequences separates them by a margin indistinguishable from noise.

So the alignments on standard output are the product and the CSV is only a summary. They are
large, roughly 200 kB for these eight fixture reads and tens of megabytes for a real gene
slice, which is why the command above redirects to a file. Add `--print-details` to list the
read names.

### Pileups

`--print-pileups` shows the reads behind a call, aligned on the variant:

```
uv run mgm-muc1-vntr run --quiet --print-pileups \
    --short-read-reference tests/data/GRCh37_1_MUC1_masked.fa.gz \
    --short-read-bam tests/data/synth_insCCCC.bam
```

Truncated on the right here; the real lines are about 300 characters wide and carry
`[ GGGG ]` in the middle, with the variant in reference orientation:

```
#  haplotype_1_11487_11991_0:0:0_0:0:0_e10   63 | GGCTGGGGGG...
## CONS          GGCTGGGGGGGCGGTGGAGCCCGGGGCCGGCCTGGTGTCCGGG...
##   r  gacaccgtgGGCTGGGGGGGCGGTGGAGCCCGGGGCCGGCCTGGTGTCCGGG...
##   r           GGCTGGGGGGGCGGTGGAGCCCGGGGCCGGCCTGGTGTCCGGG...
```

The first line summarises the group: the example read name, the read count, then the
consensus with the variant in brackets. `## CONS` is the consensus alone and one `##   r`
line follows per read, all aligned on the variant. Bases matching the consensus print
uppercase; deviations print lowercase in dark grey, as `gacaccgtg` does above. Reading down
the columns either side of the brackets is how you judge whether the flanking context really
supports the call.

`--min-support-consensus` does two jobs here. It is the per-column vote threshold when the
consensus is built, and groups with fewer reads than it are left out of the pileup entirely.

`--pileup-svg-path pileup.svg` writes the same alignment to a file, which is easier to share
and to scroll than a wide terminal. It is the only file the analysis writes.

## Running on your own data

You need the reference FASTA that the reads were mapped against, with a `.fai` index, and a
`.bai` next to each BAM. For SRS that is typically `hs37d5.fa`, for LRS `hs38.fa`.

```
uv run mgm-muc1-vntr run \
    --short-read-reference path/to/hs37d5.fa \
    --short-read-bam path/to/Sample.bam
```

### Options

| option | default | what it does |
| --- | --- | --- |
| `--short-read-bam` | required | SRS BAM, indexed |
| `--short-read-reference` | required | reference the SRS data was mapped to |
| `--short-read-release` | `GRCh37` | which VNTR interval to use for SRS |
| `--long-read-bam` | none | LRS BAM, enables the long-read mode |
| `--long-read-reference` | none | reference the LRS data was mapped to |
| `--long-read-release` | `GRCh38` | which VNTR interval to use for LRS |
| `--min-support-var` | 3 | minimum `Raw_Support` for a row to be reported |
| `--min-support-consensus` | 2 | per-column vote threshold, and pileup group cutoff |
| `--short-read-analysis-trim-flank` | 150 | flank length kept per SRS read |
| `--long-read-analysis-trim-flank` | 100 | flank length used to build the LRS markers |
| `--long-read-anchor-length` | 50 | margin a read must clear to count as spanning |
| `--print-pileups` | off | print the reads behind each call |
| `--print-details` | off | print LRS read names |
| `--pileup-svg-path` | none | write the pileup as SVG |
| `-v`, `--verbose` | 0 | repeat for more detail |
| `-q`, `--quiet` | off | warnings and errors only |

The release defaults are asymmetric, GRCh37 for short reads and GRCh38 for long reads, so
most pairings other than the one above need at least one of the flags set explicitly.

`--long-read-bam` and `--long-read-reference` must be given together; either alone exits
with status 1.

`--output-dir` exists but currently has no effect: nothing is written there, and the SVG goes
wherever `--pileup-svg-path` points.

Logging goes to stderr, so `>` redirects the results without capturing the logs.

### From a container image

Images are published to `ghcr.io/medgen-mainz/mgm-muc1-vntr` for `linux/amd64` and
`linux/arm64`.

| tag | what it is |
| --- | --- |
| `latest`, `X.Y.Z`, `X.Y` | releases |
| `main` | the tip of `main` |
| `sha-<short>` | one per merge, pruned after 30 days |
| `pr-<N>` | one per open pull request, deleted when it closes |

Reference FASTAs and BAMs are not in the image. Mount them and use the paths inside the
container. `WORKDIR` is `/data`, and `:ro` is enough unless you write output there:

```
docker run --rm -v "$PWD/tests/data:/data:ro" \
    ghcr.io/medgen-mainz/mgm-muc1-vntr:latest run \
    --short-read-bam /data/synth_insCCCC.bam \
    --short-read-reference /data/GRCh37_1_MUC1_masked.fa.gz \
    --quiet
```

```
Filename,Variant_Type,Variant_Sequence,Raw_Support,Support,Full_Path
synth_insCCCC.bam,ins,CCCC,63,63,/data/synth_insCCCC.bam
```

Identical to the checkout, with the mounted paths. Output files are written as root by
default; add `--user "$(id -u):$(id -g)"` to have them land with your own ownership, and drop
`:ro` if the output goes into the mount.

### Without a checkout

```
uvx --from git+https://github.com/medgen-mainz/mgm-muc1-vntr mgm-muc1-vntr --help
```

Nothing is compiled, since every dependency ships a wheel. The fixtures are not available
this way; they come with the checkout.

## Test data

`tests/data` holds one masked reference per genome build and six read fixtures, all in Git
LFS. Provenance, coordinates and regeneration recipes are in
[`tests/data/README.md`](tests/data/README.md).

| fixture | what it is |
| --- | --- |
| `NA24149_MUC1_SRS.bam` | real short reads, GIAB HG003, exome with spike-in |
| `HG003_MUC1_GRCh37_ONT.bam`, `HG003_MUC1_GRCh38_ONT.bam` | real ultralong nanopore reads, same donor |
| `synth_insCCCC.bam` | simulated, 4 bp insertion, frameshifting |
| `synth_insCCC_benign.bam` | simulated, 3 bp insertion, in frame |
| `synth_dupC.bam` | simulated, 1 bp insertion, the ADTKD-MUC1 allele |

The three `synth_*` fixtures come from **MucOneUp**, which builds MUC1 haplotypes carrying a
named variant. That is what makes their expected output known in advance rather than measured
after the fact.

- Repository: <https://github.com/berntpopp/MucOneUp> (MIT), pinned at `v0.44.4`
- Software: Popp B. *MucOneUp*. doi:[10.5281/zenodo.19740405](https://doi.org/10.5281/zenodo.19740405)
- Paper: Popp B, Saei H. *MucOneUp: A Simulation Framework for MUC1-VNTR Variant
  Benchmarking*. bioRxiv, 12 May 2026.
  doi:[10.64898/2026.05.08.723876](https://doi.org/10.64898/2026.05.08.723876)

## Development

Install uv, then everything else comes from `uv.lock`. There are no system packages to
install first.

```
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone git@github.com:medgen-mainz/mgm-muc1-vntr.git
cd mgm-muc1-vntr
uv run mgm-muc1-vntr --help
```

The environment is created on first use, on the interpreter named in `.python-version`.

| command | what it does |
| --- | --- |
| `make check` | formatting, lint and types |
| `make test` | the suite, with coverage |
| `make test-snapshot` | the same suite, updating snapshots |

`make check` and `make test` are the entry points CI runs. See
[CLAUDE.md](CLAUDE.md) for the conventions this repository follows.
