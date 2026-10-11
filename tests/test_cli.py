"""Tests for agw CLI entrypoint commands."""

from click.testing import CliRunner
from agw.cli.main import cli


def test_cli_help():
    runner = CliRunner()
    res = runner.invoke(cli, ["--help"])
    assert res.exit_code == 0
    assert "Antigravity Gateway CLI Administration Tool" in res.output
    assert "accounts" in res.output
    assert "health" in res.output
    assert "models" in res.output
    assert "quota" in res.output


def test_cli_models_help():
    runner = CliRunner()
    res = runner.invoke(cli, ["models", "--help"])
    assert res.exit_code == 0
    assert "List supported models" in res.output
