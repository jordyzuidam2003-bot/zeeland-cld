"""Check the CLD and build docs/, the files GitHub Pages serves.

    python3 build.py                  # check, write docs/, print the report
    python3 build.py --check          # fail if docs/ is out of date (the pre-commit hook runs this)
    python3 build.py --layout FILE    # write the positions and curvatures of FILE (layout.json,
                                      # downloaded from the page's drag mode) into cld.json, then build

Sources, edited by hand: cld.json (elements, connections, named loops, layout and
link curvature), actors.json (the Actor Map's actors, their relations and places, the one list the
CLD's actor fields name), references.json (sources), model-texts.md (the model texts each page shows),
view.scss and actors-view.scss (the Kumu views inside project.json and actors-project.json) and
page/ (index.html, a template with the placeholders <!-- SVG -->, <!-- FACTS -->, <!-- TEXTS --> and
<!-- DATA -->; actors.html, the Actor Map's, with <!-- QUESTION -->, <!-- SVG --> and <!-- DATA -->;
app.js; actors.js; style.css). draw.py draws the CLD, actormap.py the Actor Map and its table,
xlsx.py writes the table's file. Never edit docs/, which this script writes:

    docs/index.html    the page: the template with the drawing inline, the model texts (their
                       numbers counted in the model) and the data as JSON
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
    docs/actors.html   the Actor Map's page: the network inline, a panel per actor and relation
    docs/actors.js     copied from page/
    docs/actors.svg    the Actor Map's network on its own, the picture for the report
    docs/actors-bands.svg  its level bands alone, the background image of its Kumu map
    docs/actors-project.json  the Actor Map as a full Kumu project export, restored as project.json is
    docs/actors.xlsx   the actors' table, which Jordy imports into Google Drive as a Google Sheet:
                       the Actors, Relations, References and Columns sheets (actormap.sheets())
"""

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import actormap
import draw
import xlsx

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
PAGE = ROOT / "page"
TEXTS = ROOT / "model-texts.md"
CLD = ROOT / "cld.json"
ACTORS = ROOT / "actors.json"
PAGES_URL = "https://jordyzuidam2003-bot.github.io/zeeland-cld/"

ELEMENT_TYPES = ["Constant", "Auxiliary", "Stock"]
SUBQUESTIONS = ["SQ1", "SQ2", "SQ3"]
SETS_LETTER = {"Social": "S", "Ecological": "E", "Technological": "T"}
CONSTANT_REACH = 300  # the most a Constant's box keeps from a box it drives: about one box's width

# An actor's columns take a value from these lists, the Actor Map's own: they start from the
# values the group's old Actor Table used, which bind nothing (Jordy: the old table gave the
# columns only); a relation's kind is one a source names. A new value joins its list once Jordy
# agrees to it.
ACTOR_SCALES = ["inside", "outside"]  # by the CLD's boundary test (model-texts.md, System boundary)
ACTOR_TYPES = ["Business in the food chain", "Citizens & consumers", "Government", "Farmers' organisation",
               "Water management", "Knowledge institution", "Nature organisation", "Financial institution",
               "Consultancy"]
ACTOR_LEVELS = ["Global", "International", "National", "Local / Provincial / Regional"]
ACTOR_SECTORS = ["Aquaculture", "Arable Farming", "Export/distribution", "External stakeholder",
                 "Farmers organisation", "Finance", "Food processing", "Fruit Cultivation", "Government",
                 "Greenhouse Horticulture", "Knowledge institution", "Livestock Farming", "Nature preservation",
                 "Onion Cultivation & Processing", "Water management"]
