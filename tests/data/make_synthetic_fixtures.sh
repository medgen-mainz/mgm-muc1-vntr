#!/usr/bin/env bash
#
# Regenerates the synthetic MUC1 fixtures in this directory. Not run by the test suite:
# the outputs are committed via Git LFS and this script records how they were produced.
#
#   pixi run -e fixtures make-fixtures [workdir]
#
# Every tool comes from the `fixtures` pixi environment, so the simulator, aligner and
# samtools versions are pinned in pixi.lock. Passing a workdir lets a re-run reuse the bwa
# index, which costs about eight minutes and 417 MB against the mostly-N masked reference.
# Index files are intermediates and are not committed.
#
# bwa rather than minimap2: NA24149_MUC1_SRS.bam was aligned with bwa-mem and the fixtures
# should share its provenance. On identical reads minimap2 also called a 48 bp deletion
# that bwa does not, which would have been baked into expected test output. bwa also emits
# MD tags by default, which the analysis requires via pysam's get_reference_sequence().
set -euo pipefail

readonly MUCONEUP_REF=v0.44.4  # keep in step with the pin in [tool.pixi.feature.fixtures.pypi-dependencies]
readonly REPEATS=60            # VNTR repeat count per haplotype
readonly TARGET=1,25           # haplotype 1, repeat 25: an 'X' unit, which these mutations require
readonly MUCONEUP_SEED=7
readonly WGSIM_SEED=42
readonly READ_PAIRS=10000
readonly READ_LEN=150

# fixture basename : MucOneUp mutation name. Add a line to add a case; delGCCCA (-5 bp),
# ins25bp (+25), del18_31 (-14) and bigDel (-26) all work the same way.
readonly CASES=(
  "synth_insCCCC:insCCCC"
  "synth_insCCC_benign:insCCC_benign"
  "synth_dupC:dupC"
)

readonly DATA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REFERENCE_GZ="${DATA_DIR}/GRCh37_1_MUC1_masked.fa.gz"

for tool in muconeup bwa wgsim samtools git; do
  command -v "${tool}" > /dev/null || {
    echo "${tool} not on PATH; run this as: pixi run -e fixtures make-fixtures" >&2
    exit 1
  }
done

WORKDIR="${1:-$(mktemp -d)}"
mkdir -p "${WORKDIR}"
echo "workdir: ${WORKDIR}"

# MucOneUp's config.json carries the repeat units and the hg19 flanks and ships only in the
# git repository, not in the wheel, so the tag is cloned even though the tool is installed.
if [[ ! -f "${WORKDIR}/MucOneUp/config.json" ]]; then
  git clone --quiet --depth 1 --branch "${MUCONEUP_REF}" \
    https://github.com/berntpopp/MucOneUp.git "${WORKDIR}/MucOneUp"
fi

for case in "${CASES[@]}"; do
  base="${case%%:*}"
  mutation="${case##*:}"
  echo "simulating ${base} (${mutation})"
  # `normal,<mutation>` writes a matched pair and only haplotype 1 is mutated, so the
  # sample is heterozygous. The normal member stays in the workdir for delta checking.
  ( cd "${WORKDIR}/MucOneUp" && muconeup \
      --config config.json --log-level ERROR simulate \
      --out-base "${base}" --out-dir "${WORKDIR}" --seed "${MUCONEUP_SEED}" \
      --reference-assembly hg19 --fixed-lengths "${REPEATS}" \
      --mutation-name "normal,${mutation}" --mutation-targets "${TARGET}" \
      --output-structure )
done

gunzip -c "${REFERENCE_GZ}" > "${WORKDIR}/ref.fa"
if [[ ! -f "${WORKDIR}/ref.fa.bwt" ]]; then
  echo "indexing reference (about eight minutes)"
  bwa index "${WORKDIR}/ref.fa"
fi

for case in "${CASES[@]}"; do
  base="${case%%:*}"
  echo "aligning ${base}"
  # -e 0 -r 0 -R 0 -X 0: no sequencing error and no wgsim-injected variants, so every indel
  # in the BAM traces to the simulated haplotype rather than to read noise.
  wgsim -N "${READ_PAIRS}" -1 "${READ_LEN}" -2 "${READ_LEN}" -S "${WGSIM_SEED}" \
    -e 0 -r 0 -R 0 -X 0 \
    "${WORKDIR}/${base}.001.mut.simulated.fa" \
    "${WORKDIR}/${base}.r1.fq" "${WORKDIR}/${base}.r2.fq" > /dev/null
  bwa mem -t 4 "${WORKDIR}/ref.fa" \
    "${WORKDIR}/${base}.r1.fq" "${WORKDIR}/${base}.r2.fq" 2> /dev/null \
    | samtools sort -o "${DATA_DIR}/${base}.bam" -
  samtools index "${DATA_DIR}/${base}.bam"
  samtools quickcheck -v "${DATA_DIR}/${base}.bam"
done

echo
echo "wrote:"
for case in "${CASES[@]}"; do
  base="${case%%:*}"
  ls -l "${DATA_DIR}/${base}.bam" "${DATA_DIR}/${base}.bam.bai" | awk '{print "  " $5, $9}'
done
