# Build stage: resolve the `prod` pixi environment from the committed lockfile.
#
# `prod` shares a solve group with `default` in pyproject.toml, so the versions baked in here
# are the ones CI tested against, minus the dev tools. `--locked` fails on a lockfile stale
# against the manifest rather than re-resolving, so the image is reproducible from the tag.
FROM ghcr.io/prefix-dev/pixi:0.78.0-bookworm@sha256:2d9729658a777203a99b45103a120191d479b123d0a1edb06694e843ccc8000d AS build

WORKDIR /app

# README.md is here because `[project] readme = "README.md"`; the editable install of the
# project fails without it.
COPY pyproject.toml pixi.lock README.md ./
COPY src ./src

RUN pixi install --locked -e prod

# Runtime stage. Conda prefixes are not relocatable, so the environment has to land on the
# same path it was built at. The source tree comes along because pyproject.toml declares the
# project as an *editable* pypi dependency, which leaves a .pth in site-packages pointing at
# /app/src rather than copying the package into the environment.
FROM debian:bookworm-slim AS runtime

COPY --from=build /app/.pixi/envs/prod /app/.pixi/envs/prod
COPY --from=build /app/src /app/src
COPY --from=build /app/pyproject.toml /app/README.md /app/

# Activating by PATH rather than by sourcing `pixi shell-hook`. conda-forge binaries find
# their libraries through RPATH, so no LD_LIBRARY_PATH is needed, and a plain exec keeps
# signal handling and exit codes intact.
ENV PATH="/app/.pixi/envs/prod/bin:${PATH}"

# Reference FASTAs and BAMs are bind-mounted, never baked in; /data is where to mount them.
WORKDIR /data

ENTRYPOINT ["mgm-muc1-vntr"]
CMD ["--help"]
