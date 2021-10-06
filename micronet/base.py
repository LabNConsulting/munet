# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# July 9 2021, Christian Hopps <chopps@labn.net>
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
import asyncio
import datetime
import logging
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import time as time_mod

root_hostname = subprocess.check_output("hostname")

# This allows us to cleanup any leftovers later on
os.environ["MICRONET_PID"] = str(os.getpid())


class Timeout:
    def __init__(self, delta):
        self.started_on = datetime.datetime.now()
        self.expires_on = self.started_on + datetime.timedelta(seconds=delta)

    def elapsed(self):
        elapsed = datetime.datetime.now() - self.started_on
        return elapsed.total_seconds()

    def is_expired(self):
        return datetime.datetime.now() > self.expires_on


def shell_quote(command):
    """Return command wrapped in single quotes."""
    if sys.version_info[0] >= 3:
        return shlex.quote(command)
    return "'" + command.replace("'", "'\"'\"'") + "'"


def cmd_error(rc, o, e):
    s = f"rc {rc}"
    o = "\n\tstdout: " + o.strip() if o and o.strip() else ""
    e = "\n\tstderr: " + e.strip() if e and e.strip() else ""
    return s + o + e


def proc_error(p, o, e):
    args = p.args if isinstance(p.args, str) else " ".join(p.args)
    s = f"rc {p.returncode} pid {p.pid}\n\targs: {args}"
    o = "\n\tstdout: " + o.strip() if o and o.strip() else ""
    e = "\n\tstderr: " + e.strip() if e and e.strip() else ""
    return s + o + e


def comm_error(p):
    rc = p.poll()
    assert rc is not None
    if not hasattr(p, "saved_output"):
        p.saved_output = p.communicate()
    return proc_error(p, *p.saved_output)


def get_tmp_dir(uniq):
    return os.path.join(tempfile.mkdtemp(), uniq)


