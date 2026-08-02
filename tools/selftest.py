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
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/__unsafe.svg":
                demo = (ROOT / "demo" / "demo-map.svg").read_text(encoding="utf-8")
                demo = demo.replace(
                    "<svg ", '<svg onload="globalThis.__unsafeProbe=1" ', 1)
                active = """
  <script>globalThis.__unsafeProbe=2</script>
  <foreignObject width="10" height="10"><div xmlns="http://www.w3.org/1999/xhtml"
    onmouseover="globalThis.__unsafeProbe=3">active HTML</div></foreignObject>
  <style>@import url(https://example.invalid/x.css); .probe{fill:url(https://example.invalid/x)}</style>
  <image width="1" height="1" href="https://example.invalid/pixel.png"/>
"""
                demo = demo.rsplit("</svg>", 1)[0] + active + "</svg>"
                data = demo.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            super().do_GET()

    handler = functools.partial(QuietHandler,
                                directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def dump_dom(chrome, url, window_size=None):
    # Deliberately no --user-data-dir: a fresh profile makes Chrome spend the
    # whole virtual-time budget on first-run setup and the page never boots.
    cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
           "--disable-background-networking", "--disable-component-update",
           "--no-first-run", "--disable-default-apps",
           "--virtual-time-budget=15000", "--dump-dom"]
    if window_size:
        cmd.append("--window-size=" + window_size)
    cmd.append(url)
    failures = []
    for attempt in range(2):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if out.returncode == 0 and out.stdout:
                return out.stdout
            failures.append("exit %s: %s" % (out.returncode, out.stderr[-300:]))
        except subprocess.TimeoutExpired:
            failures.append("timed out after 60 seconds")
        if attempt == 0:
            print("           Chrome did not finish; retrying this check once")
    raise RuntimeError("Chrome failed twice: " + " | ".join(failures))


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
    b = run(test={"ops": [{"t": "dragpx", "key": "Eastport|R08", "dx": 0, "dy": 12}]})
    assert not b["errors"], b["errors"]
    moved_y = b["ops"][0]["movedY"]
    # MouseEvent client coordinates are quantized to CSS pixels.  At the
    # fit-to-window scale used by headless Chrome, a requested 12 map units
    # can therefore become 11, 12, or 13 after the real screen->map path.
    # Compare applyMove against that representable movement, while keeping
    # the final snapped position an exact equality check.
    assert abs(moved_y - 12) <= 1, b["ops"][0]
    a = run(test={"ops": [{"t": "name", "key": "Eastport|R08", "dx": 0, "dy": moved_y}]})
    assert not a["errors"] and not b["errors"], (a["errors"], b["errors"])
    assert a["ops"][0]["dy"] == b["ops"][0]["dy"], (a["ops"][0], b["ops"][0])
    return "requested 12, represented %s; both dy=%s" % (moved_y, a["ops"][0]["dy"])


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
    assert r["ops"][0]["hits"] > 0, r["ops"][0]
    ids = [b["id"] for b in r["state"]["blocks"]]
    assert ids == ["title-block", "legend", "under-construction", "outlying", "notes"], ids
    legend = next(b for b in r["state"]["blocks"] if b["id"] == "legend")
    assert legend["dx"] == -40 and legend["hits"] == r["ops"][0]["hits"], legend
    return "5 blocks, legend dx=%s hits=%s" % (r["ops"][0]["dx"], r["ops"][0]["hits"])


