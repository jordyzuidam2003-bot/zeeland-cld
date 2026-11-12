"""Check the CLD and build docs/, the files GitHub Pages serves.

    python3 build.py                  # check, write docs/, print the report
    python3 build.py --check          # fail if docs/ is out of date (the pre-commit hook runs this)
    python3 build.py --layout FILE    # write the positions and curvatures of FILE (layout.json,
                                      # downloaded from a page's Move mode) into cld.json, or the
                                      # Actor Map's into actor-map.json, then build

Sources, edited by hand: in model/, cld.json (elements, connections, named loops, layout and
link curvature), actor-map.json (the Actor Map's actors, their relations and places, the one list
the CLD's actor fields name), references.json (sources) and cld-texts.md (the model texts each page
shows); in src/, kumu/cld-view.scss and kumu/actor-map-view.scss (the Kumu views inside the export
in docs/kumu/) and templates/ (index.html, a template with the placeholders <!-- SVG -->,
<!-- FACTS -->, <!-- TEXTS --> and <!-- DATA -->; actors.html, the Actor Map's, with <!-- QUESTION -->,
<!-- SVG --> and <!-- DATA -->; app.js; actors.js; map.js; move.js; style.css). src/draw_cld.py draws the CLD,
src/draw_actor_map.py the Actor Map and its table, src/write_xlsx.py writes the table's file. Never
edit docs/, which this script writes:

    docs/index.html    the page: the template with the drawing inline, the model texts (their
                       numbers counted in the model) and the data as JSON
    docs/actors.html   the Actor Map's page: the network inline, a panel per actor and relation
    docs/assets/       app.js, actors.js, map.js (moving and zooming, the bar and the menu, for
                       both pages), move.js (Move mode, for both pages) and style.css, copied
                       from src/templates/
    docs/figures/cld.svg  the drawing on its own, the picture for the report
    docs/figures/named-loops/<id>.svg  each named loop on its own (draw_cld.loop_figure()), its
                       figure for the report; the page's panel for the loop shows it
    docs/figures/combined-loops/<id>.svg  each group of named loops, its loops joined at their
                       shared variables (draw_cld.group_figure())
    docs/figures/actor-map.svg  the Actor Map's network on its own, the picture for the report
    docs/tables/cld-table.xlsx  the table that explains the CLD (table_sheets()), which Jordy
                       imports into Google Drive as a Google Sheet: the Elements, Links, Named
                       loops, Combined loops (once cld.json holds groups) and References sheets;
                       linked from the page
    docs/tables/actor-map-table.xlsx  the actors' table, which Jordy imports into Google Drive as a
                       Google Sheet: the Actors, Relations, References and Columns sheets
                       (draw_actor_map.sheets()); linked from the Actor Map's page
    docs/tables/sources-to-ask.xlsx  the sources to ask the actors (ask_sheets()), a row per
                       `ask actors` entry in cld.json and actor-map.json; linked from the page
                       beside the table, until its final version goes to the group's Drive
    docs/kumu/kumu-project.json  the Kumu project, a full project export (kumu_project()): restored
                       once into a brand-new Kumu project (New Project > the next screen > restore
                       backup), it holds the full CLD, the Actor Map and a map per combined loop and
                       per named loop, each drawn as its figure, with no showcase; each map with
                       its view, the CLD's regions and the Actor Map's level bands as background
                       images inside the file (an element labelled background showing a data URL
                       of the SVG); no version, so the link to each map stays the same from one
                       copy to the next
"""

import argparse
import base64
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# the modules build.py uses live in src/, beside the templates and the Kumu views
sys.path.insert(0, str(ROOT / "src"))

import draw_actor_map  # noqa: E402
import draw_cld  # noqa: E402
import write_xlsx  # noqa: E402

DOCS = ROOT / "docs"
MODEL = ROOT / "model"
TEMPLATES = ROOT / "src" / "templates"
KUMU = ROOT / "src" / "kumu"
TEXTS = MODEL / "cld-texts.md"
CLD = MODEL / "cld.json"
ACTORS = MODEL / "actor-map.json"
REFERENCES = MODEL / "references.json"

ELEMENT_TYPES = ["Constant", "Auxiliary", "Stock"]
SUBQUESTIONS = ["SQ1", "SQ2", "SQ3"]
SETS_LETTER = {"Social": "S", "Ecological": "E", "Technological": "T"}
CONSTANT_REACH = 400  # the most a Constant's box keeps from a box it drives: about one box's width and a bit

