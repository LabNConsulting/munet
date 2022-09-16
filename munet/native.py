# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# October 1 2021, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2021-2022, LabN Consulting, L.L.C.
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
"A module that defines objects for standalone use."
import asyncio
import errno
import ipaddress
import logging
import os
import random
import re
import shlex
import socket
import subprocess

from . import cli
from .base import BaseMunet
from .base import Bridge
from .base import Commander
from .base import LinuxNamespace
from .base import MunetError
from .base import Timeout
from .base import _async_get_exec_path
from .base import _get_exec_path
from .base import cmd_error
from .base import commander
from .base import get_exec_path_host
from .config import config_subst
from .config import config_to_dict_with_key
from .config import find_matching_net_config
from .config import merge_kind_config


class L3ContainerNotRunningError(MunetError):
    "Exception if no running container exists"


def get_loopback_ips(c, nid):
    if ip := c.get("ip"):
        if ip == "auto":
            return [ipaddress.ip_interface("10.255.0.0/32") + nid]
        if isinstance(ip, str):
            return [ipaddress.ip_interface(ip)]
        return [ipaddress.ip_interface(x) for x in ip]
    return []


def make_ip_network(net, inc):
    n = ipaddress.ip_network(net)
    return ipaddress.ip_network(
        (n.network_address + inc * n.num_addresses, n.prefixlen)
    )


def get_ip_network(c, brid):
    ip = c.get("ip")
    if ip and str(ip) != "auto":
        try:
            ifip = ipaddress.ip_interface(ip)
            if ifip.ip == ifip.network.network_address:
                return ifip.network
            return ifip
        except ValueError:
            return ipaddress.ip_network(ip)
    return make_ip_network("10.0.0.0/24", brid)


def parse_pciaddr(devaddr):
    comp = re.match(
        "(?:([0-9A-Fa-f]{4}):)?([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2}).([0-7])", devaddr
    ).groups()
    if comp[0] is None:
        comp[0] = "0000"
    return [int(x, 16) for x in comp]


def read_int_value(path):
    return int(open(path, encoding="ascii").read())


def read_str_value(path):
    return open(path, encoding="ascii").read().strip()


def read_sym_basename(path):
    return os.path.basename(os.readlink(path))


async def to_thread(func):
    """to_thread for python < 3.9"""
    try:
        return await asyncio.to_thread(func)
    except AttributeError:
        logging.warning("Using backport to_thread")
        return await asyncio.get_running_loop().run_in_executor(None, func)


class L2Bridge(Bridge):
    """
    A linux bridge with no IP network address.
    """

    def __init__(self, name=None, unet=None, logger=None, config=None):
        """Create a linux Bridge."""

        super().__init__(name=name, unet=unet, logger=logger)

        self.config = config if config else {}


class L3Bridge(Bridge):
    """
    A linux bridge with associated IP network address.
    """

    def __init__(self, name=None, unet=None, logger=None, config=None):
        """Create a linux Bridge."""

        super().__init__(name=name, unet=unet, logger=logger)

        self.config = config if config else {}

        self.ip_interface = get_ip_network(self.config, self.id)
        if hasattr(self.ip_interface, "network"):
            self.ip_address = self.ip_interface.ip
            self.ip_network = self.ip_interface.network
            self.cmd_raises(f"ip addr add {self.ip_interface} dev {name}")
        else:
            self.ip_address = None
            self.ip_network = self.ip_interface

        self.logger.debug("%s: set network address to %s", self, self.ip_interface)

        self.is_nat = self.config.get("nat", False)
        if self.is_nat:
            self.cmd_raises(
                "iptables -t nat -A POSTROUTING "
                f"-s {self.ip_network} ! -o {self.name} -j MASQUERADE"
            )

    async def _async_delete(self):
        if type(self) == L3Bridge:  # pylint: disable=C0123
            self.logger.info("%s: deleting", self)
        else:
            self.logger.debug("%s: L3Bridge sub-class _async_delete", self)

        if self.config.get("nat", False):
            self.cmd_status(
                "iptables -t nat -D POSTROUTING "
                f"-s {self.ip_network} ! -o {self.name} -j MASQUERADE"
            )

        await super()._async_delete()


