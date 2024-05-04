.. SPDX-License-Identifier: GPL-2.0-or-later
..
.. November 24 2022, Christian Hopps <chopps@labn.net>
..
.. Copyright (c) 2022, LabN Consulting, L.L.C.
..

Nodes
=====

.. currentmodule:: munet.base

.. NOTE:: move this paragran to a developer section replace with common config

The base class of all controllable nodes is the :py:class:`Commander`. A Commander object
supports run-to-completion command excution with the :py:meth:`Commander.async_cmd_status`
and :py:meth:`Commander.cmd_status` (and their `nostatus` and
`raises` variants), run in parallel command execution with the `Commander.async_popen` and
`popen` methods, and finally send/expect (`pexpect`) functionality with the
:py:meth:`Commander.spawn` method.

..
  XXX add common functionallity sections about ``cmd:``, ``cleanup-cmd:``, etc
  configuration here. IOW document the node common but not qemu options

The config created node types are described in the following sections.

.. currentmodule:: munet.native

Namespace Node
--------------

The most basic node is a linux namepsace. If no other special configuration
(e.g., ``image:`` or ``qemu:``) has been specified in the configuration this is
the node type that is created. This node type is implemented by the
:py:class:`L3NamespaceNode` class.

Below is an example of creating a namespace node names ``node1`` with a single
IP interface connected to the ``mgmt0`` network.

.. code-block:: yaml

   topology:
     networks:
       - name: mgmt0
     nodes:
       - name: node1
         connections: ["mgmt0"]



Container Node
--------------

A container node is created when the ``image:`` configuration is specified.
``podman`` is used to create the container. This node type is implemented by the
:py:class:`L3ContainerNode`

Below is an example of creating a container node named ``container1`` using the
latest official ubuntu image with a single IP interface connected to the
``mgmt0`` network.

.. code-block:: yaml

   topology:
     networks:
       - name: mgmt0
     nodes:
       - name: container1
         image: docker.io/ubuntu
         connections: ["mgmt0"]


Virtual Machine Node
--------------------

A vritual machine node type is created when the ``qemu`` configuration is specified.
This node type is implemented by the :py:class:`L3QemuVM` class.

Below is an example of creating a VM named ``vm1`` using a kernel image and
initrd filesystem, which are located in the same directory as the munet
configuration files, with a single IP interface connected to the ``mgmt0``
network.

.. code-block:: yaml

   topology:
     networks:
       - name: mgmt0
     nodes:
       - name: vm1
         connections: ["mgmt0"]
         qemu:
           kernel: "%CONFIGDIR%/bzImage"
           initrd: "%CONFIGDIR%/rootfs.cpio.gz"
           cmdline-extra: "acpi=off nokaslr"

Hostnet Node
------------

A node that can run commands within the host network namespace can be created by
specifying ``hostnet: true`` configuration. This node type is implemented by the
:py:class:`HostnetNode` class.

NOTE: For this to node type to work correctly the main munet object should not
be created with unshare_inline.

Below is an example of creating an ssh connection to a server
'server.example.com` using port 5100 named ``remote1``.

.. code-block:: yaml

   topology:
     nodes:
       - name: remote1
         hostnet: true

Remote Node (SSH)
-----------------

An ssh connection to a server can be created by specifying ``server:`` configuration.
This node type is implemented by the :py:class:`SSHRemote` class.

Below is an example of creating an ssh connection to a server
'server.example.com` using port 5100 named ``remote1``.

.. code-block:: yaml

   topology:
     nodes:
       - name: remote1
         server: server.example.com
         server-port: 5100
