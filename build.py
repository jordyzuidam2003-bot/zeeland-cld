"""Check the CLD and build docs/, the files GitHub Pages serves.

    python3 build.py                  # check, write docs/, print the report
    python3 build.py --check          # fail if docs/ is out of date (the pre-commit hook runs this)
    python3 build.py --layout FILE    # write the positions and curvatures of FILE (layout.json,
                                      # downloaded from the page's drag mode) into cld.json, then build
    python3 build.py --layout FILE --v2   # the same into cld-v2.json

Sources, edited by hand: cld.json (elements, connections, named loops, layout and
link curvature), references.json (sources), view.scss (the Kumu view inside project.json) and
page/ (index.html, a template with the placeholders <!-- SVG --> and <!-- DATA -->; app.js;
style.css). draw.py draws the SVG. Version 2, cld-v2.json, stands beside version 1 until the
group makes the final CLD from both (VERSIONS); each version is checked and built into its own
folder, version 2's docs/v2/, sharing references.json, view.scss, page/ and draw.py. Never edit
docs/, which this script writes (per version):

    docs/index.html    the page: the template with the drawing inline and the data as JSON
    docs/app.js        copied from page/
    docs/style.css     copied from page/
    docs/cld.svg       the drawing on its own, the picture for the report
    docs/loops/<id>.svg  each named loop on its own (draw.loop_figure()), its figure for the
                       report; the page's panel for the loop shows it
    docs/regions.svg   the subsystem regions alone, the background image of the Kumu map
    docs/project.json  a full Kumu project export: restore it into a brand-new Kumu project
                       (New Project > the next screen > restore backup) and Kumu restores the
                       elements at their positions, the curved links, the view and the regions
                       (an element labelled background showing docs/regions.svg as its image,
                       by its URL on the published page); the model version is in the project's
                       description and the map's name
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import draw

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
PAGE = ROOT / "page"
PAGES_URL = "https://jordyzuidam2003-bot.github.io/zeeland-cld/"
# version 1 stays as Lenne approved it, its page unchanged, while version 2 is built beside it
VERSIONS = [
    {"name": "1", "file": "cld.json", "docs": DOCS, "url": PAGES_URL, "kumu": "cbp-cld"},
    {"name": "2", "file": "cld-v2.json", "docs": DOCS / "v2", "url": PAGES_URL + "v2/", "kumu": "cbp-cld-v2"},
]

ELEMENT_TYPES = ["Constant", "Auxiliary", "Stock"]
SUBQUESTIONS = ["SQ1", "SQ2", "SQ3"]
SETS_LETTER = {"Social": "S", "Ecological": "E", "Technological": "T"}


def versions():
    """The versions whose file exists, each with its model loaded."""
    return [{**v, "cld": json.loads((ROOT / v["file"]).read_text())}
            for v in VERSIONS if (ROOT / v["file"]).exists()]


def check(cld, refs):
    """Return (errors, warnings). Errors stop the build; warnings are model smells."""
    errors, warnings = [], []
    els = {}
    for e in cld["elements"]:
        name = e.get("id", "?")
        if name in els:
            errors.append(f"duplicate element id {name}")
        els[name] = e
        for key, allowed in [("element type", ELEMENT_TYPES), ("sets domain", list(SETS_LETTER)),
                             ("subsystem", list(draw.REGION)), ("subquestion", SUBQUESTIONS)]:
            if e.get(key) not in allowed:
                errors.append(f"{name}: {key} {e.get(key)!r} not in {allowed}")
        if not isinstance(e.get("adaptive practice"), bool):
            errors.append(f"{name}: adaptive practice must be true/false")
        if not all(isinstance(e.get(k), (int, float)) for k in ("x", "y")):
            errors.append(f"{name}: x and y must be numbers")
        # a decision variable names the one actor that decides it, from the model's list
        if "actor" in e and e["actor"] not in cld.get("actors", []):
            errors.append(f"{name}: actor {e['actor']!r} is not in the top-level actors list")
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
        # A behavioural claim with no source is a hypothesis for the group model building session;
        # one that finds a source takes it and loses the mark.
        if not isinstance(c.get("hypothesis", False), bool):
            errors.append(f"{name}: hypothesis must be true/false")
        elif c.get("hypothesis") and c.get("sources"):
            errors.append(f"{name}: a hypothesis with sources: a sourced link loses its hypothesis mark")

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
        # A Constant drives from outside the system, so its links run straight (Jordy's decision).
        constant = {e["id"] for e in cld["elements"] if e["element type"] == "Constant"}
        warnings += [f"{c['from']} -> {c['to']}: a Constant's link, yet bent (curvature {c['curvature']})"
                     for c in cld["connections"] if c["from"] in constant and c["curvature"] != 0]
        # A delay is a claim about duration, so its description names one (a number: years, m per decade).
        warnings += [f"{c['from']} -> {c['to']}: a delay, yet its description gives no duration"
                     for c in cld["connections"] if c["delay"] and not any(ch.isdigit() for ch in c["description"])]
        # The CLD describes mechanisms and is shaped for no lever set, so no element or link names one.
        warnings += [f"{item.get('id') or item['from'] + ' -> ' + item['to']}: names a policy lever"
                     for item in cld["elements"] + cld["connections"]
                     if re.search(r"\b(levers?|buy-?outs?|land bank)\b", item["description"], re.I)]
        warnings += draw.overlaps(cld)
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
        item["adaptive practice"] = "yes" if e["adaptive practice"] else "no"
        item.update(sourced(e))
        elements.append(item)

    connections = []
    for c in cld["connections"]:
        a, b = els[c["from"]], els[c["to"]]
        sa, sb = a["sets domain"], b["sets domain"]
        connections.append({
            "id": f'{c["from"]}--{c["to"]}', "from": c["from"], "to": c["to"],
            "direction": "directed",
            "label": "+" if c["polarity"] == "+" else "−",
            "type": c["polarity"],  # Kumu's connection type: it draws the sign at the arrowhead
            "polarity": "positive" if c["polarity"] == "+" else "negative",
            "delay": "yes" if c["delay"] else "no",
            "description": c["description"],
            "sets link": f"Within {SETS_LETTER[sa]}" if sa == sb else f"{SETS_LETTER[sa]} to {SETS_LETTER[sb]}",
            "sets scope": "Within domain" if sa == sb else "Cross-domain",
            "hypothesis": "yes" if c.get("hypothesis") else "no",
            **sourced(c),
        })
    return {"elements": elements, "connections": connections}


def page_data(cld, refs, version):
    """What the page shows per element and link: the blueprint without the drawing's numbers."""
    bp = blueprint(cld, refs)
    drop = {"x", "y", "curvature"}
    return {
        "elements": [{k: v for k, v in e.items() if k not in drop} for e in bp["elements"]],
        "connections": [{k: v for k, v in c.items() if k not in drop} for c in bp["connections"]],
        "loops": cld["loops"],
        "version": version,
    }


