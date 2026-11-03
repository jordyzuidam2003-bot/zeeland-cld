"""Check the CLD and build the files Kumu reads.

    .venv/bin/python build.py           # check, write dist/, print the report
    .venv/bin/python build.py --check   # fail if dist/ is out of date (the pre-commit hook runs this)

Edit cld.json (elements, connections, loops, layout), references.json (sources) and
view.scss (style). Never edit dist/, which this script writes:

    dist/kumu.json  the blueprint the Kumu map is linked to ("Link map to remote JSON"):
                    Kumu fetches it from GitHub on every page load
    dist/view.scss  view.scss plus each link's curvature and the glow's size; paste it into
                    Kumu's Advanced Editor whenever it changes, since Kumu cannot fetch a view
    dist/glow.png   the SETS glow behind the map: a soft blob per element in its SETS colour

Kumu's remote JSON holds elements, connections and loops only, no positions or view. So the
view uses the scatter layout, which places each element at its own x and y fields.
"""

import argparse
import hashlib
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
RAW = "https://raw.githubusercontent.com/jordyzuidam2003-bot/zeeland-cld/main/"

ELEMENT_TYPES = ["Constant", "Auxiliary", "Stock", "Adaptation"]
FOCUS_AREAS = ["Climate drivers", "Biophysical system", "Water governance",
               "Crops and market", "Finance and land"]
SUBQUESTIONS = ["SQ1", "SQ2", "SQ3"]
SETS_COLOURS = {"Social": (224, 90, 155), "Ecological": (93, 170, 74),
                "Technological": (242, 155, 48)}
SETS_LETTER = {"Social": "S", "Ecological": "E", "Technological": "T"}

GLOW_SIGMA = 300         # map units; an element is 120 across
GLOW_OPACITY = 0.45
GLOW_MARGIN = 600        # map units of glow canvas around the outermost elements
GLOW_PX_PER_UNIT = 0.25  # the glow is blurry, so a coarse image is enough


def load():
    cld = json.loads((ROOT / "cld.json").read_text())
    refs = json.loads((ROOT / "references.json").read_text())
    template = (ROOT / "view.scss").read_text()
    return cld, refs, template


def check(cld, refs):
    """Return (errors, warnings). Errors stop the build; warnings are model smells."""
    errors, warnings = [], []
    els = {}
    for e in cld["elements"]:
        name = e.get("id", "?")
        if name in els:
            errors.append(f"duplicate element id {name}")
        els[name] = e
        for key, allowed in [("element type", ELEMENT_TYPES), ("sets subsystem", list(SETS_COLOURS)),
                             ("focus area", FOCUS_AREAS), ("subquestion", SUBQUESTIONS)]:
            if e.get(key) not in allowed:
                errors.append(f"{name}: {key} {e.get(key)!r} not in {allowed}")
        if not all(isinstance(e.get(k), (int, float)) for k in ("x", "y")):
            errors.append(f"{name}: x and y must be numbers")
    labels = [e["label"] for e in cld["elements"]]
    errors += [f"duplicate label {l!r}" for l in set(labels) if labels.count(l) > 1]

    pairs = set()
    for c in cld["connections"]:
        pair = (c.get("from"), c.get("to"))
        name = " -> ".join(map(str, pair))
        if pair[0] not in els or pair[1] not in els:
            errors.append(f"{name}: unknown element")
        if pair[0] == pair[1]:
            errors.append(f"{name}: links an element to itself")
        if pair in pairs:
            errors.append(f"{name}: duplicate connection")
        pairs.add(pair)
        if c.get("polarity") not in ("+", "-"):
            errors.append(f"{name}: polarity must be '+' or '-'")
        if not isinstance(c.get("delay"), bool) or not isinstance(c.get("curvature"), (int, float)):
            errors.append(f"{name}: delay must be true/false and curvature a number")

    for item in cld["elements"] + cld["connections"]:
        for key in item.get("sources", []):
            if key not in refs:
                errors.append(f"source {key!r} is not in references.json")

    sign = {(c["from"], c["to"]): c["polarity"] for c in cld["connections"]}
    for loop in cld["loops"]:
        path = loop["path"]
        steps = list(zip(path, path[1:] + path[:1]))
        gaps = [f"{a} -> {b}" for a, b in steps if (a, b) not in sign]
        if gaps:
            errors.append(f"loop {loop['id']}: no connection {', '.join(gaps)}")
            continue
        kind = "B" if sum(sign[s] == "-" for s in steps) % 2 else "R"
        if not loop["id"].startswith(kind):
            errors.append(f"loop {loop['id']} is {'balancing' if kind == 'B' else 'reinforcing'} "
                          f"as drawn, so its id must start with {kind}")

    if not errors:
        has_in = {c["to"] for c in cld["connections"]}
        has_out = {c["from"] for c in cld["connections"]}
        for e in cld["elements"]:
            if e["id"] not in has_in | has_out:
                warnings.append(f"{e['id']}: no connections")
            elif e["id"] not in has_in and e["element type"] != "Constant":
                warnings.append(f"{e['id']}: nothing drives it, yet it is not a Constant")
            elif e["id"] in has_in and e["element type"] == "Constant":
                warnings.append(f"{e['id']}: a Constant, yet links drive it")
        cited = {k for item in cld["elements"] + cld["connections"] for k in item.get("sources", [])}
        warnings += [f"reference {k!r} is cited nowhere" for k in refs if k not in cited]
    return errors, warnings


