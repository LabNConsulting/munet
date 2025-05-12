.. SPDX-License-Identifier: GPL-2.0-or-later
..
.. November 26 2022, Christian Hopps <chopps@labn.net>
..
.. Copyright (c) 2022, LabN Consulting, L.L.C.
..

.. _munet-config:

Configuration
=============

Munet configuration is modeled with YANG. The YANG module definition can be
found XXX`here`.

Variables
---------

Munet defines a few variables for use within both any munet configuration file
and the enviornment namespaces of any munet node.

Configuration Files
^^^^^^^^^^^^^^^^^^^

The following variables are expanded with their dynamic values when munet
interprets the configuration.

  ``%CONFIGDIR%``
    Expands to the absolute path to the directory containing the config file.
    This variable is often useful for mounting configuration directories and
    files.

  ``%NAME%``
    Expands to the name of the node owning the config item this variable is used
    in.

  ``%RUNDIR%``
    Expands to the absolute path to the runtime directory of the node owning
    the config item this variable is used in. This directory is often useful for
    mounting runtime directories (e.g., log directories) in the node namespace.

.. warning::
  Some configuration options do not support the full range of configuration
  variables. In order to determine whether a variable will be expanded or not,
  please check the config's description within the YANG module definition.


Environment Variables
^^^^^^^^^^^^^^^^^^^^^

The following enviornment variables are made available to any command executed
within a munet node or interactive terminal opened within a munet node. These
variables should not be overwritten since they may be used to assist munet in
cleaning up.

  ``MUNET_PID``
    The PID of the parent munet process.

  ``MUNET_NODENAME``
    The name of the target munet node.

Some extra variables are also set *only* in interactive terminals to make
availible the same variables present within the regular munet config. (i.e.
see the start of the ``Variables`` section.)

  ``RUNDIR``
    Same as ``%RUNDIR%``.

  ``NODENAME``
    Same as ``%NAME%``.

  ``CONFIGDIR``
    Same as ``%CONFIGDIR%``.


Topology
--------

The topology section defines the networks and nodes that make up the topology
along withe a few global topology options.

.. pyang labn-munet-config.yang -f tree --tree-path=/topology

Tree diagram for topology config::

   +--rw topology
   |  +--rw dns-network?           -> ../networks/name
   |  +--rw ipv6-enable?           boolean
   |  +--rw networks-autonumber?   boolean
   |  +--rw networks* [name]
   |     ... described in subsection
   |  +--rw nodes* [name]
   |     ... described in subsection


Networks
^^^^^^^^

.. pyang labn-munet-config.yang -f tree --tree-path=/topology/networks

Tree diagram for network config::

   +--rw topology
   |  +--rw networks* [name]
   |  |  +--rw name    string
   |  |  +--rw ip?     string


Nodes
^^^^^

.. pyang labn-munet-config.yang -f tree --tree-path=/topology/nodes

Tree diagram for node config::

   +--rw topology
   |  +--rw nodes* [name]
   |     +--rw id?            uint32
   |     +--rw kind?          -> ../../../kinds/name
   |     +--rw cap-add*       string
   |     +--rw cap-remove*    string
   |     +--rw cmd?           string
   |     +--rw cleanup-cmd?   string
   |     +--rw image?         string
   |     +--rw server?        string
   |     +--rw server-port?   uint16
   |     +--rw qemu
   |     +--rw connections* [to]
   |        ... described in subsection
   |     +--rw env* [name]
   |     |  +--rw name     string
   |     |  +--rw value?   string
   |     +--rw init?          union
   |     +--rw mounts* [destination]
   |        ... described in subsection
   |     |  +--rw destination    string
   |     |  +--rw source?        string
   |     |  +--rw tmpfs-size?    string
   |     |  +--rw type?          string
   |     +--rw name           string
   |     +--rw podman
   |     |  +--rw extra-args*   string
   |     +--rw privileged?    boolean
   |     +--rw shell?         union
   |     +--rw volumes*       string