@check("proposal boxes export an anchor, unkeyed ones export a warning")
def _(run):
    r = run(ext2test={"ops": [
        {"k": "schem", "key": "Harbour Line|Phase 2", "dx": 10, "dy": 5},
        {"k": "schemIndex", "i": 1, "dx": 4, "dy": 3},
    ]})
    assert not r["errors"], r["errors"]
    assert "SCHEMATIC_ANCHOR" in r["state"]["text"]
    assert "Harbour Line|Phase 2" in r["state"]["text"]
    boxes = r["state"]["schem"]
    assert len(boxes) == 2, boxes
    assert sum(1 for b in boxes if b["key"]) == 1, boxes
    assert r["ops"][0]["anchor"] == [35, 305], r["ops"][0]
    assert "has no key in CONFIG.schematic.keys" in r["state"]["text"], r["state"]["text"]
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
    assert st["dockChildren"] == ["searchPane", "layerPane", "inspector", "sessionPane",
                                  "counts", "ext2Pane", "extPane"], st["dockChildren"]
    assert st["undo"] == 1 and st["redo"] == 1, st
    assert st["draft"] is True, st
    assert st["semanticClasses"] == {"stations": 19, "labels": 19, "codes": 21}, st
    assert st["codePointer"] == "none", st["codePointer"]
    assert st["source"] != "__SOURCE_SHA256__" and len(st["source"]) >= 16, st["source"]
    alt = run(uitest={"ops": [{"t": "layer", "name": "codes", "locked": True}]},
              selectortest="attrs")
    assert not alt["errors"], alt["errors"]
    assert alt["state"]["semanticClasses"] == {"stations": 19, "labels": 19, "codes": 21}, alt
    assert alt["state"]["codePointer"] == "none", alt["state"]
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
    assert r["state"]["movedNames"] == 0 and r["state"]["movedCodes"] == 0, r["state"]
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
    assert not en["state"]["missingI18n"] and not zh["state"]["missingI18n"], \
        (en["state"]["missingI18n"], zh["state"]["missingI18n"])
    assert not re.search(r"[a-z]+\.[a-z]+", b.split("\n")[0]), \
        "untranslated key leaked into the Chinese inspector: %r" % b
    return "en=%r / zh=%r; no visible key fallbacks" % (
        a.split("\n")[0][:28], b.split("\n")[0][:28])


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
        assert len(t) >= 140, "%s only exposed %d theme tokens" % (name, len(t))
    assert light["state"]["paper"] == dark["state"]["paper"], \
        "the artwork background must not change with the theme"
    return "light/dark both resolve %d tokens, paper=%s" % (
        len(light["state"]["tokens"]), light["state"]["paper"])


@check("the exported move list carries no interface language")
def _(run):
    r = run(uitest={"ops": [{"t": "name", "key": "Central Exchange|R04",
                              "dx": 0, "dy": 100}]},
            lang="zh")
    text = r["state"]["exportText"]
    assert not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text), \
        "CJK interface text leaked into the machine-readable export"
    assert "NAME_MOVES" in text
    return "%d bytes, English format only" % len(text)


@check("HTML-looking search input stays text, not DOM")
def _(run):
    payload = '<b id="xss-probe">probe</b>'
    r = run(uitest={"ops": [{"t": "search", "q": payload}]}, lang="zh")
    assert not r["errors"], r["errors"]
    assert r["state"]["probeExists"] is False, r["state"]["infoHTML"]
    assert "&lt;b" in r["state"]["infoHTML"], r["state"]["infoHTML"]
    return r["state"]["infoHTML"][:80]


@check("active content is removed from a loaded SVG")
def _(run):
    r = run(uitest={"ops": []}, svg="__unsafe.svg")
    assert not r["errors"], r["errors"]
    assert r["state"]["unsafeProbe"] == 0, r["state"]
    assert r["state"]["sanitized"] >= 5, r["state"]
    assert "Potentially active SVG content was removed" in r["state"]["infoHTML"], \
        r["state"]["infoHTML"]
    return "%d active elements/attributes removed; no script ran" % r["state"]["sanitized"]


@check("Fit keeps the map clear of the bottom dock on a narrow viewport")
def _(run):
    r = run(uitest={"ops": []}, _window_size="900,800")
    assert not r["errors"], r["errors"]
    assert r["state"]["mapDockOverlap"] is False, r["state"]
    return "900x800 map and dock do not overlap"


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--match", help="run only checks whose name contains this text")
    args = ap.parse_args()

    chrome = find_chrome(args.chrome)
    httpd = serve(args.port)
    base = "http://127.0.0.1:%d/index.html" % args.port

    def run(**params):
        window_size = params.pop("_window_size", None)
        q = {}
        for k, v in params.items():
            q[k] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        q.setdefault("lang", "en")
        url = base + "?" + urllib.parse.urlencode(q)
        dom = dump_dom(chrome, url, window_size=window_size)
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

    selected = [(name, fn) for name, fn in CHECKS
                if not args.match or args.match.lower() in name.lower()]
    if not selected:
        httpd.shutdown()
        sys.exit("No check matched %r" % args.match)
    failed = 0
    for i, (name, fn) in enumerate(selected, 1):
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
    print("\n%d/%d passed" % (len(selected) - failed, len(selected)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
