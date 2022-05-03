# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# April 22 2022, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2022, LabN Consulting, L.L.C
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
"""Utility functions useful when using munet testing functionailty in pytest."""
import asyncio
import datetime
import functools
import logging
import sys
import time

from munet.base import BaseMunet
from munet.cli import async_cli


# =================
# Utility Functions
# =================


async def async_pause_test(desc=""):
    isatty = sys.stdout.isatty()
    if not isatty:
        desc = f" for {desc}" if desc else ""
        logging.info("NO PAUSE on non-tty terminal%s", desc)
        return

    while True:
        if desc:
            print(f"\n== PAUSING: {desc} ==")
        user = input('PAUSED, "cli" for CLI, "pdb" to debug, "Enter" to continue: ')
        user = user.strip()
        if user == "cli":
            await async_cli(BaseMunet.g_unet)
        elif user == "pdb":
            breakpoint()  # pylint: disable=W1515
        elif user:
            print(f'Unrecognized input: "{user}"')
        else:
            break


def pause_test(desc=""):
    asyncio.run(async_pause_test(desc))


def retry(retry_timeout, initial_wait=0, expected=True):
    """
    decorator: retry while function return value is not None or it raises an exception.

    * `retry_timeout`: Retry for at least this many seconds; after waiting
                       initial_wait seconds
    * `initial_wait`: Sleeps for this many seconds before first executing function
    * `expected`: if False then the return logic is inverted, except for exceptions,
                  (i.e., a non None ends the retry loop, and returns that value)
    """

    def _retry(func):
        @functools.wraps(func)
        def func_retry(*args, **kwargs):
            retry_sleep = 2

            # Allow the wrapped function's args to override the fixtures
            _retry_timeout = kwargs.pop("retry_timeout", retry_timeout)
            _expected = kwargs.pop("expected", expected)
            _initial_wait = kwargs.pop("initial_wait", initial_wait)
            retry_until = datetime.datetime.now() + datetime.timedelta(
                seconds=_retry_timeout + _initial_wait
            )

            if initial_wait > 0:
                logging.info("Waiting for [%s]s as initial delay", initial_wait)
                time.sleep(initial_wait)

            while True:
                seconds_left = (retry_until - datetime.datetime.now()).total_seconds()
                try:
                    ret = func(*args, **kwargs)
                    if _expected and ret is None:
                        logging.debug("Function succeeds")
                        return ret
                    logging.debug("Function returned %s", ret)
                except Exception as error:
                    logging.info("Function raised exception: %s", str(error))
                    ret = error

                if seconds_left < 0:
                    logging.info("Retry timeout of %ds reached", _retry_timeout)
                    if isinstance(ret, Exception):
                        raise ret
                    return ret

                logging.info(
                    "Sleeping %ds until next retry with %.1f retry time left",
                    retry_sleep,
                    seconds_left,
                )
                time.sleep(retry_sleep)

        func_retry._original = func  # pylint: disable=W0212
        return func_retry

    return _retry