class L3Node(LinuxNamespace):
    """
    A linux namespace with IP attributes.
    """

    next_ord = 1

    @classmethod
    def _get_next_ord(cls):
        # Do not use `cls` here b/c that makes the variable class specific
        n = L3Node.next_ord
        L3Node.next_ord = n + 1
        return n

    def __init__(self, name, config=None, unet=None, **kwargs):
        """Create a linux Bridge."""

        self.config = config if config else {}
        config = self.config

        self.cmd_p = None
        self.container_id = None
        self.id = int(config["id"]) if "id" in config else self._get_next_ord()
        assert unet is not None
        self.unet = unet
        self.cleanup_called = False

        self.host_intfs = {}
        self.phy_intfs = {}
        self.phycount = 0
        self.phy_odrivers = {}
        self.tapmacs = {}

        self.intf_tc_count = 0

        if not name:
            name = "r{}".format(self.id)

        # Clear and create rundir early
        self.rundir = os.path.join(unet.rundir, name)
        commander.cmd_raises(f"rm -rf {self.rundir}")
        commander.cmd_raises(f"mkdir -p {self.rundir}")

        super().__init__(name=name, **kwargs)

        self.mount_volumes()

        # -----------------------
        # Setup node's networking
        # -----------------------
        if not self.unet.ipv6_enable:
            # Disable IPv6
            self.cmd_raises("sysctl -w net.ipv6.conf.all.autoconf=0")
            self.cmd_raises("sysctl -w net.ipv6.conf.all.disable_ipv6=1")

        self.next_p2p_network = ipaddress.ip_network(f"10.254.{self.id}.0/31")

        self.loopback_ip = None
        self.loopback_ips = get_loopback_ips(self.config, self.id)
        self.loopback_ip = self.loopback_ips[0] if self.loopback_ips else None
        if self.loopback_ip:
            self.cmd_raises_host(f"ip addr add {self.loopback_ip} dev lo")
            self.cmd_raises_host("ip link set lo up")
            for i, ip in enumerate(self.loopback_ips[1:]):
                self.cmd_raises_host(f"ip addr add {ip} dev lo:{i}")

        # -------------------
        # Setup node's rundir
        # -------------------

        # Not host path based, but we assume same
        self.set_cwd(self.rundir)

        # Save the namespace pid
        with open(os.path.join(self.rundir, "nspid"), "w", encoding="ascii") as f:
            f.write(f"{self.pid}\n")

        # Create a hosts file to map our name
        hosts_file = os.path.join(self.rundir, "hosts.txt")
        if not os.path.exists(hosts_file):
            with open(hosts_file, "w+", encoding="ascii") as hf:
                hf.write(
                    f"""127.0.0.1\tlocalhost {self.name}
::1\tip6-localhost ip6-loopback
fe00::0\tip6-localnet
ff00::0\tip6-mcastprefix
ff02::1\tip6-allnodes
ff02::2\tip6-allrouters
"""
                )
        self.bind_mount(hosts_file, "/etc/hosts")

        if not self.is_container:
            self.pytest_hook_open_shell()

    async def console(
        self,
        concmd,
        prompt=r"(^|\r\n)[^#\$]*[#\$] ",
        user=None,
        password=None,
        use_pty=False,
        will_echo=False,
        logfile_prefix="console",
        trace=True,
    ):
        """
        Create a REPL (read-eval-print-loop) driving a console.

        Args:
            concmd - string or list to popen with, or an already open socket
            prompt - the REPL prompt to look for, the function returns when seen
            user - user name to log in with
            password - password to log in with
            use_pty - true for pty based expect, otherwise uses popen (pipes/files)
            will_echo - bash is buggy in that it echo's to non-tty unlike any other
                        sh/ksh, set this value to true if running back
            trace - trace the send/expect sequence
            **kwargs - kwargs passed on the _spawn.
        """

        lfname = os.path.join(self.rundir, f"{logfile_prefix}-log.txt")
        logfile = open(lfname, "a+", encoding="utf-8")
        logfile.write("-- start logging for: '{}' --\n".format(concmd))

        lfname = os.path.join(self.rundir, f"{logfile_prefix}-read-log.txt")
        logfile_read = open(lfname, "a+", encoding="utf-8")
        logfile_read.write("-- start read logging for: '{}' --\n".format(concmd))

        lfname = os.path.join(self.rundir, f"{logfile_prefix}-send-log.txt")
        logfile_send = open(lfname, "a+", encoding="utf-8")
        logfile_send.write("-- start send logging for: '{}' --\n".format(concmd))

        expects = []
        sends = []
        if user:
            expects.append("ogin:")
            sends.append(user + "\n")
        if password is not None:
            expects.append("assword:")
            sends.append(password + "\n")
        repl = await self.shell_spawn(
            concmd,
            prompt,
            expects=expects,
            sends=sends,
            use_pty=use_pty,
            will_echo=will_echo,
            logfile=logfile,
            logfile_read=logfile_read,
            logfile_send=logfile_send,
            trace=trace,
        )
        return repl

    async def monitor(
        self,
        sockpath,
        prompt=r"\(qemu\) ",
    ):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(sockpath)

        pfx = os.path.basename(sockpath)

        lfname = os.path.join(self.rundir, f"{pfx}-log.txt")
        logfile = open(lfname, "a+", encoding="utf-8")
        logfile.write("-- start logging for: '{}' --\n".format(sock))

        lfname = os.path.join(self.rundir, f"{pfx}-read-log.txt")
        logfile_read = open(lfname, "a+", encoding="utf-8")
        logfile_read.write("-- start read logging for: '{}' --\n".format(sock))

        p = self.spawn(sock, prompt, logfile=logfile, logfile_read=logfile_read)
        from .base import ShellWrapper  # pylint: disable=C0415

        # ShellWrapper (REPLWrapper) unfortunately uses string match not regex
        # for the prompt
        p.send("\n")
        prompt = "(qemu) "
        return ShellWrapper(p, prompt, None, will_echo=True)

    def mount_volumes(self):
        for m in self.config.get("volumes", []):
            if isinstance(m, str):
                s = m.split(":", 1)
                if len(s) == 1:
                    self.tmpfs_mount(s[0])
                else:
                    spath = s[0]
                    if spath[0] == ".":
                        spath = os.path.abspath(
                            os.path.join(self.unet.config_dirname, spath)
                        )
                    self.bind_mount(spath, s[1])
                continue
            raise NotImplementedError("complex mounts for non-containers")

    def get_ifname(self, netname):
        for c in self.config["connections"]:
            if c["to"] == netname:
                return c["name"]
        return None

    async def run_cmd(self):
        """Run the configured commands for this node"""

        self.logger.debug(
            "[rundir %s exists %s]", self.rundir, os.path.exists(self.rundir)
        )

        shell_cmd = self.config.get("shell", "/bin/bash")
        if not isinstance(shell_cmd, str):
            if shell_cmd:
                shell_cmd = "/bin/bash"
            else:
                shell_cmd = ""

        cmd = self.config.get("cmd", "").strip()
        if not cmd:
            return None

        # See if we have a custom update for this `kind`
        if kind := self.config.get("kind", None):
            if kind in kind_run_cmd_update:
                await kind_run_cmd_update[kind](self, shell_cmd, [], cmd)

        if shell_cmd:
            cmd = cmd.rstrip()
            cmd = cmd.replace("%CONFIGDIR%", self.unet.config_dirname)
            cmd = cmd.replace("%RUNDIR%", self.rundir)
            cmd = cmd.replace("%NAME%", self.name)
            cmd += "\n"
            cmdpath = os.path.join(self.rundir, "cmd.shebang")
            with open(cmdpath, mode="w+", encoding="utf-8") as cmdfile:
                cmdfile.write(f"#!{shell_cmd}\n")
                cmdfile.write(cmd)
                cmdfile.flush()
            self.cmd_raises_host(f"chmod 755 {cmdpath}")
            cmds = [cmdpath]
        else:
            cmds = shlex.split(cmd)
            cmds = [x.replace("%CONFIGDIR%", self.unet.config_dirname) for x in cmds]
            cmds = [x.replace("%RUNDIR%", self.rundir) for x in cmds]
            cmds = [x.replace("%NAME%", self.name) for x in cmds]

        stdout = open(os.path.join(self.rundir, "cmd.out"), "wb")
        stderr = open(os.path.join(self.rundir, "cmd.err"), "wb")
        self.cmd_p = await self.async_popen(
            cmds,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,  # allows us to signal all children to exit
        )

        self.logger.debug(
            "%s: async_popen %s => %s",
            self,
            cmds,
            self.cmd_p.pid,
        )

        self.pytest_hook_run_cmd(stdout, stderr)

        return self.cmd_p

    async def _async_cleanup_cmd(self):
        """Run the configured cleanup commands for this node

        This function is called by subclass' async_cleanup_cmd
        """

        self.cleanup_called = True

        cmd = self.config.get("cleanup_cmd", "").strip()
        if not cmd:
            return

        # shell_cmd is a union and can be boolean or string
        shell_cmd = self.config.get("shell", "/bin/bash")
        if not isinstance(shell_cmd, str):
            if shell_cmd:
                shell_cmd = "/bin/bash"
            else:
                shell_cmd = ""

        # If we have a shell_cmd then we create a cleanup_cmds file in run_cmd
        # and volume mounted it
        if shell_cmd:
            # Create cleanup cmd file
            cmd = cmd.replace("%CONFIGDIR%", self.unet.config_dirname)
            cmd = cmd.replace("%RUNDIR%", self.rundir)
            cmd = cmd.replace("%NAME%", self.name)
            cmd += "\n"

            # Write out our cleanup cmd file at this time too.
            cmdpath = os.path.join(self.rundir, "cleanup_cmd.shebang")
            with open(cmdpath, mode="w+", encoding="utf-8") as cmdfile:
                cmdfile.write(f"#!{shell_cmd}\n")
                cmdfile.write(cmd)
                cmdfile.flush()
            self.cmd_raises_host(f"chmod 755 {cmdpath}")

            if self.container_id:
                cmds = ["/tmp/cleanup_cmds.shebang"]
            else:
                cmds = [cmdpath]
        else:
            cmds = []
            if isinstance(cmd, str):
                cmds.extend(shlex.split(cmd))
            else:
                cmds.extend(cmd)
            cmds = [x.replace("%CONFIGDIR%", self.unet.config_dirname) for x in cmds]
            cmds = [x.replace("%RUNDIR%", self.rundir) for x in cmds]
            cmds = [x.replace("%NAME%", self.name) for x in cmds]

        rc, o, e = await self.async_cmd_status(cmds)
        if not rc and (o or e):
            self.logger.info("async_cleanup_cmd: %s", cmd_error(rc, o, e))

        return rc

    async def async_cleanup_cmd(self):
        """Run the configured cleanup commands for this node"""
        return await self._async_cleanup_cmd()

    def cmd_completed(self, future):
        self.logger.debug("%s: cmd completed called", self)
        try:
            n = future.result()
            self.logger.debug("%s: node cmd completed result: %s", self, n)
        except asyncio.CancelledError:
            # Should we stop the container if we have one?
            self.logger.debug("%s: node cmd wait() canceled", future)

    def set_lan_addr(self, switch, cconf):
        if ip := cconf.get("ip"):
            ipaddr = ipaddress.ip_interface(ip)
        elif self.unet.autonumber and "ip" not in cconf:
            self.logger.debug(
                "%s: prefixlen of switch %s is %s",
                self,
                switch.name,
                switch.ip_network.prefixlen,
            )
            n = switch.ip_network
            ipaddr = ipaddress.ip_interface((n.network_address + self.id, n.prefixlen))
        else:
            return

        ifname = cconf["name"]
        self.intf_addrs[ifname] = ipaddr
        self.logger.debug("%s: adding %s to lan intf %s", self, ipaddr, ifname)
        if not self.is_vm:
            self.intf_ip_cmd(ifname, f"ip addr add {ipaddr} dev {ifname}")
            if hasattr(switch, "is_nat") and switch.is_nat:
                self.cmd_raises(f"ip route add default via {switch.ip_address}")

    def pytest_hook_run_cmd(self, stdout, stderr):
        if not self.unet or not self.unet.pytest_config:
            return

        outopt = self.unet.pytest_config.getoption("--stdout")
        outopt = outopt if outopt is not None else ""
        if outopt == "all" or self.name in outopt.split(","):
            self.run_in_window(f"tail -F {stdout.name}", title=f"O:{self.name}")

        if stderr:
            erropt = self.unet.pytest_config.getoption("--stderr")
            erropt = erropt if erropt is not None else ""
            if erropt == "all" or self.name in erropt.split(","):
                self.run_in_window(f"tail -F {stderr.name}", title=f"E:{self.name}")

    def pytest_hook_open_shell(self):
        if not self.unet or not self.unet.pytest_config:
            return
        shellopt = self.unet.pytest_config.getoption("--shell")
        shellopt = shellopt if shellopt is not None else ""
        if shellopt == "all" or self.name in shellopt.split(","):
            self.run_in_window("bash")

    def set_p2p_addr(self, other, cconf, occonf):
        ipaddr = ipaddress.ip_interface(cconf["ip"]) if cconf.get("ip") else None
        oipaddr = ipaddress.ip_interface(occonf["ip"]) if occonf.get("ip") else None

        if not ipaddr and not oipaddr:
            if self.unet.autonumber:
                n = self.next_p2p_network
                self.next_p2p_network = make_ip_network(n, 1)

                ipaddr = ipaddress.ip_interface(n)
                oipaddr = ipaddress.ip_interface((ipaddr.ip + 1, n.prefixlen))
            else:
                return

        if ipaddr:
            ifname = cconf["name"]
            self.intf_addrs[ifname] = ipaddr
            self.logger.debug("%s: adding %s to p2p intf %s", self, ipaddr, ifname)
            if "physical" not in cconf and not self.is_vm:
                self.intf_ip_cmd(ifname, f"ip addr add {ipaddr} dev {ifname}")

        if oipaddr:
            oifname = occonf["name"]
            other.intf_addrs[oifname] = oipaddr
            self.logger.debug(
                "%s: adding %s to other p2p intf %s", other, oipaddr, oifname
            )
            if "physical" not in occonf and not other.is_vm:
                other.intf_ip_cmd(oifname, f"ip addr add {oipaddr} dev {oifname}")

    async def add_host_intf(self, hname, lname):
        self.host_intfs[hname] = lname
        self.unet.rootcmd.cmd_raises(f"ip link set {hname} down ")
        self.unet.rootcmd.cmd_raises(f"ip link set {hname} netns {self.pid}")
        self.cmd_raises(f"ip link set {hname} name {lname}")
        self.cmd_raises(f"ip link set {lname} up")

    async def rem_host_intf(self, hname):
        lname = self.host_intfs[hname]
        self.cmd_raises(f"ip link set {lname} down")
        self.cmd_raises(f"ip link set {lname} name {hname}")
        self.cmd_raises(f"ip link set {hname} netns 1")
        del self.host_intfs[hname]

    async def add_phy_intf(self, devaddr, lname):
        """Add a physical inteface (i.e. mv it to vfio-pci driver

        This is primarily useful for Qemu, but also for things like TREX or DPDK
        """

        self.phy_intfs[devaddr] = lname
        index = len(self.phy_intfs)

        _, _, off, fun = parse_pciaddr(devaddr)
        doffset = off * 8 + fun

        is_virtual = self.unet.rootcmd.path_exists(
            f"/sys/bus/pci/devices/{devaddr}/physfn"
        )
        if is_virtual:
            pfname = self.unet.rootcmd.cmd_raises(
                f"ls -1 /sys/bus/pci/devices/{devaddr}/physfn/net"
            ).strip()
            pdevaddr = read_sym_basename(f"/sys/bus/pci/devices/{devaddr}/physfn")
            _, _, poff, pfun = parse_pciaddr(pdevaddr)
            poffset = poff * 8 + pfun

            offset = read_int_value(
                f"/sys/bus/pci/devices/{devaddr}/physfn/sriov_offset"
            )
            stride = read_int_value(
                f"/sys/bus/pci/devices/{devaddr}/physfn/sriov_stride"
            )
            vf = (doffset - offset - poffset) // stride
            mac = f"02:cc:cc:cc:{index:02x}:{self.id:02x}"
            # Some devices require the parent to be up (e.g., ixbge)
            self.unet.rootcmd.cmd_raises(f"ip link set {pfname} up")
            self.unet.rootcmd.cmd_raises(f"ip link set {pfname} vf {vf} mac {mac}")
            self.unet.rootcmd.cmd_status(f"ip link set {pfname} vf {vf} trust on")
            self.tapmacs[devaddr] = mac

        self.logger.info("Adding physical PCI device %s as %s", devaddr, lname)

        # Get interface name and set to down if present
        ec, ifname, _ = self.unet.rootcmd.cmd_status(
            f"ls /sys/bus/pci/devices/{devaddr}/net/", warn=False
        )
        ifname = ifname.strip()
        if not ec and ifname:
            # XXX Should only do this is the device is up, and then likewise return it
            # up on exit self.phy_intfs_hostname[devaddr] = ifname
            self.logger.info(
                "Setting physical PCI device %s named %s down", devaddr, ifname
            )
            self.unet.rootcmd.cmd_status(
                f"ip link set {ifname} down 2> /dev/null || true"
            )

        # Get the current bound driver, and unbind
        try:
            driver = read_sym_basename(f"/sys/bus/pci/devices/{devaddr}/driver")
            driver = driver.strip()
        except Exception:
            driver = ""
        if driver:
            if driver == "vfio-pci":
                self.logger.info(
                    "Physical PCI device %s already bound to vfio-pci", devaddr
                )
                return
            self.logger.info(
                "Unbinding physical PCI device %s from driver %s", devaddr, driver
            )
            self.phy_odrivers[devaddr] = driver
            self.unet.rootcmd.cmd_raises(
                f"echo {devaddr} > /sys/bus/pci/drivers/{driver}/unbind"
            )

        # Add the device vendor and device id to vfio-pci in case it's the first time
        vendor = read_str_value(f"/sys/bus/pci/devices/{devaddr}/vendor")
        devid = read_str_value(f"/sys/bus/pci/devices/{devaddr}/device")
        self.logger.info("Adding device IDs %s:%s to vfio-pci", vendor, devid)
        ec, _, _ = self.unet.rootcmd.cmd_status(
            f"echo {vendor} {devid} > /sys/bus/pci/drivers/vfio-pci/new_id", warn=False
        )

        if not self.unet.rootcmd.path_exists(f"/sys/bus/pci/driver/vfio-pci/{devaddr}"):
            # Bind to vfio-pci if wasn't added with new_id
            self.logger.info("Binding physical PCI device %s to vfio-pci", devaddr)
            ec, _, _ = self.unet.rootcmd.cmd_status(
                f"echo {devaddr} > /sys/bus/pci/drivers/vfio-pci/bind"
            )

    async def rem_phy_intf(self, devaddr):
        """Remove a physical inteface (i.e. mv it away from vfio-pci driver

        This is primarily useful for Qemu, but also for things like TREX or DPDK
        """
        lname = self.phy_intfs.get(devaddr, "")
        if lname:
            del self.phy_intfs[devaddr]

        # ifname = self.phy_intfs_hostname.get(devaddr, "")
        # if ifname
        #     del self.phy_intfs_hostname[devaddr]

        driver = self.phy_odrivers.get(devaddr, "")
        if not driver:
            self.logger.info(
                "Physical PCI device %s was bound to vfio-pci on entry", devaddr
            )
            return

        self.logger.info(
            "Unbinding physical PCI device %s from driver vfio-pci", devaddr
        )
        self.unet.rootcmd.cmd_status(
            f"echo {devaddr} > /sys/bus/pci/drivers/vfio-pci/unbind"
        )

        self.logger.info("Binding physical PCI device %s to driver %s", devaddr, driver)
        ec, _, _ = self.unet.rootcmd.cmd_status(
            f"echo {devaddr} > /sys/bus/pci/drivers/{driver}/bind"
        )
        if not ec:
            del self.phy_odrivers[devaddr]

    async def _async_delete(self):
        if type(self) == L3Node:  # pylint: disable=C0123
            # Used to use info here as the top level delete but the user doesn't care,
            # right?
            self.logger.info("%s: deleting", self)
        else:
            self.logger.debug("%s: L3Node sub-class _async_delete", self)

        # First terminate any still running "cmd:"
        # XXX We need to take care of this in container/qemu before getting here.
        await self.async_cleanup_proc(self.cmd_p)

        # Next call users "cleanup_cmd:"
        try:
            if not self.cleanup_called:
                await self.async_cleanup_cmd()
        except Exception as error:
            self.logger.warning(
                "Got an error during delete from async_cleanup_cmd: %s", error
            )

        # remove any hostintf interfaces
        for hname in list(self.host_intfs):
            await self.rem_host_intf(hname)

        # remove any hostintf interfaces
        for devaddr in list(self.phy_intfs):
            await self.rem_phy_intf(devaddr)

        # delete the LinuxNamespace/InterfaceMixin
        await super()._async_delete()


