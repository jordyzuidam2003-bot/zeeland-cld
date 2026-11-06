"""Draw the Actor Map: the actors' network as an SVG, from actors.json's own coordinates (y
downwards), and the page around it.

Imported by build.py, which writes docs/actors.html (page(): the drawing, a panel per actor and
relation), docs/actors.svg (svg(), the picture for the report), docs/actors-bands.svg (bands_svg(),
Kumu's background image), docs/actors-project.json and docs/actors.xlsx (sheets(), the actors'
table, which Jordy imports into Google Drive as a Google Sheet; rejected: the table on the page,
Jordy). tangles(actors) and overlaps(actors) give build.py's report the crossings between
relations, the relations through a box they do not connect, boxes that overlap and an actor
outside its level's band.

What the network draws, from back to front:
  bands      one faint horizontal band per level, Global at the top and Local / Provincial /
             Regional at the bottom, each named in a column at its left (Jordy, chosen between
             rendered versions: by level; rejected: rings by the CLD's scale, clusters by type, and
             boxes shaded by influence score; the scale is not drawn, Jordy)
  relations  a quadratic Bezier from box edge to box edge, as draw.py draws a CLD link, the ends on
             one edge spread along it (draw.link_paths()); its colour and dash by its kind (KIND),
             an arrowhead at the actor it acts on
  actors     the label in a white box
  legend     below the frame
"""

import json
import re

import draw

FONT_SIZE = draw.FONT_SIZE
REL_WIDTH = 4
# Each kind its colour and dash: colour alone cannot tell six kinds apart (at most three hues pass
# the dataviz skill's validator for marks that can sit side by side), so a kind sharing a hue with
# another differs from it by its dash. Orange, violet and aqua pass all pairs; aqua is under 3:1 on
# white, relieved by the legend and the table. Ink for authority, which none of them is mistaken for.
KIND = {
    "authority over": ("#333333", ""),
    "finances": ("#EB6834", ""),
    "buys from": ("#EB6834", "14 9"),
    "advises": ("#6250D6", "14 9"),
    "represents": ("#6250D6", ""),
    "works with": ("#1BAF7A", "14 9"),
}
LEVELS = ["Global", "International", "National", "Local / Provincial / Regional"]  # top to bottom
BAND_FILL = ["#EEF2F6", "#F8F6F1"]  # alternating, faint, so the relations' colours stay the marks
BAND_NAME = "#4A5560"
BAND_NAME_SIZE = 40
BAND_NAME_SPACING = 5
BAND_NAMES_WIDTH = 360  # the column left of the boxes that holds the band names
FRAME_PAD = 90
MARGIN = 40
LEGEND_SIZE = 40


def elements(actors):
    """The actors as draw.boxes() takes them."""
    return [{"id": a["id"], "label": a["label"], "x": a["x"], "y": a["y"]} for a in actors["actors"]]


def relations(actors):
    """Every relation as a connection draw.link_paths() takes, `n` its place in the list: two actors
    can hold two relations, so the pair does not name one."""
    out = []
    for a in actors["actors"]:
        for r in a.get("relations", []):
            out.append({"n": len(out), "from": a["id"], "to": r["to"], "kind": r["kind"],
                        "curvature": r["curvature"], "description": r["description"], "sources": r["sources"]})
    return out


def geometry(actors):
    """(boxes, relations, paths): each actor's box, each relation, and its curve by `n`."""
    bxs = draw.boxes({"elements": elements(actors)})
    rels = relations(actors)
    return bxs, rels, draw.link_paths({"connections": rels}, bxs, key=lambda c: c["n"])


def tangles(actors):
    """(crossings, through), as draw.tangles() counts them for the CLD: pairs of relations that
    cross, as (n, n), and each relation that passes through a box it does not connect, as (n, id)."""
    bxs, rels, paths = geometry(actors)
    pts = {n: [draw.bezier(*p, i / 30) for i in range(31)] for n, p in paths.items()}
    crossings = [(a["n"], b["n"]) for i, a in enumerate(rels) for b in rels[i + 1:]
                 for u in range(30) for v in range(30)
                 if draw.meet(pts[a["n"]][u], pts[a["n"]][u + 1], pts[b["n"]][v], pts[b["n"]][v + 1])]

    def cuts(p, q, box):
        x0, y0, x1, y1 = box[:4]
        c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return draw.inside(p, box) or draw.inside(q, box) or any(draw.meet(p, q, c[k], c[(k + 1) % 4]) for k in range(4))
    through = [(r["n"], e) for r in rels for e, b in bxs.items() if e not in (r["from"], r["to"])
               and any(cuts(pts[r["n"]][u], pts[r["n"]][u + 1], b) for u in range(30))]
    return crossings, through


