.. SPDX-License-Identifier: GPL-2.0-or-later
..
.. December 8 2022, Christian Hopps <chopps@labn.net>
..
.. Copyright (c) 2022, LabN Consulting, L.L.C.
..


Mutest (μtest)
==============

Mutest is a simplified testing framework designed for use by test developers
of any skill level. The test developer writes test cases, one per file, which
are made up of steps. Normally, these steps are commands to send (perhaps
repeatedly) to a target and a matching regular expression for the command output
to determine if the step passes. Variations of this common step exist for added
functionality (e.g., negative match).

Running
-------

To have mutest search the current directory and all subdirectories and execute
any founc test scripts simply run the command:

.. code-block:: console

   $ sudo mutest

Mutest will then search the current directory and sub-directories for all files
matching the shell glob pattern ``mutest_*.py`` and co-reside with a munet
topology configuration ``munet.yaml``. Finding both it will then launch a munet
topology with the given configuration file and execute each test on the
resulting topology. The munet topology is launched at the start and brought down
at the end of each test script.

Log Files
---------

A run of mutest generates 3 log files, ``mutest-exec.log``,
``mutest-output.log`` and ``mutest-results.log``. They are created in the root
of the mutest run directory which by default is ``/tmp/mutest``. These same 3
log files are also generated per test case (script) within the test case
directories which are named after the tests and also reside in ``/tmp/mutest``.

The log files have the following content:

``mutest-exec.log``
    Contains all logging for the execution of mutest and munet (i.e., from
    the root logger), as well as the logging from the other 2 log files.

``mutest-output.log``
    Contains the all the test commands and their output.

``mutest-results.log``
    Contains the results in an easy to read format, for each test
    step, test case and finally the entire run.

For the advanced user this logging can be customized with python logging
configuration. The logging channels are the root logger for
``mutest-exec.log``, ``mutest.output`` and it's sub-loggers for
``mutest-output.log``, and ``mutest.results`` and it's sub-loggers for
``mutest-results.log``.


Writing Mutest Tests
--------------------

.. currentmodule:: munet.mutest.userapi

As described earlier, a test script is a collection of steps. Each step is a
call to a mutest API function. One common step is a call to
:py:func:`match_step`. This step sends a command to a target and applies a
regular expression search on the output. If a match is found the step succeeds.

Here is a simple example test case:

.. code-block:: python

  match_step("r1", 'vtysh -c "show ip fib 10.0.1.1"', "Routing entry for 10.0.1.0/24")
  match_step("r1", 'vtysh -c "show ip fib 10.0.2.1"', "Routing entry for 10.0.2.0/24")

This use of :py:func:`match_step` left off the an optional parameter to :py:func:`match_step`,
``explicit_fail`` which defaults to ``False``. Here is the example
:py:func:`match_step` which specifies all of it's parameters.

.. code-block:: python

  match_step("r1", 'vtysh -c "show ip fib 10.0.1.1"', "Routing entry for 10.0.1.0/24", False)
  match_step("r1", 'vtysh -c "show ip fib 10.0.2.1"', "Routing entry for 10.0.2.0/24", False)

One can also pass the parameters using their names. This allows one to specify
only the non-default values. Below is an example of another step variant,
:py:func:`wait_step`. In this case the the ``explicit_fail`` parameter is change to
True, and the other optional values (``timeout`` and ``interval``) are left to
their defaults (``10`` and ``.5`` respectively).

.. code-block:: python

  wait_step("r1", 'vtysh -c "show ip fib 10.0.2.1"', "Routing entry for 10.0.2.0/24",
      explicit_fail=True)

The above example could be used after making some change in the network that
should cause the FIB entry to be removed on ``r1``. In detail, mutest will issue
the command ``vtysh -c "show ip fib 10.0.2.1"`` on the target ``r1`` every 1/2
second until it no longer sees a match (because ``explicit_fail`` is True) or
until the timeout is reached in 10 seconds. If the timeout is reached the step
status is marked **FAIL**. Conversely, if at some point prior to the timeout, the FIB
entry is removed the match text will no longer be seen in the output, and so the
step gets marked **PASS** and completes immediately.

The simple :py:func:`step` function can be used to simply send a command to the
target without checking the output for a match. This is typically used, perhaps
multiple times, prior to a matching step to cause some state to change on the
target. For example below an interface is shutdown and then a matching step is
used to check that the state of the interface actually changes.

.. code-block:: python

  step("r1", 'vtysh -c "conf t\n interface eth0\n shut"')
  match_step("r1", 'vtysh -c "show interface eth0", "DOWN", "Check for interface DOWN")

To see all the available functions and their specifications see
:ref:`mutest-api`.
