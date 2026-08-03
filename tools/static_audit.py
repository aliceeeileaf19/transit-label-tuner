#!/usr/bin/env python3
"""Static public-release checks for transit-label-tuner."""

import importlib.util
import math
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def balanced_block(text, marker):
    start = text.index(marker) + len(marker)
    depth = 1
    quote = None
    escaped = False
    for i in range(start, len(text)):
        char = text[i]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
    raise AssertionError("unterminated block after %r" % marker)


def audit_i18n():
    table = balanced_block(HTML, "const I18N = {")
    en_block = balanced_block(table, "en: {")
    zh_block = balanced_block(table, "zh: {")
    key_pattern = r'"([\w.-]+)"\s*:'
    en = set(re.findall(key_pattern, en_block))
    zh = set(re.findall(key_pattern, zh_block))
    assert en == zh, "locale key mismatch: en-only=%s zh-only=%s" % (sorted(en - zh), sorted(zh - en))

    used = set(re.findall(r'\b(?:t|tHTML|tEnglish)\(\s*"([\w.-]+)"', HTML))
    used.update(re.findall(r'data-i18n="([\w.-]+)"', HTML))
    for spec in re.findall(r'data-i18n-attr="([^"]+)"', HTML):
        used.update(pair.split(":", 1)[1].strip() for pair in spec.split(";") if ":" in pair)
    # The only direct-looking key is the documented example in a comment.
    used.discard("some.key")
    assert used <= en, "undefined i18n keys: %s" % sorted(used - en)

    visible_attrs = re.findall(r'\b(?:title|placeholder|aria-label)="([^"]+)"', HTML)
    allowed = {"false", "true", "polite", "status", "dialog", "group"}
    assert not [value for value in visible_attrs if value not in allowed], \
        "literal user-facing HTML attributes: %s" % visible_attrs
    return len(en), len(used)


def audit_themes():
    css = re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)
    light = balanced_block(css, ':root, :root[data-theme="light"]{')
    dark = balanced_block(css, ':root[data-theme="dark"]{')
    token_pattern = r"(--[\w-]+)\s*:"
    light_tokens = set(re.findall(token_pattern, light))
    dark_tokens = set(re.findall(token_pattern, dark))
    assert light_tokens == dark_tokens, "theme token mismatch: light-only=%s dark-only=%s" % (
        sorted(light_tokens - dark_tokens), sorted(dark_tokens - light_tokens))
    references = re.findall(r"var\((--[\w-]+)(\s*,[^)]*)?\)", css)
    missing = {name for name, fallback in references if name not in light_tokens and not fallback}
    assert not missing, "undefined theme tokens without a fallback: %s" % sorted(missing)
    assert len(light_tokens) >= 140, "theme exposes only %d tokens" % len(light_tokens)
    return len(light_tokens)