def overlaps(actors):
    """Boxes that intersect, and an actor whose box reaches into another level's band: the bands
    are drawn from their actors' boxes, so it would draw one band across another."""
    bxs = draw.boxes({"elements": elements(actors)})
    acts = actors["actors"]
    out = [f"actor map: boxes overlap: {a['id']} and {b['id']}" for i, a in enumerate(acts) for b in acts[i + 1:]
           if (lambda p, q: p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3])(bxs[a["id"]], bxs[b["id"]])]
    for a in acts:
        for b in acts:
            if LEVELS.index(a["level"]) < LEVELS.index(b["level"]) and bxs[a["id"]][3] >= bxs[b["id"]][1]:
                out.append(f"actor map: {a['id']} ({a['level']}) is not above {b['id']} ({b['level']})")
    return out


def esc(text):
    return draw.esc(text).replace('"', "&quot;")


def actor_svg(a, box):
    x0, y0, x1, y1, lines = box
    parts = [f'<g class="actor" data-id="{a["id"]}"><title>{esc(a["label"])}</title>',
             f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" rx="{draw.CORNER}" '
             f'fill="white" stroke="{draw.STROKE_COLOUR}" stroke-width="2"/>']
    top = y0 + draw.PAD_Y + draw.LINE_HEIGHT * 0.75
    for i, line in enumerate(lines):
        parts.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{top + i * draw.LINE_HEIGHT:.1f}" text-anchor="middle">{esc(line)}</text>')
    parts.append("</g>")
    return "\n".join(parts)


def relation_svg(r, p, labels):
    """A relation, its description as the tooltip a browser shows on hover."""
    colour, dash = KIND[r["kind"]]
    (x0, y0), (cx, cy), (x2, y2) = p
    dash = f' stroke-dasharray="{dash}"' if dash else ""
    title = f'{labels[r["from"]]} {r["kind"]} {labels[r["to"]]}: {r["description"]}'
    return (f'<g class="relation" data-from="{r["from"]}" data-to="{r["to"]}" data-kind="{r["kind"]}">'
            f'<title>{esc(title)}</title>'
            f'<path d="M {x0:.1f} {y0:.1f} Q {cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" fill="none" stroke="{colour}" '
            f'stroke-width="{REL_WIDTH}"{dash} marker-end="url(#arrow-{r["kind"].replace(" ", "-")})"/></g>')


def bands(actors, bxs):
    """(svg, frame): a band per level that has actors, from the top of its boxes to the bottom,
    the border between two bands halfway between them, and the frame (x0, y0, x1, y1) round the
    boxes with the names' column at its left."""
    allb = list(bxs.values())
    fx0, fy0 = min(b[0] for b in allb) - FRAME_PAD - BAND_NAMES_WIDTH, min(b[1] for b in allb) - FRAME_PAD
    fx1, fy1 = max(b[2] for b in allb) + FRAME_PAD, max(b[3] for b in allb) + FRAME_PAD
    rows = []
    for level in LEVELS:
        bs = [bxs[a["id"]] for a in actors["actors"] if a["level"] == level]
        if bs:
            rows.append((level, min(b[1] for b in bs), max(b[3] for b in bs)))
    edges = [fy0] + [(rows[k][2] + rows[k + 1][1]) / 2 for k in range(len(rows) - 1)] + [fy1]
    parts = []
    for k, (level, _, _) in enumerate(rows):
        y0, y1 = edges[k], edges[k + 1]
        parts.append(f'<rect x="{fx0:.1f}" y="{y0:.1f}" width="{fx1 - fx0:.1f}" height="{y1 - y0:.1f}" fill="{BAND_FILL[k % 2]}"/>')
        # "Local / Provincial / Regional" on three lines, so the column stays narrow
        words = level.replace(" / ", "/ ").split(" ")
        for i, w in enumerate(words):
            y = (y0 + y1) / 2 + (i - (len(words) - 1) / 2) * BAND_NAME_SIZE * 1.2
            parts.append(f'<text x="{fx0 + 40:.1f}" y="{y:.1f}" font-size="{BAND_NAME_SIZE}" font-weight="bold" '
                         f'letter-spacing="{BAND_NAME_SPACING}" fill="{BAND_NAME}" dominant-baseline="central">{esc(w.upper())}</text>')
    return "\n".join(parts), (fx0, fy0, fx1, fy1)


