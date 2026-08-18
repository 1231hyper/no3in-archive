#!/usr/bin/env python3
"""Download (or copy from a local file) Flammenkamp's no-three-in-line
snapshot and verify its SHA-256 digest against the pin in
data/snapshot_manifest.txt.

Usage:
    python data/download_snapshot.py --out data/raw/all_known_solutions.txt
    python data/download_snapshot.py --from-local /path/copy --out data/raw/all_known_solutions.txt

The raw snapshot is third-party data without an explicit redistribution
licence; this script exists so that the pinned bytes can be reproduced
anywhere. Only the download recipe and digest pin are archived here.
"""

import argparse
import hashlib
import shutil
import sys
import urllib.request

BASE = "https://wwwhomes.uni-bielefeld.de/achim/no3in/download/all_known_solutions"
SHA256 = "6c385257c34af354a596b718002e2ef552b52da54b8e5065ec6a8b8c4d5026e0"
SIZE = 23832810
CHUNK = 1 << 20


def digest_of(path):
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def check(path):
    d, size = digest_of(path)
    if d != SHA256 or size != SIZE:
        sys.stderr.write(
            "FAIL: %s\n  size   %d (expected %d)\n  sha256 %s (expected %s)\n"
            % (path, size, SIZE, d, SHA256)
        )
        return False
    sys.stderr.write("OK: %s  %d bytes  %s\n" % (path, size, d))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw/all_known_solutions.txt")
    ap.add_argument(
        "--from-local",
        metavar="PATH",
        help="use an already-downloaded copy instead of fetching from the URL",
    )
    args = ap.parse_args()

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    if args.from_local:
        shutil.copyfile(args.from_local, args.out)
    else:
        sys.stderr.write("downloading %s ...\n" % BASE)
        urllib.request.urlretrieve(BASE, args.out)
        sys.stderr.write("done\n")

    sys.exit(0 if check(args.out) else 1)


if __name__ == "__main__":
    main()