class Commander:
    """
    Commander.

    An object that can execute commands.
    """

    tmux_wait_gen = 0

    def __init__(self, name, logger=None):
        """Create a Commander."""
        self.name = name
        self.last = None
        self.exec_paths = {}
        self.pre_cmd = []
        self.pre_cmd_str = ""

        if not logger:
            self.logger = logging.getLogger(__name__ + ".commander." + name)
        else:
            self.logger = logger

    @property
    def is_container(self):
        return False

    def set_logger(self, logfile):
        self.logger = logging.getLogger(__name__ + ".commander." + self.name)
        if isinstance(logfile, str):
            handler = logging.FileHandler(logfile, mode="w")
        else:
            handler = logging.StreamHandler(logfile)

        fmtstr = "%(asctime)s.%(msecs)03d %(levelname)s: {}({}): %(message)s".format(
            self.__class__.__name__, self.name
        )
        handler.setFormatter(logging.Formatter(fmt=fmtstr))
        self.logger.addHandler(handler)

    def set_pre_cmd(self, pre_cmd=None):
        if not pre_cmd:
            self.pre_cmd = []
            self.pre_cmd_str = ""
        else:
            self.pre_cmd = pre_cmd
            self.pre_cmd_str = " ".join(self.pre_cmd) + " "

    def __str__(self):
        return f"{self.__class__.__name__}({self.name})"

    def _get_exec_path(self, binary, cmdf, cache):
        if isinstance(binary, str):
            bins = [binary]
        else:
            bins = binary
        for b in bins:
            if b in cache:
                return cache[b]

            rc, output, _ = cmdf("which " + b, warn=False)
            if not rc:
                cache[b] = os.path.abspath(output.strip())
                return cache[b]
        return None

    def get_exec_path(self, binary):
        """Return the full path to the binary executable.

        `binary` :: binary name or list of binary names
        """
        return self._get_exec_path(binary, self.cmd_status_host, self.exec_paths)

    def test(self, flags, arg):
        """Run test binary, with flags and arg"""
        test_path = self.get_exec_path(["test"])
        rc, _, _ = self.cmd_status([test_path, flags, arg], warn=False)
        return not rc

    def path_exists(self, path):
        """Check if path exists."""
        return self.test("-e", path)

    def _get_cmd_str(self, cmd):
        if isinstance(cmd, str):
            return self.pre_cmd_str + cmd
        cmd = self.pre_cmd + cmd
        return " ".join(cmd)

    def _get_sub_args(self, cmd, defaults, **kwargs):
        if isinstance(cmd, str):
            defaults["shell"] = True
            pre_cmd = self.pre_cmd_str
        else:
            defaults["shell"] = False
            pre_cmd = self.pre_cmd
            cmd = [str(x) for x in cmd]
        defaults.update(kwargs)
        return pre_cmd, cmd, defaults

    def _popen(self, method, cmd, skip_pre_cmd=False, async_exec=False, **kwargs):
        if sys.version_info[0] >= 3 and not async_exec:
            defaults = {
                "encoding": "utf-8",
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
            }
        else:
            defaults = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
            }
        pre_cmd, cmd, defaults = self._get_sub_args(cmd, defaults, **kwargs)

        self.logger.debug('%s: %s("%s", kwargs: %s)', self, method, cmd, defaults)

        actual_cmd = cmd if skip_pre_cmd else pre_cmd + cmd
        if async_exec:
            p = asyncio.create_subprocess_exec(*actual_cmd, **defaults)
        else:
            p = subprocess.Popen(actual_cmd, **defaults)
        return p, actual_cmd

    def popen(self, cmd, **kwargs):
        """
        Creates a pipe with the given `command`.

        Args:
            cmd: `str` or `list` of command to open a pipe with.
            **kwargs: kwargs is eventually passed on to Popen. If `command` is a string
                then will be invoked with `bash -c`, otherwise `command` is a list and
                will be invoked without a shell.

        Returns:
            a subprocess.Popen object.
        """
        return self._popen("popen", cmd, async_exec=False, **kwargs)[0]

    def popen_host(self, cmd, **kwargs):
        """
        Creates a pipe with the given `command`.

        Args:
            cmd: `str` or `list` of command to open a pipe with.
            **kwargs: kwargs is eventually passed on to Popen. If `command` is a string
                then will be invoked with `bash -c`, otherwise `command` is a list and
                will be invoked without a shell.

        Returns:
            a subprocess.Popen object.
        """
        return Commander._popen(self, "popen_host", cmd, async_exec=False, **kwargs)[0]

    async def async_popen(self, cmd, **kwargs):
        """Creates a pipe with the given `command`.

        Args:
            cmd: `str` or `list` of command to open a pipe with.

            **kwargs: kwargs is eventually passed on to create_subprocess_exec. If
                `command` is a string then will be invoked with `bash -c`, otherwise
                `command` is a list and will be invoked without a shell.

        Returns:
            a asyncio.subprocess.Process object.
        """
        return await self._popen("async_popen", cmd, async_exec=True, **kwargs)[0]

    async def async_popen_host(self, cmd, **kwargs):
        """Creates a pipe with the given `command`.

        Args:
            cmd: `str` or `list` of command to open a pipe with.

            **kwargs: kwargs is eventually passed on to create_subprocess_exec. If
                `command` is a string then will be invoked with `bash -c`, otherwise
                `command` is a list and will be invoked without a shell.

        Returns:
            a asyncio.subprocess.Process object.
        """
        return await Commander._popen(
            self, "async_popen_host", cmd, async_exec=True, **kwargs
        )[0]

    def _cmd_status(
        self, cmds, raises=False, warn=True, stdin=None, no_container=False, **kwargs
    ):
        """Execute a command."""

        pinput = None
        if isinstance(stdin, (bytes, str)):
            pinput = stdin
            stdin = subprocess.PIPE

        p, actual_cmd = self._popen("cmd_status", cmds, stdin=stdin, **kwargs)
        stdout, stderr = p.communicate(input=pinput)
        rc = p.wait()

        # For debugging purposes.
        self.last = (rc, actual_cmd, cmds, stdout, stderr)

        if rc:
            if warn:
                self.logger.warning(
                    "%s: proc failed: %s:", self, proc_error(p, stdout, stderr)
                )
            if raises:
                # error = Exception("stderr: {}".format(stderr))
                # This annoyingly doesnt' show stderr when printed normally
                error = subprocess.CalledProcessError(rc, actual_cmd)
                error.stdout, error.stderr = stdout, stderr
                raise error

        return rc, stdout, stderr

    def cmd_status(self, cmd, **kwargs):
        if not isinstance(cmd, str):
            cmds = cmd
        else:
            # Make sure the code doesn't think `cd` will work.
            assert not re.match(r"cd(\s*|\s+(\S+))$", cmd)
            cmds = ["/bin/bash", "-c", cmd]
        return self._cmd_status(cmds, **kwargs)

    def cmd_status_host(self, cmd, **kwargs):
        # Make sure the command runs on the host and not in any container.
        return Commander.cmd_status(self, cmd, **kwargs)

    def cmd_legacy(self, cmd, **kwargs):
        """Execute a command with stdout and stderr joined, *IGNORES ERROR*."""

        defaults = {"stderr": subprocess.STDOUT}
        defaults.update(kwargs)
        _, stdout, _ = self.cmd_status(cmd, raises=False, **defaults)
        return stdout

    def cmd_raises(self, cmd, **kwargs):
        """Execute a command. Raise an exception on errors"""

        rc, stdout, _ = self.cmd_status(cmd, raises=True, **kwargs)
        assert rc == 0
        return stdout

    def cmd_raises_host(self, cmd, **kwargs):
        # Make sure the command runs on the host and not in any container.
        return Commander.cmd_status(self, cmd, raises=True, **kwargs)

    # Run a command in a new window (gnome-terminal, screen, tmux, xterm)
    def run_in_window(
        self,
        cmd,
        wait_for=False,
        background=False,
        name=None,
        title=None,
        forcex=False,
        new_window=False,
        tmux_target=None,
    ):
        """
        Run a command in a new window (TMUX, Screen or XTerm).

        Args:
            wait_for: True to wait for exit from command or `str` as channel neme to
                      signal on exit, otherwise False
            background: Do not change focus to new window.
            title: Title for new pane (tmux) or window (xterm).
            name: Name of the new window (tmux)
            forcex: Force use of X11.
            new_window: Open new window (instead of pane) in TMUX
            tmux_target: Target for tmux pane.

        Returns:
            the pane/window identifier from TMUX (depends on `new_window`)
        """

        channel = None
        if isinstance(wait_for, str):
            channel = wait_for
        elif wait_for is True:
            channel = "{}-wait-{}".format(os.getpid(), Commander.tmux_wait_gen)
            Commander.tmux_wait_gen += 1

        sudo_path = self.get_exec_path_host(["sudo"])
        nscmd = sudo_path + " " + self.pre_cmd_str + cmd
        if "TMUX" in os.environ and not forcex:
            cmd = [self.get_exec_path_host("tmux")]
            if new_window:
                cmd.append("new-window")
                cmd.append("-P")
                if name:
                    cmd.append("-n")
                    cmd.append(name)
                if tmux_target:
                    cmd.append("-t")
                    cmd.append(tmux_target)
            else:
                cmd.append("split-window")
                cmd.append("-P")
                cmd.append("-h")
                if not tmux_target:
                    tmux_target = os.getenv("TMUX_PANE", "")
            if background:
                cmd.append("-d")
            if tmux_target:
                cmd.append("-t")
                cmd.append(tmux_target)
            if title:
                nscmd = "printf '\033]2;{}\033\\'; {}".format(title, nscmd)
            if channel:
                nscmd = 'trap "tmux wait -S {}; exit 0" EXIT; {}'.format(channel, nscmd)
            cmd.append(nscmd)
        elif "STY" in os.environ and not forcex:
            # wait for not supported in screen for now
            channel = None
            cmd = [self.get_exec_path_host("screen")]
            if not os.path.exists(
                "/run/screen/S-{}/{}".format(os.environ["USER"], os.environ["STY"])
            ):
                cmd = ["sudo", "-u", os.environ["SUDO_USER"]] + cmd
            cmd.append(nscmd)
        elif "DISPLAY" in os.environ:
            # We need it broken up for xterm
            user_cmd = cmd
            cmd = [self.get_exec_path_host("xterm")]
            if "SUDO_USER" in os.environ:
                cmd = [
                    self.get_exec_path_host("sudo"),
                    "-u",
                    os.environ["SUDO_USER"],
                ] + cmd
            if title:
                cmd.append("-T")
                cmd.append(title)
            cmd.append("-e")
            cmd.append(sudo_path)
            cmd.extend(self.pre_cmd)
            cmd.extend(["bash", "-c", user_cmd])
            # if channel:
            #    return self.cmd_raises(cmd, skip_pre_cmd=True)
            # else:
            p = self.popen(
                cmd,
                skip_pre_cmd=True,
                stdin=None,
                shell=False,
            )
            time_mod.sleep(2)
            if p.poll() is not None:
                self.logger.error("%s: Failed to launch xterm: %s", self, comm_error(p))
            return p
        else:
            self.logger.error(
                "DISPLAY, STY, and TMUX not in environment, can't open window"
            )
            raise Exception("Window requestd but TMUX, Screen and X11 not available")

        pane_info = self.cmd_raises(cmd, skip_pre_cmd=True).strip()

        # Re-adjust the layout
        if "TMUX" in os.environ:
            self.cmd_status(
                "tmux select-layout -t {} tiled".format(
                    pane_info if not tmux_target else tmux_target
                ),
                skip_pre_cmd=True,
            )

        # Wait here if we weren't handed the channel to wait for
        if channel and wait_for is True:
            cmd = [self.get_exec_path_host("tmux"), "wait", channel]
            self.cmd_status(cmd, skip_pre_cmd=True)

        return pane_info

    def delete(self):
        pass