# An actor's columns take a value from these lists, the Actor Map's own: they start from the
# values the group's old Actor Table used, which bind nothing (Jordy: the old table gave the
# columns only); a relation's kind is one a source names. A new value joins its list once Jordy
# agrees to it.
ACTOR_SCALES = ["inside", "outside"]  # by the CLD's boundary test (cld-texts.md, System boundary)
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
REF_TYPES = ["article-journal", "article-newspaper", "chapter", "dataset", "legislation", "report", "webpage"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
# the fields build.py lists while empty: a field no source carries stays empty, never a guess
ACTOR_FIELDS = ["label", "scale", "type", "level", "sector", "interest", "influence", "affected",
                "influence score", "relations", "sources"]
# the partners who can put the group in touch with an actor that may hold a missing fact: DCC, and
# the Living Lab Schouwen-Duiveland (ChallengeBasedProject1/.claude/rules/cld-model.md); an entry
# lists each one to start asking through, as one contact leads to the next (Jordy)
ASK_THROUGH = ["DCC", "Living Lab"]


def ask_errors(item, name, actor_ids):
    """The errors in an item's `ask actors`, a list of {actor, for, through}: the facts no public
    source read gives that an actor may know, `through` the partners to start asking through. Absent
    where nothing is asked, so never empty."""
    asks = item.get("ask actors")
    if asks is None:
        return []
    if not (isinstance(asks, list) and asks and all(isinstance(a, dict) for a in asks)):
        return [f"{name}: ask actors must be a list of {{actor, for, through}}; leave the field out where nothing is asked"]
    errors = []
    for a in asks:
        if a.get("actor") not in actor_ids:
            errors.append(f"{name}: ask actors names {a.get('actor')!r}, not an actor id in actor-map.json")
        if not (isinstance(a.get("for"), str) and a["for"].strip()):
            errors.append(f"{name}: ask actors {a.get('actor')!r} needs a for, what is missing in words")
        through = a.get("through")
        if not (isinstance(through, list) and through and len(set(through)) == len(through)
                and all(t in ASK_THROUGH for t in through)):
            errors.append(f"{name}: ask actors {a.get('actor')!r} through {through!r}, "
                          f"not a list of one or both of {ASK_THROUGH}")
    return errors


def through_text(through):
    """The partners of an entry as words, in ASK_THROUGH's order: "DCC or Living Lab"."""
    return " or ".join(t for t in ASK_THROUGH if t in through)


def ask_text(item, label):
    """An item's `ask actors` as one text, an entry per line, as the table and Kumu show it."""
    return "\n".join(f'{label[a["actor"]]}, through {through_text(a["through"])}: {a["for"]}'
                     for a in item.get("ask actors", []))


def apa(r):
    """The APA 7 reference of one CSL JSON item, as plain text. A Dutch law is cited by the version
    in force on its `issued` date, which APA's rules for laws (written for US law) do not cover.
    `year-suffix` holds a letter a description cites (1953a); the reference list in Zotero letters
    its own."""
    def sentence(text):
        return text if text.endswith((".", "?", "!")) else text + "."

    # an unpublished report a partner sent has no link of its own
    url = f"https://doi.org/{r['DOI']}" if r.get("DOI") else r.get("URL", "") if r["type"] == "report" else r["URL"]
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
    elif r["type"] == "chapter":
        eds = [f"{e['given']} {e['family']}" for e in r["editor"]]
        who = eds[0] if len(eds) == 1 else ", ".join(eds[:-1]) + ", & " + eds[-1]
        parts.append(sentence(f"In {who} ({'Ed.' if len(eds) == 1 else 'Eds.'}), {r['container-title']} (pp. {r['page']})"))
    elif r.get("container-title"):
        parts.append(sentence(r["container-title"]))
    if r.get("publisher"):
        parts.append(sentence(r["publisher"]))
    if r.get("accessed"):
        y, m, d = r["accessed"]["date-parts"][0]
        url = f"Retrieved {MONTHS[m - 1]} {d}, {y}, from {url}"
    return " ".join(parts + ([url] if url else []))


def references():
    """{id: APA line} from references.json, and its errors."""
    items, refs, errors = json.loads(REFERENCES.read_text()), {}, []
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
    errors += [f"actor-map.json: duplicate actor id {i}" for i in set(ids) if ids.count(i) > 1]
    labels = [a.get("label") for a in actors["actors"]]
    errors += [f"actor-map.json: duplicate label {l!r}" for l in set(labels) if labels.count(l) > 1]
    for k in ("names", "partner", "working title"):
        if k not in actors.get("header", {}):
            errors.append(f"actor-map.json: the header has no {k!r}")
    for a in actors["actors"]:
        name = f"actor-map.json: {a.get('id', '?')}"
        # empty is allowed: the content is filled from sources, and listed until then
        for key, allowed in [("scale", ACTOR_SCALES), ("type", ACTOR_TYPES), ("level", ACTOR_LEVELS),
                             ("sector", ACTOR_SECTORS), ("client", ["yes", "no"])]:
            if a.get(key) not in allowed + [""]:
                errors.append(f"{name}: {key} {a.get(key)!r} not in {allowed}")
        if not all(isinstance(a.get(k), (int, float)) for k in ("x", "y")):
            errors.append(f"{name}: x and y must be numbers, its place on the Actor Map")
        if a.get("level") not in draw_actor_map.LEVELS:  # the Actor Map draws a band per level
            errors.append(f"{name}: level {a.get('level')!r} has no band on the Actor Map: {draw_actor_map.LEVELS}")
        if a.get("influence score") not in [1, 2, 3, 4, 5, None]:
            errors.append(f"{name}: influence score {a.get('influence score')!r} must be 1 (little) to 5, or null")
        for r in a.get("relations", []):
            if r.get("to") not in ids or r.get("to") == a.get("id"):
                errors.append(f"{name}: a relation to {r.get('to')!r}, which is not another actor in actor-map.json")
            if r.get("kind") not in RELATION_KINDS:
                errors.append(f"{name}: relation kind {r.get('kind')!r} not in {RELATION_KINDS}")
            if not isinstance(r.get("curvature"), (int, float)):
                errors.append(f"{name}: the relation to {r.get('to')!r} needs a curvature, a number (0 is straight)")
        for key in a.get("sources", []) + [k for r in a.get("relations", []) for k in r.get("sources", [])]:
            if key not in refs:
                errors.append(f"{name}: source {key!r} is not in references.json")
        errors += ask_errors(a, name, set(ids))
        # `no relations`: the reason in words, from the actor's sources, that it holds none (README);
        # it fills `relations`, so the two never stand together
        if "no relations" in a:
            if not (isinstance(a["no relations"], str) and a["no relations"].strip()):
                errors.append(f"{name}: no relations must be the reason in words; leave the field out otherwise")
            if a.get("relations"):
                errors.append(f"{name}: no relations beside a relation; keep one of the two")
        missing = [k for k in ACTOR_FIELDS if a.get(k) in ("", None, [])
                   and not (k == "relations" and a.get("no relations"))]
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
    scale = {a["id"]: a["scale"] for a in actors["actors"]}
    els = {}
    for e in cld["elements"]:
        name = e.get("id", "?")
        if name in els:
            errors.append(f"duplicate element id {name}")
        els[name] = e
        for key, allowed in [("element type", ELEMENT_TYPES), ("sets domain", list(SETS_LETTER)),
                             ("subsystem", list(draw_cld.REGION)), ("subquestion", SUBQUESTIONS)]:
            if e.get(key) not in allowed:
                errors.append(f"{name}: {key} {e.get(key)!r} not in {allowed}")
        if not isinstance(e.get("adaptive practice"), bool):
            errors.append(f"{name}: adaptive practice must be true/false")
        if not all(isinstance(e.get(k), (int, float)) for k in ("x", "y")):
            errors.append(f"{name}: x and y must be numbers")
        # a decision variable names the one actor that decides it, by its id in actor-map.json
        if "actor" in e and e["actor"] not in actor_ids:
            errors.append(f"{name}: actor {e['actor']!r} is not an actor id in actor-map.json")
        # the actors outside the scale that shape it directly, each from a source; an actor inside
        # the scale is derived from the links (element_actors())
        if not isinstance(e.get("actors", []), list) or any(a not in actor_ids for a in e.get("actors", [])):
            errors.append(f"{name}: actors must be a list of actor ids in actor-map.json, got {e.get('actors')!r}")
        else:
            errors += [f"{name}: actors names {a}, inside the scale: an inside actor is derived from the links"
                       for a in e.get("actors", []) if scale[a] == "inside"]
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
        name = item.get("id") or item.get("from", "?") + " -> " + item.get("to", "?")
        for key in item.get("sources", []):
            if key not in refs:
                errors.append(f"source {key!r} is not in references.json")
        # written only where an element or link folds or idealizes something, so never empty
        if "simplification" in item and not (isinstance(item["simplification"], str) and item["simplification"].strip()):
            errors.append(f"{name}: simplification must be a text; leave the field out where nothing is simplified")
        errors += ask_errors(item, name, actor_ids)

    sign = {(c["from"], c["to"]): c["polarity"] for c in cld["connections"]}
    for loop in cld["loops"]:
        # each named loop says in words what it does; the page's panel and the table show it
        if not (isinstance(loop.get("description"), str) and loop["description"].strip()):
            errors.append(f"loop {loop['id']}: no description")
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

    # Every feedback loop holds a stock (Jordy's decision): an auxiliary is set at once by its
    # causes, so a loop of auxiliaries alone would need its own value to set itself. D2D stops on
    # such a loop, yet its own check sees only loops of up to five links (funcs/cld.py), and a longer
    # one leaves its auxiliaries at zero; so every loop is checked here, the named ones and the rest.
    if all(c["from"] in els and c["to"] in els for c in cld["connections"]):
        flows = {i for i, e in els.items() if e.get("element type") != "Stock"}
        rest = {"elements": [e for e in cld["elements"] if e.get("id") in flows],
                "connections": [c for c in cld["connections"] if c["from"] in flows and c["to"] in flows]}
        errors += [f"a feedback loop with no stock: {' -> '.join(path)}" for _, path in cycles(rest)]

    # A description names a loop by its id, which goes stale unseen once that loop leaves the named loops.
    loop_ids = {loop["id"] for loop in cld["loops"]}
    paths = {loop["id"]: set(loop["path"]) for loop in cld["loops"]}
    group_ids = [g.get("id") for g in cld.get("groups", [])]
    errors += [f"group id {i} appears twice" for i in sorted({i for i in group_ids if group_ids.count(i) > 1}, key=str)]
    for group in cld.get("groups", []):
        # a group's button, figure and table row read these; a loop gone from the named loops would stay in them unseen
        name = group.get("id", "?")
        if not re.fullmatch(r"C\d+", str(group.get("id"))):
            errors.append(f"group {name}: its id must be C and a number")
        for field in ("name", "description"):
            if not (isinstance(group.get(field), str) and group[field].strip()):
                errors.append(f"group {name}: no {field}")
        errors += [f"group {name}: source {k!r} is not in references.json" for k in group.get("sources", []) if k not in refs]
        members = group.get("loops", [])
        unknown = [m for m in members if m not in loop_ids]
        if unknown:
            errors.append(f"group {name}: {', '.join(unknown)} not a named loop")
        elif len(set(members)) < 2:
            errors.append(f"group {name}: needs at least two different loops")
        else:
            # a group is its loops joined at their shared variables, so none stands apart
            joined, rest = paths[members[0]], [paths[m] for m in members[1:]]
            while rest and any(joined & p for p in rest):
                joined = joined.union(*(p for p in rest if joined & p))
                rest = [p for p in rest if not joined & p]
            if rest:
                errors.append(f"group {name}: its loops share no variable with the others")
            # its figure's places are its own, so a loop changed on its path leaves one out or one over
            want = {"places": set().union(*(paths[m] for m in members)), "marks": set(members),
                    "bends": {f"{a} -> {b}" for a, b in draw_cld.group_links(cld, group)}}
            for field, keys in want.items():
                have = set(group.get(field, {}))
                if have != keys:
                    errors.append(f"group {name}: {field} must hold exactly its loops' own: "
                                  f"missing {sorted(keys - have)}, not on them {sorted(have - keys)}")
    for item in cld["elements"] + cld["connections"] + cld["loops"] + cld.get("groups", []):
        gone =sorted(set(re.findall(r"\b[RB]\d+\b", str(item.get("description", "")))) - loop_ids)
        if gone:
            errors.append(f"{item.get('id') or item.get('from', '?') + ' -> ' + item.get('to', '?')}: "
                          f"its description names {', '.join(gone)}, not a named loop")

    for c in cld["connections"]:
        if "delay at" in c and not (c["delay"] and 0 < c["delay at"] < 1):
            errors.append(f"{c['from']} -> {c['to']}: delay at needs a delayed link and a value between 0 and 1")

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
        bxs = draw_cld.boxes(cld)
        for c in cld["connections"]:
            if c["from"] in constant:
                a, b = bxs[c["from"]], bxs[c["to"]]
                gap = math.hypot(max(a[0] - b[2], b[0] - a[2], 0), max(a[1] - b[3], b[1] - a[3], 0))
                if gap > CONSTANT_REACH:
                    warnings.append(f"{c['from']} -> {c['to']}: a Constant {gap:.0f} from what it drives, "
                                    f"more than {CONSTANT_REACH}")
        # Every other link has some bend (Jordy), so a reader can follow it; under 0.03 reads as
        # straight, the bend src/templates/app.js keeps a dragged link from going below.
        warnings += [f"{c['from']} -> {c['to']}: not a Constant's link, yet straight (curvature {c['curvature']})"
                     for c in cld["connections"] if c["from"] not in constant and abs(c["curvature"]) < 0.03]
        # A delay is a claim about duration, so its description names one (a number: years, m per decade).
        warnings += [f"{c['from']} -> {c['to']}: a delay, yet its description gives no duration"
                     for c in cld["connections"] if c["delay"] and not any(ch.isdigit() for ch in c["description"])]
        for group in cld.get("groups", []):
            crossings, through = draw_cld.tangles(draw_cld.group_cld(cld, group))
            if crossings or through:
                warnings.append(f"group {group['id']}: its figure has {len(crossings)} crossings and {len(through)} links through a box")
        # The CLD describes mechanisms and is shaped for no lever set, so no element, link or loop names one.
        warnings += [f"{item.get('id') or item['from'] + ' -> ' + item['to']}: names a policy lever"
                     for item in cld["elements"] + cld["connections"] + cld["loops"] + cld.get("groups", [])
                     if re.search(r"\b(levers?|buy-?outs?|land bank)\b", item["description"], re.I)]
        warnings += draw_cld.overlaps(cld)
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

    shaped = element_actors(cld, actors)
    elements = []
    for e in cld["elements"]:
        item = {k: v for k, v in e.items() if k != "sources"}
        item["adaptive practice"] = "yes" if e["adaptive practice"] else "no"
        if "actor" in e:  # the page and Kumu show the actor by its label
            item["actor"] = actor_label[e["actor"]]
        # ... and the actors that decide or shape it, as one text, which a Kumu field holds
        item["actors"] = ", ".join(actor_label[a] for a in shaped[e["id"]])
        if "ask actors" in e:  # the facts an actor may hold, one text, as the actors
            item["ask actors"] = ask_text(e, actor_label)
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
            **({"ask actors": ask_text(c, actor_label)} if "ask actors" in c else {}),
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
        # the figure's numbers stay out, as the drawing's do
        "groups": [{k: g[k] for k in ("id", "name", "loops", "description")} for g in cld.get("groups", [])],
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
    """The numbers cld-texts.md names in braces, counted in the model."""
    inner = core(cld)
    links = sum(c["from"] in inner and c["to"] in inner for c in cld["connections"])
    rest = [e for e in cld["elements"] if e["id"] not in inner]
    return {"elements": len(cld["elements"]), "links": len(cld["connections"]), "named loops": len(cld["loops"]),
            "combined loops": len(cld.get("groups", [])),
            "sourced links": sum(bool(c["sources"]) for c in cld["connections"]),
            "hypotheses": sum(bool(c.get("hypothesis")) for c in cld["connections"]),
            "feedback loops": len(loops), "core elements": len(inner), "core links": links,
            "independent loops": links - len(inner) + 1, "other elements": len(rest),
            "other constants": sum(e["element type"] == "Constant" for e in rest)}


def inline(text):
    """A line of cld-texts.md as HTML: **strong**, *em*, `code`, and bare URLs as links."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return re.sub(r"https?://[^\s<]+[^\s<.,;)]", lambda m: f'<a href="{m[0]}">{m[0]}</a>', text)


def model_texts(cld, loops):
    """(facts, texts): cld-texts.md as HTML, its numbers counted in the model. The facts are
    the list before its first heading; the texts are its sections, each a ## heading with
    paragraphs or a - list. A <!-- comment --> is not shown."""
    text = re.sub(r"<!--.*?-->\n?", "", TEXTS.read_text(), flags=re.S)
    # each group's mechanism is its description in cld.json, so the two cannot differ
    text = text.replace("{combined loops list}", "\n".join(
        f"- **{g['id']} {g['name']}** ({', '.join(g['loops'])}). {g['description']}" for g in cld.get("groups", [])))
    for name, n in counts(cld, loops).items():
        text = text.replace("{" + name + "}", f"{n:,}")
    if re.search(r"\{[a-z ]+\}", text):
        sys.exit(f"cld-texts.md names a number build.py does not count: {re.search(r'{[a-z ]+}', text)[0]}")
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
    template = (TEMPLATES / "index.html").read_text()
    svg = draw_cld.svg(cld)
    # "</" inside a <script> would end it early; "<\/" is the same string to JSON
    data = json.dumps(page_data(cld, refs, actors, version), ensure_ascii=False).replace("</", "<\\/")
    facts, texts = model_texts(cld, loops)
    for marker in ("<!-- SVG -->", "<!-- DATA -->", "<!-- FACTS -->", "<!-- TEXTS -->"):
        assert template.count(marker) == 1, f"src/templates/index.html must hold {marker} once"
    return (template.replace("<!-- SVG -->", svg.rstrip()).replace("<!-- FACTS -->", facts)
            .replace("<!-- TEXTS -->", texts)
            .replace("<!-- DATA -->", f'<script type="application/json" id="data">{data}</script>'))


def element_actors(cld, actors):
    """Per element id, the actors that decide it or shape it directly, in actor-map.json's order: its
    own actor, the actor of each decision variable linked into it, and the actors outside the scale
    its `actors` field names. An actor inside the scale acts through its decisions, so the links,
    each with its source, already show whom it shapes: derived, never typed, so a link the
    structural step moves takes its actor along (Jordy: "do what you think is best"; rejected:
    typing every actor, a second record of the links)."""
    by = {e["id"]: e for e in cld["elements"]}
    found = {i: {e["actor"]} if "actor" in e else set() for i, e in by.items()}
    for c in cld["connections"]:
        if "actor" in by[c["from"]]:
            found[c["to"]].add(by[c["from"]]["actor"])
    for i, e in by.items():
        found[i] |= set(e.get("actors", []))
    return {i: [a["id"] for a in actors["actors"] if a["id"] in s] for i, s in found.items()}


def table_sheets(cld, refs, actors):
    """[(name, widths, rows)] for docs/tables/cld-table.xlsx, the table that explains the CLD, written from
    cld.json (the actors' labels from actor-map.json, the references from references.json): the
    Elements, Links and Named loops sheets, Combined loops once cld.json holds groups, and the
    References sheet, the full references the sheets cite in-text (draw_actor_map.citations()). A
    spreadsheet, as the actors' table, which Jordy imports into Google Drive as a Google Sheet
    (Jordy; rejected: an HTML page, whose tables lost their columns pasted into Google Docs)."""
    els = {e["id"]: e for e in cld["elements"]}
    label = {a["id"]: a["label"] for a in actors["actors"]}
    shaped = element_actors(cld, actors)
    cites = draw_actor_map.citations(sorted({k for i in cld["elements"] + cld["connections"] for k in i["sources"]}), refs)

    def sources(item):
        if item.get("hypothesis"):
            return "Hypothesis for the group model building session"
        return draw_actor_map.cite_list(item["sources"], cites) or "none yet"

    # the elements by subsystem, as the drawing's regions (water and soil left), then by label
    order = list(draw_cld.REGION)
    elements = sorted(cld["elements"], key=lambda e: (order.index(e["subsystem"]), e["label"].lower()))
    links = sorted(cld["connections"], key=lambda c: (els[c["from"]]["label"].lower(), els[c["to"]]["label"].lower()))
    sheets = [
        ("Elements", [28, 11, 13, 20, 90, 60, 24, 30, 36, 40],
         [["Element", "Type", "SETS domain", "Subsystem", "Description", "Simplification", "Decided by", "Actors",
           "Sources", "Ask actors"]]
         + [[e["label"], e["element type"], e["sets domain"], e["subsystem"], e["description"],
             e.get("simplification", ""), label[e["actor"]] if "actor" in e else "",
             "\n".join(label[a] for a in shaped[e["id"]]), sources(e), ask_text(e, label)] for e in elements]),
        ("Links", [28, 28, 9, 7, 90, 60, 36, 40],
         [["From", "To", "Polarity", "Delay", "Description", "Simplification", "Sources", "Ask actors"]]
         + [[els[c["from"]]["label"], els[c["to"]]["label"], "+" if c["polarity"] == "+" else "−",
             "yes" if c["delay"] else "no", c["description"], c.get("simplification", ""), sources(c),
             ask_text(c, label)] for c in links]),
        ("Named loops", [6, 34, 12, 70, 80],
         [["Loop", "Name", "Kind", "Its elements, in order", "Description"]]
         + [[L["id"], L["name"], "Reinforcing" if L["id"].startswith("R") else "Balancing",
             " → ".join(els[i]["label"] for i in L["path"] + L["path"][:1]), L.get("description", "")]
            for L in cld["loops"]]),
    ]
    if cld.get("groups"):
        sheets.append(("Combined loops", [30, 20, 80], [["Combined loops", "Its loops", "Description"]]
                       + [[g["name"], ", ".join(g["loops"]), g["description"]] for g in cld["groups"]]))
    sheets.append(("References", [120], [["Reference"]]
                   + [[r] for r in sorted((c[2] for c in cites.values()), key=str.lower)]))
    return sheets


def ask_sheets(cld, actors):
    """[(name, widths, rows)] for docs/tables/sources-to-ask.xlsx, the list Jordy and Lenne contact
    the actors from: a row per `ask actors` entry of cld.json's elements and links and of
    actor-map.json's actors (the element, link or actor; what is missing; the actor; through whom),
    by partners (DCC alone, then both, then the Living Lab alone) and then by actor, so each
    contact's questions sit together, and within an actor in the model's order. One record, the
    model's, so the list cannot drift from it (Jordy's decision, cld-model.md)."""
    els = {e["id"]: e for e in cld["elements"]}
    label = {a["id"]: a["label"] for a in actors["actors"]}
    items = ([(e["label"], e) for e in cld["elements"]]
             + [(f'{els[c["from"]]["label"]} → {els[c["to"]]["label"]}', c) for c in cld["connections"]]
             + [(a["label"], a) for a in actors["actors"]])
    entries = [(what, a) for what, item in items for a in item.get("ask actors", [])]
    # stable: the model's order within an actor
    entries.sort(key=lambda e: (sorted(ASK_THROUGH.index(t) for t in e[1]["through"]), label[e[1]["actor"]].lower()))
    rows = [[what, a["for"], label[a["actor"]], through_text(a["through"])] for what, a in entries]
    return [("Sources to ask", [36, 90, 30, 12], [["Element, link or actor", "What is missing", "Actor", "Through"]] + rows)]


def data_url(svg):
    """An SVG as a data URL: the form in which a Kumu view carries its background image inside the
    project file, so the project depends on no host (cld-drawing.md)."""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def with_image(view, svg, name):
    """The Kumu view with svg as its #background image, in place of the view's url(IMAGE)."""
    if view.count("url(IMAGE)") != 1:
        sys.exit(f"src/kumu/{name} needs url(IMAGE) once, in its #background rule: build.py puts the image there")
    return view.replace("url(IMAGE)", f"url({data_url(svg)})")


def project(cld, refs, actors, template):
    """The CLD's part of the Kumu project (kumu_project()): the map of the full CLD, then a map per
    combined loop and per named loop, each drawn as its figure (Jordy's decision, cld-drawing.md).

    The CLD's view is src/kumu/cld-view.scss with the regions as its background image, plus what is
    generated here: each SETS domain's tint from draw_cld.TINT, and by Kumu system id each
    element's box size from draw_cld.boxes(). The loop maps' view is the same without the section
    that hides the loop labels, so each label shows at its mark. Each label holds a double space
    where the page breaks its line, Kumu's manual line break, so its box fits it."""
    bp = blueprint(cld, refs, actors)
    keep = lambda item, drop: {k: v for k, v in item.items() if k not in drop}
    bxs = draw_cld.boxes(cld)
    elements = [{"_id": f'elem-{e["id"]}',
                 "attributes": {**keep(e, {"id", "x", "y"}), "label": "  ".join(bxs[e["id"]][4])}}
                for e in bp["elements"]]
    # the regions: an element labelled background, the regions its image (cld-view.scss)
    elements.append({"_id": "elem-background", "attributes": {"label": "background"}})
    regions, (fx0, fy0, fx1, fy1) = draw_cld.regions_svg(cld)
    # Kumu shows the regions stretched to the frame: with a viewBox alone a browser sizes an SVG 250
    # by 150 pixels, which Kumu blurred (draw_cld.regions_svg())
    if not re.match(r'<svg [^>]*\bwidth="\d+" height="\d+"', regions):
        sys.exit("the regions' SVG needs a width and a height besides its viewBox: draw_cld.regions_svg() writes them")
    template = with_image(template, regions, "cld-view.scss")
    rules = ([f'["sets domain"="{d.lower()}"] {{ color: {t}; }}' for d, t in draw_cld.TINT.items()]
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
                      "attributes": {"label": f'{loop["id"]} {loop["name"]}', "description": loop["description"]},
                      "connections": [f'conn-{a}--{b}' for a, b in zip(path, path[1:] + path[:1])]})
        map_loops.append({"_id": f'mloop-{loop["id"]}', "loop": f'loop-{loop["id"]}', "style": {},
                          "position": {"x": round(sum(by_id[i]["x"] for i in path) / len(path)),
                                       "y": round(sum(by_id[i]["y"] for i in path) / len(path))}})
    style = (template.rstrip() + "\n\n/* ---------- generated by build.py: tints, box sizes, the regions' size ---------- */\n"
             + "\n".join(rules) + "\n")
    # the loop maps' view: the CLD's without its Loops section, the rule that hides the loop labels
    loops_style, cut = re.subn(r"/\* -+ Loops: .*?\nloop \{\n  label: none;\n\}\n", "", style, flags=re.S)
    if cut != 1:
        sys.exit("src/kumu/cld-view.scss needs its Loops section, ending in loop { label: none; }: the loop maps' view leaves it out")

    # a map per combined loop, then per named loop: its loops' elements and links at the places and
    # bends of its figure, each loop's label at its mark; a named loop's from its oval
    figures = ([("group", g, g["loops"], g["places"], g["bends"], g["marks"]) for g in cld.get("groups", [])]
               + [("loop", loop, [loop["id"]], *draw_cld.oval_layout(cld, loop)) for loop in cld["loops"]])
    loop_maps = []
    for kind, item, ids, places, bends, marks in figures:
        key = f'{kind}-{item["id"]}'  # map items' ids are the project's, so each names its map
        links = [k.split(" -> ") for k in bends]
        loop_maps.append({
            "_id": f"map-{key}", "name": f'{item["id"]} {item["name"]}', "description": item["description"],
            "scale": 1, "center": {"x": 0, "y": 0}, "defaultPerspective": "pers-loops",
            "defaultElementBehavior": "fixed", "defaultConnectionDirection": "directed",
            "elements": [{"_id": f"node-{key}-{i}", "position": {"x": x, "y": y}, "pinned": True, "style": {},
                          "element": f"elem-{i}"} for i, (x, y) in places.items()],
            "connections": [{"_id": f"edge-{key}-{a}--{b}", "curvature": bends[f"{a} -> {b}"], "style": {},
                             "connection": f"conn-{a}--{b}"} for a, b in links],
            "loops": [{"_id": f"mloop-{key}-{i}", "loop": f"loop-{i}", "style": {},
                       "position": {"x": marks[i][0], "y": marks[i][1]}} for i in ids]})
    return {
        "elements": elements, "connections": connections, "loops": loops,
        "maps": [{"_id": "map-cld", "name": "CLD model", "description": "", "scale": 1,
                  "center": {"x": 0, "y": 0}, "defaultPerspective": "pers-cld",
                  "defaultElementBehavior": "fixed", "defaultConnectionDirection": "directed",
                  "elements": nodes, "connections": edges, "loops": map_loops}] + loop_maps,
        # the maps' edges carry the curves, so the views hold no curvature rules
        "perspectives": [{"_id": "pers-cld", "name": "CLD", "style": style},
                         {"_id": "pers-loops", "name": "Loops", "style": loops_style}],
    }


