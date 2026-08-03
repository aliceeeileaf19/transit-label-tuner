#!/usr/bin/env python3
"""Non-executing reference parser for Transit Label Tuner move lists.

The browser deliberately exports data rather than a rewritten SVG.  This
module shows the other half of that contract: parse the Python-style artifact
with ``ast.literal_eval`` and hand normalized overrides to a generator.

It never imports or executes the move-list file.
"""

import argparse
import ast
import json
import math
import re
from pathlib import Path


ROW_SECTIONS = ("NAME_MOVES", "CODE_NUDGES", "CHAIN_ANGLES")
ASSIGNMENTS = (
    "LAYOUT_NUDGE", "LAYOUT_SCALE", "LEADER_NUDGE",
    "SCHEMATIC_ANCHOR", "NEW_LINE",
)


def _rows(text, name):
    marker = "# ---- " + name
    start = text.find(marker)
    if start < 0:
        return []
    start = text.find("\n", start) + 1
    end = text.find("\n# ---- ", start)
    if end < 0:
        end = len(text)
    try:
        value = ast.literal_eval("[\n" + text[start:end] + "\n]")
    except (SyntaxError, ValueError) as exc:
        raise ValueError("could not parse %s: %s" % (name, exc)) from exc
    if not isinstance(value, list):
        raise ValueError("%s must contain tuple rows" % name)
    return value


