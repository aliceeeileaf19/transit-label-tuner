#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate demo/demo-map.svg — a small fictional transit network used as the
sample input for transit-label-tuner.

Nothing here describes a real network. Coordinates, names and colours are
invented so the demo can be shipped freely.

Structure produced (this is the contract the tool expects; see README):

  <svg viewBox="0 0 1684 1188">            outer canvas — page layout only
    <svg viewBox="0 0 800 560">            inner map — ALL station geometry
      path.rt-*                            route lines
      g.stn-g[data-name,data-code,data-x,data-y]
      text.lbl                             station name labels
      g.stn-code[data-name,data-code,data-station-x,data-station-y] > text
      line.ldr                             leader lines
      g#title-block, g#legend, ...         layout blocks (inner units)
    </svg>
    g#outlying, g#notes                    layout blocks (canvas units)
  </svg>

Run:  python3 tools/make_demo_map.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "demo" / "demo-map.svg"

CANVAS_W, CANVAS_H = 1684, 1188
MAP_W, MAP_H = 800, 560

RED, BLUE, GREEN, AMBER = "#c8433c", "#1f6fb2", "#2f8f5b", "#d69b1e"
INK, PAPER, MUTED = "#1c1f20", "#fbfaf6", "#6d7375"

# --------------------------------------------------------------------------
# stations: code -> (name, x, y, extra_codes)
# extra_codes are the second/third code shown at an interchange.
# --------------------------------------------------------------------------
STATIONS = [
    # Red line, west -> east
    ("R01", "Westgate",          90, 260, []),
    ("R02", "Foundry",          175, 260, []),
    ("R03", "Old Mill",         250, 260, []),
    ("R04", "Central Exchange", 340, 260, ["B04"]),
    ("R05", "Riverside",        430, 260, []),
    ("R06", "Cathedral",        510, 260, []),
    ("R07", "Fairground",       600, 260, []),
    ("R08", "Eastport",         690, 260, []),
    # Blue line, north -> south (B04 is the Central Exchange above)
    ("B01", "Northfield",       340,  80, []),
    ("B02", "Observatory",      340, 140, []),
    ("B03", "University",       340, 200, []),
    # Shares its name with R04, seventy units away. Real networks do this at
    # interchange complexes, and it is exactly the case the duplicate-name
    # guard in the exporter exists to catch.
    ("B05", "Central Exchange", 340, 330, []),
    ("B06", "Harbour Junction", 340, 410, ["G04"]),
    ("B07", "Southmoor",        340, 470, []),
    # Green line, south-west -> east (G04 is Harbour Junction above)
    ("G01", "Kiln Quarter",     120, 470, []),
    ("G02", "Glasshouse",       180, 410, []),
    ("G03", "Textile Row",      260, 410, []),
    ("G05", "Botanic Gardens",  450, 410, []),
    ("G06", "Riverside",        560, 410, []),   # second duplicate pair, far apart
]

LINE_OF = {"R": RED, "B": BLUE, "G": GREEN}

# label placement: code -> (dx, dy, anchor, rotate_deg or None, leader?)
LABELS = {
    "R01": (0, -14, "middle", None, False),
    "R02": (-6, -23, "end", -40, False),
    "R03": (-6, -23, "end", -50, False),
    "R04": (0, -18, "middle", None, False),
    "R05": (0, -14, "middle", None, False),
    "R06": (-2, -34, "middle", None, True),
    "R07": (0, -14, "middle", None, False),
    "R08": (12, 4, "start", None, False),
    "B01": (12, 4, "start", None, False),
    "B02": (14, 2, "start", -40, False),
    "B03": (34, 4, "start", None, True),
    "B05": (12, 4, "start", None, False),
    "B06": (14, -14, "start", None, False),
    "B07": (12, 4, "start", None, False),
    "G01": (0, 20, "middle", None, False),
    "G02": (-8, 16, "end", -50, False),
    "G03": (0, 20, "middle", None, False),
    "G05": (0, 26, "middle", None, True),
    "G06": (0, 20, "middle", None, False),
}

# quadrant slots — must stay in sync with the tool's CONFIG.slots
SLOTS = {
    "S":  (0.0,  12.0, "middle"),
    "E":  (8.0,   2.5, "start"),
    "W":  (-8.0,  2.5, "end"),
    "N":  (0.0,  -8.0, "middle"),
    "NE": (8.0,  -6.0, "start"),
    "SE": (8.0,   7.0, "start"),
    "NW": (-8.0, -7.0, "end"),
    "SW": (-8.0, 10.5, "end"),
}

CODE_SLOT = {
    "R01": "S", "R02": "S", "R03": "S", "R04": "SW", "R05": "S",
    "R06": "S", "R07": "S", "R08": "S", "B01": "W", "B02": "W",
    "B03": "W", "B05": "W", "B06": "SW", "B07": "W",
    "G01": "W", "G02": "W", "G03": "N", "G05": "N", "G06": "N",
    "B04": "SE", "G04": "SE",
}

