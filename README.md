[![CI](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml/badge.svg)](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml)

# MGM-MUC1-VNTR


- Python: 3.13+
- License: MIT
- Made: with ❤️ at [Limbach Genetics, Medizinische Genetik Mainz](https://www.medgen-mainz.de/)

## Running

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
uv run mgm-muc1-vntr run \
    --short-read-reference path/to/hs37d5.fa \
    --short-read-bam path/to/Sample.bam
```

You can increase verbosity by specifying `-v/--verbose` one or more times.
You can disable logging alltogether by using `-q/--quiet`.
Logging goes to stderr, so you can always redirect the output with `>`.

Use `--print-pileups` to print the pileups and inspect whether there is sufficient suport for the environment left/right of variant.

Use `--pileup-svg-path` to write out file with the short-read sequencing (SRS) pileups.

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
# git clone git@github.com:medgen-mainz/mgm-muc1-vntr.git
# cd mgm-muc1-vntr
# uv run mgm-muc1-vntr --help
```