class L3ContainerNode(L3Node):
    """
    An container (podman) based L3Node.
    """

    def __init__(self, name, config, **kwargs):
        """Create a Container Node."""
        self.cont_exec_paths = {}
        self.container_id = None
        self.container_image = config["image"]
        self.extra_mounts = []
        assert self.container_image

        super().__init__(
            name=name,
            config=config,
            # cgroup=True,
            # pid=True,
            # private_mounts=["/sys/fs/cgroup:/sys/fs/cgroup"],
            **kwargs,
        )

    @property
    def is_container(self):
        return True

    def get_exec_path(self, binary):
        """Return the full path to the binary executable inside the image.

        `binary` :: binary name or list of binary names
        """
        return _get_exec_path(binary, self.cmd_status, self.cont_exec_paths)

    async def async_get_exec_path(self, binary):
        """Return the full path to the binary executable inside the image.

        `binary` :: binary name or list of binary names
        """
        path = await _async_get_exec_path(
            binary, self.async_cmd_status, self.cont_exec_paths
        )
        return path

    def get_exec_path_host(self, binary):
        """Return the full path to the binary executable on the host.

        `binary` :: binary name or list of binary names
        """
        return get_exec_path_host(binary)

    def _get_podman_precmd(self, cmd, sudo=False, tty=False):
        if not self.cmd_p:
            raise L3ContainerNotRunningError(f"{self}: cannot execute command: {cmd}")
        assert self.container_id

        cmds = []
        if sudo:
            cmds.append(get_exec_path_host("sudo"))
        cmds.append(get_exec_path_host("podman"))
        cmds.append("exec")
        cmds.append(f"-eMUNET_RUNDIR={self.unet.rundir}")
        cmds.append(f"-eMUNET_NODENAME={self.name}")
        if tty:
            cmds.append("-it")
        cmds.append(self.container_id)

        if not isinstance(cmd, str):
            cmds += cmd
        else:
            # Make sure the code doesn't think `cd` will work.
            assert not re.match(r"cd(\s*|\s+(\S+))$", cmd)
            cmds += ["/bin/bash", "-c", cmd]
        return cmds

    def get_cmd_container(self, cmd, sudo=False, tty=False):
        # return " ".join(self._get_podman_precmd(cmd, sudo=sudo, tty=tty))
        return self._get_podman_precmd(cmd, sudo=sudo, tty=tty)

    def _check_use_base(self, cmd):
        """Check if we should call the base class cmd method.

        This is only the case if we haven't tried to create the container yet.
        """
        if self.cmd_p:
            return False
        if self.container_id is None:
            self.logger.debug(
                "%s: Invoking base class cmd_/popen* function "
                "b/c no container yet: cmd: %s",
                self,
                cmd,
            )
            return True
        self.logger.debug(
            "%s: No running cmd_p, invoking cmd_/popen* to raise exception: cmd: %s",
            self,
            cmd,
        )
        return False

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
        if self._check_use_base(cmd):
            return super().popen(cmd, **kwargs)

        # By default run inside container
        skip_pre_cmd = kwargs.get("skip_pre_cmd", False)

        # Never use the base class nsenter precmd
        kwargs["skip_pre_cmd"] = True
        cmds = cmd if skip_pre_cmd else self._get_podman_precmd(cmd)
        p, _ = self._popen("popen", cmds, **kwargs)
        return p

    async def async_popen(self, cmd, **kwargs):
        if self._check_use_base(cmd):
            return await super().async_popen(cmd, **kwargs)

        # By default run inside container
        skip_pre_cmd = kwargs.get("skip_pre_cmd", False)

        # Never use the base class nsenter precmd
        kwargs["skip_pre_cmd"] = True
        cmds = cmd if skip_pre_cmd else self._get_podman_precmd(cmd)
        p, _ = await self._async_popen("async_popen", cmds, **kwargs)
        return p

    def cmd_status(self, cmd, **kwargs):
        if self._check_use_base(cmd):
            return super().cmd_status(cmd, **kwargs)
        if tty := kwargs.get("tty", False):
            # tty always runs inside container (why?)
            skip_pre_cmd = False
            del kwargs["tty"]
        else:
            # By default run inside container
            skip_pre_cmd = kwargs.get("skip_pre_cmd", False)

        # Never use the base class nsenter precmd
        kwargs["skip_pre_cmd"] = True
        cmds = cmd if skip_pre_cmd else self._get_podman_precmd(cmd, tty)
        cmds = self.cmd_get_cmd_list(cmds)
        return self._cmd_status(cmds, **kwargs)

    async def async_cmd_status(self, cmd, **kwargs):
        if self._check_use_base(cmd):
            return await super().async_cmd_status(cmd, **kwargs)
        if tty := kwargs.get("tty", False):
            # tty always runs inside container (why?)
            skip_pre_cmd = False
            del kwargs["tty"]
        else:
            # By default run inside container
            skip_pre_cmd = kwargs.get("skip_pre_cmd", False)

        # Never use the base class nsenter precmd
        kwargs["skip_pre_cmd"] = True
        cmds = cmd if skip_pre_cmd else self._get_podman_precmd(cmd, tty)
        cmds = self.cmd_get_cmd_list(cmds)
        return await self._async_cmd_status(cmds, **kwargs)

    def tmpfs_mount(self, inner):
        # eventually would be nice to support live mounting
        assert not self.container_id
        self.logger.debug("Mounting tmpfs on %s", inner)
        self.extra_mounts.append(f"--mount=type=tmpfs,destination={inner}")

    def bind_mount(self, outer, inner):
        # eventually would be nice to support live mounting
        assert not self.container_id
        self.logger.debug("Bind mounting %s on %s", outer, inner)
        if not self.test_host("-e", outer):
            self.cmd_raises(f"mkdir -p {outer}")
        self.extra_mounts.append(f"--mount=type=bind,src={outer},dst={inner}")

    def mount_volumes(self):
        args = []
        for m in self.config.get("volumes", []):
            if isinstance(m, str):
                s = m.split(":", 1)
                if len(s) == 1:
                    args.append("--mount=type=tmpfs,destination=" + m)
                else:
                    spath = s[0]
                    spath = os.path.abspath(
                        os.path.join(
                            os.path.dirname(self.unet.config["config_pathname"]), spath
                        )
                    )
                    if not self.test_host("-e", spath):
                        self.cmd_raises(f"mkdir -p {spath}")
                    args.append(f"--mount=type=bind,src={spath},dst={s[1]}")
                continue

        for m in self.config.get("mounts", []):
            margs = ["type=" + m["type"]]
            for k, v in m.items():
                if k == "type":
                    continue
                if v:
                    if k in ("src", "source"):
                        v = os.path.abspath(
                            os.path.join(
                                os.path.dirname(self.unet.config["config_pathname"]), v
                            )
                        )
                        if not self.test_host("-e", v):
                            self.cmd_raises(f"mkdir -p {v}")
                    margs.append(f"{k}={v}")
                else:
                    margs.append(f"{k}")
            args.append("--mount=" + ",".join(margs))

        if args:
            # Need to work on a way to mount into live container too
            self.extra_mounts += args

    async def run_cmd(self):
        """Run the configured commands for this node"""
        self.logger.debug("%s: starting container", self.name)
        self.logger.debug(
            "[rundir %s exists %s]", self.rundir, os.path.exists(self.rundir)
        )

        self.container_id = f"{self.name}-{os.getpid()}"
        cmds = [
            get_exec_path_host("podman"),
            "run",
            f"--name={self.container_id}",
            f"--net=ns:/proc/{self.pid}/ns/net",
            f"--hostname={self.name}",
            f"--add-host={self.name}:127.0.0.1",
            # We can't use --rm here b/c podman fails on "stop".
            # u"--rm",
        ]

        if self.config.get("init", True):
            cmds.append("--init")

        if self.config.get("privileged", False):
            cmds.append("--privileged")
            # If we don't do this then the host file system is remounted read-only on
            # exit!
            cmds.append("--systemd=false")
        else:
            cmds.extend(
                [
                    # "--cap-add=SYS_ADMIN",
                    "--cap-add=NET_ADMIN",
                    "--cap-add=NET_RAW",
                ]
            )

        # Add volumes:
        if self.extra_mounts:
            cmds += self.extra_mounts

        # Add environment variables:
        envdict = self.config.get("env", {})
        if envdict is None:
            envdict = {}
        for k, v in envdict.items():
            cmds.append(f"--env={k}={v}")

        # Update capabilities
        cmds += [f"--cap-add={x}" for x in self.config.get("cap-add", [])]
        cmds += [f"--cap-drop={x}" for x in self.config.get("cap-drop", [])]
        # cmds += [f"--expose={x.split(':')[0]}" for x in self.config.get("ports", [])]
        cmds += [f"--publish={x}" for x in self.config.get("ports", [])]

        # Add extra flags from user:
        if "podman" in self.config:
            for x in self.config["podman"].get("extra-args", []):
                cmds.append(x.strip())

        # shell_cmd is a union and can be boolean or string
        shell_cmd = self.config.get("shell", "/bin/bash")
        if not isinstance(shell_cmd, str):
            if shell_cmd:
                shell_cmd = "/bin/bash"
            else:
                shell_cmd = ""

        # Create cleanup cmd file
        cleanup_cmd = self.config.get("cleanup_cmd", "").strip()
        if shell_cmd and cleanup_cmd:
            # Will write the file contents out when the command is run
            cleanup_cmdpath = os.path.join(self.rundir, "cleanup_cmd.shebang")
            await self.async_cmd_raises_host(f"touch {cleanup_cmdpath}")
            await self.async_cmd_raises_host(f"chmod 755 {cleanup_cmdpath}")
            cmds += [
                # How can we override this?
                # u'--entrypoint=""',
                f"--volume={cleanup_cmdpath}:/tmp/cleanup_cmds.shebang",
            ]

        cmd = self.config.get("cmd", "").strip()

        # See if we have a custom update for this `kind`
        if kind := self.config.get("kind", None):
            if kind in kind_run_cmd_update:
                cmds, cmd = await kind_run_cmd_update[kind](self, shell_cmd, cmds, cmd)

        # Create running command file
        if shell_cmd and cmd:
            assert isinstance(cmd, str)
            # make cmd \n terminated for script
            cmd = cmd.rstrip()
            cmd = cmd.replace("%CONFIGDIR%", self.unet.config_dirname)
            cmd = cmd.replace("%RUNDIR%", self.rundir)
            cmd = cmd.replace("%NAME%", self.name)
            cmd += "\n"
            cmdpath = os.path.join(self.rundir, "cmd.shebang")
            with open(cmdpath, mode="w+", encoding="utf-8") as cmdfile:
                cmdfile.write(f"#!{shell_cmd}\n")
                cmdfile.write(cmd)
                cmdfile.flush()
            self.cmd_raises_host(f"chmod 755 {cmdpath}")
            cmds += [
                # How can we override this?
                # u'--entrypoint=""',
                f"--volume={cmdpath}:/tmp/cmds.shebang",
                self.container_image,
                "/tmp/cmds.shebang",
            ]
        else:
            # `cmd` is a direct run (no shell) cmd
            cmds.append(self.container_image)
            if cmd:
                if isinstance(cmd, str):
                    cmds.extend(shlex.split(cmd))
                else:
                    cmds.extend(cmd)

            cmds = [x.replace("%CONFIGDIR%", self.unet.config_dirname) for x in cmds]
            cmds = [x.replace("%RUNDIR%", self.rundir) for x in cmds]
            cmds = [x.replace("%NAME%", self.name) for x in cmds]

        stdout = open(os.path.join(self.rundir, "cmd.out"), "wb")
        stderr = open(os.path.join(self.rundir, "cmd.err"), "wb")
        self.cmd_p = await self.async_popen(
            cmds,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            # We don't need this here b/c we are only ever running podman and that's all
            # we need to kill for cleanup
            # start_new_session=True,  # allows us to signal all children to exit
            # Skip running with `podman exec` we are creating that ability here.
            skip_pre_cmd=True,
        )

        self.logger.debug("%s: async_popen => %s", self, self.cmd_p.pid)

        self.pytest_hook_run_cmd(stdout, stderr)

        # ---------------------------------------
        # Now let's wait until container shows up
        # ---------------------------------------
        timeout = Timeout(30)
        while self.cmd_p.returncode is None and not timeout.is_expired():
            o = await self.async_cmd_raises_host(
                f"podman ps -q -f name={self.container_id}"
            )
            if o.strip():
                break
            elapsed = int(timeout.elapsed())
            if elapsed <= 3:
                await asyncio.sleep(0.1)
            else:
                self.logger.info("%s: run_cmd taking more than %ss", self, elapsed)
                await asyncio.sleep(1)
        if self.cmd_p.returncode is not None:
            self.logger.warning(
                "%s: run_cmd exited quickly (%ss) rc: %s",
                self,
                timeout.elapsed(),
                self.cmd_p.returncode,
            )
        elif timeout.is_expired():
            self.logger.critical(
                "%s: timeout (%ss) waiting for container to start",
                self.name,
                timeout.elapsed(),
            )
            assert not timeout.is_expired()

        self.logger.info("%s: started container", self.name)

        self.pytest_hook_open_shell()

        return self.cmd_p

    async def async_cleanup_cmd(self):
        """Run the configured cleanup commands for this node"""

        self.cleanup_called = True

        if "cleanup_cmd" not in self.config:
            return

        if not self.cmd_p:
            self.logger.warning("async_cleanup_cmd: container no longer running")
            return

        return await self._async_cleanup_cmd()

    def cmd_completed(self, future):
        try:
            log = self.logger.debug if self.deleting else self.logger.warning
            n = future.result()
            if self.deleting:
                log("contianer `cmd:` result: %s", n)
            else:
                log(
                    "contianer `cmd:` exited early, "
                    "try adding `tail -f /dev/null` to `cmd:`, result: %s",
                    n,
                )
        except asyncio.CancelledError as error:
            # Should we stop the container if we have one? or since we are canceled
            # we know we will be deleting soon?
            self.logger.warning(
                "node container cmd wait() canceled: %s:%s", future, error
            )
        self.cmd_p = None

    async def _async_delete(self):
        if type(self) == L3ContainerNode:  # pylint: disable=C0123
            # Used to use info here as the top level delete but the user doesn't care,
            # right?
            self.logger.info("%s: deleting", self)
        else:
            self.logger.debug("%s: L3ContainerNode delete", self)

        if contid := self.container_id:
            try:
                if not self.cleanup_called:
                    await self.async_cleanup_cmd()
            except Exception as error:
                self.logger.warning(
                    "Got an error during delete from async_cleanup_cmd: %s", error
                )

            o = ""
            e = ""
            if self.cmd_p:
                if (rc := self.cmd_p.returncode) is None:
                    rc, o, e = await self.async_cmd_status_host(
                        [get_exec_path_host("podman"), "stop", contid]
                    )
                if rc and rc < 128:
                    self.logger.warning(
                        "%s: podman stop on cmd failed: %s",
                        self,
                        cmd_error(rc, o, e),
                    )
                else:
                    # It's gone
                    self.cmd_p = None

            # now remove the container
            rc, o, e = await self.async_cmd_status_host(
                [get_exec_path_host("podman"), "rm", contid]
            )
            if rc:
                self.logger.warning(
                    "%s: podman rm failed: %s", self, cmd_error(rc, o, e)
                )
            # keeps us from cleaning up twice
            self.container_id = None

        await super()._async_delete()


