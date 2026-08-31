[![CI](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml/badge.svg)](https://github.com/medgen-mainz/mgm-muc1-vntr/actions/workflows/main.yml)

# MGM-MUC1-VNTR


- Python: 3.13+
- License: MIT
- Made: with ❤️ at [Limbach Genetics, Medizinische Genetik Mainz](https://www.medgen-mainz.de/)

## Running

### From Source Code

There are no system packages to install first. Everything, including the compiled
dependencies, comes from the lockfile.

Install uv:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then `uv run` any command in the project environment; the first invocation creates it
from `uv.lock`.

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

You can enable the long-read sequencing analysis mode by passing `--long-read-bam` (LRS BAM/CRAM file) and `--long-read-reference` (reference used in LRS analysis).

Note that you may have to use `--short-read-release` and `--long-read-release` to select the appropriate genome release for short and long read analysis.

### From a Container Image

Images are published to `ghcr.io/medgen-mainz/mgm-muc1-vntr` for `linux/amd64` and
`linux/arm64`.

| tag | what it is |
| --- | --- |
| `latest`, `X.Y.Z`, `X.Y` | releases |
| `main` | the tip of `main` |
| `sha-<short>` | one per merge, pruned after 30 days |
| `pr-<N>` | one per open pull request, deleted when it closes |

Reference FASTAs and BAMs are not in the image. Mount them and refer to the paths inside
the container:

```
docker run --rm -v /path/to/data:/data \
    ghcr.io/medgen-mainz/mgm-muc1-vntr:latest run \
    --short-read-reference /data/hs37d5.fa \
    --short-read-bam /data/Sample.bam
```

Output files are written as root by default. Add `--user "$(id -u):$(id -g)"` to have them
land with your own ownership.

## Developer Notes

First, install `uv`

```
# curl -LsSf https://astral.sh/uv/install.sh | sh
[...]
# which uv
/home/mholtgrewe/.local/bin/uv
```

Clone and run with uv:

```
# git clone git@github.com:medgen-mainz/mgm-muc1-vntr.git
# cd mgm-muc1-vntr
# uv run mgm-muc1-vntr --help
```

The environment is created from `uv.lock` on first use, on the interpreter named in
`.python-version`. `make check` and `make test` are the same entry points CI runs.