def page(cld, refs, version, v):
    """docs/index.html: the template with the drawing inline and the data as JSON; a version
    other than 1 names itself and links to version 1."""
    template = (PAGE / "index.html").read_text()
    if v["name"] != "1":
        for old, new in [("<title>Zeeland CLD</title>", f'<title>Zeeland CLD, version {v["name"]}</title>'),
                         ("<h1>Zeeland CLD</h1>", f'<h1>Zeeland CLD, version {v["name"]}</h1>'),
                         ('</p>\n</header>', f'</p>\n  <p class="intro">Version {v["name"]}, built from version 1 and '
                          'its review; <a href="../">version 1</a> stays beside it, unchanged.</p>\n</header>')]:
            assert template.count(old) == 1, f"page/index.html must hold {old!r} once"
            template = template.replace(old, new)
    svg = draw.svg(cld)
    # "</" inside a <script> would end it early; "<\/" is the same string to JSON
    data = json.dumps(page_data(cld, refs, version), ensure_ascii=False).replace("</", "<\\/")
    for marker in ("<!-- SVG -->", "<!-- DATA -->"):
        assert template.count(marker) == 1, f"page/index.html must hold {marker} once"
    return (template.replace("<!-- SVG -->", svg.rstrip())
            .replace("<!-- DATA -->", f'<script type="application/json" id="data">{data}</script>'))


