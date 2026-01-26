#!/usr/bin/env python3
# -*- coding: utf-8 eval: (blacken-mode 1) -*-
# SPDX-License-Identifier: GPL-2.0-or-later
#
# October 24 2022, Christian Hopps <chopps@labn.net>
#
# Copyright (c) 2022, LabN Consulting, L.L.C.
#
"Code to fetch artifacts from github"

import argparse
import datetime
import logging
import os
import pprint
import sys
import time

import requests


def fetch(owner, repo, files, release="latest", dest=".", token=""):
    bheader = {"Accept": "application/octet-stream"}
    api = "https://api.github.com/repos"
    base_url = f"{api}/{owner}/{repo}"

    if not os.path.exists(dest):
        os.mkdir(dest)
    assert os.path.isdir(dest)

    headers = {}
    if token:
        headers["authorization"] = f"Bearer {token}"
        bheader["authorization"] = f"Bearer {token}"

    remaining = list(files)
    qurl = base_url + f"/releases/{release}"
    if qurl in fetch.cache:
        jr = fetch.cache[qurl]
    else:
        for i in range(0, 4):
            jr = requests.get(qurl, headers=headers, timeout=60).json()
            logging.debug(
                "URL: %s content:\n%s", qurl, pprint.pformat(jr, indent=4, width=120)
            )
            if "assets" in jr:
                break
            logging.warning("query returned with no assets: %s", jr)
            time.sleep(5)
        else:
            raise Exception(f"Never got list of assest after {i} tries")
        fetch.cache[qurl] = jr

    for asset in jr["assets"]:
        name = asset["name"]
        if name not in files:
            continue

        aid = asset["id"]
        if "updated_at" in asset:
            tss = asset["updated_at"]
        else:
            tss = asset["created_at"]
        adt = datetime.datetime.strptime(tss, "%Y-%m-%dT%X%z")
        atime = adt.timestamp()
        asize = int(asset["size"])

        # Check if we already have the asset
        path = os.path.join(dest, name)
        if os.path.exists(path):
            oatime = os.path.getmtime(path)
            oasize = os.path.getsize(path)
            if oatime == atime and oasize == asize:
                logging.info("Skipping download of %s matches on date and size", name)
                remaining.remove(name)
                continue

        # Download the asset
        aurl = base_url + f"/releases/assets/{aid}"
        logging.info("Downloading %s url: %s", name, aurl)
        r = requests.get(aurl, timeout=60, headers=bheader)
        assert (
            r.headers["Content-Type"] == "application/octet-stream"
        ), f"Wrong content type: {r.headers['Content-Type']}: request: {r}"

        # Save the asset
        with open(path, "wb") as f:
            f.write(r.content)
        os.utime(path, (atime, atime))
        logging.info("Saved %s to %s", len(r.content), name)

        remaining.remove(name)

    assert not remaining, f"Failed to fetch {remaining}"


fetch.cache = {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--owner", default="LabNConsulting", help="owner of github project"
    )
    parser.add_argument("--repo", default="iptfs-dev", help="github project repo")
    parser.add_argument(
        "--release", default="latest", help="release to fetch artifcats from"
    )
    parser.add_argument(
        "-d", "--destination", default=".", help="directory to save files in"
    )
    parser.add_argument("--token", default="", help="github api token")
    parser.add_argument("-v", "--verbose", action="store_true", help="Be verbose")
    parser.add_argument("files", nargs="+", help="artificat files to download")
    args = parser.parse_args()

    level = logging.DEBUG if bool(args.verbose) else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s: %(message)s")

    try:
        fetch(
            args.owner,
            args.repo,
            args.files,
            args.release,
            args.destination,
            token=args.token,
        )
    except AssertionError as error:
        logging.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