RELATION_KINDS = ["authority over", "finances", "buys from", "advises", "represents", "works with"]
# references.json is CSL JSON, as Zotero imports it, and apa() writes each APA line from it, so
# the page, the table and Zotero's copy hold one record; a type joins once apa() writes it
REF_TYPES = ["article-journal", "article-newspaper", "dataset", "legislation", "report", "webpage"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
# the fields build.py lists while empty: a field no source carries stays empty, never a guess
ACTOR_FIELDS = ["label", "scale", "type", "level", "sector", "interest", "influence", "affected",
                "influence score", "relations", "sources"]


def apa(r):
    """The APA 7 reference of one CSL JSON item, as plain text. A Dutch law is cited by the version
    in force on its `issued` date, which APA's rules for laws (written for US law) do not cover.
    `year-suffix` holds a letter a description cites (1953a); the reference list in Zotero letters
    its own."""
    def sentence(text):
        return text if text.endswith((".", "?", "!")) else text + "."

    url = f"https://doi.org/{r['DOI']}" if r.get("DOI") else r["URL"]
    if r["type"] == "legislation":
        y, m, d = r["issued"]["date-parts"][0]
        return f"{r['title']} (version in force from {d} {MONTHS[m - 1]} {y}). {url}"
    names = [a.get("literal") or f"{a['family']}, {a['given']}" for a in r["author"]]
    parts = [sentence(names[0] if len(names) == 1 else ", ".join(names[:-1]) + ", & " + names[-1])]
    if "issued" in r:
        y, *md = r["issued"]["date-parts"][0]
        when = f"{y}{r.get('year-suffix', '')}" + (f", {MONTHS[md[0] - 1]}" if md else "") + (f" {md[1]}" if len(md) > 1 else "")
    else:
        when = "n.d." + (f"-{r['year-suffix']}" if r.get("year-suffix") else "")
    parts.append(f"({when}).")
    # a number and the series it belongs to in parentheses after the title; a genre with no
    # number is a description, in brackets
    numbered = " ".join(x for x in (r.get("genre") if r.get("number") else None, r.get("number")) if x)
    series = " ".join(x for x in (r.get("collection-title"), r.get("collection-number")) if x)
    paren = ", ".join(x for x in (numbered, series, r.get("version")) if x)
    title = r["title"] + (f" ({paren})" if paren else "") + (f" [{r['genre']}]" if r.get("genre") and not r.get("number") else "")
    parts.append(sentence(title + (" [Data set]" if r["type"] == "dataset" else "")))
    if r["type"] == "article-journal":
        parts.append(sentence(f"{r['container-title']}, {r['volume']}" + (f"({r['issue']})" if r.get("issue") else "") + f", {r['page']}"))
    elif r.get("container-title"):
        parts.append(sentence(r["container-title"]))
    if r.get("publisher"):
        parts.append(sentence(r["publisher"]))
    if r.get("accessed"):
        y, m, d = r["accessed"]["date-parts"][0]
        url = f"Retrieved {MONTHS[m - 1]} {d}, {y}, from {url}"
    return " ".join(parts + [url])


def references():
    """{id: APA line} from references.json, and its errors."""
    items, refs, errors = json.loads((ROOT / "references.json").read_text()), {}, []
    for r in items:
        name = f"references.json: {r.get('id')!r}"
        if not r.get("id") or r["id"] in refs:
            errors.append(f"{name}: an item needs an id no other item has")
        elif r.get("type") not in REF_TYPES:
            errors.append(f"{name}: type must be one of {', '.join(REF_TYPES)}")
        else:
            try:
                refs[r["id"]] = apa(r)
            except (KeyError, IndexError, TypeError, ValueError) as e:
                errors.append(f"{name}: a field its APA line needs is missing or malformed ({type(e).__name__}: {e})")
    return refs, errors


def check_actors(actors, refs):
    """Return (errors, empty): errors stop the build; empty is each actor's fields still empty."""
    errors, empty = [], {}
    ids = [a.get("id") for a in actors["actors"]]
    errors += [f"actors.json: duplicate actor id {i}" for i in set(ids) if ids.count(i) > 1]
    labels = [a.get("label") for a in actors["actors"]]
    errors += [f"actors.json: duplicate label {l!r}" for l in set(labels) if labels.count(l) > 1]
    for k in ("names", "partner", "working title"):
        if k not in actors.get("header", {}):
            errors.append(f"actors.json: the header has no {k!r}")
    for a in actors["actors"]:
        name = f"actors.json: {a.get('id', '?')}"
        # empty is allowed: the content is filled from sources, and listed until then
        for key, allowed in [("scale", ACTOR_SCALES), ("type", ACTOR_TYPES), ("level", ACTOR_LEVELS),
                             ("sector", ACTOR_SECTORS), ("client", ["yes", "no"])]:
            if a.get(key) not in allowed + [""]:
                errors.append(f"{name}: {key} {a.get(key)!r} not in {allowed}")
        if not all(isinstance(a.get(k), (int, float)) for k in ("x", "y")):
            errors.append(f"{name}: x and y must be numbers, its place on the Actor Map")
        if a.get("level") not in actormap.LEVELS:  # the Actor Map draws a band per level
            errors.append(f"{name}: level {a.get('level')!r} has no band on the Actor Map: {actormap.LEVELS}")
        if a.get("influence score") not in [1, 2, 3, 4, 5, None]:
            errors.append(f"{name}: influence score {a.get('influence score')!r} must be 1 (little) to 5, or null")
        for r in a.get("relations", []):
            if r.get("to") not in ids or r.get("to") == a.get("id"):
                errors.append(f"{name}: a relation to {r.get('to')!r}, which is not another actor in actors.json")
            if r.get("kind") not in RELATION_KINDS:
                errors.append(f"{name}: relation kind {r.get('kind')!r} not in {RELATION_KINDS}")
            if not isinstance(r.get("curvature"), (int, float)):
                errors.append(f"{name}: the relation to {r.get('to')!r} needs a curvature, a number (0 is straight)")
        for key in a.get("sources", []) + [k for r in a.get("relations", []) for k in r.get("sources", [])]:
            if key not in refs:
                errors.append(f"{name}: source {key!r} is not in references.json")
        missing = [k for k in ACTOR_FIELDS if a.get(k) in ("", None, [])]
        if missing:
            empty[a.get("id", "?")] = missing
    return errors, empty


def decisions(cld, actors):
    """Per actor id, the CLD variables it decides: derived from the elements' actor fields, never typed."""
    out = {a["id"]: [] for a in actors["actors"]}
    for e in cld["elements"]:
        if "actor" in e and e["actor"] in out:
            out[e["actor"]].append(e["id"])
    return out


def check(cld, refs, actors):
    """Return (errors, warnings). Errors stop the build; warnings are model smells."""
    errors, warnings = [], []
    actor_ids = {a["id"] for a in actors["actors"]}
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
        # a decision variable names the one actor that decides it, by its id in actors.json
        if "actor" in e and e["actor"] not in actor_ids:
            errors.append(f"{name}: actor {e['actor']!r} is not an actor id in actors.json")
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
        # written only where an element or link folds or idealizes something, so never empty
        if "simplification" in item and not (isinstance(item["simplification"], str) and item["simplification"].strip()):
            errors.append(f"{item.get('id') or item.get('from', '?') + ' -> ' + item.get('to', '?')}: "
                          "simplification must be a text; leave the field out where nothing is simplified")

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
        # ... and it sits beside what it drives (Jordy's decision), so its link reads as its own.
        bxs = draw.boxes(cld)
        for c in cld["connections"]:
            if c["from"] in constant:
                a, b = bxs[c["from"]], bxs[c["to"]]
                gap = math.hypot(max(a[0] - b[2], b[0] - a[2], 0), max(a[1] - b[3], b[1] - a[3], 0))
                if gap > CONSTANT_REACH:
                    warnings.append(f"{c['from']} -> {c['to']}: a Constant {gap:.0f} from what it drives, "
                                    f"more than {CONSTANT_REACH}")
        # Every other link has some bend (Jordy), so a reader can follow it; under 0.03 reads as
        # straight, the bend page/app.js keeps a dragged link from going below.
        warnings += [f"{c['from']} -> {c['to']}: not a Constant's link, yet straight (curvature {c['curvature']})"
                     for c in cld["connections"] if c["from"] not in constant and abs(c["curvature"]) < 0.03]
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


def blueprint(cld, refs, actors):
    els = {e["id"]: e for e in cld["elements"]}
    actor_label = {a["id"]: a["label"] for a in actors["actors"]}

    def sourced(item):
        return {"sources": "\n".join(refs[k] for k in item["sources"]),
                "sourced": "yes" if item["sources"] else "no"}

    elements = []
    for e in cld["elements"]:
        item = {k: v for k, v in e.items() if k != "sources"}
        item["adaptive practice"] = "yes" if e["adaptive practice"] else "no"
        if "actor" in e:  # the page and Kumu show the actor by its label
            item["actor"] = actor_label[e["actor"]]
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
            **({"simplification": c["simplification"]} if "simplification" in c else {}),
            **sourced(c),
        })
    return {"elements": elements, "connections": connections}