def project(cld, refs, template, version, ver):
    """A full Kumu project export, the shape of Kumu's own "Export JSON" of a project.

    The view is view.scss plus what is generated here: a showcase button per named loop, in
    view.scss's place for it, each SETS domain's tint from draw.TINT,
    and by Kumu system id each element's box size from draw.boxes(). Each label holds a double space where the page breaks its line,
    Kumu's manual line break, so its box fits it."""
    bp = blueprint(cld, refs)
    keep = lambda item, drop: {k: v for k, v in item.items() if k not in drop}
    bxs = draw.boxes(cld)
    elements = [{"_id": f'elem-{e["id"]}',
                 "attributes": {**keep(e, {"id", "x", "y"}), "label": "  ".join(bxs[e["id"]][4])}}
                for e in bp["elements"]]
    # the regions: an element labelled background, its image docs/regions.svg (view.scss)
    elements.append({"_id": "elem-background", "attributes": {"label": "background"}})
    _, (fx0, fy0, fx1, fy1) = draw.regions_svg(cld)
    rules = ([f'["sets domain"="{d.lower()}"] {{ color: {t}; }}' for d, t in draw.TINT.items()]
             + [f'#elem-{i} {{ width: {round(b[2] - b[0])}; height: {round(b[3] - b[1])}; }}'
                for i, b in bxs.items()]
             + [f'#background {{ width: {round(fx1 - fx0)}; height: {round(fy1 - fy0)}; }}'])
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
    # Kumu's own type fields are spelled this way; "Connection type" would be a second field
    builtin = {"element type": "Element Type", "connection type": "Connection Type"}
    attributes = []
    for k, seen in values.items():
        text = k in ("description", "sources")
        listed = not text and k != "label" and len(seen) <= 20
        attributes.append({"_id": "attr-" + k.replace(" ", "-"), "name": builtin.get(k, k[0].upper() + k[1:]),
                           "format": "text" if text else "string", "private": False, "limit": 1,
                           "category": "General", "prompt": "list" if listed else "autocomplete",
                           "locked": False, "values": sorted(seen) if listed else [],
                           "sort": False, "cluster": listed})

    nodes = [{"_id": f'node-{i}', "position": {"x": x, "y": y}, "pinned": True,
              "style": {}, "element": f'elem-{i}'}
             for i, x, y in [(e["id"], e["x"], e["y"]) for e in cld["elements"]]
             + [("background", round((fx0 + fx1) / 2), round((fy0 + fy1) / 2))]]
    edges = [{"_id": f'edge-{c["from"]}--{c["to"]}', "curvature": c["curvature"], "style": {},
              "connection": f'conn-{c["from"]}--{c["to"]}'} for c in cld["connections"]]
    # A Kumu loop is its connections by id, its label and description as attributes; the map places
    # the loop's label. Kumu does not document its export: this is the shape its exports hold (read
    # in Loopweft's Kumu importer, checked there on real exports), with the label at the centre of
    # the loop's elements.
    by_id = {e["id"]: e for e in cld["elements"]}
    loops, map_loops = [], []
    for loop in cld["loops"]:
        path = loop["path"]
        loops.append({"_id": f'loop-{loop["id"]}',
                      "attributes": {"label": f'{loop["id"]} {loop["name"]}', "description": ""},
                      "connections": [f'conn-{a}--{b}' for a, b in zip(path, path[1:] + path[:1])]})
        map_loops.append({"_id": f'mloop-{loop["id"]}', "loop": f'loop-{loop["id"]}', "style": {},
                          "position": {"x": round(sum(by_id[i]["x"] for i in path) / len(path)),
                                       "y": round(sum(by_id[i]["y"] for i in path) / len(path))}})
    description = (f"Model version {version}, the first seven characters of the SHA-256 of {ver['file']}. "
                   "A copy for milestones: the current model is the page "
                   f"{ver['url']}, built from "
                   "https://github.com/jordyzuidam2003-bot/zeeland-cld.")
    # a showcase button per named loop: its elements and links (Kumu's :loop selector, by the
    # loop's label), and the regions, which a showcase fades unless it selects them
    options = "\n\n".join(f'      option {{\n        label: "{label}";\n'
                          f'        selector: *:loop(["label"="{label}"]), #background;\n      }}'
                          for label in (f'{loop["id"]} {loop["name"]}' for loop in cld["loops"]))
    template = template.replace("      /* LOOP OPTIONS */", options)
    template = template.replace(PAGES_URL + "regions.svg", ver["url"] + "regions.svg")
    style = (template.rstrip() + "\n\n/* ---------- generated by build.py: tints, box sizes, the regions' size ---------- */\n"
             + "\n".join(rules) + "\n")
    # a restore sets the project's name, so it is the name of the project the group's URL names
    return {
        "version": 1, "name": ver["kumu"], "description": description, "proxyImages": True,
        "defaultMap": "map-cld", "defaultPerspective": None, "attributeRelevance": {},
        "attributes": attributes, "elements": elements, "connections": connections, "loops": loops,
        "maps": [{"_id": "map-cld", "name": f"CLD{'' if ver['name'] == '1' else ' version ' + ver['name']}, model {version}", "description": "", "scale": 1,
                  "center": {"x": 0, "y": 0}, "defaultPerspective": "pers-cld",
                  "defaultElementBehavior": "fixed", "defaultConnectionDirection": "directed",
                  "elements": nodes, "connections": edges, "loops": map_loops}],
        # the map's edges carry the curves, so the view holds no curvature rules
        "perspectives": [{"_id": "pers-cld", "name": "CLD", "style": style}],
    }


