#!/usr/bin/env python3
"""Pack the trader/ memory into one JSON text, and unpack it. Standard library only.

Cloud runs start on a fresh machine, so what the skills remember (news already
seen, alerts already rung, notifications already sent, the portfolio, the
day's risk log) would be lost between runs. The scheduled agents keep it in
one Google Drive file, "day-trader-state.json":

    python3 statepack.py pack   > /tmp/state.json     # then upload it to Drive
    python3 statepack.py unpack < state-from-drive.json

Packed: trader/config.json, portfolio.json, alerts.json, plan.json,
watchlist.json, orders.json, and every trader/state/*.json. Not packed: big
or rebuildable files (universe.txt, the PTR PDFs, prices). Unpack never
overwrites a file with an older copy (it compares the "packed_at" stamp kept
per file) unless --force.
"""

import argparse
import datetime as _dt
import glob
import json
import os
import sys

TOP = ["config.json", "portfolio.json", "alerts.json", "plan.json", "watchlist.json",
       "orders.json"]
MAX_BYTES = 2000000


def pack(root="trader"):
    files = {}
    names = [os.path.join(root, n) for n in TOP] + sorted(glob.glob(os.path.join(root, "state", "*.json")))
    for path in names:
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
            continue
        with open(path, encoding="utf-8") as fh:
            try:
                files[os.path.relpath(path, root).replace(os.sep, "/")] = json.load(fh)
            except ValueError:
                continue
    return {"format": "day-trader-state/1",
            "packed_at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "files": files}


def unpack(doc, root="trader", force=False):
    if doc.get("format") != "day-trader-state/1":
        raise ValueError("not a day-trader state file")
    written = []
    stamp_path = os.path.join(root, "state", ".packed_at")
    local_stamp = ""
    if os.path.isfile(stamp_path):
        with open(stamp_path, encoding="utf-8") as fh:
            local_stamp = fh.read().strip()
    if not force and local_stamp and local_stamp >= doc.get("packed_at", ""):
        return written
    for rel, content in sorted(doc.get("files", {}).items()):
        if rel.startswith("/") or ".." in rel.split("/"):
            continue  # never write outside trader/
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(content, fh, indent=2)
            fh.write("\n")
        written.append(rel)
    os.makedirs(os.path.dirname(stamp_path), exist_ok=True)
    with open(stamp_path, "w", encoding="utf-8") as fh:
        fh.write(doc.get("packed_at", ""))
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["pack", "unpack"])
    ap.add_argument("--root", default="trader")
    ap.add_argument("--file", help="read (unpack) or write (pack) this file instead of stdin/stdout")
    ap.add_argument("--force", action="store_true", help="unpack even over newer local files")
    args = ap.parse_args(argv)
    if args.cmd == "pack":
        text = json.dumps(pack(args.root), indent=1, ensure_ascii=False)
        if args.file:
            with open(args.file, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        else:
            sys.stdout.write(text + "\n")
        return 0
    raw = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    try:
        doc = json.loads(raw)
        written = unpack(doc, args.root, args.force)
    except ValueError as exc:
        print("statepack: %s" % exc, file=sys.stderr)
        return 2
    print("restored %d file(s)%s" % (len(written), (": " + ", ".join(written)) if written else
                                     " (local copy is as new or newer)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