class L3QemuVM(L3Node):
    """
    An container (podman) based L3Node.
    """

    def __init__(self, name, config, **kwargs):
        """Create a Container Node."""
        self.cont_exec_paths = {}
        self.launch_p = None
        self.qemu_config = config["qemu"]
        self.extra_mounts = []
        assert self.qemu_config
        self.cmdrepl = None
        self.conrepl = None
        self.monrepl = None
        self.use_console = False
        self.tapfds = {}
        self.tapnames = {}

        super().__init__(name=name, config=config, **kwargs)

        self.sockdir = os.path.join(self.rundir, "s")
        self.bind_mount(self.sockdir, "/tmp/qemu-sock")

        self.qemu_config = config_subst(
            self.qemu_config,
            name=self.name,
            rundir=os.path.join(self.rundir, self.name),
            configdir=self.unet.config_dirname,
        )

    @property
    def is_vm(self):
        return True

    async def moncmd(self):
        "Uses internal REPL to send cmmand to qemu monitor and get reply"

    async def run_cmd(self):
        """Run the configured commands for this node inside VM"""

        self.logger.debug(
            "[rundir %s exists %s]", self.rundir, os.path.exists(self.rundir)
        )

        shell_cmd = self.config.get("shell", "/bin/bash")
        if not isinstance(shell_cmd, str):
            if shell_cmd:
                shell_cmd = "/bin/bash"
            else:
                shell_cmd = ""

        cmd = self.config.get("cmd", "").strip()
        if not cmd:
            return None

        # See if we have a custom update for this `kind`
        if kind := self.config.get("kind", None):
            if kind in kind_run_cmd_update:
                await kind_run_cmd_update[kind](self, shell_cmd, [], cmd)

        if shell_cmd:
            cmd = cmd.rstrip()
            cmd = f"#!{shell_cmd}\n" + cmd
            cmd = cmd.replace("%CONFIGDIR%", self.unet.config_dirname)
            cmd = cmd.replace("%RUNDIR%", self.rundir)
            cmd = cmd.replace("%NAME%", self.name)
            cmd += "\n"

            # Write a copy to the rundir
            cmdpath = os.path.join(self.rundir, "cmd.shebang")
            with open(cmdpath, mode="w+", encoding="utf-8") as cmdfile:
                cmdfile.write(cmd)
            self.cmd_raises_host(f"chmod 755 {cmdpath}")

            # Now write a copy inside the VM
            self.conrepl.cmd_status("cat > /tmp/cmd.shebang << EOF\n" + cmd + "\nEOF")
            self.conrepl.cmd_status("chmod 755 /tmp/cmd.shebang")
            cmds = "/tmp/cmd.shebang"
        else:
            cmds = cmds.replace("%CONFIGDIR%", self.unet.config_dirname)
            cmds = cmds.replace("%RUNDIR%", self.rundir)
            cmds = cmds.replace("%NAME%", self.name)

        class future_proc:
            """Treat awaitable minimally as a proc"""

            def __init__(self, aw):
                self.aw = aw
                # XXX would be nice to have a real value here
                self.returncode = 0

            async def wait(self):
                return await self.aw

        self.cmd_p = future_proc(
            # We need our own console here b/c this is async and not returning
            # immediately
            self.cmdrepl.run_command(cmds, timeout=120, async_=True)
        )
        # output =
        # stdout = open(os.path.join(self.rundir, "cmd.out"), "w")
        # stdout.write(output)
        # stdout.flush()
        # self.pytest_hook_run_cmd(stdout, None)

        return self.cmd_p

    async def add_host_intf(self, hname, lname):
        # L3QemuVM needs it's own add_host_intf for macvtap, We need to create the tap
        # in the host then move that interface so that the ifindex/devfile are
        # different.
        self.host_intfs[hname] = lname
        index = len(self.host_intfs)

        tapindex = self.unet.tapcount
        self.unet.tapcount = self.unet.tapcount + 1

        tapname = f"tap{tapindex}"
        self.tapnames[hname] = tapname

        mac = f"02:bb:bb:bb:{index:02x}:{self.id:02x}"
        self.tapmacs[hname] = mac

        self.unet.rootcmd.cmd_raises(
            f"ip link add link {hname} name {tapname} type macvtap"
        )
        self.unet.rootcmd.cmd_raises(f"ip link set {tapname} address {mac} up")
        ifindex = self.unet.rootcmd.cmd_raises(
            f"cat /sys/class/net/{tapname}/ifindex"
        ).strip()
        # self.unet.rootcmd.cmd_raises(f"ip link set {tapname} netns {self.pid}")

        tapfile = f"/dev/tap{ifindex}"
        fd = os.open(tapfile, os.O_RDWR)
        self.tapfds[hname] = fd
        self.logger.info(
            "%s: Add host intf: created macvtap interface %s (%s) on %s fd %s",
            self,
            tapname,
            tapfile,
            hname,
            fd,
        )

    async def rem_host_intf(self, hname):
        tapname = self.tapnames[hname]
        self.unet.rootcmd.cmd_raises(f"ip link set {tapname} down")
        self.unet.rootcmd.cmd_raises(f"ip link delete {tapname} type macvtap")
        del self.tapnames[hname]
        del self.host_intfs[hname]

    async def create_tap(self, index, ifname):
        # XXX we shouldn't be doign a tap on a bridge with a veth
        # we should just be using a tap created earlier which was connected to the
        # bridge. Except we need to handle the case of p2p qemu <-> namespace
        #
        tapindex = self.unet.tapcount
        self.unet.tapcount += 1
        mac = f"02:aa:aa:aa:{index:02x}:{self.id:02x}"
        # nic = "tap,model=virtio-net-pci"
        # qemu -net nic,model=virtio,addr=1a:46:0b:ca:bc:7b -net tap,fd=3 3<>/dev/tap11
        self.cmd_raises(f"ip address flush dev {ifname}")
        self.cmd_raises(f"ip tuntap add tap{tapindex} mode tap")
        self.cmd_raises(f"ip link add name br{index} type bridge")
        self.cmd_raises(f"ip link set dev {ifname} master br{index}")
        self.cmd_raises(f"ip link set dev tap{tapindex} master br{index}")
        self.cmd_raises(f"ip link set dev tap{tapindex} up")
        self.cmd_raises(f"ip link set dev {ifname} up")
        self.cmd_raises(f"ip link set dev br{index} up")
        return [
            "-netdev",
            f"tap,id=n{index},ifname=tap{tapindex},script=no,downscript=no",
            "-device",
            f"virtio-net-pci,netdev=n{index},mac={mac}",
        ]

    async def renumber_interfaces(self):
        """Re-number the interfaces.

        After VM comes up need to renumber the interfaces now on the inside.
        """
        self.logger.info("Renumbering interfaces")
        con = self.conrepl
        con.cmd_raises("sysctl -w net.ipv4.ip_forward=1")
        for ifname in sorted(self.intf_addrs):
            ifaddr = self.intf_addrs[ifname]
            con.cmd_raises(f"ip link set {ifname} up")
            con.cmd_raises(f"ip addr add {ifaddr} dev {ifname}")

            # # XXX
            # if hasattr(switch, "is_nat") and switch.is_nat:
            #     self.cmd_raises(f"ip route add default via {switch.ip_address}")

    async def _opencons(self, *cnames):
        "Open consoles based on socket file names"

        timeout = Timeout(30)
        cons = []
        for cname in cnames:
            sockpath = os.path.join(self.sockdir, cname)
            connected = False
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            while self.launch_p.returncode is None and not timeout.is_expired():
                try:
                    sock.connect(sockpath)
                    connected = True
                    break
                except OSError as error:
                    if error.errno == errno.ENOENT:
                        self.logger.debug("waiting for console socket: %s", sockpath)
                    else:
                        self.logger.warning(
                            "can't open console socket: %s", error.strerror
                        )
                        raise
                elapsed = int(timeout.elapsed())
                if elapsed <= 3:
                    await asyncio.sleep(0.25)
                else:
                    self.logger.info(
                        "%s: launch (qemu) taking more than %ss", self, elapsed
                    )
                    await asyncio.sleep(1)

            if connected:
                cons.append(
                    await self.console(
                        sock,
                        user="root",
                        use_pty=False,
                        logfile_prefix=cname,
                        will_echo=True,
                        trace=True,
                    )
                )
            elif self.launch_p.returncode is not None:
                self.logger.warning(
                    "%s: launch (qemu) exited quickly (%ss) rc: %s",
                    self,
                    timeout.elapsed(),
                    self.launch_p.returncode,
                )
                raise Exception("Qemu launch exited early")
            elif timeout.is_expired():
                self.logger.critical(
                    "%s: timeout (%ss) waiting for qemu to start",
                    self,
                    timeout.elapsed(),
                )
                assert not timeout.is_expired()

        return cons

    async def launch(self):
        "Launch qemu"
        self.logger.info("%s: Launch Qemu", self)

        qc = self.qemu_config
        bootd = "d" if "iso" in qc else "c"
        args = [get_exec_path_host("qemu-system-x86_64"), "-nodefaults", "-boot", bootd]

        if qc.get("kvm"):
            args += ["-accel", "kvm", "-cpu", "host"]

        if ncpu := qc.get("ncpu"):
            args += ["-smp", f"{ncpu},sockets=1,cores={ncpu},threads=1"]

        args.extend(["-m", str(qc.get("memory", "512M"))])

        if "kernel" in qc:
            args.extend(["-kernel", qc["kernel"]])
        if "initrd" in qc:
            args.extend(["-initrd", qc["initrd"]])
        if "iso" in qc:
            args.extend(["-cdrom", qc["iso"]])

        # we only have append if we have a kernel
        if "kernel" in qc:
            args.append("-append")
            root = qc.get("root", "/dev/ram0")
            # Only 1 serial console the other ports (ttyS[123] hvc[01]) should have
            # gettys in inittab
            append = f"root={root} rw console=ttyS0"
            if "cmdline-extra" in qc:
                append += f" {qc['cmdline-extra']}"
            args.append(append)

        if "extra-args" in qc:
            if isinstance(qc["extra-args"], list):
                args.extend(qc["extra-args"])
            else:
                args.extend(shlex.split(qc["extra-args"]))

        # Walk the list of connections in order so we attach them the same way
        pass_fds = []
        nnics = 0
        pciaddr = 3
        for index, conn in enumerate(self.config["connections"]):
            devaddr = conn.get("physical", "")
            hostintf = conn.get("hostintf", "")
            if devaddr:
                # if devaddr in self.tapmacs:
                #     mac = f",mac={self.tapmacs[devaddr]}"
                # else:
                #     mac = ""
                args += ["-device", f"vfio-pci,host={devaddr},addr={pciaddr}"]
            elif hostintf:
                fd = self.tapfds[hostintf]
                mac = self.tapmacs[hostintf]
                args += [
                    "-nic",
                    f"tap,model=virtio-net-pci,mac={mac},fd={fd},addr={pciaddr}",
                ]
                pass_fds.append(fd)
                nnics += 1
            elif not hostintf:
                tapargs = await self.create_tap(index, conn["name"])
                tapargs[-1] += f",addr={pciaddr}"
                args += tapargs
                nnics += 1
            pciaddr += 1
        if not nnics:
            args += ["-nic", "none"]

        args += [
            # 4 serial ports (max)
            "-serial",
            "stdio",
            "-serial",
            # All these serial/console ports require entries in inittab
            # to have getty running on them, modify inittab
            "unix:/tmp/qemu-sock/_cmdcon,server,nowait",
            "-serial",
            "unix:/tmp/qemu-sock/_console,server,nowait",
            "-serial",
            "unix:/tmp/qemu-sock/console,server,nowait",
            # A 2 virtual consoles - /dev/hvc[01]
            # Requires CONFIG_HVC_DRIVER=y CONFIG_VIRTIO_CONSOLE=y
            "-device",
            "virtio-serial",  # serial console bus
            "-chardev",
            "socket,path=/tmp/qemu-sock/vcon0,server=on,wait=off,id=vcon0",
            "-chardev",
            "socket,path=/tmp/qemu-sock/vcon1,server=on,wait=off,id=vcon1",
            "-device",
            "virtconsole,chardev=vcon0",
            "-device",
            "virtconsole,chardev=vcon1",
            # 2 monitors
            "-monitor",
            "unix:/tmp/qemu-sock/_monitor,server,nowait",
            "-monitor",
            "unix:/tmp/qemu-sock/monitor,server,nowait",
            "-gdb",
            "unix:/tmp/qemu-sock/gdbserver,server,nowait",
            "-nographic",
        ]

        #
        # Launch Qemu
        #

        stdout = open(os.path.join(self.rundir, "qemu.out"), "wb")
        stderr = open(os.path.join(self.rundir, "qemu.err"), "wb")
        self.launch_p = await self.async_popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            pass_fds=pass_fds,
            # We don't need this here b/c we are only ever running qemu and that's all
            # we need to kill for cleanup
            # XXX reconcile this
            start_new_session=True,  # allows us to signal all children to exit
        )

        # We've passed these on, so don't need these open here anymore.
        for fd in pass_fds:
            os.close(fd)

        self.logger.debug("%s: async_popen => %s", self, self.launch_p.pid)

        #
        # Connect to the console socket, retrying
        #
        cons = await self._opencons("_cmdcon", "_console")
        self.cmdrepl = cons[0]
        self.conrepl = cons[1]
        self.monrepl = await self.monitor(os.path.join(self.sockdir, "_monitor"))

        # the monitor output has super annoying ANSI escapes in it
        output = self.monrepl.cmd_nostatus("info status")
        self.logger.info("VM status: %s", output)
        output = self.monrepl.cmd_nostatus("info kvm")
        self.logger.info("KVM status: %s", output)

        # Have standard commands begin to use the console
        self.use_console = True

        await self.renumber_interfaces()

        self.pytest_hook_open_shell()

        return self.launch_p

    def launch_completed(self, future):
        self.logger.debug("%s: launch (qemu) completed called", self)
        try:
            n = future.result()
            self.logger.debug("%s: node launch (qemu) completed result: %s", self, n)
        except asyncio.CancelledError as error:
            self.logger.debug(
                "%s: node launch (qemu) cmd wait() canceled: %s", future, error
            )

    async def cleanup_qemu(self):
        "Launch qemu"
        if self.launch_p:
            await self.async_cleanup_proc(self.launch_p)

    async def async_cleanup_cmd(self):
        """Run the configured cleanup commands for this node"""

        self.cleanup_called = True

        if "cleanup_cmd" not in self.config:
            return

        if not self.launch_p:
            self.logger.warning("async_cleanup_cmd: qemu no longer running")
            return

        raise NotImplementedError("Needs to be like run_cmd")
        # return await self._async_cleanup_cmd()

    async def _async_delete(self):
        if type(self) == L3QemuVM:  # pylint: disable=C0123
            self.logger.info("%s: deleting", self)
        else:
            self.logger.debug("%s: L3QemuVM _async_delete", self)

        if self.cmd_p:
            await self.async_cleanup_proc(self.cmd_p)
            self.cmd_p = None

        try:
            if not self.cleanup_called:
                await self.async_cleanup_cmd()
        except Exception as error:
            self.logger.warning(
                "Got an error during delete from async_cleanup_cmd: %s", error
            )

        try:
            if not self.launch_p:
                self.logger.warning("async_delete: qemu is not running")
            else:
                await self.cleanup_qemu()
        except Exception as error:
            self.logger.warning("%s: failued to cleanup qemu process: %s", self, error)

        await super()._async_delete()