def bands_svg(actors):
    """(svg, frame): the bands alone, their viewBox the frame in the actors' coordinates, with a
    width and a height, for Kumu's background image (as draw.regions_svg() for the CLD)."""
    band_svg, frame = bands(actors, draw.boxes({"elements": elements(actors)}))
    x0, y0, x1, y1 = frame
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}" '
            f'width="{x1 - x0:.0f}" height="{y1 - y0:.0f}" font-family="{draw.FONT}">\n{band_svg}\n</svg>\n'), frame


def legend_svg(x, y):
    """The legend, two rows of three kinds, its first row's middle at y; returns (svg, width, height)."""
    f = LEGEND_SIZE
    sw = f * 2.6
    col = sw + f * 0.4 + len("authority over") * draw.CHAR_WIDTH / FONT_SIZE * f + f
    items = [f'<text x="{x:.1f}" y="{y:.1f}" font-size="{f}" font-weight="bold" dominant-baseline="central">Relations</text>']
    for i, (kind, (colour, dash)) in enumerate(KIND.items()):
        xx, yy = x + f * 5 + (i % 3) * col, y + (i // 3) * f * 1.5
        dash = f' stroke-dasharray="{dash}"' if dash else ""
        items.append(f'<path d="M {xx:.1f} {yy:.1f} L {xx + sw - draw.ARROW:.1f} {yy:.1f}" stroke="{colour}" stroke-width="{REL_WIDTH}"{dash} '
                     f'fill="none" marker-end="url(#arrow-{kind.replace(" ", "-")})"/>')
        items.append(f'<text x="{xx + sw + f * 0.4:.1f}" y="{yy:.1f}" font-size="{f}" dominant-baseline="central">{kind}</text>')
    return '<g class="legend">\n' + "\n".join(items) + "\n</g>", f * 5 + 3 * col, 2 * f * 1.5


def head(vb):
    """The opening of the drawing: the svg tag, an arrowhead per kind, a white ground."""
    arrow = lambda name, colour: (f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="{draw.ARROW}" '
                                  f'markerHeight="{draw.ARROW}" markerUnits="userSpaceOnUse" orient="auto">'
                                  f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{colour}"/></marker>')
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb[0]:.0f} {vb[1]:.0f} {vb[2]:.0f} {vb[3]:.0f}" '
            f'font-family="{draw.FONT}" font-size="{FONT_SIZE}" fill="black">',
            "<defs>", *(arrow(k.replace(" ", "-"), c) for k, (c, _) in KIND.items()), "</defs>",
            f'<rect x="{vb[0]:.0f}" y="{vb[1]:.0f}" width="{vb[2]:.0f}" height="{vb[3]:.0f}" fill="white"/>']


def svg(actors):
    bxs, rels, paths = geometry(actors)
    labels = {a["id"]: a["label"] for a in actors["actors"]}
    band_svg, (x0, y0, x1, y1) = bands(actors, bxs)
    legend, lw, lh = legend_svg(x0, y1 + MARGIN + LEGEND_SIZE)
    y1 += MARGIN + lh + LEGEND_SIZE / 2
    x1 = max(x1, x0 + lw)
    vb = (x0 - MARGIN, y0 - MARGIN, x1 - x0 + 2 * MARGIN, y1 - y0 + 2 * MARGIN)
    parts = [*head(vb), '<g class="bands">', band_svg, "</g>",
             '<g class="relations">', *(relation_svg(r, paths[r["n"]], labels) for r in rels), "</g>",
             '<g class="actors">', *(actor_svg(a, bxs[a["id"]]) for a in actors["actors"]), "</g>",
             legend, "</svg>"]
    return "\n".join(parts) + "\n"