def apply_layout(path, file):
    """Write the positions and curvatures of a layout.json ({id: {x, y}, "curvature": {"from->to": k}},
    from the page's drag mode) into cld.json, in its own formatting; a file without "curvature"
    moves the elements only."""
    layout = json.loads(path.read_text())
    curvature = layout.pop("curvature", {})
    cld = json.loads((ROOT / file).read_text())
    by_id = {e["id"]: e for e in cld["elements"]}
    by_link = {f'{c["from"]}->{c["to"]}': c for c in cld["connections"]}
    unknown = [i for i in layout if i not in by_id] + [k for k in curvature if k not in by_link]
    if unknown:
        sys.exit(f"--layout: unknown element or link {', '.join(unknown)}")
    for i, pos in layout.items():
        by_id[i]["x"], by_id[i]["y"] = int(pos["x"]), int(pos["y"])
    for k, v in curvature.items():
        if by_link[k]["curvature"] != v:  # an unchanged value keeps its spelling (0 or 0.0)
            by_link[k]["curvature"] = v
    (ROOT / file).write_text(json.dumps(cld, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if docs/ is out of date")
    parser.add_argument("--layout", metavar="FILE", help="write the x, y and curvatures of FILE (layout.json from the page) into cld.json, then build")
    parser.add_argument("--v2", action="store_true", help="with --layout: write into cld-v2.json")
    args = parser.parse_args()

    if args.layout:
        apply_layout(Path(args.layout), "cld-v2.json" if args.v2 else "cld.json")
    refs = json.loads((ROOT / "references.json").read_text())
    template = (ROOT / "view.scss").read_text()
    built = versions()
    outputs, extra, reports = {}, [], []
    for v in built:
        cld = v["cld"]
        errors, warnings = check(cld, refs)
        if errors:
            sys.exit(f"{v['file']} has errors:\n  " + "\n  ".join(errors))

        # the model version teammates compare: the first seven characters of the file's SHA-256
        version = hashlib.sha256((ROOT / v["file"]).read_bytes()).hexdigest()[:7]
        rel = v["docs"].relative_to(DOCS).as_posix()
        at = lambda name: name if rel == "." else f"{rel}/{name}"
        files = {
            "project.json": json.dumps(project(cld, refs, template, version, v), indent=2, ensure_ascii=False) + "\n",
            "cld.svg": draw.svg(cld),
            "regions.svg": draw.regions_svg(cld)[0],
            "index.html": page(cld, refs, version, v),
            "app.js": (PAGE / "app.js").read_text(),
            "style.css": (PAGE / "style.css").read_text(),
            **{f"loops/{loop['id']}.svg": draw.loop_figure(cld, loop) for loop in cld["loops"]},
        }
        # Kumu shows regions.svg stretched to the frame: with a viewBox alone a browser sizes it 250 by
        # 150 pixels, which Kumu blurred (draw.regions_svg())
        if not re.match(r'<svg [^>]*\bwidth="\d+" height="\d+"', files["regions.svg"]):
            sys.exit("docs/regions.svg needs a width and a height besides its viewBox: draw.regions_svg() writes them")
        outputs.update({at(name): text for name, text in files.items()})
        # a figure whose loop is gone or renamed would stay published
        loops_dir = v["docs"] / "loops"
        extra += sorted(at(f"loops/{f.name}") for f in loops_dir.glob("*") if f"loops/{f.name}" not in files) \
            if loops_dir.is_dir() else []
        reports.append((v, cld, warnings))

    if args.check:
        stale = [name for name, text in outputs.items()
                 if not (DOCS / name).exists() or (DOCS / name).read_text() != text]
        if stale or extra:
            sys.exit(f"docs/ is out of date ({', '.join(stale + extra)}): run build.py and commit docs/")
        return

    for v in built:
        (v["docs"] / "loops").mkdir(parents=True, exist_ok=True)
    for name in extra:
        (DOCS / name).unlink()
    for name, text in outputs.items():
        (DOCS / name).write_text(text)

    for v, cld, warnings in reports:
        if len(built) > 1:
            print(f"version {v['name']} ({v['file']}):")
        loops = cycles(cld)
        n_el, n_conn = len(cld["elements"]), len(cld["connections"])
        print(f"{n_el} elements, {n_conn} connections, {len(cld['loops'])} named loops")
        hypotheses = sum(bool(c.get("hypothesis")) for c in cld["connections"])
        sourced = sum(bool(c["sources"]) for c in cld["connections"])
        print(f"sourced: {sum(bool(e['sources']) for e in cld['elements'])}/{n_el} elements, "
              f"{sourced}/{n_conn} connections; {hypotheses} connections are hypotheses, "
              f"{n_conn - sourced - hypotheses} have neither")
        print(f"feedback loops in the diagram: {len(loops)} "
              f"({sum(k == 'R' for k, _ in loops)} R, {sum(k == 'B' for k, _ in loops)} B), "
              f"shortest {min((len(p) for _, p in loops), default=0)} links")
        if warnings:
            print("warnings:\n  " + "\n  ".join(warnings))
    # a reference is shared by the versions, so it is cited nowhere only when no version cites it
    cited = {k for v in built for item in v["cld"]["elements"] + v["cld"]["connections"] for k in item.get("sources", [])}
    uncited = [f"reference {k!r} is cited nowhere" for k in refs if k not in cited]
    if uncited:
        print("warnings:\n  " + "\n  ".join(uncited))


if __name__ == "__main__":
    main()