def load_generator():
    spec = importlib.util.spec_from_file_location("demo_gen", ROOT / "tools/make_demo_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def number(el, key):
    value = float(el.attrib[key])
    assert math.isfinite(value), (el.tag, key, el.attrib.get(key))
    return value


def audit_demo():
    gen = load_generator()
    current = (ROOT / "demo/demo-map.svg").read_text(encoding="utf-8")
    assert current == gen.build(), "demo SVG is not byte-identical to generator output"
    ns = {"s": "http://www.w3.org/2000/svg"}
    root = ET.fromstring(current)
    assert root.attrib.get("viewBox") == "0 0 1684 1188"
    assert root.attrib.get("width") == "1684" and root.attrib.get("height") == "1188"
    inner = root.find("s:svg[@id='map']", ns)
    assert inner is not None and inner.attrib.get("viewBox") == "0 0 800 560"

    stations = inner.findall(".//s:g[@class='stn-g']", ns)
    labels = inner.findall(".//s:text[@class='lbl']", ns)
    codes = inner.findall(".//s:g[@class='stn-code']", ns)
    leaders = inner.findall(".//s:line[@class='ldr']", ns)
    routes = [path for path in inner.findall(".//s:path", ns)
              if path.attrib.get("class", "").startswith("rt")
              and not path.attrib["class"].endswith("-casing")]
    assert (len(stations), len(labels), len(codes), len(leaders), len(routes)) == (19, 19, 21, 3, 4)

    station_rows = []
    for station in stations:
        for key in ("data-name", "data-code", "data-x", "data-y"):
            assert station.attrib.get(key), ("missing station attribute", key, station.attrib)
        sx, sy = number(station, "data-x"), number(station, "data-y")
        circles = station.findall("s:circle", ns)
        assert circles and all(abs(number(circle, "cx") - sx) < .001
                               and abs(number(circle, "cy") - sy) < .001 for circle in circles)
        station_rows.append((station.attrib["data-name"], station.attrib["data-code"], sx, sy))

    label_rows = []
    for label in labels:
        text = "".join(label.itertext())
        x, y = number(label, "x"), number(label, "y")
        candidates = [row for row in station_rows if row[0] == text]
        assert candidates, ("label has no same-name station", text)
        nearest = min(candidates, key=lambda row: math.hypot(row[2] - x, row[3] - y))
        assert math.hypot(nearest[2] - x, nearest[3] - y) <= 120
        transform = label.attrib.get("transform")
        if transform:
            match = re.fullmatch(r"rotate\((-?[\d.]+) ([\d.]+) ([\d.]+)\)", transform)
            assert match, transform
            angle, cx, cy = map(float, match.groups())
            configured_angles = {0} | {row[3] for row in gen.LABELS.values() if row[3] is not None}
            assert angle in configured_angles and abs(cx - x) < .001 and abs(cy - y) < .001
        label_rows.append((text, nearest[1], x, y))

    for group in codes:
        for key in ("data-name", "data-code", "data-station-x", "data-station-y"):
            assert group.attrib.get(key), ("missing code-group attribute", key, group.attrib)
        text_nodes = group.findall("s:text", ns)
        assert len(text_nodes) == 1
        label = text_nodes[0]
        x, y = number(label, "x"), number(label, "y")
        sx, sy = number(group, "data-station-x"), number(group, "data-station-y")
        anchor = label.attrib.get("text-anchor", "start")
        matches = [key for key, (dx, dy, slot_anchor) in gen.SLOTS.items()
                   if abs((x - sx) - dx) < .05 and abs((y - sy) - dy) < .05
                   and anchor == slot_anchor]
        assert len(matches) == 1, (group.attrib, label.attrib, matches)

    bindings = []
    for leader in leaders:
        x1, y1, x2, y2 = (number(leader, key) for key in ("x1", "y1", "x2", "y2"))
        candidates = []
        for name, code, lx, ly in label_rows:
            station = next(row for row in station_rows if row[0] == name and row[1] == code)
            if math.hypot(x1 - station[2], y1 - station[3]) <= 1.0 \
                    and math.hypot(x2 - lx, y2 - ly) < 30:
                candidates.append((name, code))
        assert len(candidates) == 1, (leader.attrib, candidates)
        bindings.extend(candidates)
    assert sorted(bindings) == sorted([("Cathedral", "R06"), ("University", "B03"),
                                       ("Botanic Gardens", "G05")])

    ids = {el.attrib.get("id") for el in root.iter()}
    assert {"title-block", "legend", "under-construction", "outlying", "notes"} <= ids
    markers = [el for el in inner.findall(".//s:text", ns)
               if "".join(el.itertext()) == "SCHEMATIC ONLY"]
    assert len(markers) == 2
    rects = inner.findall(".//s:rect", ns)
    origins = []
    for marker in markers:
        x, y = number(marker, "x"), number(marker, "y")
        containing = [rect for rect in rects
                      if number(rect, "x") - 2 <= x <= number(rect, "x") + number(rect, "width") + 2
                      and number(rect, "y") - 2 <= y <= number(rect, "y") + number(rect, "height") + 2]
        assert containing
        smallest = min(containing, key=lambda rect: number(rect, "width") * number(rect, "height"))
        origins.append((round(number(smallest, "x")), round(number(smallest, "y"))))
    assert sorted(origins) == [(25, 300), (620, 425)]
    return len(stations), len(codes), len(leaders), len(routes)


def audit_screenshots():
    names = ("screenshot-en.png", "screenshot-zh.png", "screenshot-dark.png", "screenshot-zh-dark.png")
    for name in names:
        data = (ROOT / "docs" / name).read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n"), "%s is named .png but is not PNG data" % name
        width, height = struct.unpack(">II", data[16:24])
        assert (width, height) == (1851, 938), "%s is %dx%d, expected 1851x938" % (
            name, width, height)
    return len(names)


def main():
    locales, used = audit_i18n()
    tokens = audit_themes()
    stations, codes, leaders, routes = audit_demo()
    shots = audit_screenshots()
    print("i18n: %d symmetric keys; %d direct/static uses resolved" % (locales, used))
    print("themes: %d matching semantic tokens; every var() is defined" % tokens)
    print("demo: %d stations / %d codes / %d leaders / %d routes; contract valid" % (
        stations, codes, leaders, routes))
    print("screenshots: %d files contain real PNG data" % shots)


if __name__ == "__main__":
    main()