# --- the table: in-text citations ------------------------------------------------------------
def author_year(ref):
    """(author, year, title) of a full APA reference, its author as an in-text citation names it:
    one or two people by surname, three or more as the first et al.; a group author whole, two
    joined by &, three or more as the first et al."""
    m = re.match(r"(.*?) \(([^)]*)\)\.? ?(.*)", ref)
    authors, when, title = m[1].rstrip("."), m[2], m[3]
    year = re.search(r"\d{4}", when)[0] if re.search(r"\d{4}", when) else "n.d."
    if re.search(r", [A-Z]\.", m[1]):  # people: Surname, I. I., Surname, I., & Surname, I.
        names = [item.split(", ")[0] for item in re.split(r"(?<=\.), (?:& )?", m[1])]
    else:  # group authors: a comma also falls inside one name (Minister van Landbouw, Visserij, …),
        # so split only after ", &" or where the next name begins as the first does
        first = authors.split()[0]
        names = re.split(rf", & |, (?={re.escape(first)} )", authors)
    name = names[0] if len(names) == 1 else " & ".join(names) if len(names) == 2 else f"{names[0]} et al."
    return name, year, title


def citations(keys, refs):
    """{key: (author, year, reference)} for the keys cited, one author's works of one year told
    apart by a letter after the year in the order of their titles, as APA does (2021a, n.d.-a), the
    reference given the same letter."""
    parts = {k: author_year(refs[k]) for k in keys}
    same = {}
    for k in sorted(keys, key=lambda k: parts[k][2].lower()):
        same.setdefault(parts[k][:2], []).append(k)
    out = {}
    for (name, year), ks in same.items():
        for i, k in enumerate(ks):
            y = year if len(ks) == 1 else f"{year}-{'abcdefghij'[i]}" if year == "n.d." else f"{year}{'abcdefghij'[i]}"
            ref = refs[k] if len(ks) == 1 else re.sub(r"\((n\.d\.|\d{4})", f"({y}", refs[k], count=1)
            out[k] = (name, y, ref)
    return out


def cite_list(keys, cites):
    """The in-text citations of keys as APA joins them: one author's years together, the authors
    in alphabetical order (Kaandorp et al. (2022); Waterschap Scheldestromen (2021a, 2022))."""
    years = {}
    for k in keys:
        years.setdefault(cites[k][0], set()).add(cites[k][1])
    return "; ".join(f"{n} ({', '.join(sorted(years[n], key=lambda y: (y.startswith('n.d.'), y)))})"
                     for n in sorted(years, key=str.lower))


def by_kind(pairs, labels):
    """Relations as one "kind: actor, actor" line per kind, in KIND's order."""
    kinds = {}
    for kind, other in pairs:
        kinds.setdefault(kind, []).append(labels[other])
    return "\n".join(f"{k}: {', '.join(kinds[k])}" for k in KIND if k in kinds)


# --- the table: a spreadsheet Jordy imports into Google Drive as a Google Sheet -----------------
# The columns follow the course's actor analysis guidelines (Krueger): each actor's interests (2b),
# how it influences and is affected by the issue (2c), the relations with their direction and nature
# (2d, here also the Relations sheet) and its link to the system's elements (3: the CLD's variables
# it decides). No column for the CLD's scale, which the guidelines do not ask (Jordy).
COLUMNS = [  # (name, width in characters, what it holds): the Columns sheet explains each
    ("Actor", 26, "The actor, at the grain of the CLD's variables: a public body by its name, the island's arable farmers as one."),
    ("Type", 18, "The kind of organisation."),
    ("Level", 16, "Where it acts: Local / Provincial / Regional, National, International or Global."),
    ("Sector", 18, "The sector it works in."),
    ("Interest", 50, "What it wants, in words it would accept, from its own documents first."),
    ("Influence", 80, "How it shapes the adaptation of the island's arable farming, and the reason for its score."),
    ("How it is affected", 60, "How salinisation and freshwater scarcity on the island, and the farms' adaptation to them, "
                               "affect the actor; empty where no source read says."),
    ("Influence score", 10, "5: decides binding rules or plans for the island's farms, or the adaptation itself (the farmers); "
                            "4: decides something many of the farms depend on, without binding them; 3: shapes those "
                            "decisions directly (advice, representation, funding); 2: shapes them indirectly; 1: little "
                            "effect on the island's adaptation by 2050."),
    ("Client", 8, "yes for the project's partners."),
    ("Influences", 40, "The actors it influences, by the kind of relation: authority over, finances, buys from, advises, "
                       "represents, works with (a cooperation recorded once, on the actor that leads it)."),
    ("Influenced by", 40, "The actors that influence it, by the kind of relation."),
    ("Decides in the CLD", 36, "The CLD's variables it decides."),
    ("Sources", 40, "In-text citations; the full references are on the References sheet."),
]