def actors_project(actors, refs, decides, cld_labels, template):
    """The Actor Map's part of the Kumu project (kumu_project()), as project() gives the CLD's: each
    actor an element with its fields, its type the CLD's field element type, each relation a
    connection whose type is its kind, the actors at their places, the relations with their curves,
    and the level bands as the background image (an element labelled background, as the CLD's
    regions). The view is src/kumu/actor-map-view.scss with the bands as its background image, plus
    each kind's colour and dash from draw_actor_map.KIND and each box's size."""
    bxs, rels, _ = draw_actor_map.geometry(actors)
    bands, (fx0, fy0, fx1, fy1) = draw_actor_map.bands_svg(actors)
    template = with_image(template, bands, "actor-map-view.scss")
    labels = {a["id"]: a["label"] for a in actors["actors"]}
    elements = [{"_id": f'elem-{a["id"]}', "attributes": {
        "label": "  ".join(bxs[a["id"]][4]), "element type": a["type"], "level": a["level"], "sector": a["sector"],
        "interest": a["interest"], "influence": a["influence"], "affected": a["affected"],
        "influence score": a["influence score"], "client": a["client"],
        "decides in the CLD": "\n".join(cld_labels[e] for e in decides[a["id"]]),
        **({"ask actors": ask_text(a, labels)} if "ask actors" in a else {}),
        **({"no relations": a["no relations"]} if "no relations" in a else {}),
        "sources": "\n".join(refs[k] for k in a["sources"])}} for a in actors["actors"]]
    # its own id beside the CLD's background, and the same label, which the view's #background selects
    elements.append({"_id": "elem-actors-background", "attributes": {"label": "background"}})
    connections = [{"_id": f'conn-{r["n"]}', "direction": "directed", "delayed": False, "reversed": False,
                    "attributes": {"connection type": r["kind"], "description": r["description"],
                                   "sources": "\n".join(refs[k] for k in r["sources"])},
                    "from": f'elem-{r["from"]}', "to": f'elem-{r["to"]}'} for r in rels]
    nodes = [{"_id": f'node-{a["id"]}', "position": {"x": a["x"], "y": a["y"]}, "pinned": True, "style": {},
              "element": f'elem-{a["id"]}'} for a in actors["actors"]]
    nodes.append({"_id": "node-actors-background", "position": {"x": round((fx0 + fx1) / 2), "y": round((fy0 + fy1) / 2)},
                  "pinned": True, "style": {}, "element": "elem-actors-background"})
    edges = [{"_id": f'edge-{r["n"]}', "curvature": r["curvature"], "style": {}, "connection": f'conn-{r["n"]}'}
             for r in rels]
    rules = ([f'["connection type"="{k}"] {{ color: {c}; style: {"dashed" if d else "solid"}; }}'
              for k, (c, d) in draw_actor_map.KIND.items()]
             + [f'#elem-{i} {{ width: {round(b[2] - b[0])}; height: {round(b[3] - b[1])}; }}' for i, b in bxs.items()]
             + [f'#background {{ width: {round(fx1 - fx0)}; height: {round(fy1 - fy0)}; }}'])
    style = (template.rstrip() + "\n\n/* ---------- generated by build.py: the kinds' look, box sizes, the bands' size ---------- */\n"
             + "\n".join(rules) + "\n")
    return {
        "elements": elements, "connections": connections, "loops": [],
        "maps": [{"_id": "map-actors", "name": "Actor Map", "description": " ".join(draw_actor_map.BANDS_NOTE), "scale": 1,
                  "center": {"x": 0, "y": 0}, "defaultPerspective": "pers-actors",
                  "defaultElementBehavior": "fixed", "defaultConnectionDirection": "directed",
                  "elements": nodes, "connections": edges, "loops": []}],
        "perspectives": [{"_id": "pers-actors", "name": "Actor Map", "style": style}],
    }