def _assignments(text):
    positions = [(text.find(name + " ="), name) for name in ASSIGNMENTS]
    positions = [(position, name) for position, name in positions if position >= 0]
    if not positions:
        return {}
    source = text[min(position for position, _name in positions):]
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise ValueError("could not parse assignment sections: %s" % exc) from exc
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            raise ValueError("unexpected statement in assignment sections")
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in ASSIGNMENTS:
            raise ValueError("unexpected assignment in move list")
        if target.id in found:
            raise ValueError("duplicate assignment for %s" % target.id)
        try:
            found[target.id] = ast.literal_eval(node.value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError("could not parse %s: %s" % (target.id, exc)) from exc
    return found


def _string(value, field):
    if not isinstance(value, str):
        raise ValueError("%s must be a string" % field)
    return value


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("%s must be a finite number" % field)
    return value


def _optional_number(value, field):
    return None if value is None else _number(value, field)


def _pair(value, field):
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("%s must be a two-number tuple" % field)
    return [_number(value[0], field + "[0]"), _number(value[1], field + "[1]")]


def _mapping_pairs(value, field):
    if not isinstance(value, dict):
        raise ValueError("%s must be a dictionary" % field)
    return {_string(key, field + " key"): _pair(pair, "%s[%r]" % (field, key))
            for key, pair in value.items()}


def _validate_assignments(assigned):
    layout_nudge = _mapping_pairs(assigned.get("LAYOUT_NUDGE", {}), "LAYOUT_NUDGE")

    layout_scale = assigned.get("LAYOUT_SCALE", {})
    if not isinstance(layout_scale, dict):
        raise ValueError("LAYOUT_SCALE must be a dictionary")
    layout_scale = {
        _string(key, "LAYOUT_SCALE key"): _number(scale, "LAYOUT_SCALE[%r]" % key)
        for key, scale in layout_scale.items()
    }

    leader_nudge = assigned.get("LEADER_NUDGE", [])
    if not isinstance(leader_nudge, list):
        raise ValueError("LEADER_NUDGE must be a list")
    normalized_leaders = []
    for index, row in enumerate(leader_nudge):
        if not isinstance(row, tuple) or len(row) != 3:
            raise ValueError("LEADER_NUDGE[%d] must contain 3 fields" % index)
        normalized_leaders.append([
            _pair(row[0], "LEADER_NUDGE[%d] station end" % index),
            _number(row[1], "LEADER_NUDGE[%d] dx" % index),
            _number(row[2], "LEADER_NUDGE[%d] dy" % index),
        ])

    schematic_anchor = _mapping_pairs(
        assigned.get("SCHEMATIC_ANCHOR", {}), "SCHEMATIC_ANCHOR")

    new_line = assigned.get("NEW_LINE", [])
    if not isinstance(new_line, list):
        raise ValueError("NEW_LINE must be a list")
    normalized_lines = []
    for index, line in enumerate(new_line):
        if not isinstance(line, dict):
            raise ValueError("NEW_LINE[%d] must be a dictionary" % index)
        if set(line) != {"points", "d", "note"}:
            raise ValueError("NEW_LINE[%d] must contain points, d and note" % index)
        points = line["points"]
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError("NEW_LINE[%d].points must contain at least two points" % index)
        normalized_lines.append({
            "points": [_pair(point, "NEW_LINE[%d].points" % index) for point in points],
            "d": _string(line["d"], "NEW_LINE[%d].d" % index),
            "note": _string(line["note"], "NEW_LINE[%d].note" % index),
        })

    return {
        "layout_nudge": layout_nudge,
        "layout_scale": layout_scale,
        "leader_nudge": normalized_leaders,
        "schematic_anchor": schematic_anchor,
        "new_line": normalized_lines,
    }


def _metadata(text):
    def field(label):
        match = re.search(r"^# %s\s*:\s*(.+?)\s*$" % re.escape(label), text, re.M)
        return match.group(1) if match else None
    return {
        "source": field("source diagram"),
        "format": field("format version"),
        "fingerprint": field("source fingerprint"),
    }


def parse_move_list(text):
    """Return a normalized, JSON-serializable move-list dictionary."""
    rows = {name: _rows(text, name) for name in ROW_SECTIONS}
    name_moves = []
    seen_names = set()
    for row in rows["NAME_MOVES"]:
        if not isinstance(row, tuple) or len(row) != 9:
            raise ValueError("NAME_MOVES rows must contain 9 fields")
        label, station, code, dx, dy, anchor, angle, leader, why = row
        label = _string(label, "NAME_MOVES label")
        station = _string(station, "NAME_MOVES station")
        code = _string(code, "NAME_MOVES code")
        dx = _number(dx, "NAME_MOVES dx")
        dy = _number(dy, "NAME_MOVES dy")
        why = _string(why, "NAME_MOVES why")
        key = (label, code)
        if key in seen_names:
            raise ValueError("duplicate NAME_MOVES row for %s|%s" % key)
        seen_names.add(key)
        if anchor not in ("start", "middle", "end") or not isinstance(leader, bool):
            raise ValueError("invalid NAME_MOVES anchor/leader for %s|%s" % key)
        name_moves.append({
            "label": label, "station": station, "code": code,
            "dx": dx, "dy": dy, "anchor": anchor,
            "original_angle": _optional_number(angle, "NAME_MOVES original angle"),
            "has_leader": leader, "why": why,
        })

    # Later code rows intentionally win; this mirrors the documented contract.
    code_by_key = {}
    for row in rows["CODE_NUDGES"]:
        if not isinstance(row, tuple) or len(row) != 6:
            raise ValueError("CODE_NUDGES rows must contain 6 fields")
        station, data_code, code, slot, old_slot, why = row
        station = _string(station, "CODE_NUDGES station")
        data_code = _string(data_code, "CODE_NUDGES data-code")
        code = _string(code, "CODE_NUDGES code")
        why = _string(why, "CODE_NUDGES why")
        valid_slots = ("S", "E", "W", "N", "NE", "SE", "NW", "SW")
        if slot not in valid_slots or old_slot not in valid_slots:
            raise ValueError("invalid code slot %r" % (slot,))
        code_by_key[(station, data_code, code)] = {
            "station": station, "data_code": data_code, "code": code,
            "slot": slot, "old_slot": old_slot, "why": why,
        }

    angles = []
    seen_angle_labels = set()
    for row in rows["CHAIN_ANGLES"]:
        if not isinstance(row, tuple) or len(row) != 5:
            raise ValueError("CHAIN_ANGLES rows must contain 5 fields")
        chain, labels, old_angle, new_angle, why = row
        if not isinstance(labels, list) or not labels:
            raise ValueError("CHAIN_ANGLES labels must be a non-empty list")
        chain = _string(chain, "CHAIN_ANGLES chain")
        labels = [_string(label, "CHAIN_ANGLES label") for label in labels]
        old_angle = _number(old_angle, "CHAIN_ANGLES old angle")
        new_angle = _number(new_angle, "CHAIN_ANGLES new angle")
        why = _string(why, "CHAIN_ANGLES why")
        duplicated = seen_angle_labels.intersection(labels)
        if duplicated:
            raise ValueError("duplicate CHAIN_ANGLES target: %s" % sorted(duplicated))
        seen_angle_labels.update(labels)
        angles.append({
            "chain": chain, "labels": labels, "old_angle": old_angle,
            "new_angle": new_angle, "why": why,
        })

    assigned = _validate_assignments(_assignments(text))
    return {
        "metadata": _metadata(text),
        "name_moves": name_moves,
        "code_nudges": list(code_by_key.values()),
        "chain_angles": angles,
        **assigned,
    }


def load_move_list(path):
    return parse_move_list(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(
        description="Parse a Transit Label Tuner move list without executing it")
    parser.add_argument("move_list", type=Path)
    args = parser.parse_args()
    print(json.dumps(load_move_list(args.move_list), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
