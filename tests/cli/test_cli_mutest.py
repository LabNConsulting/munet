# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# November 17 2026, Liam Brady <lbrady@labn.net>
#
# Copyright 2026, LabN Consulting, L.L.C.
#
"""Test invoking mutest from the munet CLI."""

import io
import logging
import re
from pathlib import Path

import pytest

from munet import cli

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.parametrize("unet", [True, False], indirect=["unet"]),
]

# pylint: disable=redefined-outer-name

@pytest.fixture
def cli_mutest_logging():
    """Configure the results logger as munet's logconf.yaml normally would."""
    # Save the old global logging configuration
    reslog = logging.getLogger("cli.mutest.results")
    olog = logging.getLogger("cli.mutest.output")
    old_reslog = (reslog.level, reslog.propagate, tuple(reslog.handlers))
    old_olog = (olog.level, olog.propagate)

    # Replace the global logging configuration with a string IO handler
    for handler in old_reslog[2]:
        reslog.removeHandler(handler)

    handler = logging.StreamHandler(io.StringIO())
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(levelname)5s: %(message)s"))
    reslog.addHandler(handler)
    reslog.setLevel(logging.DEBUG)
    reslog.propagate = False
    olog.setLevel(logging.DEBUG)
    olog.propagate = False

    try:
        yield handler
    finally:
        # Restore the old global logging configuration
        for current in tuple(reslog.handlers):
            reslog.removeHandler(current)
            if current not in old_reslog[2]:
                current.close()
        for original in old_reslog[2]:
            reslog.addHandler(original)
        reslog.setLevel(old_reslog[0])
        reslog.propagate = old_reslog[1]
        olog.setLevel(old_olog[0])
        olog.propagate = old_olog[1]


async def run_cli_command(unet, command):
    stdout = io.StringIO()
    assert await cli.doline(unet, command, stdout)
    return stdout.getvalue()


async def test_mutest_cli_basic(unet, cli_mutest_logging):
    output = await run_cli_command(unet, "test mutest_cli_a.py")
    assert re.search(r"PASS.*CLI marker A", output), output
    assert output.count("CLI marker A") == 1

    logfile = unet.rundir / "munet-test-exec.log"
    text = logfile.read_text(encoding="utf-8")
    assert "CLI_A_OK" in text
    assert "CLI marker A" in text
    assert logging.getLogger("cli.mutest.results").handlers == [cli_mutest_logging]


async def test_mutest_cli_repeated(unet, cli_mutest_logging):
    test_path = Path(unet.config_dirname) / "mutest_cli_a.py"
    result_logger = logging.getLogger(f"cli.mutest.results.{test_path}")
    output_logger = logging.getLogger(f"cli.mutest.output.{test_path}")
    before_result = tuple(result_logger.handlers)
    before_output = tuple(output_logger.handlers)

    for _ in range(2):
        output = await run_cli_command(unet, "test mutest_cli_a.py")
        assert output.count("CLI marker A") == 1, output
        assert tuple(result_logger.handlers) == before_result
        assert tuple(output_logger.handlers) == before_output
        # Ensure that logging handlers are not accumulated accidentally
        assert logging.getLogger("cli.mutest.results").handlers == [cli_mutest_logging]

        text = (unet.rundir / "munet-test-exec.log").read_text(encoding="utf-8")
        result_lines = [
            line for line in text.splitlines()
            if "cli.mutest.results." in line and "CLI marker A" in line
        ]
        assert len(result_lines) == 1, result_lines


async def test_mutest_cli_glob_order(unet, cli_mutest_logging):  # pylint: disable=unused-argument
    output = await run_cli_command(unet, "test mutest_cli_[ab].py")
    assert output.count("CLI marker A") == 1, output
    assert output.count("CLI marker B") == 1, output
    assert output.index("CLI marker A") < output.index("CLI marker B")


async def test_mutest_cli_no_match(unet, cli_mutest_logging):  # pylint: disable=unused-argument
    output = await run_cli_command(unet, "test mutest_missing.py mutest_cli_a.py")
    assert "% No tests matched: mutest_missing.py" in output
    assert re.search(r"PASS.*CLI marker A", output), output


async def test_mutest_cli_nested_failure(unet, cli_mutest_logging):
    # Ensures two things:
    #  1. Specifically selected tests (not in configdir) still execute
    #  2. Failing mutests report failures to the CLI
    output = await run_cli_command(unet, "test subdir/cli_mutest_fail.py")
    assert re.search(r"FAIL.*CLI deliberate failure", output), output
    assert output.count("CLI deliberate failure") == 1
    assert logging.getLogger("cli.mutest.results").handlers == [cli_mutest_logging]


async def test_mutest_cli_no_args(unet, cli_mutest_logging):
    output = await run_cli_command(unet, "test")
    assert "No tests specified" in output, output
    assert logging.getLogger("cli.mutest.results").handlers == [cli_mutest_logging]


async def test_mutest_cli_multiple_explicit(unet, cli_mutest_logging):
    output = await run_cli_command(
        unet, "test mutest_cli_b.py mutest_cli_a.py"
    )
    assert output.count("CLI marker A") == 1, output
    assert output.count("CLI marker B") == 1, output
    assert output.index("CLI marker B") < output.index("CLI marker A")
    assert logging.getLogger("cli.mutest.results").handlers == [cli_mutest_logging]
