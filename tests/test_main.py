"""End-to-end tests for the CLI.

Everything here goes through `typer.testing.CliRunner`, so the argument parsing, the
option defaults and the wiring between the two analyses are all exercised as a user gets
them. `CliRunner` captures stdout, which matters: an LRS run prints a full alignment per
read.
"""

import pathlib
import runpy
import sys

import pytest
from typer.testing import CliRunner

from mgm_muc1_vntr import __version__
from mgm_muc1_vntr.__main__ import app, main, setup_loguru
from mgm_muc1_vntr.common import VNTR_INTERVALS

DATA = pathlib.Path(__file__).parent / "data"
SRS_BAM = DATA / "NA24149_MUC1_SRS.bam"
SRS_REFERENCE = DATA / "GRCh37_1_MUC1_masked.fa.gz"
GRCH38_REFERENCE = DATA / "GRCh38_chr1_MUC1_masked.fa.gz"

runner = CliRunner()


def srs_args(**overrides) -> list[str]:
    args = ["run", "--short-read-bam", str(SRS_BAM), "--short-read-reference", str(SRS_REFERENCE)]
    for key, value in overrides.items():
        args += [f"--{key.replace('_', '-')}", str(value)]
    return args


@pytest.mark.parametrize("verbose", [-1, 0, 1, 2])
def test_setup_loguru_accepts_every_verbosity(verbose: int):
    """-1 is what `--quiet` passes; 2 and above is TRACE."""
    setup_loguru(verbose=verbose)


def test_version_prints_the_package_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_no_arguments_shows_help():
    result = runner.invoke(app, [])
    assert "SRS and LRS analysis for MUC1 VNTR" in result.output


@pytest.mark.parametrize("flag", ["-q", "-v", "-vv"])
def test_verbosity_flags(tmp_path, flag):
    result = runner.invoke(app, srs_args(output_dir=tmp_path) + [flag])
    assert result.exit_code == 0, result.output


def test_short_read_csv_is_unreachable_from_the_runner(tmp_path):
    """The CSV row is missing from `result.output`, and that is a source bug.

    `print_short_read_result` and `print_short_read_pileups` declare
    `file: typing.TextIO = sys.stdout`, which binds whatever `sys.stdout` was when the
    module was imported. Nothing installed later can intercept them: not `CliRunner`, not
    `contextlib.redirect_stdout`, not `capsys`, not `capfd`. Under pytest the rows land in
    the session-wide capture and show up as "Captured stdout call" on failure.

    Making the default `None` and resolving `sys.stdout` per call would fix it. Until then
    the row content is asserted in `test_srs_analysis.py`, which passes `file=` explicitly,
    and this test pins the CLI symptom.
    """
    result = runner.invoke(app, srs_args(output_dir=tmp_path))
    assert result.exit_code == 0, result.output
    assert "NA24149_MUC1_SRS.bam,del" not in result.output


@pytest.mark.parametrize("flag", [[], ["--print-pileups"]])
def test_print_pileups_flag_is_accepted(tmp_path, flag):
    """Covers the `--print-pileups` branch; its output is asserted in `test_srs_analysis.py`."""
    result = runner.invoke(app, srs_args(output_dir=tmp_path) + flag)
    assert result.exit_code == 0, result.output


def test_pileup_svg_option_writes_the_file(tmp_path):
    svg_path = tmp_path / "pileup.svg"
    result = runner.invoke(app, srs_args(output_dir=tmp_path, pileup_svg_path=svg_path))
    assert result.exit_code == 0, result.output
    assert svg_path.stat().st_size > 0


def test_long_read_bam_without_reference_exits_one():
    result = runner.invoke(app, srs_args(long_read_bam="/nonexistent.bam"))
    assert result.exit_code == 1
    assert "Long read reference FASTA is required" in result.output


def test_long_read_reference_without_bam_exits_one():
    result = runner.invoke(app, srs_args(long_read_reference="/nonexistent.fa"))
    assert result.exit_code == 1
    assert "Long read BAM is required" in result.output


@pytest.mark.parametrize("extra", [[], ["--print-details"]])
def test_short_and_long_read_run(tmp_path, ont_bams, extra):
    """The full path: SRS on GRCh37, then LRS on the GRCh38 ONT fixture."""
    result = runner.invoke(
        app,
        srs_args(
            output_dir=tmp_path,
            long_read_bam=ont_bams["GRCh38"],
            long_read_reference=GRCH38_REFERENCE,
            long_read_release="GRCh38",
        )
        + extra,
    )
    assert result.exit_code == 0, result.output
    csv_rows = [line for line in result.output.splitlines() if line.startswith("HG003_MUC1_GRCh38_ONT.bam,")]
    assert len(csv_rows) == 1
    assert csv_rows[0].split(",")[1:4] == ["8", "6", "8"]
    assert ("####  " in result.output) is bool(extra)


def test_long_read_skip_names_the_missing_short_read_results(tmp_path):
    """Both LRS paths are read before any file is opened, so they need not exist.

    Both LRS arguments are present here, so the only reason to skip the analysis is the
    empty SRS result, and the warning has to say so rather than blame the arguments.
    """
    result = runner.invoke(
        app,
        srs_args(
            output_dir=tmp_path,
            min_support_var=99999,
            long_read_bam="/nonexistent.bam",
            long_read_reference="/nonexistent.fa",
        ),
    )
    assert result.exit_code == 0, result.output
    assert "no short read results found" in result.output


def test_no_results_and_no_long_read_arguments(tmp_path):
    result = runner.invoke(app, srs_args(output_dir=tmp_path, min_support_var=99999))
    assert result.exit_code == 0, result.output
    assert "no short read results found" in result.output


def test_main_entry_point(monkeypatch):
    """The `mgm-muc1-vntr` console script, which reads `sys.argv` rather than arguments."""
    monkeypatch.setattr(sys, "argv", ["mgm-muc1-vntr", "version"])
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 0


@pytest.mark.filterwarnings("ignore:.*found in sys.modules.*:RuntimeWarning")
def test_module_is_runnable_with_dash_m(monkeypatch):
    """`python -m mgm_muc1_vntr`, run in process so coverage sees it."""
    monkeypatch.setattr(sys, "argv", ["mgm-muc1-vntr", "version"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("mgm_muc1_vntr.__main__", run_name="__main__")
    assert excinfo.value.code == 0


def test_vntr_interval_matches_the_release_the_cli_selects():
    """`--short-read-release` picks the interval, so the two builds must not collide."""
    assert VNTR_INTERVALS["GRCh37"] != VNTR_INTERVALS["GRCh38"]