class LinuxNamespace(Commander):
    """
    A linux Namespace.

    An object that creates and executes commands in a linux namespace
    """

    def __init__(
        self,
        name,
        net=True,
        mount=True,
        uts=True,
        cgroup=False,
        ipc=False,
        pid=False,
        time=False,
        user=False,
        set_hostname=True,
        private_mounts=None,
        logger=None,
    ):
        """
        Create a new linux namespace.

        Args:
            name: Internal name for the namespace.
            net: Create network namespace.
            mount: Create network namespace.
            uts: Create UTS (hostname) namespace.
            cgroup: Create cgroup namespace.
            ipc: Create IPC namespace.
            pid: Create PID namespace, also mounts new /proc.
            time: Create time namespace.
            user: Create user namespace, also keeps capabilities.
                set_hostname: Set the hostname to `name`, uts must also be True.
                private_mounts: List of strings of the form
                "[/external/path:]/internal/path. If no external path is specified a
                tmpfs is mounted on the internal path. Any paths specified are first
                passed to `mkdir -p`.
            logger: Passed to superclass.
        """
        super(LinuxNamespace, self).__init__(name, logger)

        self.logger.debug("%s: Creating", self)

        self.cwd = os.path.abspath(os.getcwd())

        self.intf_addrs = {}
        self.next_intf_index = 0

        nslist = []
        # cmd = [] if os.geteuid() == 0 else ["/usr/bin/sudo"]
        cmd = []
        cmd += ["/usr/bin/unshare"]
        flags = "-"
        self.ifnetns = {}

        if cgroup:
            nslist.append("cgroup")
            flags += "C"
        if ipc:
            nslist.append("ipc")
            flags += "i"
        if mount:
            nslist.append("mnt")
            flags += "m"
        if net:
            nslist.append("net")
            # if pid:
            #     os.system(f"touch /tmp/netns-{name}")
            #     cmd.append(f"--net=/tmp/netns-{name}")
            # else:
            flags += "n"
        if pid:
            nslist.append("pid")
            flags += "f"
            flags += "p"
            cmd.append("--mount-proc")
        if time:
            nslist.append("time")
            flags += "T"
        if user:
            nslist.append("user")
            flags += "U"
            cmd.append("--keep-caps")
        if uts:
            nslist.append("uts")
            cmd.append("--uts")

        cmd.append(flags)
        if pid:
            cmd.append(self.get_exec_path_host("tini"))
            cmd.append("-vvv")
        cmd.append("/bin/cat")

        # Using cat and a stdin PIPE is nice as it will exit when we do. However, we
        # also detach it from the pgid so that signals do not propagate to it. This is
        # b/c it would exit early (e.g., ^C) then, at least the main micronet proc which
        # has no other processes like frr daemons running, will take the main network
        # namespace with it, which will remove the bridges and the veth pair (because
        # the bridge side veth is deleted).
        self.logger.debug("%s: creating namespace process: %s", self, cmd)
        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,  # detach from pgid so signals don't propogate
            shell=False,
        )
        self.p = p
        self.pid = p.pid

        self.logger.debug("%s: namespace pid: %d", self, self.pid)

        # -----------------------------------------------
        # Now let's wait until unshare completes it's job
        # -----------------------------------------------
        timeout = Timeout(30)
        while p.poll() is None and not timeout.is_expired():
            for fname in tuple(nslist):
                ours = os.readlink("/proc/self/ns/{}".format(fname))
                theirs = os.readlink("/proc/{}/ns/{}".format(self.pid, fname))
                # See if their namespace is different
                if ours != theirs:
                    nslist.remove(fname)
            if not nslist or (pid and nslist == ["pid"]):
                break
            elapsed = int(timeout.elapsed())
            if elapsed <= 3:
                time_mod.sleep(0.1)
            elif elapsed > 10:
                self.logger.warning(
                    "%s: unshare taking more than %ss: %s", self, elapsed, nslist
                )
                time_mod.sleep(3)
            else:
                self.logger.info(
                    "%s: unshare taking more than %ss: %s", self, elapsed, nslist
                )
                time_mod.sleep(1)
        if p.poll():
            logger.error("%s: namespace process failed: %s", self, comm_error(p))
        assert p.poll() is None, "unshare unexpectedly exited!"
        # assert not nslist, "unshare never unshared!"

        # Set pre-command based on our namespace proc
        self.base_pre_cmd = ["/usr/bin/nsenter", "-a", "-t", str(self.pid)]
        if not pid:
            self.base_pre_cmd.append("-F")
        self.set_pre_cmd(self.base_pre_cmd)

        # Remount /sys to pickup any changes, but keep root /sys/fs/cgroup
        # This pattern could be made generic and supported for any overlapping mounts
        tmpmnt = f"/tmp/cgm-{self.pid}"

        #
        # We do not want cmd_status in child classes (e.g., container) for the remaining
        # setup calls in this __init__ function.
        #
        cmdf = LinuxNamespace.cmd_status
        cmdf(self, f"mkdir {tmpmnt} && mount --rbind /sys/fs/cgroup {tmpmnt}")
        cmdf(self, "mount -t sysfs sysfs /sys")
        cmdf(self, f"mount --move {tmpmnt} /sys/fs/cgroup && rmdir {tmpmnt}")
        # self.cmd_raises(
        #     f"mount -N {self.pid} --bind /sys/fs/cgroup /sys/fs/cgroup",
        #     skip_pre_cmd=True,
        # )
        # o = self.cmd_raises("ls -l /sys/fs/cgroup")
        # self.logger.warning("XXX %s", o)

        # Set the hostname to the namespace name
        if uts and set_hostname:
            # Debugging get the root hostname
            cmdf(self, "hostname " + self.name)
            nroot = subprocess.check_output("hostname")
            if root_hostname != nroot:
                result = self.p.poll()
                assert root_hostname == nroot, "STATE of namespace process {}".format(
                    result
                )

        if private_mounts:
            if isinstance(private_mounts, str):
                private_mounts = [private_mounts]
            for m in private_mounts:
                s = m.split(":", 1)
                if len(s) == 1:
                    self.tmpfs_mount(s[0])
                else:
                    self.bind_mount(s[0], s[1])

        o = cmdf(self, "ls -l /proc/{}/ns".format(self.pid))
        self.logger.debug("namespaces:\n %s", o)

        # will cache the path, which is important in delete to avoid running a shell
        # which can hang during cleanup
        self.ip_path = self.get_exec_path_host("ip")
        cmdf(self, [self.ip_path, "link", "set", "lo", "up"])

    @property
    def intfs(self):
        return self.intf_addrs.keys()

    def tmpfs_mount(self, inner):
        self.logger.debug("Mounting tmpfs on %s", inner)
        self.cmd_raises("mkdir -p " + inner)
        self.cmd_raises("mount -n -t tmpfs tmpfs " + inner)

    def bind_mount(self, outer, inner):
        self.logger.debug("Bind mounting %s on %s", outer, inner)
        # self.cmd_raises("mkdir -p " + inner)
        self.cmd_raises("mount --rbind {} {} ".format(outer, inner))

    def get_exec_path_host(self, binary):
        return self._get_exec_path(binary, self.cmd_status_host, self.exec_paths)

    def add_netns(self, ns):
        self.logger.debug("Adding network namespace %s", ns)

        if os.path.exists("/run/netns/{}".format(ns)):
            self.logger.warning("%s: Removing existing nsspace %s", self, ns)
            try:
                self.delete_netns(ns)
            except Exception as ex:
                self.logger.warning(
                    "%s: Couldn't remove existing nsspace %s: %s",
                    self,
                    ns,
                    str(ex),
                    exc_info=True,
                )
        self.cmd_raises_host([self.ip_path, "netns", "add", ns])

    def delete_netns(self, ns):
        self.logger.debug("Deleting network namespace %s", ns)
        self.cmd_raises_host([self.ip_path, "netns", "delete", ns])

    def set_intf_netns(self, intf, ns, up=False):
        # In case a user hard-codes 1 thinking it "resets"
        ns = str(ns)
        if ns == "1":
            ns = str(self.pid)

        self.logger.debug("Moving interface %s to namespace %s", intf, ns)

        cmd = [self.ip_path, "link", "set", intf, "netns", ns]
        if up:
            cmd.append("up")
        self.intf_ip_cmd(intf, cmd)
        if ns == str(self.pid):
            # If we are returning then remove from dict
            if intf in self.ifnetns:
                del self.ifnetns[intf]
        else:
            self.ifnetns[intf] = ns

    def reset_intf_netns(self, intf):
        self.logger.debug("Moving interface %s to default namespace", intf)
        self.set_intf_netns(intf, str(self.pid))

    def intf_ip_cmd(self, intf, cmd):
        """Run an ip command, considering an interface's possible namespace."""
        if intf in self.ifnetns:
            if isinstance(cmd, list):
                assert cmd[0].endswith("ip")
                cmd[1:1] = ["-n", self.ifnetns[intf]]
            else:
                assert cmd.startswith("ip ")
                cmd = "ip -n " + self.ifnetns[intf] + cmd[2:]
        self.cmd_raises_host(cmd)

    def set_cwd(self, cwd):
        # Set pre-command based on our namespace proc
        if os.path.abspath(cwd) == os.path.abspath(os.getcwd()):
            self.set_pre_cmd(self.base_pre_cmd)
            return
        self.logger.debug("%s: new CWD %s", self, cwd)
        self.set_pre_cmd(self.base_pre_cmd + ["--wd=" + cwd])

    def get_next_intf_name(self):
        ifname = self.name + "-eth" + str(self.next_intf_index)
        self.next_intf_index += 1
        return ifname

    def register_interface(self, ifname):
        if ifname not in self.intf_addrs:
            self.intf_addrs[ifname] = None

    def cleanup_proc(self, p):
        if not p or p.returncode is not None:
            return None

        self.logger.debug("%s: terminate process: %s (%s)", self, p.pid, p)
        os.kill(-p.pid, signal.SIGTERM)
        try:
            if isinstance(p, subprocess.Popen):
                p.communicate(timeout=10)
            else:
                asyncio.wait_for(p.communicate(), timeout=10)
        except (subprocess.TimeoutExpired, asyncio.TimeoutError):
            self.logger.warning(
                "%s: terminate timeout, killing %s (%s)", self, p.pid, p
            )
            os.kill(-p.pid, signal.SIGKILL)
            try:
                if isinstance(p, subprocess.Popen):
                    p.communicate(timeout=2)
                else:
                    asyncio.wait_for(p.communicate(), timeout=2)
            except (subprocess.TimeoutExpired, asyncio.TimeoutError):
                self.logger.warning("%s: kill timeout", self)
                return p
        return None

    def delete(self):
        self.logger.debug("%s: delete", self)
        self.cleanup_proc(self.p)
        self.set_pre_cmd(["/bin/false"])