def cycles(cld):
    """Every simple feedback loop in the diagram, as (kind, element ids)."""
    order = [e["id"] for e in cld["elements"]]
    out = {i: [] for i in order}
    sign = {}
    for c in cld["connections"]:
        out[c["from"]].append(c["to"])
        sign[(c["from"], c["to"])] = c["polarity"]
    found = []
    for start_index, start in enumerate(order):
        allowed = set(order[start_index:])  # each loop is found once, from its earliest element
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for nxt in out[node]:
                if nxt == start:
                    steps = list(zip(path, path[1:] + path[:1]))
                    negatives = sum(sign[s] == "-" for s in steps)
                    found.append(("B" if negatives % 2 else "R", path))
                elif nxt in allowed and nxt not in path:
                    stack.append((nxt, path + [nxt]))
    return found


def glow(cld):
    """The glow image and the square of the map it covers: (rgba array, centre x, centre y, side)."""
    xs = [e["x"] for e in cld["elements"]]
    ys = [e["y"] for e in cld["elements"]]
    cx, cy = round((min(xs) + max(xs)) / 2), round((min(ys) + max(ys)) / 2)
    side = math.ceil((max(max(xs) - min(xs), max(ys) - min(ys)) + 2 * GLOW_MARGIN) / 100) * 100
    px = round(side * GLOW_PX_PER_UNIT)
    grid = (np.arange(px) + 0.5) / GLOW_PX_PER_UNIT - side / 2
    gx, gy = np.meshgrid(cx + grid, cy + grid)

    # per SETS domain: the chance that any of its blobs covers the pixel
    cover = {}
    for e in cld["elements"]:
        w = np.exp(-((gx - e["x"]) ** 2 + (gy - e["y"]) ** 2) / (2 * GLOW_SIGMA ** 2))
        domain = e["sets subsystem"]
        cover[domain] = 1 - (1 - cover.get(domain, 0)) * (1 - w)
    total = sum(cover.values())
    rgb = sum(cover[d][..., None] * np.array(SETS_COLOURS[d]) for d in cover)
    rgb = rgb / np.maximum(total, 1e-9)[..., None]
    alpha = GLOW_OPACITY * (1 - np.prod([1 - a for a in cover.values()], axis=0))
    rgba = np.dstack([rgb, alpha * 255]).round().clip(0, 255).astype(np.uint8)
    return rgba, cx, cy, side


