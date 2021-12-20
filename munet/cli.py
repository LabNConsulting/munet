# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# July 24 2021, Christian Hopps <chopps@labn.net>
#
# Copyright 2021, LabN Consulting, L.L.C.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; see the file COPYING; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
import argparse
import asyncio
import concurrent.futures
import functools
import logging
import os
import pty
import re
import readline
import select
import socket
import subprocess
import sys
import tempfile
import termios
import tty


ENDMARKER = b"\x00END\x00"

logger = logging.getLogger(__name__)


def lineiter(sock):
    s = ""
    while True:
        sb = sock.recv(256)
        if not sb:
            return

        s += sb.decode("utf-8")
        i = s.find("\n")
        if i != -1:
            yield s[:i]
            s = s[i + 1 :]


def spawn(unet, host, cmd, iow, on_host):
    if sys.stdin.isatty():
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
    try:
        master_fd, slave_fd = pty.openpty()

        # use os.setsid() make it run in a new process group, or bash job
        # control will not be enabled
        p = unet.hosts[host].popen(
            cmd,
            preexec_fn=os.setsid,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            universal_newlines=True,
            skip_pre_cmd=on_host,
        )
        iow.write("\r")
        iow.flush()

        while p.poll() is None:
            r, _, _ = select.select([sys.stdin, master_fd], [], [], 0.25)
            if sys.stdin in r:
                d = os.read(sys.stdin.fileno(), 10240)
                os.write(master_fd, d)
            elif master_fd in r:
                o = os.read(master_fd, 10240)
                if o:
                    iow.write(o.decode("utf-8"))
                    iow.flush()
    finally:
        # restore tty settings back
        if sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)


def host_line_split(unet, line):
    all_hosts = set(unet.hosts)
    csplit = line.split()
    i = 0
    for i, e in enumerate(csplit):
        if e not in all_hosts:
            break
    else:
        i += 1

    if i == 0 and csplit and csplit[0] == "*":
        hosts = sorted(all_hosts)
        csplit = csplit[1:]
    else:
        hosts = csplit[:i]
        csplit = csplit[i:]

    if not hosts:
        hosts = sorted(all_hosts)

    if not csplit:
        return hosts, "", ""

    i = line.index(csplit[0])
    i += len(csplit[0])
    return hosts, csplit[0], line[i:].strip()


def host_cmd_split(unet, cmd, kinds, defall):
    if kinds:
        all_hosts = {
            x for x in unet.hosts if unet.hosts[x].config.get("kind", "") in kinds
        }
    else:
        all_hosts = set(unet.hosts)

    csplit = cmd.split()
    i = 0
    for i, e in enumerate(csplit):
        if e not in all_hosts:
            break
    else:
        i += 1

    if i == 0 and csplit and csplit[0] == "*":
        hosts = sorted(all_hosts)
        csplit = csplit[1:]
    else:
        hosts = csplit[:i]

    if not hosts and defall:
        hosts = sorted(all_hosts)
    # Filter hosts based on cmd
    cmd = " ".join(csplit[i:])
    return hosts, cmd


def proc_readline(fd, prompt, histfile):
    histfile = init_history(None, histfile)
    try:
        sys.stdin = os.fdopen(fd)
        line = input(prompt)
        readline.write_history_file(histfile)
    except Exception:
        return None
    if line is None:
        return None
    return str(line)


async def async_input(prompt, histfile):
    loop = asyncio.get_running_loop()
    input_pool = concurrent.futures.ProcessPoolExecutor()
    partial = functools.partial(proc_readline, sys.stdin.fileno(), prompt, histfile)
    result = await loop.run_in_executor(input_pool, partial)
    return result


def make_help_str(unet):

    w = sorted([x if x else "" for x in unet.cli_in_window_cmds])
    ww = unet.cli_in_window_cmds
    u = sorted([x if x else "" for x in unet.cli_run_cmds])
    uu = unet.cli_run_cmds

    s = (
        """
Basic Commands:
  cli   :: open a secondary CLI window
  help  :: this help
  hosts :: list hosts
  quit  :: quit the cli

New Window Commands:\n"""
        + "\n".join([f"  {ww[v][0]}\t:: {ww[v][1]}" for v in w])
        + """\nInline Commands:\n"""
        + "\n".join([f"  {uu[v][0]}\t:: {uu[v][1]}" for v in u])
        + "\n"
    )
    return s