class SharedNamespace(Commander):
    """
    Share another namespace.

    An object that executes commands in an existing pid's linux namespace
    """

    def __init__(self, name, pid, logger=None):
        """
        Share a linux namespace.

        Args:
            name: Internal name for the namespace.
            pid: PID of the process to share with.
        """
        super(SharedNamespace, self).__init__(name, logger)

        self.logger.debug("%s: Creating", self)

        self.cwd = os.path.abspath(os.getcwd())
        self.pid = pid
        self.intfs = []
        self.next_intf_index = 0

        self.base_pre_cmd = ["/usr/bin/nsenter", "-a", "-t", str(self.pid)]
        self.set_pre_cmd(self.base_pre_cmd)

        self.ip_path = self.get_exec_path("ip")

    def set_cwd(self, cwd):
        # Set pre-command based on our namespace proc
        if os.path.abspath(cwd) == os.path.abspath(os.getcwd()):
            self.set_pre_cmd(self.base_pre_cmd)
            return
        self.logger.debug("%s: new CWD %s", self, cwd)
        self.set_pre_cmd(self.base_pre_cmd + ["--wd=" + cwd])

    def get_next_intf_name(self):
        ifname = self.name + "-eth" + str(self.next_intf_index)
        self.next_intf_index += 1
        return ifname

    def register_interface(self, ifname):
        if ifname not in self.intfs:
            self.intfs.append(ifname)