def sheets(actors, refs, decides, cld_labels):
    """[(name, widths, rows)]: the Actors sheet, a row per actor in actors.json's order; the
    Relations sheet, a row per relation, read "From relation To"; the References sheet, every
    reference the two cite; the Columns sheet, what each of the Actors sheet's columns holds."""
    acts = actors["actors"]
    labels = {a["id"]: a["label"] for a in acts}
    rel_in = {a["id"]: [] for a in acts}
    for a in acts:
        for r in a.get("relations", []):
            rel_in[r["to"]].append((r["kind"], a["id"]))
    # an actor's sources and its relations': every reference listed is cited on the Actors sheet
    keys = {a["id"]: sorted(set(a["sources"]) | {k for r in a.get("relations", []) for k in r["sources"]}) for a in acts}
    cites = citations(sorted({k for ks in keys.values() for k in ks}), refs)
    rows = [[c for c, _, _ in COLUMNS]]
    for a in acts:
        rows.append([a["label"], a["type"], a["level"], a["sector"], a["interest"], a["influence"], a["affected"],
                     a["influence score"], a["client"],
                     by_kind([(r["kind"], r["to"]) for r in a.get("relations", [])], labels),
                     by_kind(rel_in[a["id"]], labels),
                     "\n".join(cld_labels[e] for e in decides[a["id"]]), cite_list(keys[a["id"]], cites)])
    rels = [["From", "Relation", "To", "Description", "Sources"]] + [
        [labels[r["from"]], r["kind"], labels[r["to"]], r["description"], cite_list(r["sources"], cites)]
        for r in relations(actors)]
    references = [["Reference"]] + [[r] for r in sorted((c[2] for c in cites.values()), key=str.lower)]
    columns = [["Column", "What it holds"]] + [[c, what] for c, _, what in COLUMNS]
    return [("Actors", [w for _, w, _ in COLUMNS], rows), ("Relations", [26, 14, 26, 80, 40], rels),
            ("References", [120], references), ("Columns", [26, 120], columns)]


# --- the page --------------------------------------------------------------------------------
def page_data(actors, refs, decides, cld_labels, version):
    """What the page's panel shows per actor and relation, as page/actors.js reads it."""
    labels = {a["id"]: a["label"] for a in actors["actors"]}
    full = lambda keys: [refs[k] for k in keys]
    return {
        "actors": [{"id": a["id"], "label": a["label"], "type": a["type"], "level": a["level"],
                    "sector": a["sector"], "interest": a["interest"], "influence": a["influence"], "affected": a["affected"],
                    "influence score": a["influence score"], "client": a["client"],
                    "decides in the CLD": [cld_labels[e] for e in decides[a["id"]]], "sources": full(a["sources"])}
                   for a in actors["actors"]],
        "relations": [{"from": labels[r["from"]], "to": labels[r["to"]], "kind": r["kind"],
                       "description": r["description"], "sources": full(r["sources"])} for r in relations(actors)],
        "version": version,
    }


def page(actors, refs, decides, cld_labels, version, template):
    """docs/actors.html: the template with the question, the drawing inline and the data as JSON."""
    # "</" inside a <script> would end it early; "<\/" is the same string to JSON
    data = json.dumps(page_data(actors, refs, decides, cld_labels, version), ensure_ascii=False).replace("</", "<\\/")
    out = template
    for marker, text in (("<!-- QUESTION -->", esc(actors["question"])), ("<!-- SVG -->", svg(actors).rstrip()),
                         ("<!-- DATA -->", f'<script type="application/json" id="data">{data}</script>')):
        assert out.count(marker) == 1, f"page/actors.html must hold {marker} once"
        out = out.replace(marker, text)
    return out