def get_shcmd(unet, host, kinds, execfmt, ucmd):
    h = unet.hosts[host]
    kind = h.config.get("kind", "")
    if kinds and kind not in kinds:
        return ""
    if not isinstance(execfmt, str):
        execfmt = execfmt.get(kind)
    if not execfmt:
        return ""
    ucmd = execfmt.format(ucmd)
    ucmd = ucmd.replace("%RUNDIR%", unet.rundir)
    return ucmd.replace("%NAME%", host)


async def run_command(
    unet, outf, line, execfmt, hosts, kinds, on_host=False, with_pty=False
):
    """Runs a command on a set of hosts.

    Runs `execfmt` after calling `str.format` on it passing `uargs` as the lone
        substitution value.  The output is sent to `outf`.  If `on_host` is True then the
        `execfmt` is run using `Commander.cmd_status_host` otherwise it is run with
        `Commander.cmd_status`.
    """
    if kinds:
        logging.info("Filtering hosts to kinds: %s", kinds)
        hosts = [x for x in hosts if unet.hosts[x].config.get("kind", "") in kinds]
        logging.info("Filtered hosts: %s", hosts)

    if not hosts:
        return

    # if unknowns := [x for x in hosts if x not in unet.hosts]:
    #     outf.write("%% Unknown host[s]: %s\n" % ", ".join(unknowns))
    #     return

    # if sys.stdin.isatty() and with_pty:
    if with_pty:
        for host in hosts:
            shcmd = get_shcmd(unet, host, kinds, execfmt, line)
            if not shcmd:
                continue
            if len(hosts) > 1:
                outf.write(f"------ Host: {host} ------\n")
            spawn(unet, host, shcmd, outf, on_host)
            if len(hosts) > 1:
                outf.write(f"------- End: {host} ------\n")
        outf.write("\n")
        return

    aws = []
    for host in hosts:
        shcmd = get_shcmd(unet, host, kinds, execfmt, line)
        if not shcmd:
            continue
        if on_host:
            cmdf = unet.hosts[host].async_cmd_status_host
        else:
            cmdf = unet.hosts[host].async_cmd_status
        aws.append(cmdf(shcmd, warn=False, stderr=subprocess.STDOUT))

    results = await asyncio.gather(*aws, return_exceptions=True)
    for host, result in zip(hosts, results):
        rc, o, _ = result
        if len(hosts) > 1:
            outf.write(f"------ Host: {host} ------\n")
        if rc:
            outf.write("*** non-zero exit status: %d\n" % rc)
        outf.write(o)
        if len(hosts) > 1:
            outf.write(f"------- End: {host} ------\n")


async def doline(unet, line, outf, background=False, notty=False):

    line = line.strip()
    m = re.match(r"^(\S+)(?:\s+(.*))?$", line)
    if not m:
        return True

    cmd = m.group(1)
    nline = m.group(2) if m.group(2) else ""

    if cmd in ("q", "quit"):
        return False

    if cmd == "help":
        outf.write(make_help_str(unet))
        return True
    if cmd in ("h", "hosts"):
        outf.write(f"% Hosts:\t{' '.join(sorted(unet.hosts.keys()))}\n")
        return True
    if cmd == "cli":
        await remote_cli(
            unet,
            "secondary> ",
            "Secondary CLI",
            background,
        )
        return True

    #
    # In window commands
    #

    if cmd in unet.cli_in_window_cmds:
        execfmt, kinds, kwargs = unet.cli_in_window_cmds[cmd][2:]

        hosts, ucmd = host_cmd_split(unet, nline, kinds, False)
        if not hosts:
            return True

        if "{}" not in execfmt and ucmd:
            # CLI command does not expect user command so treat as hosts of which some
            # must be unknown
            unknowns = [x for x in ucmd.split() if x not in unet.hosts]
            outf.write(f"% Unknown host[s]: {' '.join(unknowns)}\n")
            return True
        try:
            for host in hosts:
                shcmd = get_shcmd(unet, host, kinds, execfmt, ucmd)
                unet.hosts[host].run_in_window(shcmd, **kwargs)
        except Exception as error:
            outf.write(f"% Error: {error}\n")
        return True

    #
    # Inline commands
    #
    hosts, cmd, nline = host_line_split(unet, line)

    logging.debug("hosts: %s cmd: %s nline: %s", hosts, cmd, nline)

    if cmd in unet.cli_run_cmds:
        pass
    elif "" in unet.cli_run_cmds:
        nline = f"{cmd} {nline}"
        cmd = ""
    else:
        outf.write(f"% Unknown command: {cmd} {nline}\n")
        return True

    execfmt, kinds, on_host, with_pty = unet.cli_run_cmds[cmd][2:]
    if with_pty and notty:
        outf.write("% Error: interactive command must be run from primary CLI\n")
        return True
    await run_command(unet, outf, nline, execfmt, hosts, kinds, on_host, with_pty)
    return True