def blueprint(cld, refs, glow_url, cx, cy):
    els = {e["id"]: e for e in cld["elements"]}

    def sourced(item):
        return {"sources": "\n".join(refs[k] for k in item["sources"]),
                "sourced": "yes" if item["sources"] else "no"}

    elements = []
    for e in cld["elements"]:
        item = {k: v for k, v in e.items() if k != "sources"}
        item.update(sourced(e))
        elements.append(item)
    elements.append({"id": "background", "label": "background", "element type": "Background",
                     "description": "SETS glow behind the map, generated by build.py.",
                     "image": glow_url, "x": cx, "y": cy})

    connections = []
    for c in cld["connections"]:
        a, b = els[c["from"]], els[c["to"]]
        sa, sb = a["sets subsystem"], b["sets subsystem"]
        fa, fb = a["focus area"], b["focus area"]
        connections.append({
            "id": f'{c["from"]}--{c["to"]}', "from": c["from"], "to": c["to"],
            "direction": "directed",
            "label": "+" if c["polarity"] == "+" else "−",
            "polarity": "positive" if c["polarity"] == "+" else "negative",
            "delay": "yes" if c["delay"] else "no",
            "loop id": c["loop id"],
            "description": c["description"],
            "sets link": f"Within {SETS_LETTER[sa]}" if sa == sb else f"{SETS_LETTER[sa]} to {SETS_LETTER[sb]}",
            "sets scope": "Within domain" if sa == sb else "Cross-domain",
            "focus link": f"Within {fa}" if fa == fb else f"{fa} to {fb}",
            "focus scope": "Within focus area" if fa == fb else "Cross-focus area",
            **sourced(c),
        })
    # Kumu loops are added here once cld.json defines loops; build.py already checks them
    return {"elements": elements, "connections": connections}


def view(template, cld, side):
    # Kumu's size is a radius. A linked connection has no Kumu id, so "#id" cannot select it:
    # the id field can. Every link is listed, since Kumu's default curvature is 0.25, not 0.
    lines = ["", "/* ---------- generated by build.py from cld.json: change it there ---------- */",
             f"#background {{\n  size: {side // 2};\n}}", ""]
    for c in cld["connections"]:
        lines.append(f'connection["id"="{c["from"]}--{c["to"]}"] {{ curvature: {c["curvature"]}; }}')
    return template.rstrip() + "\n" + "\n".join(lines) + "\n"


def png_bytes(rgba):
    buffer = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if dist/ is out of date")
    args = parser.parse_args()

    cld, refs, template = load()
    errors, warnings = check(cld, refs)
    if errors:
        sys.exit("cld.json has errors:\n  " + "\n  ".join(errors))

    rgba, cx, cy, side = glow(cld)
    glow_url = f"{RAW}dist/glow.png?v={hashlib.sha256(rgba.tobytes()).hexdigest()[:10]}"
    outputs = {
        "kumu.json": json.dumps(blueprint(cld, refs, glow_url, cx, cy), indent=2, ensure_ascii=False) + "\n",
        "view.scss": view(template, cld, side),
    }

    if args.check:
        stale = [name for name, text in outputs.items()
                 if not (DIST / name).exists() or (DIST / name).read_text() != text]
        png = DIST / "glow.png"
        if not png.exists() or not np.array_equal(np.asarray(Image.open(png)), rgba):
            stale.append("glow.png")
        if stale:
            sys.exit(f"dist/ is out of date ({', '.join(stale)}): run build.py and commit dist/")
        return

    DIST.mkdir(exist_ok=True)
    for name, text in outputs.items():
        (DIST / name).write_text(text)
    (DIST / "glow.png").write_bytes(png_bytes(rgba))

    loops = cycles(cld)
    n_el, n_conn = len(cld["elements"]), len(cld["connections"])
    print(f"{n_el} elements, {n_conn} connections, {len(cld['loops'])} named loops")
    print(f"sourced: {sum(bool(e['sources']) for e in cld['elements'])}/{n_el} elements, "
          f"{sum(bool(c['sources']) for c in cld['connections'])}/{n_conn} connections")
    print(f"feedback loops in the diagram: {len(loops)} "
          f"({sum(k == 'R' for k, _ in loops)} R, {sum(k == 'B' for k, _ in loops)} B), "
          f"shortest {min((len(p) for _, p in loops), default=0)} links")
    if warnings:
        print("warnings:\n  " + "\n  ".join(warnings))


if __name__ == "__main__":
    main()
