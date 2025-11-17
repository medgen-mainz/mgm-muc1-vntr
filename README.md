[![CI](https://github.com/medgen-mainz/mainz-muc1-vntr/actions/workflows/main.yml/badge.svg)](https://github.com/medgen-mainz/mainz-muc1-vntr/actions/workflows/main.yml)

# Mainz-MUC1-VNTR


- Python: 3.13+
- License: MIT
- Made: with ❤️ at [Limbach Genetics, Medizinische Genetik Mainz](https://www.medgen-mainz.de/)

## Running

### Prerequisites

You will need to install the development versions of a number of libraries...

On Ubuntu 24.04:

```
sudo apt install -y libbz2-dev libcairo-dev liblzma-dev
```

### From Source Code

First, install uv

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, you will need the reference that you mapped the SRS/LRS data to.
Below, we use `hs37d5.fa` for SRS data and `hs38.fa` for LRS data.
You will need FASTA index `.fai` files for each.
Also, your BAM file must have a `.bai` index.

Then:

```
uv run mainz-muc1-vntr run \
    --short-read-reference path/to/hs37d5.fa \
    --short-read-bam path/to/Sample.bam
```

You can increase verbosity by specifying `-v/--verbose` one or more times.
You can disable logging alltogether by using `-q/--quiet`.
Logging goes to stderr, so you can always redirect the output with `>`.

Use `--print-pileups` to print the pileups and inspect whether there is sufficient suport for the environment left/right of variant.

Use `--pileup-svg-path` to write out file with the short-read sequencing (SRS) pileups.

You can enable the long-read sequencing analysis mode by passing `--long-read-bam` (LRS BAM/CRAM file) and `--long-read-reference` (reference used in LRS analysis).

Note that you may have to use `--short-read-release` and `--long-read-release` to select the appropriate genome release for short and long read analysis.

## Developer Notes

First, install `uv`

```
# curl -LsSf https://astral.sh/uv/install.sh | sh
[...]
# which uv uvx
/home/mholtgrewe/.local/bin/uv
/home/mholtgrewe/.local/bin/uvx
```

Clone and run with uv:

```
# git clone git@github.com:medgen-mainz/mainz-muc1-vntr.git
# cd mainz-muc1-vntr
# uv run mainz-muc1-vntr --help
```