async def cli_client(sockpath, prompt="munet> "):
    """Implement the user-facing CLI for a remote munet reached by a socket"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect(sockpath)

    # Go into full non-blocking mode now
    sock.settimeout(None)

    print("\n--- Munet CLI Starting ---\n\n")
    while True:
        line = input(prompt)
        if line is None:
            return

        # Need to put \n back
        line += "\n"

        # Send the CLI command
        sock.send(line.encode("utf-8"))

        def bendswith(b, sentinel):
            slen = len(sentinel)
            return len(b) >= slen and b[-slen:] == sentinel

        # Collect the output
        rb = b""
        while not bendswith(rb, ENDMARKER):
            lb = sock.recv(4096)
            if not lb:
                return
            rb += lb

        # Remove the marker
        rb = rb[: -len(ENDMARKER)]

        # Write the output
        sys.stdout.write(rb.decode("utf-8"))


async def local_cli(unet, outf, prompt, histfile, background):
    """Implement the user-side CLI for local munet"""

    print("\n--- Munet CLI Starting ---\n\n")
    while True:
        try:
            line = await async_input(prompt, histfile)
            if line is None:
                return
            if not await doline(unet, line, outf, background):
                return
        except KeyboardInterrupt:
            outf.write("%% Caught KeyboardInterrupt\nUse ^D or 'quit' to exit")


def init_history(unet, histfile):
    try:
        if histfile is None:
            histfile = os.path.expanduser("~/.munet-history.txt")
            if not os.path.exists(histfile):
                if unet:
                    unet.cmd("touch " + histfile)
                else:
                    subprocess.run("touch " + histfile, shell=True, check=True)
        if histfile:
            readline.read_history_file(histfile)
        return histfile
    except Exception as error:
        logging.warning("init_history failed: %s", error)
    return None


async def cli_client_connected(unet, background, reader, writer):
    """Handle CLI commands inside the munet process from a socket."""
    # # Go into full non-blocking mode now
    # client.settimeout(None)
    logging.debug("cli client connected")
    while True:
        line = await reader.readline()
        if not line:
            logging.debug("client closed cli connection")
            break
        line = line.decode("utf-8").strip()

        # def writef(x):
        #     writer.write(x.encode("utf-8"))

        if not await doline(unet, line, writer, background, notty=True):
            logging.debug("server closing cli connection")
            return

        writer.write(ENDMARKER)
        await writer.drain()


async def remote_cli(unet, prompt, title, background):
    "Open a CLI in a new window"
    try:
        if not unet.cli_sockpath:
            sockpath = os.path.join(tempfile.mkdtemp("-sockdir", "pty-"), "cli.sock")
            ccfunc = functools.partial(cli_client_connected, unet, background)
            s = await asyncio.start_unix_server(ccfunc, path=sockpath)
            unet.cli_server = asyncio.create_task(s.serve_forever(), name="cli-task")
            unet.cli_sockpath = sockpath
            logging.info("server created on :\n%s\n", sockpath)

        # Open a new window with a new CLI
        python_path = await unet.async_get_exec_path(["python3", "python"])
        us = os.path.realpath(__file__)
        cmd = "{} {}".format(python_path, us)
        if unet.cli_histfile:
            cmd += " --histfile=" + unet.cli_histfile
        if prompt:
            cmd += " --prompt='{}'".format(prompt)
        cmd += " " + unet.cli_sockpath
        unet.run_in_window(cmd, title=title, background=False)
    except Exception as error:
        logging.error("cli server: unexpected exception: %s", error)


def add_cli_in_window_cmd(unet, name, helpfmt, helptxt, execfmt, kinds, **kwargs):
    """Adds a CLI command to the CLI.

    The command `cmd` is added to the commands executable by the user from the CLI.  See
    `base.Commander.run_in_window` for the arguments that can be passed in `args` and
    `kwargs` to this function.

    Args:
        unet: unet object
        name: command string (no spaces)
        helpfmt: format of command to display in help (left side)
        helptxt: help string for command (right side)
        execfmt: interpreter `cmd` to pass to `host.run_in_window()`, if {} present then
          allow for user commands to be entered and inserted.
        kinds: limit CLI command to nodes which match list of kinds.
        **kwargs: keyword args to pass to `host.run_in_window()`
    """
    unet.cli_in_window_cmds[name] = (helpfmt, helptxt, execfmt, kinds, kwargs)


def add_cli_run_cmd(
    unet, name, helpfmt, helptxt, execfmt, kinds, on_host=False, interactive=False
):
    """Adds a CLI command to the CLI.

    The command `cmd` is added to the commands executable by the user from the CLI.
    See `run_command` above in the `doline` function and for the arguments that can
    be passed in to this function.

    Args:
        unet: unet object
        name: command string (no spaces)
        helpfmt: format of command to display in help (left side)
        helptxt: help string for command (right side)
        execfmt: format string to insert user cmds into for execution
        on_host: Should execute the command on the host vs in the node namespace.
        interactive: Should execute the command inside an allocated pty (interactive)
        kinds: limit CLI command to nodes which match list of kinds.
    """
    unet.cli_run_cmds[name] = (helpfmt, helptxt, execfmt, kinds, on_host, interactive)


def add_cli_config(unet, config):
    """Adds CLI commands based on config.

    All strings will have %NAME% and %RUNDIR% replaced with the corresponding
    current node `name` and `rundir`.  The format of the config dictionary can
    be seen in the following example.  The first list entry represents the default
    command because it has no `name` key.

      commands:
        - help: "run the given FRR command using vtysh"
          format: "[HOST ...] FRR-CLI-COMMAND"
          exec: "vtysh -c {}"
          on-host: false        # the default
          interactive: false    # the default
        - name: "vtysh"
          help: "Open a FRR CLI inside new terminal[s] on the given HOST[s]"
          format: "vtysh HOST [HOST ...]"
          exec: "vtysh"
          new-window: true

    The `new_window` key can also be a dictionary which will be passed as keyward
    arguments to the `Commander.run_in_window()` function.

    Args:
        unet: unet object
        config: dictionary of cli config
    """

    for cli_cmd in config.get("commands", []):
        name = cli_cmd.get("name", None)
        helpfmt = cli_cmd.get("format", "")
        helptxt = cli_cmd.get("help", "")
        execfmt = cli_cmd.get("exec", "bash -c '{}'")
        kinds = cli_cmd.get("kinds", [])
        stdargs = (unet, name, helpfmt, helptxt, execfmt, kinds)
        new_window = cli_cmd.get("new-window", None)
        if new_window is True:
            add_cli_in_window_cmd(*stdargs)
        elif new_window is not None:
            add_cli_in_window_cmd(*stdargs, **new_window)
        else:
            add_cli_run_cmd(
                *stdargs,
                cli_cmd.get("run-on-host", False),
                cli_cmd.get("interactive", False),
            )


def cli(
    unet,
    histfile=None,
    sockpath=None,
    force_window=False,
    title=None,
    prompt=None,
    background=True,
):
    if prompt is None:
        prompt = "munet> "

    if force_window or not sys.stdin.isatty():
        asyncio.run(remote_cli(unet, prompt, title, background))
        return

    if not unet:
        logger.debug("client-cli using sockpath %s", sockpath)

    try:
        if sockpath:
            asyncio.run(cli_client(sockpath, prompt))
        else:
            asyncio.run(local_cli(unet, sys.stdout, prompt, histfile, background))
    except EOFError:
        pass
    except Exception as ex:
        logger.critical("cli: got exception: %s", ex, exc_info=True)
        raise
    finally:
        # readline.write_history_file(histfile)
        pass


async def async_cli(
    unet,
    histfile=None,
    sockpath=None,
    force_window=False,
    title=None,
    prompt=None,
    background=True,
):
    if prompt is None:
        prompt = "munet> "

    if force_window or not sys.stdin.isatty():
        await remote_cli(unet, prompt, title, background)

    if not unet:
        logger.debug("client-cli using sockpath %s", sockpath)

    try:
        if sockpath:
            await cli_client(sockpath, prompt)
        else:
            await local_cli(unet, sys.stdout, prompt, histfile, background)
    except EOFError:
        pass
    except Exception as ex:
        logger.critical("cli: got exception: %s", ex, exc_info=True)
        raise


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG, filename="/tmp/topotests/cli-client.log")
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("cli-client")
    logger.info("Start logging cli-client")

    parser = argparse.ArgumentParser()
    parser.add_argument("--histfile", help="file to user for history")
    parser.add_argument("--prompt", help="prompt string to use")
    parser.add_argument("socket", help="path to pair of sockets to communicate over")
    cli_args = parser.parse_args()

    cli_prompt = cli_args.prompt if cli_args.prompt else "munet> "
    asyncio.run(
        async_cli(
            None,
            cli_args.histfile,
            cli_args.socket,
            prompt=cli_prompt,
            background=False,
        )
    )