class Bridge(SharedNamespace):
    """
    A linux bridge.
    """

    next_ord = 1

    @classmethod
    def _get_next_id(cls):
        n = cls.next_ord
        cls.next_ord = n + 1
        return n

    def __init__(self, name=None, unet=None, logger=None):
        """Create a linux Bridge."""

        self.id = self._get_next_id()
        if not name:
            name = "br{}".format(self.id)
        super(Bridge, self).__init__(name, unet.pid, logger)

        self.unet = unet

        self.logger.debug("Bridge: Creating")

        assert len(self.name) <= 16  # Make sure fits in IFNAMSIZE
        self.cmd_raises(f"ip link delete {name} || true")
        self.cmd_raises(f"ip link add {name} type bridge")
        self.cmd_raises(f"ip link set {name} up")

        self.logger.debug("%s: Created, Running", self)

    def delete(self):
        """Stop the bridge (i.e., delete the linux resources)."""

        rc, o, e = self.cmd_status(
            [self.ip_path, "link", "show", self.name],
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            warn=False,
        )
        if not rc:
            rc, o, e = self.cmd_status(
                [self.ip_path, "link", "delete", self.name],
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                warn=False,
            )
        if rc:
            self.logger.error(
                "%s: error deleting bridge %s: %s",
                self,
                self.name,
                cmd_error(rc, o, e),
            )
        else:
            self.logger.debug("%s: Deleted.", self)


