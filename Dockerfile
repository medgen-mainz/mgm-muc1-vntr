# Build stage: create /app/.venv from the committed lockfile.
#
# `--locked` fails on a lockfile stale against the manifest rather than re-resolving, so the
# versions baked in here are the ones CI tested against; `--no-dev` leaves the dev group out.
# This is what the `prod` pixi environment and its solve group used to buy (#38).
#
# `--no-editable` installs the project into site-packages instead of leaving a .pth pointing
# at /app/src. That is the reason the runtime stage copies the venv and nothing else.
FROM python:3.13-slim@sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f AS build

# uv ships as a static binary in its own image, so it is copied in rather than installed.
COPY --from=ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /bin/uv

WORKDIR /app

# Bytecode is compiled at build time on purpose. Without it the interpreter recompiles the
# imported half of numpy, pysam and biopython on every container start, and these containers
# are one-shot, so the cost would be paid on every single run.
#
# The base image already carries the interpreter `.python-version` asks for; downloading a
# second one would only make the image bigger.
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# README.md is here because `[project] readme = "README.md"`; building the project fails
# without it. .python-version is here so uv resolves the same interpreter the tests ran on.
COPY pyproject.toml uv.lock .python-version README.md ./
COPY src ./src

RUN uv sync --locked --no-dev --no-editable --no-cache

# Runtime stage. The venv is copied to the path it was built at, which keeps the console
# script's shebang valid without rewriting it, and a plain exec keeps signal handling and
# exit codes intact.
FROM python:3.13-slim@sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f AS runtime

COPY --from=build /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:${PATH}"

# Reference FASTAs and BAMs are bind-mounted, never baked in; /data is where to mount them.
WORKDIR /data

ENTRYPOINT ["mgm-muc1-vntr"]
CMD ["--help"]