class Munet(BaseMunet):
    """
    Munet.
    """

    def __init__(self, rundir=None, config=None, pytestconfig=None, **kwargs):
        super().__init__(**kwargs)

        self.built = False
        self.tapcount = 0

        self.rundir = rundir if rundir else "/tmp/unet-" + os.environ["USER"]
        self.cmd_raises(f"mkdir -p {self.rundir} && chmod 755 {self.rundir}")
        self.set_cwd(self.rundir)

        if not config:
            config = {}
        self.config = config
        if "config_pathname" in config:
            self.config_pathname = os.path.realpath(config["config_pathname"])
            self.config_dirname = os.path.dirname(self.config_pathname)
        else:
            self.config_pathname = ""
            self.config_dirname = ""

        self.pytest_config = pytestconfig

        # We need some way to actually get back to the root namespace
        if not self.isolated:
            self.rootcmd = commander
        else:
            self.rootcmd = Commander("host")
            self.rootcmd.set_pre_cmd(
                ["/usr/bin/nsenter", *self.a_flags, "-t", "1", "-F"]
            )

        # Save the namespace pid
        with open(os.path.join(self.rundir, "nspid"), "w", encoding="ascii") as f:
            f.write(f"{self.pid}\n")

        # Common CLI commands for any topology
        cdict = {
            "commands": [
                {
                    "name": "pcap",
                    "format": "pcap NETWORK",
                    "help": (
                        "capture packets from NETWORK into file capture-NETWORK.pcap"
                        " the command is run within a new window which also shows"
                        " packet summaries"
                    ),
                    "exec": "tshark -s 1508 -i {0} -P -w capture-{0}.pcap",
                    "top-level": True,
                    "new-window": {"background": True},
                },
                {
                    "name": "hterm",
                    "format": "hterm HOST [HOST ...]",
                    "help": (
                        "open terminal[s] on HOST[S] (outside containers), * for all"
                    ),
                    "exec": "bash",
                    "on-host": True,
                    "new-window": True,
                },
                {
                    "name": "term",
                    "format": "term HOST [HOST ...]",
                    "help": "open terminal[s] (TMUX or XTerm) on HOST[S], * for all",
                    "exec": "bash",
                    "new-window": True,
                },
                {
                    "name": "xterm",
                    "format": "xterm HOST [HOST ...]",
                    "help": "open XTerm[s] on HOST[S], * for all",
                    "exec": "bash",
                    "new-window": {
                        "forcex": True,
                    },
                },
                {
                    "name": "sh",
                    "format": "[HOST ...] sh <SHELL-COMMAND>",
                    "help": "execute <SHELL-COMMAND> on hosts",
                    "exec": "bash -c '{}'",
                },
                {
                    "name": "shi",
                    "format": "[HOST ...] shi <INTERACTIVE-COMMAND>",
                    "help": "execute <INTERACTIVE-COMMAND> on HOST[s]",
                    "exec": "bash -c '{}'",
                    "interactive": True,
                },
                {
                    "name": "stdout",
                    "exec": "tail -F %RUNDIR%/cmd.out",
                    "format": "stdout HOST [HOST ...]",
                    "help": "tail -f on the stdout of the cmd for this node",
                    "new-window": True,
                },
                {
                    "name": "stderr",
                    "exec": "tail -F %RUNDIR%/cmd.err",
                    "format": "stdout HOST [HOST ...]",
                    "help": "tail -f on the stdout of the cmd for this node",
                    "new-window": True,
                },
            ]
        }

        cli.add_cli_config(self, cdict)

        if "cli" in config:
            cli.add_cli_config(self, config["cli"])

        if "topology" not in self.config:
            self.config["topology"] = {}

        self.topoconf = self.config["topology"]
        self.ipv6_enable = self.topoconf.get("ipv6-enable", False)

        if self.isolated and not self.ipv6_enable:
            # Disable IPv6
            self.cmd_raises("sysctl -w net.ipv6.conf.all.autoconf=0")
            self.cmd_raises("sysctl -w net.ipv6.conf.all.disable_ipv6=1")

    def __del__(self):
        "Catch case of build object but not async_deleted"
        if hasattr(self, "built"):
            if not self.deleting:
                logging.critical(
                    "Munet object deleted without calling `async_delete` for cleanup."
                )
        s = super()
        if hasattr(s, "__del__"):
            s.__del__(self)

    async def _async_build(self, logger=None):
        """Build the topology based on config"""

        if self.built:
            self.logger.warning("%s: is already built", self)
            return

        self.built = True

        # Allow for all networks to be auto-numbered
        topoconf = self.topoconf
        autonumber = self.autonumber

        # ---------------------------------------------
        # Merge Kinds and perform variable substitution
        # ---------------------------------------------

        kinds = self.config.get("kinds", {})

        for name, conf in config_to_dict_with_key(topoconf, "networks", "name").items():
            if kind := conf.get("kind"):
                if kconf := kinds[kind]:
                    conf = merge_kind_config(kconf, conf)
            conf = config_subst(conf, name=name, rundir=self.rundir)
            if "ip" not in conf and autonumber:
                conf["ip"] = "auto"
            topoconf["networks"][name] = conf
            self.add_network(name, conf, logger=logger)

        for name, conf in config_to_dict_with_key(topoconf, "nodes", "name").items():
            config_to_dict_with_key(
                conf, "env", "name"
            )  # convert list of env objects to dict

            if kind := conf.get("kind"):
                if kconf := kinds[kind]:
                    conf = merge_kind_config(kconf, conf)

            conf = config_subst(conf, name=name, rundir=os.path.join(self.rundir, name))
            topoconf["nodes"][name] = conf
            self.add_l3_node(name, conf, logger=logger)

        # ------------------
        # Create connections
        # ------------------

        # Go through all connections and name them so they are sane to the user
        # otherwise when we do p2p links the names/ords skip around based oddly
        for name, node in self.hosts.items():
            nconf = node.config
            if "connections" not in nconf:
                continue
            nconns = []
            for cconf in nconf["connections"]:
                # Replace string only with a dictionary
                if isinstance(cconf, str):
                    splitconf = cconf.split(":", 1)
                    cconf = {"to": splitconf[0]}
                    if len(splitconf) == 2:
                        cconf["name"] = splitconf[1]
                # Allocate a name if not already assigned
                if "name" not in cconf:
                    cconf["name"] = node.get_next_intf_name()
                nconns.append(cconf)
            nconf["connections"] = nconns

        for name, node in self.hosts.items():
            nconf = node.config
            if "connections" not in nconf:
                continue
            for cconf in nconf["connections"]:
                # Eventually can add support for unconnected intf here.
                if "to" not in cconf:
                    continue
                to = cconf["to"]
                if to in self.switches:
                    switch = self.switches[to]
                    swconf = find_matching_net_config(name, cconf, switch.config)
                    await self.add_native_link(switch, node, swconf, cconf)
                elif cconf["name"] not in node.intfs:
                    # Only add the p2p interface if not already there.
                    other = self.hosts[to]
                    oconf = find_matching_net_config(name, cconf, other.config)
                    await self.add_native_link(node, other, cconf, oconf)

    @property
    def autonumber(self):
        return self.topoconf.get("networks-autonumber", False)

    @autonumber.setter
    def autonumber(self, value):
        self.topoconf["networks-autonumber"] = bool(value)

    async def add_native_link(self, node1, node2, c1=None, c2=None):
        """Add a link between switch and node or 2 nodes."""
        isp2p = False

        c1 = {} if c1 is None else c1
        c2 = {} if c2 is None else c2

        if node1.name in self.switches:
            assert node2.name in self.hosts
        elif node2.name in self.switches:
            assert node1.name in self.hosts
            node1, node2 = node2, node1
            c1, c2 = c2, c1
        else:
            # p2p link
            assert node1.name in self.hosts
            assert node1.name in self.hosts
            isp2p = True

        if "name" not in c1:
            c1["name"] = node1.get_next_intf_name()
        if1 = c1["name"]

        if "name" not in c2:
            c2["name"] = node2.get_next_intf_name()
        if2 = c2["name"]

        do_add_link = True
        for n, c in ((node1, c1), (node2, c2)):
            if "hostintf" in c:
                await n.add_host_intf(c["hostintf"], c["name"])
                do_add_link = False
            elif "physical" in c:
                await n.add_phy_intf(c["physical"], c["name"])
                do_add_link = False
        if do_add_link:
            assert "hostintf" not in c1
            assert "hostintf" not in c2
            assert "physical" not in c1
            assert "physical" not in c2
            super().add_link(node1, node2, if1, if2)

        if isp2p:
            node1.set_p2p_addr(node2, c1, c2)
        else:
            node2.set_lan_addr(node1, c2)

        if "physical" not in c1 and not node1.is_vm:
            node1.set_intf_constraints(if1, **c1)
        if "physical" not in c2 and not node2.is_vm:
            node2.set_intf_constraints(if2, **c2)

    def add_l3_node(self, name, config=None, **kwargs):
        """Add a node to munet."""

        if config and config.get("image"):
            cls = L3ContainerNode
        elif config and config.get("qemu"):
            cls = L3QemuVM
        else:
            cls = L3Node
        return super().add_host(name, cls=cls, unet=self, config=config, **kwargs)

    def add_network(self, name, config=None, **kwargs):
        """Add a l2 or l3 switch to munet."""
        if config is None:
            config = {}

        cls = L3Bridge if config.get("ip") else L2Bridge
        return super().add_switch(name, cls=cls, config=config, **kwargs)

    async def run(self):
        tasks = []

        launch_nodes = [x for x in self.hosts.values() if hasattr(x, "launch")]
        launch_nodes = [x for x in launch_nodes if x.config.get("qemu")]

        run_nodes = [x for x in self.hosts.values() if hasattr(x, "run_cmd")]
        run_nodes = [
            x for x in run_nodes if x.config.get("cmd") or x.config.get("image")
        ]

        if not self.pytest_config:
            pcapopt = ""
        else:
            pcapopt = self.pytest_config.getoption("--pcap")
            pcapopt = pcapopt if pcapopt else ""
        if pcapopt == "all":
            pcapopt = self.switches.keys()
        if pcapopt:
            for pcap in pcapopt.split(","):
                self.run_in_window(
                    f"tshark -s 1508 -i {pcap} -P -w capture-{pcap}.pcap",
                    background=True,
                    title=f"cap:{pcap}",
                )

        # launch first
        await asyncio.gather(*[x.launch() for x in launch_nodes])
        for node in launch_nodes:
            task = asyncio.create_task(
                node.launch_p.wait(), name=f"Node-{node.name}-launch"
            )
            task.add_done_callback(node.launch_completed)
            tasks.append(task)

        # the run
        await asyncio.gather(*[x.run_cmd() for x in run_nodes])
        for node in run_nodes:
            task = asyncio.create_task(node.cmd_p.wait(), name=f"Node-{node.name}-cmd")
            task.add_done_callback(node.cmd_completed)
            tasks.append(task)
        return tasks

    async def _async_delete(self):
        from munet.testing.util import async_pause_test  # pylint: disable=C0415

        if type(self) == Munet:  # pylint: disable=C0123
            self.logger.info("%s: deleting.", self)
        else:
            self.logger.debug("%s: Munet sub-class munet deleting.", self)

        if not self.pytest_config:
            pause = False
        else:
            pause = bool(self.pytest_config.getoption("--pause-at-end"))
            pause = pause or bool(self.pytest_config.getoption("--pause"))
        if pause:
            try:
                await async_pause_test("Before MUNET delete")
            except KeyboardInterrupt:
                print("^C...continuing")
            except Exception as error:
                self.logger.error("\n...continuing after error: %s", error)

        # XXX should we cancel launch and run tasks?

        await super()._async_delete()