class BaseMicronet(LinuxNamespace):
    """
    Micronet.
    """

    def __init__(self, **kwargs):
        """Create a Micronet."""

        self.hosts = {}
        self.switches = {}
        self.links = {}
        self.macs = {}
        self.rmacs = {}

        super().__init__("micronet", mount=True, net=True, uts=True, **kwargs)

        # this is for testing purposes do not use
        if not BaseMicronet.g_unet:
            BaseMicronet.g_unet = self

        self.logger.debug("%s: Creating", self)

    def __getitem__(self, key):
        if key in self.switches:
            return self.switches[key]
        return self.hosts[key]

    def add_host(self, name, cls=LinuxNamespace, **kwargs):
        """Add a host to micronet."""

        self.logger.debug("%s: add_host %s(%s)", self, cls.__name__, name)

        self.hosts[name] = cls(name, **kwargs)
        # Create a new mounted FS for tracking nested network namespaces creatd by the
        # user with `ip netns add`

        # XXX add me back smarter to handle containers
        # self.hosts[name].tmpfs_mount("/run/netns")

        return self.hosts[name]

    def add_link(self, node1, node2, if1, if2):
        """Add a link between switch and node or 2 nodes."""
        isp2p = False

        try:
            name1 = node1.name
        except AttributeError:
            if node1 in self.switches:
                node1 = self.switches[node1]
            else:
                node1 = self.hosts[node1]
            name1 = node1.name

        try:
            name2 = node2.name
        except AttributeError:
            if node2 in self.switches:
                node2 = self.switches[node2]
            else:
                node2 = self.hosts[node2]
            name2 = node2.name

        if name1 in self.switches:
            assert name2 in self.hosts
        elif name2 in self.switches:
            assert name1 in self.hosts
            name1, name2 = name2, name1
            if1, if2 = if2, if1
        else:
            # p2p link
            assert name1 in self.hosts
            assert name2 in self.hosts
            isp2p = True

        lname = "{}:{}-{}:{}".format(name1, if1, name2, if2)
        self.logger.debug("%s: add_link %s%s", self, lname, " p2p" if isp2p else "")
        self.links[lname] = (name1, if1, name2, if2)

        # And create the veth now.
        if isp2p:
            lhost, rhost = self.hosts[name1], self.hosts[name2]
            lifname = "i1{:x}".format(lhost.pid)
            rifname = "i2{:x}".format(rhost.pid)
            self.cmd_raises_host(
                "ip link add {} type veth peer name {}".format(lifname, rifname)
            )

            self.cmd_raises_host("ip link set {} netns {}".format(lifname, lhost.pid))
            lhost.cmd_raises_host("ip link set {} name {}".format(lifname, if1))
            lhost.cmd_raises_host("ip link set {} up".format(if1))
            lhost.register_interface(if1)

            self.cmd_raises_host("ip link set {} netns {}".format(rifname, rhost.pid))
            rhost.cmd_raises_host("ip link set {} name {}".format(rifname, if2))
            rhost.cmd_raises_host("ip link set {} up".format(if2))
            rhost.register_interface(if2)
        else:
            switch = self.switches[name1]
            host = self.hosts[name2]

            assert len(if1) <= 16 and len(if2) <= 16  # Make sure fits in IFNAMSIZE

            self.logger.debug("%s: Creating veth pair for link %s", self, lname)
            self.cmd_raises_host(
                f"ip link add {if1} type veth peer name {if2} netns {host.pid}"
            )
            self.cmd_raises_host(f"ip link set {if1} netns {switch.pid}")
            switch.register_interface(if1)
            host.register_interface(if2)
            self.cmd_raises_host(f"ip link set {if1} master {switch.name}")
            self.cmd_raises_host(f"ip link set {if1} up")
            host.cmd_raises_host(f"ip link set {if2} up")

        # Cache the MAC values, and reverse mapping
        self.get_mac(name1, if1)
        self.get_mac(name2, if2)

    def add_switch(self, name, cls=Bridge, **kwargs):
        """Add a switch to micronet."""

        self.logger.debug("%s: add_switch %s(%s)", self, cls.__name__, name)
        self.switches[name] = cls(name, unet=self, **kwargs)
        return self.switches[name]

    def get_mac(self, name, ifname):
        if name in self.hosts:
            dev = self.hosts[name]
        else:
            dev = self.switches[name]

        if (name, ifname) not in self.macs:
            _, output, _ = dev.cmd_status_host("ip -o link show " + ifname)
            m = re.match(".*link/(loopback|ether) ([0-9a-fA-F:]+) .*", output)
            mac = m.group(2)
            self.macs[(name, ifname)] = mac
            self.rmacs[mac] = (name, ifname)

        return self.macs[(name, ifname)]

    def delete(self):
        """Delete the micronet topology."""

        self.logger.debug("%s: Deleting.", self)

        for lname, (_, _, rname, rif) in self.links.items():
            host = self.hosts[rname]

            self.logger.debug("%s: Deleting veth pair for link %s", self, lname)

            rc, o, e = host.cmd_status_host(
                [self.ip_path, "link", "delete", rif],
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                warn=False,
            )
            if rc:
                self.logger.error(
                    "Error deleting veth pair %s: %s", lname, cmd_error(rc, o, e)
                )

        self.links = {}

        for host in self.hosts.values():
            try:
                host.delete()
            except Exception as error:
                self.logger.error(
                    "%s: error while deleting host %s: %s", self, host, error
                )

        self.hosts = {}

        for switch in self.switches.values():
            try:
                switch.delete()
            except Exception as error:
                self.logger.error(
                    "%s: error while deleting switch %s: %s", self, switch, error
                )
        self.switches = {}

        self.logger.debug("%s: Deleted.", self)

        super().delete()


BaseMicronet.g_unet = None


# ---------------------------
# Root level utility function
# ---------------------------


def get_exec_path(binary):
    base = Commander("base")
    return base.get_exec_path(binary)


commander = Commander("micronet")
