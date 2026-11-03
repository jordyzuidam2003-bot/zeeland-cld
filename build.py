"""Check the CLD and build the files Kumu reads.

    python3 build.py           # check, write dist/, print the report
    python3 build.py --check   # fail if dist/ is out of date (the pre-commit hook runs this)

Edit cld.json (elements, connections, loops, layout), references.json (sources) and
view.scss (style). Never edit dist/, which this script writes:

    dist/project.json  a full Kumu project export: import it into a Kumu project without maps
                       (green + > Import > Advanced > Import JSON file) and Kumu restores the
                       elements at their positions, the curved links and the view
    dist/kumu.json     the blueprint form (elements and connections only), for a map linked to
                       its raw GitHub URL; such a map cannot hold a layout, so it is force-directed
    dist/view.scss     view.scss plus each link's curvature, to paste into the Advanced Editor
                       of a map built from the blueprint
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

ELEMENT_TYPES = ["Constant", "Auxiliary", "Stock", "Adaptation"]
FOCUS_AREAS = ["Climate drivers", "Biophysical system", "Water governance",
               "Crops and market", "Finance and land"]
SUBQUESTIONS = ["SQ1", "SQ2", "SQ3"]
SETS_LETTER = {"Social": "S", "Ecological": "E", "Technological": "T"}


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
        for key, allowed in [("element type", ELEMENT_TYPES), ("sets subsystem", list(SETS_LETTER)),
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


def blueprint(cld, refs):
    els = {e["id"]: e for e in cld["elements"]}

    def sourced(item):
        return {"sources": "\n".join(refs[k] for k in item["sources"]),
                "sourced": "yes" if item["sources"] else "no"}

    elements = []
    for e in cld["elements"]:
        item = {k: v for k, v in e.items() if k != "sources"}
        item.update(sourced(e))
        elements.append(item)

    connections = []
    for c in cld["connections"]:
        a, b = els[c["from"]], els[c["to"]]
        sa, sb = a["sets subsystem"], b["sets subsystem"]
        fa, fb = a["focus area"], b["focus area"]
        connections.append({
            "id": f'{c["from"]}--{c["to"]}', "from": c["from"], "to": c["to"],
            "direction": "directed",
            "label": "+" if c["polarity"] == "+" else "−",
            "type": c["polarity"],  # Kumu's connection type: it draws the sign at the arrowhead
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


def project(cld, refs, template):
    """A full Kumu project export, the shape of Kumu's own "Export JSON" of a project."""
    bp = blueprint(cld, refs)
    keep = lambda item, drop: {k: v for k, v in item.items() if k not in drop}
    elements = [{"_id": f'elem-{e["id"]}', "attributes": keep(e, {"id", "x", "y"})}
                for e in bp["elements"]]
    # the blueprint key "type" is "connection type" in a project export: the +/- at the arrowhead
    connections = [{"_id": f'conn-{c["id"]}', "direction": "directed", "delayed": c["delay"] == "yes",
                    "reversed": False,
                    "attributes": {**keep(c, {"id", "from", "to", "direction", "type"}),
                                   "connection type": c["type"]},
                    "from": f'elem-{c["from"]}', "to": f'elem-{c["to"]}'}
                   for c in bp["connections"]]

    # one attribute entry per field, a drop-down list where the values are few
    values = {}
    for item in [e["attributes"] for e in elements] + [c["attributes"] for c in connections]:
        for k, v in item.items():
            values.setdefault(k, set()).add(v)
    attributes = []
    for k, seen in values.items():
        text = k in ("description", "sources")
        listed = not text and k != "label" and len(seen) <= 20
        attributes.append({"_id": "attr-" + k.replace(" ", "-"), "name": k[0].upper() + k[1:],
                           "format": "text" if text else "string", "private": False, "limit": 1,
                           "category": "General", "prompt": "list" if listed else "autocomplete",
                           "locked": False, "values": sorted(seen) if listed else [],
                           "sort": False, "cluster": listed})

    nodes = [{"_id": f'node-{e["id"]}', "position": {"x": e["x"], "y": e["y"]}, "pinned": True,
              "style": {}, "element": f'elem-{e["id"]}'} for e in cld["elements"]]
    edges = [{"_id": f'edge-{c["from"]}--{c["to"]}', "curvature": c["curvature"], "style": {},
              "connection": f'conn-{c["from"]}--{c["to"]}'} for c in cld["connections"]]
    return {
        "version": 1, "name": "Zeeland CLD", "description": "", "proxyImages": True,
        "defaultMap": "map-cld", "defaultPerspective": None, "attributeRelevance": {},
        "attributes": attributes, "elements": elements, "connections": connections, "loops": [],
        "maps": [{"_id": "map-cld", "name": "CLD", "description": "", "scale": 1,
                  "center": {"x": 0, "y": 0}, "defaultPerspective": "pers-cld",
                  "defaultElementBehavior": "fixed", "defaultConnectionDirection": "directed",
                  "elements": nodes, "connections": edges, "loops": []}],
        # the view without the generated curvature rules: the map's edges carry the curves
        "perspectives": [{"_id": "pers-cld", "name": "CLD", "style": template.rstrip() + "\n"}],
    }


def view(template, cld):
    # A linked connection has no Kumu id, so "#id" cannot select it: the id field can.
    # Every link is listed, since Kumu's default curvature is 0.25, not 0. No comment goes
    # above these rules: Kumu turns a comment above a rule into a legend entry.
    lines = [""]
    for c in cld["connections"]:
        lines.append(f'connection["id"="{c["from"]}--{c["to"]}"] {{ curvature: {c["curvature"]}; }}')
    return template.rstrip() + "\n" + "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if dist/ is out of date")
    args = parser.parse_args()

    cld, refs, template = load()
    errors, warnings = check(cld, refs)
    if errors:
        sys.exit("cld.json has errors:\n  " + "\n  ".join(errors))

    outputs = {
        "kumu.json": json.dumps(blueprint(cld, refs), indent=2, ensure_ascii=False) + "\n",
        "project.json": json.dumps(project(cld, refs, template), indent=2, ensure_ascii=False) + "\n",
        "view.scss": view(template, cld),
    }

    if args.check:
        stale = [name for name, text in outputs.items()
                 if not (DIST / name).exists() or (DIST / name).read_text() != text]
        if stale:
            sys.exit(f"dist/ is out of date ({', '.join(stale)}): run build.py and commit dist/")
        return

    DIST.mkdir(exist_ok=True)
    for name, text in outputs.items():
        (DIST / name).write_text(text)

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