def page_data(cld, refs, actors, version):
    """What the page shows per element and link: the blueprint without the drawing's numbers."""
    bp = blueprint(cld, refs, actors)
    drop = {"x", "y", "curvature"}
    return {
        "elements": [{k: v for k, v in e.items() if k not in drop} for e in bp["elements"]],
        "connections": [{k: v for k, v in c.items() if k not in drop} for c in bp["connections"]],
        "loops": cld["loops"],
        "version": version,
    }


def core(cld):
    """The largest set of elements that each reach every other along the links (the model's
    feedback core), as a set of ids."""
    out, back = {e["id"]: set() for e in cld["elements"]}, {e["id"]: set() for e in cld["elements"]}
    for c in cld["connections"]:
        out[c["from"]].add(c["to"])
        back[c["to"]].add(c["from"])

    def reach(start, step):
        seen, todo = {start}, [start]
        while todo:
            for nxt in step[todo.pop()] - seen:
                seen.add(nxt)
                todo.append(nxt)
        return seen
    return max((reach(i, out) & reach(i, back) for i in out), key=len)


def counts(cld, loops):
    """The numbers model-texts.md names in braces, counted in the model."""
    inner = core(cld)
    links = sum(c["from"] in inner and c["to"] in inner for c in cld["connections"])
    rest = [e for e in cld["elements"] if e["id"] not in inner]
    return {"elements": len(cld["elements"]), "links": len(cld["connections"]), "named loops": len(cld["loops"]),
            "sourced links": sum(bool(c["sources"]) for c in cld["connections"]),
            "hypotheses": sum(bool(c.get("hypothesis")) for c in cld["connections"]),
            "feedback loops": len(loops), "core elements": len(inner), "core links": links,
            "independent loops": links - len(inner) + 1, "other elements": len(rest),
            "other constants": sum(e["element type"] == "Constant" for e in rest)}