ROUTES = [
    ("rt-red",   RED,   "M 90,260 L 690,260",                       None),
    ("rt-blue",  BLUE,  "M 340,80 L 340,470",                       None),
    ("rt-green", GREEN, "M 120,470 L 180,410 L 560,410",            None),
    ("rt-amber", AMBER, "M 690,260 L 760,190",                      "10 7"),
]


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def rounded(d, setback=15):
    """Rewrite an L-only polyline into the tool's corner convention:
    stop `setback` short of the corner, then Q through the corner itself."""
    pts = []
    for token in d.replace("M", " ").replace("L", " ").split():
        x, y = token.split(",")
        pts.append((float(x), float(y)))
    if len(pts) < 3:
        return d
    out = ["M%g,%g" % pts[0]]
    for i in range(1, len(pts) - 1):
        (ax, ay), (cx, cy), (bx, by) = pts[i - 1], pts[i], pts[i + 1]
        la = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
        lb = ((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5
        s = min(setback, la / 2, lb / 2)
        p1 = (cx + (ax - cx) / la * s, cy + (ay - cy) / la * s)
        p2 = (cx + (bx - cx) / lb * s, cy + (by - cy) / lb * s)
        out.append("L%g,%g" % p1)
        out.append("Q%g,%g %g,%g" % (cx, cy, p2[0], p2[1]))
    out.append("L%g,%g" % pts[-1])
    return " ".join(out)


def panel(pid, x, y, w, h, title, rows, unit_scale=1.0):
    """A layout block: rounded background rect + heading + lines of text."""
    fs = 13 * unit_scale
    L = ['<g id="%s">' % pid]
    L.append('  <rect x="%g" y="%g" width="%g" height="%g" rx="%g" '
             'fill="#ffffff" stroke="rgba(28,31,32,.18)" stroke-width="%g"/>'
             % (x, y, w, h, 6 * unit_scale, 1 * unit_scale))
    L.append('  <text x="%g" y="%g" font-size="%g" font-weight="700" fill="%s">%s</text>'
             % (x + 12 * unit_scale, y + 20 * unit_scale, fs, INK, esc(title)))
    for i, (swatch, text) in enumerate(rows):
        ty = y + (38 + i * 17) * unit_scale
        if swatch:
            L.append('  <rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s"/>'
                     % (x + 12 * unit_scale, ty - 8 * unit_scale,
                        16 * unit_scale, 5 * unit_scale, 2 * unit_scale, swatch))
            tx = x + 34 * unit_scale
        else:
            tx = x + 12 * unit_scale
        L.append('  <text x="%g" y="%g" font-size="%g" fill="%s">%s</text>'
                 % (tx, ty, 11 * unit_scale, MUTED, esc(text)))
    L.append("</g>")
    return L


def schematic(x, y, w, h, caption, marker="SCHEMATIC ONLY"):
    """A 'not to scale' proposal box. The tool finds these by the marker text
    and by the smallest rect that contains it."""
    return [
        '<rect x="%g" y="%g" width="%g" height="%g" rx="5" fill="#ffffff" '
        'stroke="%s" stroke-width="1" stroke-dasharray="5 4"/>' % (x, y, w, h, MUTED),
        '<text x="%g" y="%g" font-size="10" font-weight="700" fill="%s">%s</text>'
        % (x + 10, y + 18, MUTED, esc(marker)),
        '<text x="%g" y="%g" font-size="11" fill="%s">%s</text>'
        % (x + 10, y + 36, INK, esc(caption)),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="4" '
        'stroke-dasharray="9 6"/>' % (x + 12, y + 56, x + w - 12, y + 56, AMBER),
        '<circle cx="%g" cy="%g" r="4" fill="#ffffff" stroke="%s" stroke-width="2"/>'
        % (x + 12, y + 56, AMBER),
        '<circle cx="%g" cy="%g" r="4" fill="#ffffff" stroke="%s" stroke-width="2"/>'
        % (x + w - 12, y + 56, AMBER),
    ]


def build():
    by_code = {s[0]: s for s in STATIONS}
    L = []
    L.append('<svg xmlns="http://www.w3.org/2000/svg" '
             'xmlns:xlink="http://www.w3.org/1999/xlink" '
             'viewBox="0 0 %d %d" width="%d" height="%d" '
             'font-family="Helvetica Neue, Helvetica, Arial, sans-serif">'
             % (CANVAS_W, CANVAS_H, CANVAS_W, CANVAS_H))
    L.append('<rect id="canvas-bg" x="0" y="0" width="%d" height="%d" fill="%s"/>'
             % (CANVAS_W, CANVAS_H, PAPER))

    # ---------------- inner map ----------------
    L.append('<svg id="map" x="0" y="0" width="%d" height="%d" viewBox="0 0 %d %d">'
             % (CANVAS_W, CANVAS_H, MAP_W, MAP_H))

    L.append('<g id="routes">')
    for cls, colour, d, dash in ROUTES:
        d2 = rounded(d)
        L.append('  <path class="%s-casing" d="%s" fill="none" stroke="%s" '
                 'stroke-width="11" stroke-linejoin="round" stroke-linecap="round"/>'
                 % (cls, d2, PAPER))
        extra = ' stroke-dasharray="%s"' % dash if dash else ""
        L.append('  <path class="%s" d="%s" fill="none" stroke="%s" stroke-width="6.5" '
                 'stroke-linejoin="round" stroke-linecap="round"%s/>'
                 % (cls, d2, colour, extra))
    L.append("</g>")

    # proposal boxes (one keyed, one deliberately unkeyed)
    L.append('<g id="schematics">')
    L += schematic(25, 300, 155, 85, "Harbour Line, phase 2")
    L += schematic(620, 425, 165, 80, "Airport spur (study)")
    L.append("</g>")

    L += panel("title-block", 20, 20, 250, 66, "HARBOUR CITY TRANSIT",
               [(None, "Network diagram — demo data"),
                (None, "Not a real network")])
    L += panel("legend", 440, 20, 250, 150, "LEGEND",
               [(RED, "Red Line"), (BLUE, "Blue Line"),
                (GREEN, "Green Line"), (AMBER, "Under construction"),
                (None, "○  Interchange")])
    L += panel("under-construction", 620, 295, 170, 95, "UNDER CONSTRUCTION",
               [(AMBER, "Amber Line"), (None, "Opening: TBD"),
                (None, "Alignment indicative")])

    # ---- stations ----
    L.append('<g id="stations">')
    for code, name, x, y, extra in STATIONS:
        colour = LINE_OF[code[0]]
        interchange = bool(extra)
        L.append('  <g class="stn-g" data-name="%s" data-code="%s" data-x="%g" data-y="%g">'
                 % (esc(name), code, x, y))
        if interchange:
            L.append('    <circle cx="%g" cy="%g" r="8" fill="%s" stroke="%s" stroke-width="2.6"/>'
                     % (x, y, PAPER, INK))
        else:
            L.append('    <circle cx="%g" cy="%g" r="8" fill="%s" stroke="%s" stroke-width="2.4"/>'
                     % (x, y, PAPER, colour))
            L.append('    <circle cx="%g" cy="%g" r="3.4" fill="%s"/>' % (x, y, colour))
        L.append("  </g>")
    L.append("</g>")

    # ---- station name labels ----
    L.append('<g id="labels">')
    for code, name, x, y, extra in STATIONS:
        dx, dy, anchor, rot, _ = LABELS[code]
        lx, ly = x + dx, y + dy
        tr = ' transform="rotate(%g %g %g)"' % (rot, lx, ly) if rot is not None else ""
        L.append('  <text class="lbl" x="%g" y="%g" text-anchor="%s" font-size="13" '
                 'font-weight="600" fill="%s"%s>%s</text>'
                 % (lx, ly, anchor, INK, tr, esc(name)))
    L.append("</g>")

    # ---- station code labels ----
    L.append('<g id="codes">')
    for code, name, x, y, extra in STATIONS:
        for c in [code] + extra:
            sx, sy, anchor = SLOTS[CODE_SLOT[c]]
            colour = LINE_OF[c[0]]
            L.append('  <g class="stn-code" data-name="%s" data-code="%s" '
                     'data-station-x="%g" data-station-y="%g">' % (esc(name), c, x, y))
            L.append('    <text x="%g" y="%g" text-anchor="%s" font-size="9" '
                     'font-weight="700" fill="%s">%s</text>'
                     % (x + sx, y + sy, anchor, colour, c))
            L.append("  </g>")
    L.append("</g>")

    # ---- leader lines (station end first, label end second) ----
    L.append('<g id="leaders">')
    for code in ("R06", "B03", "G05"):
        _, name, x, y, _ = by_code[code]
        dx, dy, _a, _r, has = LABELS[code]
        if not has:
            continue
        L.append('  <line class="ldr" x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" '
                 'stroke-width="1.1"/>' % (x, y, x + dx, y + dy + 4, INK))
    L.append("</g>")

    L.append("</svg>")   # /inner map

    # ---------------- canvas-unit blocks ----------------
    # These two live on the outer canvas, so the tool has to handle blocks in
    # both coordinate systems. They sit in the strip below the network.
    L += panel("notes", 60, 1072, 890, 96, "NOTES",
               [(None, "Demo data for transit-label-tuner."),
                (None, "Names, colours and coordinates are fictional.")],
               unit_scale=1.0)
    L += panel("outlying", 990, 1072, 620, 96, "OUTLYING SERVICES",
               [(None, "Ferry — Harbour · Ferry — North Cape"),
                (None, "Cable car — Signal Hill   (not to scale)")],
               unit_scale=1.0)

    L.append("</svg>")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".svg.new")
    tmp.write_text(build(), encoding="utf-8")
    import os
    os.replace(tmp, OUT)
    print("wrote %s (%d bytes)" % (OUT, OUT.stat().st_size))