# the fields whose values are prose: free text in Kumu, never a list to pick from
TEXT_FIELDS = {"description", "simplification", "sources", "interest", "influence", "affected", "decides in the CLD",
               "ask actors", "no relations"}
# Kumu's own type fields are spelled this way; "Connection type" would be a second field
BUILTIN_FIELDS = {"element type": "Element Type", "connection type": "Connection Type"}


def fields(items):
    """Kumu's fields for the attributes of items, every element and link of both maps: one per name,
    its _id attr- and the name in lower case with hyphens, a drop-down list of the values of both
    maps where they are 20 or fewer, else autocomplete."""
    values = {}
    for item in items:
        for k, v in item.items():
            values.setdefault(k, set()).add(v)
    attributes = []
    for k, seen in values.items():
        name = BUILTIN_FIELDS.get(k, k[0].upper() + k[1:])
        text = k in TEXT_FIELDS
        listed = not text and k != "label" and len(seen) <= 20
        attributes.append({"_id": "attr-" + name.lower().replace(" ", "-"), "name": name,
                           "format": "text" if text else "string", "private": False, "limit": 1,
                           "category": "General", "prompt": "list" if listed else "autocomplete",
                           "locked": False, "values": sorted(seen, key=str) if listed else [],
                           "sort": False, "cluster": listed})
    return attributes


