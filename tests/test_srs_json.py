"""End-to-end tests for the `--json-output` document.

Everything goes through the CLI, since the document is what a downstream consumer gets
from a real invocation. It is then re-read from the file and validated against
:class:`JsonDocument` rather than compared to the object the writer built, so the
assertions cover the serialised form a consumer actually parses.
"""

import json
import pathlib

import pysam
import pytest
from typer.testing import CliRunner

from mgm_muc1_vntr import __version__
from mgm_muc1_vntr.__main__ import app
from mgm_muc1_vntr.common import revcomp
from mgm_muc1_vntr.srs_json import SCHEMA_VERSION, JsonDocument

DATA = pathlib.Path(__file__).parent / "data"
SRS_REFERENCE = DATA / "GRCh37_1_MUC1_masked.fa.gz"

#: BAMs carrying a call at the CLI defaults: the NA24149 slice and one synthetic fixture
#: whose variant is known by construction. See `tests/data/README.md`.
CALLED_BAMS = [DATA / "NA24149_MUC1_SRS.bam", DATA / "synth_insCCCC.bam"]

runner = CliRunner()


def run_cli(bam: pathlib.Path, **overrides) -> str:
    """Invoke `run` on `bam` and hand back the output, asserting a clean exit.

    Always `--quiet`, so the captured stream holds what the analysis printed and nothing
    else: loguru writes to stderr, which `CliRunner` folds into stdout mid-line, and an
    INFO line landing inside a pileup row would defeat comparing two runs.
    """
    args = ["run", "--quiet", "--short-read-bam", str(bam), "--short-read-reference", str(SRS_REFERENCE)]
    for key, value in overrides.items():
        flag = f"--{key.replace('_', '-')}"
        args += [flag] if value is True else [flag, str(value)]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return result.output


def read_document(path: pathlib.Path) -> JsonDocument:
    """Parse and validate the written document, as a consumer would."""
    return JsonDocument.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("bam", CALLED_BAMS, ids=lambda bam: bam.stem)
def test_document_round_trips_and_records_the_run(bam: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """The file parses into the model and repeats the parameters the run used."""
    json_path = tmp_path / "result.json"
    run_cli(bam, json_output=json_path)

    document = read_document(json_path)

    assert document.schema_version == SCHEMA_VERSION
    assert document.tool_version == __version__
    assert document.genome_release == "GRCh37"
    assert document.input_bam == str(bam)
    assert (document.min_support_var, document.min_support_consensus, document.trim_flank) == (3, 2, 150)
    assert document.results, "expected a call to assert against"


@pytest.mark.parametrize("bam", CALLED_BAMS, ids=lambda bam: bam.stem)
def test_read_counts_bound_the_reported_support(bam: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """`locus_read_count >= indel_read_count >= sum(raw_support)`.

    The second step is `>=` and not `==` because a variation below `min_support_var` is
    dropped from `results` while its reads still count towards `indel_read_count`, so
    equality would fail on any BAM carrying a singleton indel.
    """
    json_path = tmp_path / "result.json"
    run_cli(bam, json_output=json_path)

    document = read_document(json_path)

    assert document.locus_read_count >= document.indel_read_count
    assert document.indel_read_count >= sum(result.raw_support for result in document.results)


@pytest.mark.parametrize("bam", CALLED_BAMS, ids=lambda bam: bam.stem)
def test_emitted_reads_account_for_every_supporting_read(bam: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """No supporting read is missing from the evidence, and none is counted twice."""
    json_path = tmp_path / "result.json"
    run_cli(bam, json_output=json_path)

    document = read_document(json_path)

    for result in document.results:
        assert sum(len(group.reads) for group in result.flank_groups) == result.raw_support
        assert result.support == max(group.count for group in result.flank_groups)
        for group in result.flank_groups:
            assert group.count == len(group.reads)


def test_groups_below_the_consensus_threshold_are_emitted(tmp_path: pathlib.Path) -> None:
    """Every group goes out, not only those `--print-pileups` would render.

    `min_support_consensus` defaults to 2, so a single-read group is one the terminal view
    drops. At `min_support_var=1` this fixture produces such groups, which is what makes
    the assertion able to fail.
    """
    json_path = tmp_path / "result.json"
    run_cli(CALLED_BAMS[0], json_output=json_path, min_support_var=1)

    document = read_document(json_path)
    counts = [group.count for result in document.results for group in result.flank_groups]

    assert min(counts) < document.min_support_consensus


@pytest.mark.parametrize("bam", CALLED_BAMS, ids=lambda bam: bam.stem)
def test_sequence_is_emitted_in_both_orientations(bam: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """`sequence` is as analysed and `sequence_transcript` is what the CSV row prints.

    Asserted against the CSV on stdout rather than against `revcomp` alone, so the two
    outputs cannot disagree about which orientation the lab sees.
    """
    json_path = tmp_path / "result.json"
    output = run_cli(bam, json_output=json_path)

    document = read_document(json_path)
    csv_sequences = [line.split(",")[2] for line in output.splitlines() if line.startswith(f"{bam.name},")]

    assert csv_sequences == [result.sequence_transcript for result in document.results]
    for result in document.results:
        assert result.sequence_transcript == revcomp(result.sequence)
        assert result.length == len(result.sequence) == len(result.sequence_transcript)


@pytest.mark.parametrize("bam", CALLED_BAMS, ids=lambda bam: bam.stem)
def test_json_output_leaves_stdout_unchanged(bam: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """The option adds a file and nothing else, so the human view is untouched."""
    without = run_cli(bam, print_pileups=True)
    with_json = run_cli(bam, print_pileups=True, json_output=tmp_path / "result.json")

    assert with_json == without


def test_no_file_is_written_when_the_option_is_omitted(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The working directory is moved first, so an unnamed output has one place to land."""
    monkeypatch.chdir(tmp_path)

    run_cli(CALLED_BAMS[0])

    assert list(tmp_path.iterdir()) == []


def test_empty_locus_is_distinguishable_from_no_variation(tmp_path: pathlib.Path) -> None:
    """A BAM with no reads over the interval reports zero coverage and exits 0.

    The empty BAM carries the committed fixture's own header, so the contig the analysis
    fetches exists and the fetch returns nothing rather than raising.
    """
    empty_bam = tmp_path / "empty.bam"
    with pysam.AlignmentFile(str(CALLED_BAMS[0]), mode="rb") as template:
        with pysam.AlignmentFile(str(empty_bam), mode="wb", header=template.header):
            pass
    pysam.index(str(empty_bam))

    json_path = tmp_path / "result.json"
    output = run_cli(empty_bam, json_output=json_path)

    document = read_document(json_path)

    assert document.results == []
    assert document.locus_read_count == 0
    assert document.indel_read_count == 0
    assert "no short read results found" in output
