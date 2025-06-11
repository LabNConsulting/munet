.. SPDX-License-Identifier: GPL-2.0-or-later
..
.. November 23 2022, Christian Hopps <chopps@labn.net>
..
.. Copyright (c) 2022, LabN Consulting, L.L.C.
..

Usage
=====

Installation
------------

Install munet using pip:

.. code-block:: console

   $ pip install munet

Or if you need the latest changes from master:

.. code-block:: console

   $ pip install git+https://github.com/LabNConsulting/munet.git#egg=munet

Running
-------

Launching the topology:

.. code-block:: console

   $ sudo munet
   $ sudo munet -c otherconf.yaml

For a list of option use the ``--help`` arg.

.. code-block:: console

   $ sudo munet --help

   usage: () [-h] [-c CONFIG] [-C] [-k KINDS_CONFIG] [--gdb GDB] [--gdb-breakpoints GDB_BREAKPOINTS] [--host] [--log-config LOG_CONFIG] [--no-kill] [--no-cli] [--no-wait] [-d RUNDIR] [--validate-only] [--topology-only] [-v] [-V] [--shell SHELL] [--stdout STDOUT] [--stderr STDERR] [--pcap PCAP]

   optional arguments:
     -h, --help            show this help message and exit
     -c CONFIG, --config CONFIG
                           config file (yaml, toml, json, ...)
     -C, --cleanup         Remove the entire rundir (not just node subdirs) prior to running.
     -k KINDS_CONFIG, --kinds-config KINDS_CONFIG
                           kinds config file (yaml, toml, json, ...)
     --gdb GDB             comma-sep list of hosts to run gdb on
     --gdb-breakpoints GDB_BREAKPOINTS
                           comma-sep list of breakpoints to set
     --host                no isolation for top namespace, bridges exposed to default namespace
     --log-config LOG_CONFIG
                           logging config file (yaml, toml, json, ...)
     --no-kill             Do not kill previous running processes
     --no-cli              Do not run the interactive CLI
     --no-wait             Exit after commands
     -d RUNDIR, --rundir RUNDIR
                           runtime directory for tempfiles, logs, etc
     --validate-only       Validate the config against the schema definition
     --topology-only       Do not run any node commands
     -v, --verbose         be verbose
     -V, --version         print the verison number and exit
     --shell SHELL         comma-sep list of nodes to open shells for
     --stdout STDOUT       comma-sep list of nodes to open windows on their stdout
     --stderr STDERR       comma-sep list of nodes to open windows on their stderr
     --pcap PCAP           comma-sep list of network to open network captures on