def kumu_project(cld_part, actors_part):
    """The Kumu project, a full project export in the shape of Kumu's own "Export JSON": the CLD's
    part (project()) and the Actor Map's (actors_project()) as maps of one project, the full CLD's
    the default. It holds no version, so the link to each map stays the same from one copy to the
    next (Jordy: the versions are the repository's), and links to neither the page nor the
    repository: outsiders see only Kumu and the submissions (Jordy's decision, in
    ChallengeBasedProject1/.claude/CLAUDE.md)."""
    parts = [cld_part, actors_part]
    # the CLD's map and view first, then the Actor Map's, then the CLD's loop maps and their view
    order = lambda k: cld_part[k][:1] + actors_part[k] + cld_part[k][1:]
    # Kumu lists the maps sorted by name as plain text, whatever their order here (B10 before B2),
    # so each name starts with its place in this order (Jordy; rejected: zero-padded loop ids, which
    # keep the list grouped by letter, and the names alone)
    maps = order("maps")
    width = max(2, len(str(len(maps))))
    maps = [dict(m, name=f"{n:0{width}} {m['name']}") for n, m in enumerate(maps, 1)]
    if [m["name"] for m in maps] != sorted(m["name"] for m in maps):
        sys.exit("the Kumu map names sort into another order than the maps': Kumu's list would show that order")
    # a restore sets the project's name, so it is the name of the project the group's URL names
    return {
        "version": 1, "name": "cbp1", "description": "", "proxyImages": True,
        "defaultMap": "map-cld", "defaultPerspective": None, "attributeRelevance": {},
        "attributes": fields([x["attributes"] for p in parts for x in p["elements"] + p["connections"]]),
        **{k: [x for p in parts for x in p[k]] for k in ("elements", "connections", "loops")},
        "maps": maps, "perspectives": order("perspectives"),
    }