def inline(text):
    """A line of model-texts.md as HTML: **strong**, *em*, `code`, and bare URLs as links."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return re.sub(r"https?://[^\s<]+[^\s<.,;)]", lambda m: f'<a href="{m[0]}">{m[0]}</a>', text)


def model_texts(cld, loops):
    """(facts, texts): model-texts.md as HTML, its numbers counted in the model. The facts are
    the list before its first heading; the texts are its sections, each a ## heading with
    paragraphs or a - list. A <!-- comment --> is not shown."""
    text = re.sub(r"<!--.*?-->\n?", "", TEXTS.read_text(), flags=re.S)
    for name, n in counts(cld, loops).items():
        text = text.replace("{" + name + "}", f"{n:,}")
    if re.search(r"\{[a-z ]+\}", text):
        sys.exit(f"model-texts.md names a number build.py does not count: {re.search(r'{[a-z ]+}', text)[0]}")
    html = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.split("\n")
        if lines[0].startswith("## "):
            html.append(f"<h2>{inline(lines[0][3:])}</h2>")
        elif lines[0].startswith("- "):
            html.append("<ul>" + "".join(f"<li>{inline(l[2:])}</li>" for l in lines) + "</ul>")
        else:
            html.append(f"<p>{inline(' '.join(lines))}</p>")
    first = next(i for i, h in enumerate(html) if h.startswith("<h2>"))
    return "\n".join(html[:first]), "\n".join(html[first:])


def page(cld, refs, actors, version, loops):
    """docs/index.html: the template with the drawing inline, the model texts and the data as
    JSON."""
    template = (PAGE / "index.html").read_text()
    svg = draw.svg(cld)
    # "</" inside a <script> would end it early; "<\/" is the same string to JSON
    data = json.dumps(page_data(cld, refs, actors, version), ensure_ascii=False).replace("</", "<\\/")
    facts, texts = model_texts(cld, loops)
    for marker in ("<!-- SVG -->", "<!-- DATA -->", "<!-- FACTS -->", "<!-- TEXTS -->"):
        assert template.count(marker) == 1, f"page/index.html must hold {marker} once"
    return (template.replace("<!-- SVG -->", svg.rstrip()).replace("<!-- FACTS -->", facts)
            .replace("<!-- TEXTS -->", texts)
            .replace("<!-- DATA -->", f'<script type="application/json" id="data">{data}</script>'))


def project(cld, refs, actors, template, version):
    """A full Kumu project export, the shape of Kumu's own "Export JSON" of a project.

    The view is view.scss plus what is generated here: a showcase button per named loop, in
    view.scss's place for it, each SETS domain's tint from draw.TINT,
    and by Kumu system id each element's box size from draw.boxes(). Each label holds a double space where the page breaks its line,
    Kumu's manual line break, so its box fits it."""
    bp = blueprint(cld, refs, actors)
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
        text = k in ("description", "simplification", "sources")
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
    description = (f"Model version {version}, the first seven characters of the SHA-256 of cld.json. "
                   "A copy for milestones: the current model is the page "
                   f"{PAGES_URL}, built from "
                   "https://github.com/jordyzuidam2003-bot/zeeland-cld.")
    # a showcase button per named loop: its elements and links (Kumu's :loop selector, by the
    # loop's label), and the regions, which a showcase fades unless it selects them
    options = "\n\n".join(f'      option {{\n        label: "{label}";\n'
                          f'        selector: *:loop(["label"="{label}"]), #background;\n      }}'
                          for label in (f'{loop["id"]} {loop["name"]}' for loop in cld["loops"]))
    template = template.replace("      /* LOOP OPTIONS */", options)
    style = (template.rstrip() + "\n\n/* ---------- generated by build.py: tints, box sizes, the regions' size ---------- */\n"
             + "\n".join(rules) + "\n")
    # a restore sets the project's name, so it is the name of the project the group's URL names
    return {
        "version": 1, "name": "cbp-cld", "description": description, "proxyImages": True,
        "defaultMap": "map-cld", "defaultPerspective": None, "attributeRelevance": {},
        "attributes": attributes, "elements": elements, "connections": connections, "loops": loops,
        "maps": [{"_id": "map-cld", "name": f"CLD, model {version}", "description": "", "scale": 1,
                  "center": {"x": 0, "y": 0}, "defaultPerspective": "pers-cld",
                  "defaultElementBehavior": "fixed", "defaultConnectionDirection": "directed",
                  "elements": nodes, "connections": edges, "loops": map_loops}],
        # the map's edges carry the curves, so the view holds no curvature rules
        "perspectives": [{"_id": "pers-cld", "name": "CLD", "style": style}],
    }


