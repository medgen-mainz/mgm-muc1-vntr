[![CI](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml/badge.svg)](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml)

# MGM-MUC1-VNTR


- Python: 3.13+
- License: MIT
- Made: with ❤️ at [Limbach Genetics, Medizinische Genetik Mainz](https://www.medgen-mainz.de/)

## Running

### From Source Code

There are no system packages to install first. Everything, including the compiled
dependencies, comes from the lockfile.

Install pixi:

```
curl -fsSL https://pixi.sh/install.sh | sh
```

Then `pixi run` any command in the project environment; the first invocation creates it
from `pixi.lock`.

Then, you will need the reference that you mapped the SRS/LRS data to.
Below, we use `hs37d5.fa` for SRS data and `hs38.fa` for LRS data.
You will need FASTA index `.fai` files for each.
Also, your BAM file must have a `.bai` index.

Then:

```
pixi run mgm-muc1-vntr run \
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

First, install `pixi`

```
# curl -fsSL https://pixi.sh/install.sh | sh
[...]
# which pixi
/home/mholtgrewe/.pixi/bin/pixi
```

Clone and run with pixi:

```
# git clone git@github.com:medgen-mainz/mgm-muc1-vntr.git
# cd mgm-muc1-vntr
# pixi run mgm-muc1-vntr --help
```

The environment is created from `pixi.lock` on first use. `make check` and `make test` are
the same entry points CI runs.
