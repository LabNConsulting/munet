# -*- coding: utf-8 eval: (blacken-mode 1) -*-
#
# June 25 2022, Christian Hopps <chopps@gmail.com>
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
"A module that defines common configuration utility functions."
from collections.abc import Iterable
from copy import deepcopy


def find_with_kv(lst, k, v):
    if lst:
        for e in lst:
            if k in e and e[k] == v:
                return e
    return {}


def find_all_with_kv(lst, k, v):
    rv = []
    if lst:
        for e in lst:
            if k in e and e[k] == v:
                rv.append(e)
    return rv


def find_matching_net_config(name, cconf, oconf):
    p = find_all_with_kv(oconf.get("connections", {}), "to", name)
    if not p:
        return {}

    rname = cconf.get("remote-name", None)
    if not rname:
        return p[0]

    return find_with_kv(p, "name", rname)


def merge_using_key(a, b, k):
    # First get a dict of indexes in `a` for the key value of `k` in objects of `a`
    m = list(a)
    mi = {o[k]: i for i, o in enumerate(m)}
    for o in b:
        bkv = o[k]
        if bkv in mi:
            m[mi[bkv]] = o
        else:
            mi[bkv] = len(m)
            m.append(o)
    return m


def list_to_dict_with_key(lst, k):
    "Convert list of objects to dict using the object key `k`"
    return {x[k]: x for x in (lst if lst else [])}


def config_to_dict_with_key(c, ck, k):
    "Convert the config item at `ck` from a list objects to dict using the key `k`"
    c[ck] = list_to_dict_with_key(c.get(ck, []), k)
    return c[ck]


def config_subst(config, **kwargs):
    if isinstance(config, str):
        for name, value in kwargs.items():
            config = config.replace(f"%{name.upper()}%", value)
    elif isinstance(config, Iterable):
        try:
            return {k: config_subst(config[k], **kwargs) for k in config}
        except (KeyError, TypeError):
            return [config_subst(x, **kwargs) for x in config]
    return config


def value_merge_deepcopy(s1, s2):
    "Create a deepcopy of the result of merging the values of keys from dicts d1 and d2"
    d = {}
    for k, v in s1.items():
        if k not in s2:
            d[k] = deepcopy(v)


def merge_kind_config(kconf, config):
    mergekeys = kconf.get("merge", [])
    config = deepcopy(config)
    new = deepcopy(kconf)
    for k in new:
        if k not in config:
            continue

        if k not in mergekeys:
            new[k] = config[k]
        elif isinstance(new[k], list):
            new[k].extend(config[k])
        elif isinstance(new[k], dict):
            new[k] = {**new[k], **config[k]}
        else:
            new[k] = config[k]
    for k in config:
        if k not in new:
            new[k] = config[k]
    return new