def actors_project(actors, refs, decides, cld_labels, template, version):
    """The Actor Map as a full Kumu project export, the shape project() gives the CLD: each actor an
    element with its fields, each relation a connection whose type is its kind, the actors at their
    places, the relations with their curves, and the level bands as the background image (an
    element labelled background, as the CLD's regions). The view is actors-view.scss plus each
    kind's colour and dash from actormap.KIND and each box's size."""
    bxs, rels, _ = actormap.geometry(actors)
    _, (fx0, fy0, fx1, fy1) = actormap.bands_svg(actors)
    elements = [{"_id": f'elem-{a["id"]}', "attributes": {
        "label": "  ".join(bxs[a["id"]][4]), "type": a["type"], "level": a["level"], "sector": a["sector"],
        "interest": a["interest"], "influence": a["influence"], "affected": a["affected"],
        "influence score": a["influence score"], "client": a["client"],
        "decides in the CLD": "\n".join(cld_labels[e] for e in decides[a["id"]]),
        "sources": "\n".join(refs[k] for k in a["sources"])}} for a in actors["actors"]]
    elements.append({"_id": "elem-background", "attributes": {"label": "background"}})
    connections = [{"_id": f'conn-{r["n"]}', "direction": "directed", "delayed": False, "reversed": False,
                    "attributes": {"connection type": r["kind"], "description": r["description"],
                                   "sources": "\n".join(refs[k] for k in r["sources"])},
                    "from": f'elem-{r["from"]}', "to": f'elem-{r["to"]}'} for r in rels]
    values = {}
    for item in [e["attributes"] for e in elements] + [c["attributes"] for c in connections]:
        for k, v in item.items():
            values.setdefault(k, set()).add(v)
    builtin = {"type": "Element Type", "connection type": "Connection Type"}
    attributes = []
    for k, seen in values.items():
        text = k in ("interest", "influence", "affected", "description", "sources", "decides in the CLD")
        listed = not text and k != "label" and len(seen) <= 20
        attributes.append({"_id": "attr-" + k.replace(" ", "-"), "name": builtin.get(k, k[0].upper() + k[1:]),
                           "format": "text" if text else "string", "private": False, "limit": 1,
                           "category": "General", "prompt": "list" if listed else "autocomplete",
                           "locked": False, "values": sorted(seen, key=str) if listed else [],
                           "sort": False, "cluster": listed})
    nodes = [{"_id": f'node-{a["id"]}', "position": {"x": a["x"], "y": a["y"]}, "pinned": True, "style": {},
              "element": f'elem-{a["id"]}'} for a in actors["actors"]]
    nodes.append({"_id": "node-background", "position": {"x": round((fx0 + fx1) / 2), "y": round((fy0 + fy1) / 2)},
                  "pinned": True, "style": {}, "element": "elem-background"})
    edges = [{"_id": f'edge-{r["n"]}', "curvature": r["curvature"], "style": {}, "connection": f'conn-{r["n"]}'}
             for r in rels]
    rules = ([f'["connection type"="{k}"] {{ color: {c}; style: {"dashed" if d else "solid"}; }}'
              for k, (c, d) in actormap.KIND.items()]
             + [f'#elem-{i} {{ width: {round(b[2] - b[0])}; height: {round(b[3] - b[1])}; }}' for i, b in bxs.items()]
             + [f'#background {{ width: {round(fx1 - fx0)}; height: {round(fy1 - fy0)}; }}'])
    style = (template.rstrip() + "\n\n/* ---------- generated by build.py: the kinds' look, box sizes, the bands' size ---------- */\n"
             + "\n".join(rules) + "\n")
    description = (f"Actor Map version {version}, the first seven characters of the SHA-256 of actors.json. "
                   "A copy for milestones: the current Actor Map is the page "
                   f"{PAGES_URL}actors.html, built from https://github.com/jordyzuidam2003-bot/zeeland-cld.")
    return {
        "version": 1, "name": "cbp-actors", "description": description, "proxyImages": True,
        "defaultMap": "map-actors", "defaultPerspective": None, "attributeRelevance": {},
        "attributes": attributes, "elements": elements, "connections": connections, "loops": [],
        "maps": [{"_id": "map-actors", "name": f"Actor Map, version {version}", "description": "", "scale": 1,
                  "center": {"x": 0, "y": 0}, "defaultPerspective": "pers-actors",
                  "defaultElementBehavior": "fixed", "defaultConnectionDirection": "directed",
                  "elements": nodes, "connections": edges, "loops": []}],
        "perspectives": [{"_id": "pers-actors", "name": "Actor Map", "style": style}],
    }