async def run_cmd_update_ceos(node, shell_cmd, cmds, cmd):
    cmd = cmd.strip()
    if shell_cmd or cmd != "/sbin/init":
        return cmds, cmd

    #
    # Add flash dir and mount it
    #
    flashdir = os.path.join(node.rundir, "flash")
    node.cmd_raises_host(f"mkdir -p {flashdir} && chmod 775 {flashdir}")
    cmds += [f"--volume={flashdir}:/mnt/flash"]

    #
    # Startup config (if not present already)
    #
    if startup_config := node.config.get("startup-config", None):
        dest = os.path.join(flashdir, "startup-config")
        if os.path.exists(dest):
            node.logger.info("Skipping copy of startup-config, already present")
        else:
            source = os.path.join(node.unet.config_dirname, startup_config)
            node.cmd_raises_host(f"cp {source} {dest} && chmod 664 {dest}")

    #
    # system mac address (if not present already
    #
    dest = os.path.join(flashdir, "system_mac_address")
    if os.path.exists(dest):
        node.logger.info("Skipping system-mac generation, already present")
    else:
        random_arista_mac = "00:1c:73:%02x:%02x:%02x" % (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )
        system_mac = node.config.get("system-mac", random_arista_mac)
        with open(dest, "w", encoding="ascii") as f:
            f.write(system_mac + "\n")
        node.cmd_raises_host(f"chmod 664 {dest}")

    args = []

    # Pass special args for the environment variables
    if "env" in node.config:
        args += [f"systemd.setenv={k}={v}" for k, v in node.config["env"].items()]

    return cmds, [cmd] + args


kind_run_cmd_update = {"ceos": run_cmd_update_ceos}
