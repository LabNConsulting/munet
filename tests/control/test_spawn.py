# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# February 12 2022, Christian Hopps <chopps@labn.net>
#
# Copyright 2022, LabN Consulting, L.L.C.
#
"Testing use of pexect/REPL in munet."
import logging
import os
import time
import pexpect
import logging
import munet
import re

import pytest


# All tests are coroutines
pytestmark = pytest.mark.asyncio

# All tests are coroutines
pytestmark = pytest.mark.asyncio

# if "GITHUB_ACTION" in os.environ:
#     pytestmark = pytest.mark.parametrize(
#         "unet_share", ["munet-ci"], indirect=["unet_share"]
#     )


async def _test_repl(unet, hostname, cmd, use_pty, will_echo=False):
    host = unet.hosts[hostname]
    time.sleep(1)
    if hasattr(host, "console"):
        repl = await host.console(
            cmd, user="root", use_pty=use_pty, will_echo=will_echo, trace=True
        )
    else:

        lfname = os.path.join(unet.rundir, hostname + "-shell_spawn-log.txt")
        logfile = open(lfname, "a+", encoding="utf-8")
        logfile.write("-- start logging for: '{}' --\n".format(cmd))

        prompt = r"(^|\r?\n)[^#\$]*[#\$] "
        repl = await host.shell_spawn(
            cmd,
            prompt,
            use_pty=use_pty,
            will_echo=will_echo,
            logfile=logfile,
            trace=True,
        )
    return repl


@pytest.mark.parametrize("host", ["host1", "container1", "remote1", "hn1"])
@pytest.mark.parametrize("mode", ["pty", "piped"])
@pytest.mark.parametrize("shellcmd", ["/bin/bash", "/bin/dash", "/usr/bin/ksh"])
async def test_shell_expect(unet_share, host, mode, shellcmd):
    unet = unet_share
    if not os.path.exists(shellcmd):
        pytest.skip(f"{shellcmd} not installed skipping")

    os.environ["TEST_SHELL"] = shellcmd

    if mode == "pty":
        # Do we really want to have to set this? Why is it different?
        will_echo = host == "container1"
        repl = await _test_repl(
            unet, host, [shellcmd], use_pty=True, will_echo=will_echo
        )
    else:
        # why is our command differnt here? Will the user know to do this?
        repl = await _test_repl(unet, host, [shellcmd, "-si"], use_pty=False)

    try:
        rn = unet.hosts[host]
        output = rn.cmd_raises("pwd ; ls -l --color=auto /")
        logging.debug("pwd and ls -l: %s", output)

        output = repl.cmd_raises("unset HISTFILE LSCOLORS")
        assert not output.strip()

        if host not in ("remote1", "container1"):
            output = repl.cmd_raises("env | grep TEST_SHELL")
            logging.debug("'env | grep TEST_SHELL' output: %s", output)
            assert output == f"TEST_SHELL={shellcmd}"

        expected = (
            "block\nbus\nclass\ndev\ndevices\nfirmware\nfs\nkernel\nmodule\npower"
        )
        rc, output = repl.cmd_status("ls --color=never -1 /sys")
        output = output.replace("hypervisor\n", "")
        logging.debug("'ls --color=never -1 /sys' rc: %s output: %s", rc, output)
        assert output == expected

        if shellcmd == "/bin/bash":
            output = repl.cmd_raises("!!")
            logging.debug("'!!' output: %s", output)
    finally:
        # this is required for setns() restoration to work for non-pty (piped) bash
        if mode != "pty":
            repl.child.proc.kill()


@pytest.mark.parametrize("host_name", ["host1", "container1", "remote1", "hn1"])
@pytest.mark.parametrize("mode", ["pty", "piped"])
@pytest.mark.parametrize("shellcmd", ["/bin/bash", "/bin/dash", "/usr/bin/ksh"])
# As of 6-24-25, spawn is unused in the munet API. It is still maintained for the future
async def test_spawn(unet_share, host_name, mode, shellcmd):
    unet = unet_share
    if not os.path.exists(shellcmd):
        pytest.skip(f"{shellcmd} not installed skipping")

    use_pty = mode == "pty"
    prompt = r"(^|\r?\n)[^#\$]*[#\$] "

    if use_pty:
        cmd = [shellcmd]
    else:
        cmd = [shellcmd, "-si"]

    host = unet.hosts[host_name]
    time.sleep(1)

    p = host.spawn(
        cmd,
        prompt,
        use_pty=use_pty,
        timeout=1,
    )

    p.send("\n")

    # Sanity check, create a value in p's STDOUT that doesn't appear within p's STDIN
    p.send("echo $(( 3 * 7 )) \n")

    try:
        index = p.expect([r"21"], timeout=1)
        assert index == 0
    except pexpect.TIMEOUT:
        host.logger.critical("test_spawn: Expect failed with the process returned by spawn()")
        assert False
    finally:
        p.kill(9)


@pytest.mark.parametrize("mode", ['async', 'sync'])
@pytest.mark.parametrize("catch_err", ["timeout", "eof"])
async def test_spawn_err(unet_share, mode, catch_err):
    unet = unet_share
    hostname = "host1"
    prompt = r"foo"
    expects = ["bar"]
    sends = ["baz"]

    if catch_err == "timeout":
        expected_error = pexpect.TIMEOUT
        cmd = ["/bin/bash"]
    elif catch_err == "eof":
        expected_error = munet.base.CalledProcessError
        cmd = ["/bin/sleep", "1"]  # A command that exits instantly results in a broken pipe

    host = unet.hosts[hostname]
    time.sleep(1)

    saved_level = host.logger.getEffectiveLevel()
    host.logger.setLevel(logging.CRITICAL)  # Hide expected error messages for duration of test

    try:
        if mode == 'async':
            p = await host.async_spawn(
                cmd,
                prompt,
                expects=expects,
                sends=sends,
                use_pty=False,
                echo=False,
                timeout=1,
            )
            host.logger.critical("test_spawn_err: async_spawn unexpectedly succeeded")
        else:
            p = host.spawn(
                cmd,
                prompt,
                expects=expects,
                sends=sends,
                use_pty=False,
                echo=False,
                timeout=1,
            )
            host.logger.critical("test_spawn_err: spawn unexpectedly succeeded")
        assert False
    except expected_error:
        pass
    finally:
        host.logger.setLevel(saved_level)  # Revert to initial logging level