def apply_layout(path):
    """Write the positions and curvatures of a layout.json ({id: {x, y}, "curvature": {"from->to": k}},
    from the page's drag mode) into cld.json, in its own formatting; a file without "curvature"
    moves the elements only."""
    layout = json.loads(path.read_text())
    curvature = layout.pop("curvature", {})
    cld = json.loads(CLD.read_text())
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
    CLD.write_text(json.dumps(cld, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if docs/ is out of date")
    parser.add_argument("--layout", metavar="FILE", help="write the x, y and curvatures of FILE (layout.json from the page) into cld.json, then build")
    args = parser.parse_args()

    if args.layout:
        apply_layout(Path(args.layout))
    cld = json.loads(CLD.read_text())
    refs, ref_errors = references()
    actors = json.loads(ACTORS.read_text())
    template = (ROOT / "view.scss").read_text()
    actor_errors, empty = check_actors(actors, refs)
    errors, warnings = check(cld, refs, actors)
    if errors or actor_errors or ref_errors:
        sys.exit("cld.json, actors.json or references.json has errors:\n  " + "\n  ".join(ref_errors + actor_errors + errors))

    # the model version teammates compare: the first seven characters of cld.json's SHA-256
    version = hashlib.sha256(CLD.read_bytes()).hexdigest()[:7]
    loops = cycles(cld)  # the page's texts count them, and the report
    actors_version = hashlib.sha256(ACTORS.read_bytes()).hexdigest()[:7]
    decides = decisions(cld, actors)
    cld_labels = {e["id"]: e["label"] for e in cld["elements"]}
    outputs = {
        "project.json": json.dumps(project(cld, refs, actors, template, version), indent=2, ensure_ascii=False) + "\n",
        "actors.html": actormap.page(actors, refs, decides, cld_labels, actors_version, (PAGE / "actors.html").read_text()),
        "actors.js": (PAGE / "actors.js").read_text(),
        "actors.svg": actormap.svg(actors),
        "actors-bands.svg": actormap.bands_svg(actors)[0],
        "actors-project.json": json.dumps(actors_project(actors, refs, decides, cld_labels,
                                                         (ROOT / "actors-view.scss").read_text(), actors_version),
                                          indent=2, ensure_ascii=False) + "\n",
        "actors.xlsx": xlsx.workbook(actormap.sheets(actors, refs, decides, cld_labels)),
        "cld.svg": draw.svg(cld),
        "regions.svg": draw.regions_svg(cld)[0],
        "index.html": page(cld, refs, actors, version, loops),
        "app.js": (PAGE / "app.js").read_text(),
        "style.css": (PAGE / "style.css").read_text(),
        **{f"loops/{loop['id']}.svg": draw.loop_figure(cld, loop) for loop in cld["loops"]},
    }
    # Kumu shows regions.svg stretched to the frame: with a viewBox alone a browser sizes it 250 by
    # 150 pixels, which Kumu blurred (draw.regions_svg())
    if not re.match(r'<svg [^>]*\bwidth="\d+" height="\d+"', outputs["regions.svg"]):
        sys.exit("docs/regions.svg needs a width and a height besides its viewBox: draw.regions_svg() writes them")
    # a figure whose loop is gone or renamed would stay published
    extra = sorted(f"loops/{f.name}" for f in (DOCS / "loops").glob("*") if f"loops/{f.name}" not in outputs) \
        if (DOCS / "loops").is_dir() else []

    if args.check:
        # the table is bytes, every other file text
        stale = [name for name, out in outputs.items() if not (DOCS / name).exists()
                 or ((DOCS / name).read_bytes() if isinstance(out, bytes) else (DOCS / name).read_text()) != out]
        if stale or extra:
            sys.exit(f"docs/ is out of date ({', '.join(stale + extra)}): run build.py and commit docs/")
        return

    (DOCS / "loops").mkdir(parents=True, exist_ok=True)
    for name in extra:
        (DOCS / name).unlink()
    for name, out in outputs.items():
        (DOCS / name).write_bytes(out) if isinstance(out, bytes) else (DOCS / name).write_text(out)

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
    # the layout's measure: the eye found crossings and links over boxes that no warning named
    crossings, through = draw.tangles(cld)
    print(f"layout: {len(crossings)} crossings between links, "
          f"{len(through)} links through a box they do not connect")
    warnings += [f"link through a box: {a} -> {b} passes through {e}" for (a, b), e in through]
    a_crossings, a_through = actormap.tangles(actors)
    print(f"actor map: {len(a_crossings)} crossings between relations, "
          f"{len(a_through)} relations through a box they do not connect")
    rel = actormap.relations(actors)
    warnings += [f"actor map: relation through a box: {rel[n]['from']} {rel[n]['kind']} {rel[n]['to']} passes through {e}"
                 for n, e in a_through] + actormap.overlaps(actors)
    print(f"actors: {len(actors['actors'])} ({sum(a['scale'] == 'inside' for a in actors['actors'])} inside the scale); "
          "CLD variables each decides: " + ", ".join(f"{i} {len(v)}" for i, v in decides.items() if v))
    if empty:
        print("actor fields still empty:\n  " + "\n  ".join(f"{i}: {', '.join(ks)}" for i, ks in empty.items()))
    cited = {k for item in cld["elements"] + cld["connections"] + actors["actors"] for k in item.get("sources", [])}
    cited |= {k for a in actors["actors"] for r in a.get("relations", []) for k in r.get("sources", [])}
    warnings += [f"reference {k!r} is cited nowhere" for k in refs if k not in cited]
    # a section the page would show with nothing under its heading
    warnings += [f"model-texts.md: the section {h!r} is still empty" for h, body in
                 re.findall(r"^## (.+)\n((?:(?!## ).*\n?)*)", re.sub(r"<!--.*?-->", "", TEXTS.read_text(), flags=re.S), re.M)
                 if not body.strip()]
    if warnings:
        print("warnings:\n  " + "\n  ".join(warnings))


if __name__ == "__main__":
    main()
