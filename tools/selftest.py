#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless self-test for transit-label-tuner.

Serves the repo on a local port, drives the tool through its own scripting
hooks with headless Chrome, and asserts on the JSON each layer publishes.

Every operation below goes through the same snap/guard path as a real mouse
drag — that is the whole reason those hooks exist.

Usage:
    python3 tools/selftest.py [--chrome /path/to/chrome] [--port 8791]

Exit code 0 means every check passed.
"""

import argparse
import functools
import http.server
import json
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
]


def find_chrome(explicit):
    if explicit:
        return explicit
    for c in CHROME_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    sys.exit("No Chrome/Chromium found. Pass --chrome /path/to/binary.")


def serve(port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    httpd.log_message = lambda *a, **k: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def dump_dom(chrome, url):
    # Deliberately no --user-data-dir: a fresh profile makes Chrome spend the
    # whole virtual-time budget on first-run setup and the page never boots.
    out = subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=15000", "--dump-dom", url],
        capture_output=True, text=True, timeout=180)
    return out.stdout


def unescape(s):
    return (s.replace("&quot;", '"').replace("&lt;", "<")
             .replace("&gt;", ">").replace("&amp;", "&"))


def grab(dom, node_id):
    # Take the last parseable match: the string "<pre id=...>" can legitimately
    # appear inside the page's own source, and only the real node holds JSON.
    found = None
    for m in re.finditer(r'<pre id="%s"[^>]*>(.*?)</pre>' % node_id, dom, re.S):
        try:
            found = json.loads(unescape(m.group(1)))
        except ValueError:
            continue
    return found


CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


# --------------------------------------------------------------------------

@check("model loads and indexes the demo map")
def _(run):
    r = run(test={"ops": []})
    assert not r["errors"], r["errors"]
    m = r["model"]
    assert m["stations"] == 19, m
    assert m["labels"] == 19, m
    assert m["codes"] == 21, m
    assert m["leaders"] == 3, m
    assert m["panels"] > 0, m
    return "%d stations / %d labels / %d codes / %d leaders / %d panels" % (
        m["stations"], m["labels"], m["codes"], m["leaders"], m["panels"])


@check("dragging a name snaps the offset to whole units")
def _(run):
    r = run(test={"ops": [{"t": "name", "key": "Cathedral|R06", "dx": 3.4, "dy": -7.6}]})
    assert not r["errors"], r["errors"]
    op = r["ops"][0]
    assert float(op["dx"]) == round(float(op["dx"])), op
    assert float(op["dy"]) == round(float(op["dy"])), op
    return "dx=%s dy=%s" % (op["dx"], op["dy"])


@check("a synthetic mouse drag lands on the same place as applyMove")
def _(run):
    a = run(test={"ops": [{"t": "name", "key": "Eastport|R08", "dx": 0, "dy": 12}]})
    b = run(test={"ops": [{"t": "dragpx", "key": "Eastport|R08", "dx": 0, "dy": 12}]})
    assert not a["errors"] and not b["errors"], (a["errors"], b["errors"])
    assert a["ops"][0]["dy"] == b["ops"][0]["dy"], (a["ops"][0], b["ops"][0])
    return "both dy=%s" % a["ops"][0]["dy"]


@check("a code can only land on one of the eight quadrants")
def _(run):
    r = run(test={"ops": [{"t": "code", "key": "Central Exchange|B05|B05", "dx": 13, "dy": -11}]})
    assert not r["errors"], r["errors"]
    slot = r["ops"][0]["slot"]
    assert slot in ("S", "E", "W", "N", "NE", "SE", "NW", "SW"), slot
    return "snapped to %s (was %s)" % (slot, r["ops"][0]["was"])


@check("angles only step along the configured ladder")
def _(run):
    r = run(test={"ops": [{"t": "angle", "key": "Foundry|R02", "ang": -50}]})
    assert not r["errors"], r["errors"]
    assert r["ops"][0]["rot"] == -50, r["ops"][0]
    bad = run(test={"ops": [{"t": "angle", "key": "Foundry|R02", "ang": -33}]})
    assert bad["errors"], "an off-ladder angle should have been refused"
    return "accepted -50, refused -33"


@check("a label without a rotate() cannot be given an angle")
def _(run):
    r = run(test={"ops": [{"t": "angle", "key": "Westgate|R01", "ang": -40}]})
    assert r["errors"], "adding an angle to a horizontal label should be refused"
    return r["errors"][0][:60]


@check("duplicate station names are flagged, not silently exported")
def _(run):
    # R04 and B05 are both "Central Exchange", 70 units apart. Drag R04's label
    # far enough and B05's label becomes the nearer match for R04's station —
    # exactly the case where an applier would silently move the wrong one.
    r = run(test={"ops": [{"t": "name", "key": "Central Exchange|R04",
                           "dx": 0, "dy": 100}]})
    assert not r["errors"], r["errors"]
    warns = r["export"]["warn"]
    assert any("Central Exchange" in w for w in warns), warns
    assert not any("limit" in w for w in warns), \
        "should trip the duplicate-name guard, not the distance limit: %s" % warns
    return warns[0][:78]


@check("a move beyond the offset limit is refused")
def _(run):
    r = run(test={"ops": [{"t": "name", "key": "Southmoor|B07", "dx": 0, "dy": 200}]})
    warns = r["export"]["warn"]
    assert any("limit" in w or "over" in w for w in warns), warns
    return warns[0][:70]


@check("undo restores the previous position")
def _(run):
    r = run(test={"ops": [
        {"t": "name", "key": "Northfield|B01", "dx": 0, "dy": 9},
        {"t": "undo"},
    ]})
    assert not r["errors"], r["errors"]
    assert not r["export"]["nameRows"], r["export"]["nameRows"]
    return "no rows left after undo"


@check("blocks move and report their own collisions")
def _(run):
    r = run(exttest={"ops": [{"k": "block", "id": "legend", "dx": -40, "dy": 0}]})
    assert not r["errors"], r["errors"]
    assert r["ops"][0]["dx"] == -40, r["ops"][0]
    ids = [b["id"] for b in r["state"]["blocks"]]
    assert ids == ["title-block", "legend", "under-construction", "outlying", "notes"], ids
    return "5 blocks, legend dx=%s hits=%s" % (r["ops"][0]["dx"], r["ops"][0]["hits"])


@check("proposal boxes export an anchor, unkeyed ones export a warning")
def _(run):
    r = run(ext2test={"ops": [{"k": "schem", "key": "Harbour Line|Phase 2",
                               "dx": 10, "dy": 5}]})
    assert not r["errors"], r["errors"]
    assert "SCHEMATIC_ANCHOR" in r["state"]["text"]
    assert "Harbour Line|Phase 2" in r["state"]["text"]
    boxes = r["state"]["schem"]
    assert len(boxes) == 2, boxes
    assert sum(1 for b in boxes if b["key"]) == 1, boxes
    return "2 boxes found, 1 keyed, anchor=%s" % (r["ops"][0]["anchor"],)


@check("traced lines snap every segment to eight directions")
def _(run):
    r = run(ext2test={"ops": [{"k": "trace", "pts": [[100, 100], [200, 137], [260, 60]]}]})
    assert not r["errors"], r["errors"]
    pts = r["ops"][0]["pts"]
    for a, b in zip(pts, pts[1:]):
        dx, dy = b["x"] - a["x"], b["y"] - a["y"]
        ok = abs(dx) < 1e-6 or abs(dy) < 1e-6 or abs(abs(dx) - abs(dy)) < 0.2
        assert ok, "segment %s -> %s is not on an eight-direction axis" % (a, b)
    return "%d vertices, all segments on axis" % len(pts)


@check("the working layer wires history, search, preflight and draft together")
def _(run):
    r = run(uitest="1")
    assert not r["errors"], r["errors"]
    st = r["state"]
    assert st["dockChildren"], st
    assert st["undo"] >= 0 and st["redo"] >= 0, st
    assert st["draft"] is not False if "draft" in st else True
    return "undo=%s redo=%s dock=%d panes" % (
        st["undo"], st["redo"], len(st["dockChildren"]))


@check("undo / redo no longer break part-way through restoreState")
def _(run):
    # Regression guard: restoreState() used to call an undefined function,
    # which aborted it after the geometry had already been written back.
    r = run(uitest={"ops": [
        {"t": "name", "key": "Glasshouse|G02", "dx": 0, "dy": 6},
        {"t": "undo"}, {"t": "redo"}, {"t": "undo"},
    ]})
    assert not r["errors"], r["errors"]
    assert "not defined" not in json.dumps(r), r
    return "undo/redo/undo clean"


@check("both interface languages render without falling back")
def _(run):
    en = run(uitest="1", lang="en")
    zh = run(uitest="1", lang="zh")
    for r in (en, zh):
        assert not r["errors"], r["errors"]
    a = en["state"]["inspector"]
    b = zh["state"]["inspector"]
    assert a and b and a != b, (a, b)
    assert not re.search(r"[a-z]+\.[a-z]+", b.split("\n")[0]), \
        "untranslated key leaked into the Chinese inspector: %r" % b
    return "en=%r / zh=%r" % (a.split("\n")[0][:28], b.split("\n")[0][:28])


@check("both themes resolve their tokens, and the map keeps its own paper")
def _(run):
    light = run(uitest="1", theme="light")
    dark = run(uitest="1", theme="dark")
    for r in (light, dark):
        assert not r["errors"], r["errors"]
    assert light["state"]["theme"] == "light", light["state"]
    assert dark["state"]["theme"] == "dark", dark["state"]
    # A token that failed to resolve leaves the property empty, which is how a
    # half-finished theme block shows up.
    for name, r in (("light", light), ("dark", dark)):
        t = r["state"]["tokens"]
        missing = [k for k, v in t.items() if not v.strip()]
        assert not missing, "%s theme has unresolved tokens: %s" % (name, missing)
    assert light["state"]["paper"] == dark["state"]["paper"], \
        "the artwork background must not change with the theme"
    return "light/dark both resolve %d tokens, paper=%s" % (
        len(light["state"]["tokens"]), light["state"]["paper"])


@check("the exported move list carries no interface language")
def _(run):
    r = run(test={"ops": [{"t": "name", "key": "Old Mill|R03", "dx": 0, "dy": 4}]},
            lang="zh")
    text = r["text"]
    assert not re.search(r"[一-鿿]", text), \
        "CJK leaked into the machine-readable export"
    assert "NAME_MOVES" in text
    return "%d bytes, ASCII only" % len(text)


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome")
    ap.add_argument("--port", type=int, default=8791)
    args = ap.parse_args()

    chrome = find_chrome(args.chrome)
    httpd = serve(args.port)
    base = "http://127.0.0.1:%d/index.html" % args.port

    def run(**params):
        q = {}
        for k, v in params.items():
            q[k] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        q.setdefault("lang", "en")
        url = base + "?" + urllib.parse.urlencode(q)
        dom = dump_dom(chrome, url)
        for key, node in (("uitest", "uitestresult"), ("ext2test", "ext2result"),
                          ("exttest", "extresult"), ("test", "testresult")):
            if key in q:
                r = grab(dom, node)
                if r is None:
                    boot = re.search(r'<div id="boot".*?</div>', dom, re.S)
                    raise AssertionError(
                        "no %s in the DOM. boot said: %s"
                        % (node, unescape(boot.group(0))[:300] if boot else "(nothing)"))
                return r
        raise AssertionError("no test parameter given")

    print("transit-label-tuner self-test")
    print("  chrome : %s" % chrome)
    print("  serving: %s\n" % ROOT)

    failed = 0
    for i, (name, fn) in enumerate(CHECKS, 1):
        try:
            detail = fn(run)
            print("  %2d. PASS  %s" % (i, name))
            if detail:
                print("           %s" % detail)
        except Exception as e:
            failed += 1
            print("  %2d. FAIL  %s" % (i, name))
            print("           %s: %s" % (type(e).__name__, e))

    httpd.shutdown()
    print("\n%d/%d passed" % (len(CHECKS) - failed, len(CHECKS)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