Connections
"""""""""""

.. pyang labn-munet-config.yang -f tree --tree-path=/topology/nodes/connections

Tree diagram for node connections::

   +--rw topology
   |  +--rw nodes* [name]
   |     +--rw connections* [to]
   |     |  +--rw to                    string
   |     |  +--rw ip?                   string
   |     |  +--rw name?                 string
   |     |  +--rw hostintf?             string
   |     |  +--rw physical?             string
   |     |  +--rw remote-name?          string
   |     |  +--rw driver?               string
   |     |  +--rw delay?                uint64
   |     |  +--rw jitter?               uint64
   |     |  +--rw jitter-correlation?   decimal64
   |     |  +--rw loss?                 uint64
   |     |  +--rw loss-correlation?     decimal64
   |     |  +--rw rate
   |     |     +--rw rate?    number64
   |     |     +--rw limit?   number64
   |     |     +--rw burst?   number64


Mounts
""""""

.. pyang labn-munet-config.yang -f tree --tree-path=/topology/nodes/mounts

Tree diagrame for node mounts::

   +--rw topology
   |  +--rw nodes* [name]
   |     +--rw mounts* [destination]
   |     |  +--rw destination    string
   |     |  +--rw source?        string
   |     |  +--rw tmpfs-size?    string
   |     |  +--rw type?          string


Kinds
-----

A kind configuration is the same as ``node:`` config and allows for specifying
common node configuration for a "kind" of node. By specifying a ``kind:`` config
type for a node, the node will inherits all the config values from that kind.

The following example illustrates creating an **ubuntu-container** kind which
specifies a container image and a tmpfs mount. This new kind is used to create 3
nodes, **u1**, **u2**, and **u3**.

.. code-block:: yaml

  topology:
    nodes:
      - name: u1
        kind: ubuntu-container
      - name: u2
        kind: ubuntu-container
      - name: u3
        kind: ubuntu-container
    # ...
  kinds:
    - name: ubuntu-container
      image: docker.io/ubuntu
      mounts:
        - type: tmpfs
          tmpfs-size: 512M
          destination: /mytmp


CLI
---

.. pyang labn-munet-config.yang -f tree --tree-path=/cli

Tree diagram for CLI config::

   +--rw cli
      +--rw commands* [name]
         +--rw exec?          string
         +--rw exec-kind* [kind]
         |  +--rw kind    string
         |  +--rw exec?   string
         +--rw format?        string
         +--rw help?          string
         +--rw interactive?   boolean
         +--rw kinds*         -> ../../../kinds/name
         +--rw name           string
         +--rw new-window?    boolean
         +--rw top-level?     boolean

The following example illustrates creating 2 CLI commands.

.. code-block:: yaml
   :caption: An example of defining 2 CLI commands

   cli:
     commands:
       - name: ""
         exec: "vtysh -c '{}'"
         format: "[ROUTER ...] COMMAND"
         help: "execute vtysh COMMAND on the router[s]"
         kinds: ["frr"]

       - name: "vtysh"
         exec: "/usr/bin/vtysh"
         format: "vtysh ROUTER [ROUTER ...]"
         new-window: true
         kinds: ["frr"]

The first CLI command, because it has an empty :yaml:`name:`, is a default command. The
default command is executed if the user entered command line does not match any
other defined CLI commands. In this case the command text is inserted into the
command :code:`vtysh -c 'user-entered-value'` and is executed on the ROUTER[s]
(node[s]) the user specifies or all nodes if no ROUTER (node names) are
supplied.

Note the use of the **kinds:** config. This restricts the command to only
running on nodes of the specified kinds. In the example above the commands will
only run on nodes which are defined as **frr** kind.

The second command is a window creating command. For each ROUTER (node)
specified a window will be opened using the users window system (**tmux**,
**screen**, or **X11**). In this case the command that will be run in each
window is an *FRR* console (**vtysh**).