def apply_layout(path):
    """Write a layout.json from a page's Move mode into its model, in the model's own formatting. The
    CLD's ({id: {x, y}, "curvature": {"from->to": k}, "delay": {"from->to": t}}) goes into cld.json:
    each element's place, each link's curvature, each dragged delay mark. The Actor Map's ({"model":
    "actor-map.json", id: {x, y}, "curvature": {"from->to kind": k}}) goes into actor-map.json: each
    actor's place and each relation's curvature, a relation named by its two actors and its kind,
    since two actors can hold two relations. A file without "curvature" moves the boxes only."""
    layout = json.loads(path.read_text())
    target = layout.pop("model", "cld.json")
    curvature = layout.pop("curvature", {})
    if target == "cld.json":
        file, what = CLD, "element or link"
        delay_at = layout.pop("delay", {})
        model = json.loads(CLD.read_text())
        boxes = model["elements"]
        links = [(f'{c["from"]}->{c["to"]}', c) for c in model["connections"]]
    elif target == "actor-map.json":
        file, what, delay_at = ACTORS, "actor or relation", {}
        model = json.loads(ACTORS.read_text())
        boxes = model["actors"]
        links = [(f'{a["id"]}->{r["to"]} {r["kind"]}', r) for a in boxes for r in a.get("relations", [])]
    else:
        sys.exit(f"--layout: model {target!r} is neither cld.json nor actor-map.json")
    by_id = {b["id"]: b for b in boxes}
    by_link = dict(links)
    unknown = [i for i in layout if i not in by_id] + [k for k in list(curvature) + list(delay_at) if k not in by_link]
    if unknown:
        sys.exit(f"--layout: unknown {what} {', '.join(unknown)}")
    # a name that two relations share would bend both
    twice = [k for k in curvature if sum(k == n for n, _ in links) > 1]
    if twice:
        sys.exit(f"--layout: {', '.join(twice)} names more than one {what.split(' or ')[1]}")
    for i, pos in layout.items():
        by_id[i]["x"], by_id[i]["y"] = int(pos["x"]), int(pos["y"])
    for k, v in curvature.items():
        if by_link[k]["curvature"] != v:  # an unchanged value keeps its spelling (0 or 0.0)
            by_link[k]["curvature"] = v
    for k, v in delay_at.items():
        by_link[k]["delay at"] = v
    file.write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if docs/ is out of date")
    parser.add_argument("--layout", metavar="FILE", help="write the x, y and curvatures of FILE (layout.json from a page) into cld.json, or the Actor Map's into actor-map.json, then build")
    args = parser.parse_args()

    if args.layout:
        apply_layout(Path(args.layout))
    cld = json.loads(CLD.read_text())
    refs, ref_errors = references()
    actors = json.loads(ACTORS.read_text())
    template = (KUMU / "cld-view.scss").read_text()
    actor_errors, empty = check_actors(actors, refs)
    errors, warnings = check(cld, refs, actors)
    if errors or actor_errors or ref_errors:
        sys.exit("cld.json, actor-map.json or references.json has errors:\n  " + "\n  ".join(ref_errors + actor_errors + errors))

    # the model version teammates compare: the first seven characters of cld.json's SHA-256
    version = hashlib.sha256(CLD.read_bytes()).hexdigest()[:7]
    loops = cycles(cld)  # the page's texts count them, and the report
    actors_version = hashlib.sha256(ACTORS.read_bytes()).hexdigest()[:7]
    decides = decisions(cld, actors)
    cld_labels = {e["id"]: e["label"] for e in cld["elements"]}
    outputs = {
        "kumu/kumu-project.json": json.dumps(kumu_project(
            project(cld, refs, actors, template),
            actors_project(actors, refs, decides, cld_labels, (KUMU / "actor-map-view.scss").read_text())),
            indent=2, ensure_ascii=False) + "\n",
        "actors.html": draw_actor_map.page(actors, refs, decides, cld_labels, actors_version, (TEMPLATES / "actors.html").read_text()),
        "assets/actors.js": (TEMPLATES / "actors.js").read_text(),
        "figures/actor-map.svg": draw_actor_map.svg(actors),
        "tables/actor-map-table.xlsx": write_xlsx.workbook(draw_actor_map.sheets(actors, refs, decides, cld_labels)),
        "figures/cld.svg": draw_cld.svg(cld),
        "index.html": page(cld, refs, actors, version, loops),
        "tables/cld-table.xlsx": write_xlsx.workbook(table_sheets(cld, refs, actors)),
        "tables/sources-to-ask.xlsx": write_xlsx.workbook(ask_sheets(cld, actors)),
        "assets/app.js": (TEMPLATES / "app.js").read_text(),
        "assets/map.js": (TEMPLATES / "map.js").read_text(),
        "assets/move.js": (TEMPLATES / "move.js").read_text(),
        "assets/style.css": (TEMPLATES / "style.css").read_text(),
        **{f"figures/named-loops/{loop['id']}.svg": draw_cld.loop_figure(cld, loop) for loop in cld["loops"]},
        **{f"figures/combined-loops/{g['id']}.svg": draw_cld.group_figure(cld, g) for g in cld.get("groups", [])},
    }
    # a figure whose loop is gone or renamed would stay published
    extra = sorted(f"{d}/{f.name}" for d in ("figures/named-loops", "figures/combined-loops") if (DOCS / d).is_dir()
                   for f in (DOCS / d).glob("*") if f"{d}/{f.name}" not in outputs)

    if args.check:
        # the table is bytes, every other file text
        stale = [name for name, out in outputs.items() if not (DOCS / name).exists()
                 or ((DOCS / name).read_bytes() if isinstance(out, bytes) else (DOCS / name).read_text()) != out]
        if stale or extra:
            sys.exit(f"docs/ is out of date ({', '.join(stale + extra)}): run build.py and commit docs/")
        return

    for name in extra:
        (DOCS / name).unlink()
    for name, out in outputs.items():
        (DOCS / name).parent.mkdir(parents=True, exist_ok=True)
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
    crossings, through = draw_cld.tangles(cld)
    print(f"layout: {len(crossings)} crossings between links, "
          f"{len(through)} links through a box they do not connect")
    warnings += [f"link through a box: {a} -> {b} passes through {e}" for (a, b), e in through]
    a_crossings, a_through = draw_actor_map.tangles(actors)
    print(f"actor map: {len(a_crossings)} crossings between relations, "
          f"{len(a_through)} relations through a box they do not connect")
    rel = draw_actor_map.relations(actors)
    warnings += [f"actor map: relation through a box: {rel[n]['from']} {rel[n]['kind']} {rel[n]['to']} passes through {e}"
                 for n, e in a_through] + draw_actor_map.overlaps(actors)
    print(f"actors: {len(actors['actors'])} ({sum(a['scale'] == 'inside' for a in actors['actors'])} inside the scale); "
          "CLD variables each decides: " + ", ".join(f"{i} {len(v)}" for i, v in decides.items() if v))
    if empty:
        print("actor fields still empty:\n  " + "\n  ".join(f"{i}: {', '.join(ks)}" for i, ks in empty.items()))
    # an element no decision variable drives and no source names an outside actor for
    shaped = element_actors(cld, actors)
    no_actors = [i for i, s in shaped.items() if not s]
    if no_actors:
        print(f"elements no actor decides or shapes directly ({len(no_actors)}): {', '.join(no_actors)}")
    cited = {k for item in cld["elements"] + cld["connections"] + cld.get("groups", []) + actors["actors"] for k in item.get("sources", [])}
    cited |= {k for a in actors["actors"] for r in a.get("relations", []) for k in r.get("sources", [])}
    warnings += [f"reference {k!r} is cited nowhere" for k in refs if k not in cited]
    # a section the page would show with nothing under its heading
    warnings += [f"cld-texts.md: the section {h!r} is still empty" for h, body in
                 re.findall(r"^## (.+)\n((?:(?!## ).*\n?)*)", re.sub(r"<!--.*?-->", "", TEXTS.read_text(), flags=re.S), re.M)
                 if not body.strip()]
    if warnings:
        print("warnings:\n  " + "\n  ".join(warnings))


if __name__ == "__main__":
    main()
