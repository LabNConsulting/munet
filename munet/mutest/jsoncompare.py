# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# July 11 2023, Liam Brady <lbrady@labn.net>
#
# Copyright 2023, LabN Consulting, L.L.C.
#
"""Commands that allow for comparing or diffing json data."""

from deepdiff import DeepDiff
from deepdiff.operator import BaseOperator


class ExcludeUnexpectedJSON(BaseOperator):
    """Custom operator for DeepDiff that removes unexpected JSON data from the diff.

    level.t1 is the expected JSON dict to be diffed against. Any fields that are present
    in the JSON dict level.t2 but not level.t1 will be excluded.
    """
    def give_up_diffing(self, level, diff_instance) -> bool:
        unexpected_keys = set(level.t2.keys()) - set(level.t1.keys())
        if diff_instance.exclude_paths is None:
            diff_instance.exclude_paths = []
        for key in unexpected_keys:
            # Remove unexpected JSON data from diff by excluding the data's path
            diff_instance.exclude_paths.append(level.path() + f"['{key}']")

        # If there are no expected keys, then there is nothing left to diff against
        # at the current level
        return len(level.t1.keys()) == 0


def json_expected_cmp(*args, **kwargs):
    """Compare only the expected's fields against another JSON dict and return the diff.

    json_expected_cmp will simply call DeepDiff with `custom_operators` modified
    to always include the custom ExcludeUnexpectedJSON operator. The expected JSON dict
    should be the first argument (t1).

    See https://zepworks.com/deepdiff/current/diff.html for how to use DeepDiff.
    """
    operators = kwargs.get('custom_operators')
    if operators is None:
        operators = []
    operators.append(ExcludeUnexpectedJSON(types=[dict]))
    kwargs.update({'custom_operators': operators})
    return DeepDiff(*args, **kwargs)
