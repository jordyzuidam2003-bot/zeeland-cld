"""Draw the CLD as an SVG, from cld.json's own coordinates (y downwards).

Imported by build.py, which writes docs/figures/cld.svg and puts the same drawing inline in
docs/index.html. svg(cld) returns the drawing as a string; overlaps(cld) the warnings about
boxes that intersect and other layout faults, and tangles(cld) the crossings between links and
the links through a box, for build.py's report; boxes(cld) the geometry
build.py gives Kumu's elements.

What is drawn, from back to front:
  regions   Jordy's drawing of the subsystem regions, a PNG at its frame (backdrop.py)
  links     a quadratic Bezier from a point on the source box's edge to one on the target's,
            the ends on one edge spread along it; the sign on the link just before the
            arrowhead, a delay as two short strokes across it at the clearest place along the link
  elements  the label in a box filled with the pale tint of its SETS domain, the one place the
            domain shows in the drawing (the layout follows the loops, not the domains):
            square corners for a Stock, rounded for an Auxiliary, dashed for a Constant, a
            thick stroke for an adaptive practice
  legend    in the first bottom corner inside the frame with room for it, else below the frame
No loop marks on the full drawing: the page highlights a named loop by its button.
loop_figure(cld, loop) draws one named loop on its own (build.py writes docs/figures/named-loops/<id>.svg): its
elements evenly round one oval, clockwise from the top left, its links along it, drawn as svg()
draws them, with its mark, turning clockwise, at the oval's centre.
group_figure(cld, group) draws one group of named loops (build.py writes docs/figures/combined-loops/<id>.svg): its
loops' elements and links at the group's own `places` and `bends`, each loop's mark at `marks`,
turning the way the loop runs; group_layout(cld, group) computes those three, each loop its own
area (one wrapping another where three share one chain) and each mark with room for Kumu's label
of its loop, and marks_astray(cld, group) names a mark outside its own loop's area or inside
another's, and a label on a box or a link, for build.py's warnings;
report_panels(cld) draws every group as the report's panels (docs/figures/report-panels/<id>.svg):
its places spread over one shared frame, every panel in one viewBox size.

The link formulas are duplicated for the pages' Move mode, which redraws every link when a box moves:
link_path() and link_paths() in src/templates/move.js, for the CLD and the Actor Map, sign_position()
in src/templates/app.js; keep them and their JS twins the same.
"""

from itertools import combinations
from math import atan2, ceil, cos, hypot, pi, sin

import backdrop

# --- style -------------------------------------------------------------------------------
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
FONT_SIZE = 28
LINE_HEIGHT = 34
CHAR_WIDTH = 0.53 * FONT_SIZE  # average glyph width of the font stack, an estimate: a label wider than its box shows only on screen
WRAP = 22                      # characters per line, about
PAD_X, PAD_Y = 14, 9
STROKE, STROKE_THICK = 1.5, 5
STROKE_COLOUR = "#444444"
LINK_WIDTH = 2.5
LINK_COLOUR = {"+": "#2166AC", "-": "#B2182B"}  # by polarity (Jordy, chosen against one grey with the signs alone: the eye finds
                                                   # the − links along a loop, and an odd number makes it balancing)
SIGN_TEXT = {"+": "+", "-": "−"}
SIGN_SIZE = 42
SIGN_BACK = 50                 # a sign's centre on its link: the arrowhead (ARROW) and half a sign before the end
SIGN_HALO = 10                 # the white round a sign, which cuts its own line round it
DELAY_HALF, DELAY_GAP = 24, 8  # a delay's two strokes the height of a sign, a white cut round them, so they read at the
DELAY_WIDTH, DELAY_CUT = 5, 11  # report's print size where the signs do (Jordy, chosen between rendered versions)
DELAY_CLEAR = 55               # a delay's centre keeps this far from its link's sign, so the two never overlap (Jordy)
DELAY_MIN = 120                # the shortest link, end to end, that holds its delay and its sign apart; build.py warns below it
CORNER = 18                    # an Auxiliary's and a Constant's corner radius (Jordy, chosen between rendered versions)
LEGEND_SIZE = 52               # the legend reads at a glance, so larger than the labels (Jordy, chosen between rendered versions)
ARROW = 22                     # arrowhead length, in drawing units
TINT = {  # each box's fill: the hue of Figure 1 in the group's Project Plan, as a pale tint
    "Ecological": "#9DD9AC", "Social": "#ABC9F4", "Technological": "#FBC07C"}
# a new TINT first passes the dataviz skill's validator: black text and both link colours read
# on each tint, and the three tints read apart, for normal vision and deutan; build.py gives
# Kumu the same tints
MARGIN = 40


# --- elements -------------------------------------------------------------------------------
def wrap(label):
    """Greedy word wrap onto lines of at most about WRAP characters."""
    lines, line = [], ""
    for word in label.split():
        if line and len(line) + 1 + len(word) > WRAP:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    return lines + [line]


def boxes(cld):
    """{id: (x0, y0, x1, y1, lines)}: every element's box, fitted to its wrapped label."""
    out = {}
    for e in cld["elements"]:
        lines = wrap(e["label"])
        w = max(len(l) for l in lines) * CHAR_WIDTH + 2 * PAD_X
        h = len(lines) * LINE_HEIGHT + 2 * PAD_Y
        out[e["id"]] = (e["x"] - w / 2, e["y"] - h / 2, e["x"] + w / 2, e["y"] + h / 2, lines)
    return out


def element_svg(e, box):
    x0, y0, x1, y1, lines = box
    w, h = x1 - x0, y1 - y0
    kind = e["element type"]
    style = f'stroke="{STROKE_COLOUR}" stroke-width="{STROKE_THICK if e["adaptive practice"] else STROKE}"'
    if kind == "Constant":
        style += ' stroke-dasharray="8 5"'
    rx = 0 if kind == "Stock" else CORNER
    parts = [f'<g class="element" data-id="{e["id"]}" data-domain="{e["sets domain"]}" '
             f'data-type="{kind}" data-adaptive="{"true" if e["adaptive practice"] else "false"}">',
             f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{TINT[e["sets domain"]]}" {style}/>']
    top = y0 + PAD_Y + LINE_HEIGHT * 0.75
    for i, line in enumerate(lines):
        parts.append(f'<text x="{e["x"]:.1f}" y="{top + i * LINE_HEIGHT:.1f}" text-anchor="middle">{esc(line)}</text>')
    parts.append("</g>")
    return "\n".join(parts)


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- links ----------------------------------------------------------------------------------
def bezier(p0, p1, p2, t):
    s = 1 - t
    return (s * s * p0[0] + 2 * s * t * p1[0] + t * t * p2[0],
            s * s * p0[1] + 2 * s * t * p1[1] + t * t * p2[1])


def tangent(p0, p1, p2, t):
    return (2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0]),
            2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1]))


def inside(p, box):
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def link_path(a, b, curvature):
    """The curve from box a's border to box b's border; see the JS twin in src/templates/move.js.

    Control point: the midpoint of the chord between the two centres, moved perpendicular to the
    chord by curvature x chord length, to the left of the direction of travel on the y-down canvas
    for a positive curvature: the side Kumu bows it (checked on the project cbp-cld). The curve is cut
    where it leaves a and where it enters b, by bisection, and the piece between is again a
    quadratic Bezier (de Casteljau). Returns (p0, c, p2): start, control, end.
    """
    ca = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    cb = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    dx, dy = cb[0] - ca[0], cb[1] - ca[1]
    ctrl = ((ca[0] + cb[0]) / 2 + curvature * dy, (ca[1] + cb[1]) / 2 - curvature * dx)

    def crossing(box, p, q, r):
        """p is inside box: the t in [0, 0.5] where the curve p, q, r leaves it, by bisection."""
        lo, hi = 0.0, 0.5
        for _ in range(30):
            mid = (lo + hi) / 2
            if inside(bezier(p, q, r, mid), box):
                lo = mid
            else:
                hi = mid
        return hi

    middle = bezier(ca, ctrl, cb, 0.5)
    t0 = 0.0 if inside(middle, a) else crossing(a, ca, ctrl, cb)
    t1 = 1.0 if inside(middle, b) else 1 - crossing(b, cb, ctrl, ca)
    return sub_curve(ca, ctrl, cb, t0, t1)


# rule 2 of the layout: each link end gets its own point on the box edge it leaves or enters
GAP = 34    # least distance between two link ends on one box edge
INSET = 10  # how far a link end keeps from a box corner


def edge_of(p, box):
    """The edge of box that the border point p lies on: 0 top, 1 right, 2 bottom, 3 left."""
    d = (abs(p[1] - box[1]), abs(p[0] - box[2]), abs(p[1] - box[3]), abs(p[0] - box[0]))
    return d.index(min(d))


def spread(xs, lo, hi, gap):
    """Positions as near the sorted xs as a forward and a backward pass give, at least gap apart
    (less when the edge is too short for that), within [lo, hi]."""
    n = len(xs)
    gap = min(gap, (hi - lo) / max(n - 1, 1))
    p = [min(max(x, lo), hi) for x in xs]
    for i in range(1, n):
        p[i] = max(p[i], p[i - 1] + gap)
    if p[-1] > hi:
        p[-1] = hi
        for i in range(n - 2, -1, -1):
            p[i] = min(p[i], p[i + 1] - gap)
    return p


def link_paths(cld, bxs, key=lambda c: (c["from"], c["to"])):
    """{(from, to): (p0, c, p2)} for every connection; see the JS twin paths() in src/templates/move.js.
    `key` names each connection in the result: the Actor Map (draw_actor_map.py), where two actors can
    hold two relations, names each by its place in the list.

    Each end starts where link_path() cuts the curve between the two centres; the ends on one
    edge of a box are then spread along it, in the order they arrive, so arrowheads do not
    converge on the box's centre. The curve between the two end points has its control point
    at the chord's midpoint, moved perpendicular by curvature x chord length, as in link_path().
    """
    ends = {}
    for c in cld["connections"]:
        k = key(c)
        p0, _, p2 = link_path(bxs[c["from"]], bxs[c["to"]], c["curvature"])
        for which, eid, p in ((0, c["from"], p0), (1, c["to"], p2)):
            e = edge_of(p, bxs[eid])
            ends.setdefault((eid, e), []).append((p[0] if e in (0, 2) else p[1], k, which))
    anchor = {}
    for (eid, e), lst in ends.items():
        x0, y0, x1, y1 = bxs[eid][:4]
        lst.sort(key=lambda t: t[0])
        lo, hi = (x0 + INSET, x1 - INSET) if e in (0, 2) else (y0 + INSET, y1 - INSET)
        for (_, k, which), v in zip(lst, spread([t[0] for t in lst], lo, hi, GAP)):
            anchor[k, which] = ((v, y0) if e == 0 else (x1, v) if e == 1 else (v, y1) if e == 2 else (x0, v))
    out = {}
    for c in cld["connections"]:
        k = key(c)
        p0, p2 = anchor[k, 0], anchor[k, 1]
        dx, dy = p2[0] - p0[0], p2[1] - p0[1]
        bow = c["curvature"]
        out[k] = (p0, ((p0[0] + p2[0]) / 2 + bow * dy, (p0[1] + p2[1]) / 2 - bow * dx), p2)
    return out


def lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def sub_curve(p0, p1, p2, t0, t1):
    """The piece [t0, t1] of a quadratic Bezier is one too: split at t0, keep the right piece
    (B(t0), lerp(p1, p2, t0), p2), split that at s and keep the left piece."""
    r0, r1 = bezier(p0, p1, p2, t0), lerp(p1, p2, t0)
    s = (t1 - t0) / (1 - t0) if t0 < 1 else 0
    return r0, lerp(r0, r1, s), bezier(p0, p1, p2, t1)


def link_svg(c, pieces, spot=None):
    """The link as joined quadratic Beziers, pieces [(p0, ctrl, p2), ...]: one in the full drawing,
    several along a one-loop figure's oval; the sign on the last piece, a delay at `spot` on the one
    piece if given (the full drawing's delay_spots()), else halfway along it."""
    colour = LINK_COLOUR[c["polarity"]]
    d = f"M {pieces[0][0][0]:.1f} {pieces[0][0][1]:.1f} " + " ".join(f"Q {q[0]:.1f} {q[1]:.1f} {r[0]:.1f} {r[1]:.1f}" for _, q, r in pieces)
    parts = [f'<g class="link" data-from="{c["from"]}" data-to="{c["to"]}" data-sign="{c["polarity"]}" '
             f'data-delay="{"true" if c["delay"] else "false"}" data-curvature="{c["curvature"]}"'
             + (f' data-delay-t="{spot:.2f}"' if spot is not None else "") + ">",
             f'<path class="link-path" d="{d}" '
             f'fill="none" stroke="{colour}" stroke-width="{LINK_WIDTH}" marker-end="url(#arrow-{"plus" if c["polarity"] == "+" else "minus"})"/>']
    sx, sy = sign_position(*pieces[-1])
    parts.append(f'<text class="sign" x="{sx:.1f}" y="{sy:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="{SIGN_SIZE}" font-weight="bold" fill="{colour}" stroke="white" stroke-width="{SIGN_HALO}" paint-order="stroke">{SIGN_TEXT[c["polarity"]]}</text>')
    if c["delay"]:
        d = delay_path(*pieces[0], spot) if spot is not None else delay_path(*halfway(pieces))
        parts.append(f'<path class="delay-cut" d="{d}" stroke="white" stroke-width="{DELAY_CUT}" fill="none"/>')
        parts.append(f'<path class="delay" d="{d}" stroke="{STROKE_COLOUR}" stroke-width="{DELAY_WIDTH}" fill="none"/>')
    parts.append("</g>")
    return "\n".join(parts)


def sign_position(p0, ctrl, p2, back=SIGN_BACK):
    """On the link itself, `back` units (straight line) before its end, by bisection on t: a sign
    on its own line can only be read as that link's, wherever the boxes move (Jordy, chosen
    between rendered versions; rejected: beside the arrowhead, on the outside of the bow or on the
    side clear of other links, where heads that land close together share their signs)."""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        q = bezier(p0, ctrl, p2, mid)
        if hypot(q[0] - p2[0], q[1] - p2[1]) > back:
            lo = mid
        else:
            hi = mid
    return bezier(p0, ctrl, p2, hi)


def delay_t(p0, ctrl, p2):
    """Where a delay sits on one curve: at its middle, or on a short link further back, DELAY_CLEAR
    before the sign, so the two never overlap (Jordy); see the JS twin delayT() in src/templates/app.js."""
    back = SIGN_BACK + DELAY_CLEAR
    mid = bezier(p0, ctrl, p2, 0.5)
    if hypot(mid[0] - p2[0], mid[1] - p2[1]) >= back or hypot(p0[0] - p2[0], p0[1] - p2[1]) < back:
        return 0.5
    lo, hi = 0.0, 0.5
    for _ in range(40):
        m = (lo + hi) / 2
        q = bezier(p0, ctrl, p2, m)
        if hypot(q[0] - p2[0], q[1] - p2[1]) > back:
            lo = m
        else:
            hi = m
    return lo


def delay_spots(cld, paths):
    """{(from, to): t}: where each delayed link's mark sits on its curve in the full drawing: its
    own `delay at` if it has one (Jordy drags it on the page), else the place along it furthest
    from other links and boxes, near its middle where several are as clear, so the mark never
    sits where lines cross (Jordy). A mark keeps DELAY_CLEAR from its sign and from other marks."""
    pts = {k: [bezier(*p[0], i / 12) for i in range(13)] for k, p in paths.items()}
    bxs = boxes(cld)
    near = lambda f, x, y, m=80: f[0] - m <= x <= f[2] + m and f[1] - m <= y <= f[3] + m
    frame = {k: (min(x for x, _ in p), min(y for _, y in p), max(x for x, _ in p), max(y for _, y in p)) for k, p in pts.items()}

    def to_segment(x, y, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        u = max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy or 1)))
        return hypot(x - a[0] - u * dx, y - a[1] - u * dy)

    out, placed = {}, []
    for c in cld["connections"]:
        k = (c["from"], c["to"])
        if not c["delay"]:
            continue
        p0, ctrl, p2 = paths[k][0]
        if "delay at" in c:
            out[k] = c["delay at"]
            placed.append(bezier(p0, ctrl, p2, c["delay at"]))
            continue
        sign = sign_position(p0, ctrl, p2)
        best, best_t = None, None
        for i in range(3, 23):
            t = i / 25
            x, y = bezier(p0, ctrl, p2, t)
            if hypot(x - sign[0], y - sign[1]) < DELAY_CLEAR or any(
                    hypot(max(bxs[e][0] - x, x - bxs[e][2], 0), max(bxs[e][1] - y, y - bxs[e][3], 0)) < DELAY_HALF + 10 for e in k):
                continue
            clear = 80.0
            for j, q in pts.items():
                if j != k and near(frame[j], x, y):
                    clear = min(clear, min(to_segment(x, y, q[n], q[n + 1]) for n in range(12)))
            for j, b in bxs.items():
                if j not in k:
                    clear = min(clear, hypot(max(b[0] - x, x - b[2], 0), max(b[1] - y, y - b[3], 0)))
            clear = min([clear] + [hypot(x - m[0], y - m[1]) - DELAY_CLEAR for m in placed])
            score = clear - 14 * abs(t - 0.5)
            if best is None or score > best:
                best, best_t = score, t
        out[k] = delay_t(p0, ctrl, p2) if best_t is None else best_t
        placed.append(bezier(p0, ctrl, p2, out[k]))
    return out


def halfway(pieces, steps=200):
    """(p0, ctrl, p2, t): the point halfway along a link by length. A link of several pieces (a
    loop figure's) is measured along them, since the middle piece's own middle can sit near an
    end, on the sign (Jordy); one piece keeps its t = 0.5, as app.js's delayPath() draws it."""
    if len(pieces) == 1:
        return (*pieces[0], delay_t(*pieces[0]))
    walk = []  # (length so far, piece, t)
    total = 0.0
    for p in pieces:
        prev = p[0]
        for k in range(1, steps + 1):
            q = bezier(*p, k / steps)
            total += hypot(q[0] - prev[0], q[1] - prev[1])
            walk.append((total, p, k / steps))
            prev = q
    _, p, t = next(w for w in walk if w[0] >= total / 2)
    return (*p, t)


def delay_path(p0, ctrl, p2, t=0.5, half=DELAY_HALF, gap=DELAY_GAP):
    x, y = bezier(p0, ctrl, p2, t)
    tx, ty = tangent(p0, ctrl, p2, t)
    n = hypot(tx, ty) or 1
    ux, uy = tx / n, ty / n
    nx, ny = -uy, ux
    d = []
    for k in (-gap, gap):
        cx, cy = x + ux * k, y + uy * k
        d.append(f"M {cx - nx * half:.1f} {cy - ny * half:.1f} L {cx + nx * half:.1f} {cy + ny * half:.1f}")
    return " ".join(d)


# --- loops ----------------------------------------------------------------------------------
def loop_svg(loop, centre, clockwise=True):
    """The loop's mark at centre: its id in a three-quarter circle that ends in an arrowhead,
    turning the way the loop runs on the page: clockwise in a one-loop figure; in a combined
    loop's figure two loops sharing a chain run opposite ways (group_layout())."""
    cx, cy = centre
    r = MARK_R
    # from the top clockwise round to the left, or anticlockwise round to the right; y grows downwards
    a0, a1 = -pi / 2, (pi if clockwise else 0)
    start = (cx + r * cos(a0), cy + r * sin(a0))
    end = (cx + r * cos(a1), cy + r * sin(a1))
    return "\n".join([
        f'<g class="loop" data-id="{loop["id"]}">',
        f'<path d="M {start[0]:.1f} {start[1]:.1f} A {r} {r} 0 1 {1 if clockwise else 0} {end[0]:.1f} {end[1]:.1f}" fill="none" '
        f'stroke="{STROKE_COLOUR}" stroke-width="{LINK_WIDTH}" marker-end="url(#arrow-grey)"/>',
        f'<text class="loop-id" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="{SIGN_SIZE}" font-weight="bold">{esc(loop["id"])}</text>',
        "</g>"])


# --- regions ----------------------------------------------------------------------------------
# The page draws Jordy's regions (backdrop.py). regions() still lays out the generated ones, whose
# border steers legend_spot() clear of the gap and whose names' places overlaps() keeps links off:
# his drawing follows the same split, the names in the same top corners.
# One region per subsystem behind everything: the first subsystem left of one smooth border, the
# second right of it, together filling the drawing's rounded frame, a white gap of even width
# between them (Jordy: the split across the canvas, the border as a gentle wave). The fills are
# faint so the SETS tints stay the boxes' colour; they differ by OKLab dE 7.3 (normal vision) and
# 6.7 (protan), under the dataviz validator's floor for marks told apart by colour alone, which is
# why each region carries its name; both link colours keep 3:1 on both fills.
REGION = {"Water and soil": "#D6E6F5", "Agricultural economy": "#F7E3C4"}
# Each name in spaced bold capitals at its region's top outer corner, a darker shade of its fill
# (Jordy, chosen between rendered versions: inside the region, standing out a little; contrast on
# its fill 6.3:1 and 5.8:1)
REGION_NAME_COLOUR = {"Water and soil": "#2C5378", "Agricultural economy": "#74501F"}
REGION_NAME_SIZE = 56
REGION_NAME_SPACING = 8   # letter spacing
REGION_NAME_INSET = 280   # from the frame's side to the name's outer end: clear of the rounded corner (Jordy)
REGION_NAME_TOP = 170     # from the frame's top to the name's middle
GRID = 20           # the grid the region outlines are traced on
FRAME_PAD = 110     # the frame's margin around the boxes
FRAME_CORNER = 160  # the frame's corner radius
BORDER_GAP = 40     # the white gap's width
BORDER_CLEAR = 30   # how far every box keeps from the gap
BORDER_TENSION = 0.008  # how hard the border is pulled straight: 0.008 a gentle wave (Jordy), 0.05 nearly straight


def name_box(n, frame, first):
    """(x0, y0, x1, y1): the box of the region name n, at the top left of the frame for the
    first subsystem, the top right for the second; its width estimated from the capitals' glyphs."""
    w = len(n) * (REGION_NAME_SIZE * 0.68 + REGION_NAME_SPACING)
    y = frame[1] + REGION_NAME_TOP
    x0 = frame[0] + REGION_NAME_INSET if first else frame[2] - REGION_NAME_INSET - w
    return (x0, y - REGION_NAME_SIZE / 2, x0 + w, y + REGION_NAME_SIZE / 2)


def corridor(left, right, y0, ny):
    """Per grid row from y0, the range (lo, hi) the border may take: right of every `left` box and
    left of every `right` box that reaches the row, each kept BORDER_CLEAR from the gap."""
    pad = BORDER_GAP / 2 + BORDER_CLEAR
    lo, hi = [-1e9] * ny, [1e9] * ny
    for j in range(ny):
        y = y0 + j * GRID
        for b in left:
            if b[1] - pad <= y <= b[3] + pad:
                lo[j] = max(lo[j], b[2] + pad)
        for b in right:
            if b[1] - pad <= y <= b[3] + pad:
                hi[j] = min(hi[j], b[0] - pad)
    return lo, hi


def region_border(left, right, y0, ny):
    """Per grid row, the x of the border between the boxes `left` and `right`, and the rows where
    the two sides leave it no room. The smoothest curve through the corridor: it starts in each
    row's corridor (between its neighbours where no box constrains a row), is smoothed by its
    fourth difference and pulled straight by BORDER_TENSION, clamped into the corridor after
    every step, and runs straight up and down beyond the outermost boxes."""
    lo, hi = corridor(left, right, y0, ny)
    known = [(lo[j] + hi[j]) / 2 if lo[j] > -1e9 and hi[j] < 1e9 else lo[j] if lo[j] > -1e9
             else hi[j] if hi[j] < 1e9 else None for j in range(ny)]
    rows = [j for j in range(ny) if known[j] is not None]
    j0, j1 = rows[0], rows[-1]
    x = known[:]
    for j in range(j0, j1 + 1):
        if x[j] is None:
            a = max(k for k in rows if k < j)
            b = min(k for k in rows if k > j)
            x[j] = known[a] + (known[b] - known[a]) * (j - a) / (b - a)
    g = lambda k: x[2 * j0 - k if k < j0 else 2 * j1 - k if k > j1 else k]  # mirrored ends
    for _ in range(20000):
        nxt = x[:]
        for j in range(j0, j1 + 1):
            nxt[j] = (x[j] - 0.04 * (g(j - 2) - 4 * g(j - 1) + 6 * x[j] - 4 * g(j + 1) + g(j + 2))
                      + BORDER_TENSION * (g(j - 1) - 2 * x[j] + g(j + 1)))
            nxt[j] = (lo[j] + hi[j]) / 2 if lo[j] > hi[j] else min(max(nxt[j], lo[j]), hi[j])
        x = nxt
    x = [x[j0]] * j0 + x[j0:j1 + 1] + [x[j1]] * (ny - 1 - j1)
    return x, [j for j in range(ny) if lo[j] > hi[j]]


def contours(val, nx, ny, x0, y0):
    """Closed polylines where val crosses 0 (marching squares); val[j][i] at (x0 + i GRID, y0 + j GRID)."""
    def pt(key):
        kind, i, j = key
        a, b = (val[j][i], val[j][i + 1]) if kind == "h" else (val[j][i], val[j + 1][i])
        t = a / (a - b)
        return (x0 + (i + t) * GRID, y0 + j * GRID) if kind == "h" else (x0 + i * GRID, y0 + (j + t) * GRID)
    nb = {}
    for j in range(ny - 1):
        for i in range(nx - 1):
            c = [val[j][i] > 0, val[j][i + 1] > 0, val[j + 1][i + 1] > 0, val[j + 1][i] > 0]
            top, right, bottom, left = ("h", i, j), ("v", i + 1, j), ("h", i, j + 1), ("v", i, j)
            edges = [e for e, (p, q) in zip((top, right, bottom, left), ((0, 1), (1, 2), (3, 2), (0, 3))) if c[p] != c[q]]
            if len(edges) == 2:
                segs = [edges]
            elif len(edges) == 4:  # a saddle: the centre decides which corners join
                centre = (val[j][i] + val[j][i + 1] + val[j + 1][i + 1] + val[j + 1][i]) > 0
                segs = [[top, left], [right, bottom]] if centre != c[0] else [[top, right], [bottom, left]]
            else:
                segs = []
            for a, b in segs:
                nb.setdefault(a, []).append(b)
                nb.setdefault(b, []).append(a)
    loops, seen = [], set()
    for start in nb:
        if start in seen:
            continue
        loop, prev, cur = [], None, start
        while cur not in seen:
            seen.add(cur)
            loop.append(pt(cur))
            nxt = [k for k in nb[cur] if k != prev and k not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
        if len(loop) > 8:
            loops.append(loop)
    return loops


def chaikin(loop, rounds=3):
    """Corner cutting: the traced outline's grid steps smoothed away."""
    for _ in range(rounds):
        out = []
        for k in range(len(loop)):
            p, q = loop[k], loop[(k + 1) % len(loop)]
            out += [(0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]),
                    (0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1])]
        loop = out
    return loop


def regions(cld, bxs):
    """(svg, frame, crowded, border): the subsystems' regions, their frame (x0, y0, x1, y1), the
    grid rows where the boxes leave the border no room, and the border as (y of its first grid row,
    its x per row). Each name sits at its region's top outer corner (name_box()); overlaps() warns
    when a link runs under it."""
    names = list(REGION)
    members = {n: [bxs[e["id"]] for e in cld["elements"] if e["subsystem"] == n] for n in names}
    allb = list(bxs.values())
    fx0, fy0 = min(b[0] for b in allb) - FRAME_PAD, min(b[1] for b in allb) - FRAME_PAD
    fx1, fy1 = max(b[2] for b in allb) + FRAME_PAD, max(b[3] for b in allb) + FRAME_PAD
    x0, y0 = fx0 - 2 * GRID, fy0 - 2 * GRID
    nx, ny = int((fx1 - fx0) / GRID) + 5, int((fy1 - fy0) / GRID) + 5
    border, crowded = region_border(members[names[0]], members[names[1]], y0, ny)
    r = FRAME_CORNER

    def frame(p):
        qx = max(fx0 + r - p[0], 0, p[0] - (fx1 - r))
        qy = max(fy0 + r - p[1], 0, p[1] - (fy1 - r))
        return r - (qx * qx + qy * qy) ** 0.5 if qx and qy else min(p[0] - fx0, fx1 - p[0], p[1] - fy0, fy1 - p[1])

    parts = []
    for side, n in ((1, names[0]), (-1, names[1])):
        val = [[-1.0] * nx for _ in range(ny)]
        for j in range(1, ny - 1):
            for i in range(1, nx - 1):
                p = (x0 + i * GRID, y0 + j * GRID)
                v = min(frame(p), side * (border[j] - p[0]) - BORDER_GAP / 2)
                val[j][i] = v if v != 0 else -1e-6
        d = " ".join("M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in chaikin(l)) + " Z"
                     for l in contours(val, nx, ny, x0, y0))
        nb = name_box(n, (fx0, fy0, fx1, fy1), side == 1)
        name = (f'<text class="region-name" x="{nb[0]:.1f}" y="{(nb[1] + nb[3]) / 2:.1f}" '
                f'dominant-baseline="central" font-size="{REGION_NAME_SIZE}" font-weight="bold" '
                f'letter-spacing="{REGION_NAME_SPACING}" fill="{REGION_NAME_COLOUR[n]}">{esc(n.upper())}</text>')
        parts.append(f'<g class="region" data-subsystem="{n}"><path d="{d}" fill="{REGION[n]}" fill-rule="evenodd"/>{name}</g>')
    return "\n".join(parts), (fx0, fy0, fx1, fy1), crowded, (y0, border)


# --- legend ---------------------------------------------------------------------------------
def legend_svg(x, y):
    """The legend, its title's baseline at (x, y); returns (svg, width, height)."""
    f = LEGEND_SIZE
    row, sw, sh = f * 1.5, f * 2.6, f * 0.9  # row height, swatch width and height
    items = []

    def swatch(i, body, text):
        yy = y + f * 1.4 + i * row
        items.append(body(x, yy))
        items.append(f'<text x="{x + sw + f * 0.6:.1f}" y="{yy + f * 0.35:.1f}" font-size="{f}">{text}</text>')

    items.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{f}" font-weight="bold">Legend</text>')
    box = lambda xx, yy, extra, rx, width=STROKE, fill="white": (f'<rect x="{xx:.1f}" y="{yy - sh / 2:.1f}" width="{sw:.1f}" height="{sh:.1f}" rx="{rx}" fill="{fill}" '
                                                                 f'stroke="{STROKE_COLOUR}" stroke-width="{width}" {extra}/>')
    for i, (domain, tint) in enumerate(TINT.items()):
        swatch(i, lambda xx, yy, t=tint: box(xx, yy, "", CORNER, fill=t), f"{domain} domain")
    n = len(TINT)
    swatch(n, lambda xx, yy: box(xx, yy, "", 0), "Stock")
    swatch(n + 1, lambda xx, yy: box(xx, yy, "", CORNER), "Auxiliary")
    swatch(n + 2, lambda xx, yy: box(xx, yy, 'stroke-dasharray="8 5"', CORNER), "Constant (exogenous)")
    swatch(n + 3, lambda xx, yy: box(xx, yy, "", CORNER, STROKE_THICK), "Adaptive practice")
    line = lambda xx, yy, colour, name: (f'<path d="M {xx:.1f} {yy:.1f} L {xx + sw - ARROW:.1f} {yy:.1f}" stroke="{colour}" '
                                         f'stroke-width="{LINK_WIDTH}" fill="none" marker-end="url(#arrow-{name})"/>')
    swatch(n + 4, lambda xx, yy: line(xx, yy, LINK_COLOUR["+"], "plus"), "+ : change in the same direction")
    swatch(n + 5, lambda xx, yy: line(xx, yy, LINK_COLOUR["-"], "minus"), "− : change in the opposite direction")
    marks = lambda xx, yy: " ".join(f"M {xx + sw / 2 + k:.1f} {yy - DELAY_HALF:.1f} L {xx + sw / 2 + k:.1f} {yy + DELAY_HALF:.1f}"
                                    for k in (-DELAY_GAP, DELAY_GAP))
    swatch(n + 6, lambda xx, yy: (f'<path d="M {xx:.1f} {yy:.1f} L {xx + sw:.1f} {yy:.1f}" stroke="{STROKE_COLOUR}" stroke-width="{LINK_WIDTH}"/>'
                                  f'<path d="{marks(xx, yy)}" stroke="white" stroke-width="{DELAY_CUT}" fill="none"/>'
                                  f'<path d="{marks(xx, yy)}" stroke="{STROKE_COLOUR}" stroke-width="{DELAY_WIDTH}" fill="none"/>'), "Delay")
    height = f * 1.4 + (n + 7) * row
    width = sw + f * 0.6 + len("− : change in the opposite direction") * CHAR_WIDTH / FONT_SIZE * f
    return '<g class="legend">\n' + "\n".join(items) + "\n</g>", width, height


# --- the drawing ----------------------------------------------------------------------------
def head(vb):
    """The opening of a drawing with the viewBox vb: the svg tag, the arrowheads, a white ground."""
    arrow = lambda name, colour: (f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="{ARROW}" '
                                  f'markerHeight="{ARROW}" markerUnits="userSpaceOnUse" orient="auto">'
                                  f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{colour}"/></marker>')
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb[0]:.0f} {vb[1]:.0f} {vb[2]:.0f} {vb[3]:.0f}" '
        f'font-family="{FONT}" font-size="{FONT_SIZE}" fill="black">',
        "<defs>", arrow("plus", LINK_COLOUR["+"]), arrow("minus", LINK_COLOUR["-"]), arrow("grey", STROKE_COLOUR), "</defs>",
        f'<rect x="{vb[0]:.0f}" y="{vb[1]:.0f}" width="{vb[2]:.0f}" height="{vb[3]:.0f}" fill="white"/>']


def links_and_elements(cld, bxs, paths, spots={}):
    """The links, then the elements over them: what svg() and loop_figure() both draw; paths gives
    each link its pieces (link_svg())."""
    return ['<g class="links">', *(link_svg(c, paths[c["from"], c["to"]], spots.get((c["from"], c["to"]))) for c in cld["connections"]), "</g>",
            '<g class="elements">', *(element_svg(e, bxs[e["id"]]) for e in cld["elements"]), "</g>"]


LEGEND_INSET = 70  # the legend inside the frame: clear of its rounded corner
LEGEND_CLEAR = 30  # ... and this far from every box, link and the border's gap


def legend_spot(bxs, paths, frame, border, lw, lh):
    """(x, y) for legend_svg() in the first bottom corner inside the frame, left then right, where
    the legend keeps clear of every box and link and lies wholly in one region; None when neither
    has room (Jordy, chosen between rendered versions: inside the frame where the drawing leaves
    room, so the drawing takes no more of an A4 page than it needs)."""
    fx0, fy0, fx1, fy1 = frame
    gy0, xs = border
    pts = [bezier(*p, t / 40) for p in paths.values() for t in range(41)]
    for left in (True, False):
        x0 = fx0 + LEGEND_INSET if left else fx1 - LEGEND_INSET - lw
        y0 = fy1 - LEGEND_INSET - lh
        r = (x0 - LEGEND_CLEAR, y0 - LEGEND_CLEAR, x0 + lw + LEGEND_CLEAR, y0 + lh + LEGEND_CLEAR)
        if any(b[0] < r[2] and r[0] < b[2] and b[1] < r[3] and r[1] < b[3] for b in bxs.values()):
            continue
        if any(r[0] < p[0] < r[2] and r[1] < p[1] < r[3] for p in pts):
            continue
        rows = [x for j, x in enumerate(xs) if r[1] <= gy0 + j * GRID <= r[3]]
        if any((r[2] > x - BORDER_GAP / 2) if left else (r[0] < x + BORDER_GAP / 2) for x in rows):
            continue
        return x0, y0 + LEGEND_SIZE  # legend_svg()'s y is the title's baseline
    return None


def svg(cld):
    bxs = boxes(cld)
    paths = link_paths(cld, bxs)
    # Jordy's drawing of the regions behind it all, its frame the drawing's (backdrop.py); the
    # generated border only steers the legend clear of the gap between the regions
    _, _, _, border = regions(cld, bxs)
    frame = backdrop.frame("cld")
    x0, y0, x1, y1 = frame
    _, lw, lh = legend_svg(0, 0)
    spot = legend_spot(bxs, paths, frame, border, lw, lh)
    if spot:
        legend, _, _ = legend_svg(*spot)
    else:
        legend, lw, lh = legend_svg(x0, y1 + MARGIN)
        y1 += MARGIN + lh
        x1 = max(x1, x0 + lw)
    vb = (x0 - MARGIN, y0 - MARGIN, x1 - x0 + 2 * MARGIN, y1 - y0 + 2 * MARGIN)
    parts = [*head(vb), '<g class="regions">', backdrop.image_svg("cld"), "</g>", *links_and_elements(cld, bxs, {k: [p] for k, p in paths.items()}, delay_spots(cld, {k: [p] for k, p in paths.items()})), legend, "</svg>"]
    return "\n".join(parts) + "\n"


MARK_R = 48  # the loop mark's radius: it reads at the size of the signs


# Kumu writes each loop's label, "<id> <name>", on its map, centred at the loop's position, behind
# the boxes (README's Kumu), so a mark's room holds the label at its size, measured in a restore
# (cbp1-v4): Kumu wraps the label greedily, a line ending once it holds KUMU_WRAP characters or
# more, and draws text at KUMU_TEXT of its font-size in map units, lines KUMU_LINE of that apart.
KUMU_LOOP_FONT = 42   # font-size under `loop` in the loop maps' view: the boxes' (cld-view.scss), so a map has one text size
KUMU_TEXT = 0.693
KUMU_WRAP = 20
KUMU_GLYPH = 0.5      # a glyph's average width over the drawn size: 0.47 measured on Kumu's font, rounded up
KUMU_LINE = 1.25      # 1.23 measured
LABEL_CLEAR_BOX = 50  # a label's room: this far from every box, as a mark kept before the labels grew
LABEL_CLEAR_LINK = 30  # ... and from every link


def kumu_label(loop):
    """The lines Kumu wraps a loop's label into.

    >>> kumu_label({"id": "R4", "name": "Storage keeps up the income that pays for it"})
    ['R4 Storage keeps up the', 'income that pays for', 'it']
    >>> kumu_label({"id": "B6", "name": "Farms store water when harvests fall"})
    ['B6 Farms store water', 'when harvests fall']
    """
    lines, line = [], ""
    for word in f'{loop["id"]} {loop["name"]}'.split():
        line = f"{line} {word}" if line else word
        if len(line) >= KUMU_WRAP:
            lines, line = lines + [line], ""
    return lines + ([line] if line else [])


def kumu_label_half(loop):
    """(half width, half height) of the loop's label as Kumu draws it at KUMU_LOOP_FONT, at least
    the page's mark (MARK_R), which sits at the same spot."""
    size, lines = KUMU_LOOP_FONT * KUMU_TEXT, kumu_label(loop)
    return max(max(map(len, lines)) * KUMU_GLYPH * size / 2, MARK_R), max(len(lines) * KUMU_LINE * size / 2, MARK_R)


def label_fits(m, half, rects, points):
    """Whether a label of half size `half` centred at m keeps LABEL_CLEAR_BOX from each rect (x0, y0,
    x1, y1) and LABEL_CLEAR_LINK from each point on a link."""
    def to_rect(r):
        return hypot(max(r[0] - m[0] - half[0], m[0] - half[0] - r[2], 0), max(r[1] - m[1] - half[1], m[1] - half[1] - r[3], 0))
    return (all(to_rect(r) >= LABEL_CLEAR_BOX for r in rects)
            and all(hypot(max(abs(p[0] - m[0]) - half[0], 0), max(abs(p[1] - m[1]) - half[1], 0)) >= LABEL_CLEAR_LINK for p in points))


OVAL_ASPECT = 1.5  # a one-loop figure's oval, its width over its height: the boxes are wider than tall
OVAL_GAP = 150     # the least gap between two boxes of a one-loop figure: room for an arrowhead and its sign


def oval(cld, loop):
    """(elements, bxs, pieces, middles): one named loop laid out as an oval for its figure; middles
    holds each link's point on the oval midway, by angle, between its two elements' centres.

    Its elements evenly spaced on an ellipse round (0, 0), in the loop's order, clockwise, the
    path's first element at the top left and the second at the top right, so the eye starts left
    and reads to the right (Jordy, who disliked the anticlockwise figures that turning the way
    the loop runs in the full drawing gave); the ellipse just large enough that every two boxes keep
    OVAL_GAP apart and the mark has room at its centre for Kumu's label (kumu_label_half()), clear
    of the boxes and of the links as Kumu draws them (oval_layout()). Each link is the piece of the ellipse from
    its source's box border to its target's, as quadratic Beziers of at most 45 degrees, each with
    its control point where the ellipse's tangents at its two ends meet, so the links run along the
    oval (Jordy, chosen between rendered versions: the loop at its places in the full drawing drew
    R4 and R8 lopsided, with long sweeping links)."""
    path = loop["path"]
    n = len(path)
    E = {e["id"]: e for e in cld["elements"]}
    # with y downwards a growing angle turns clockwise on the page; the first element half a step
    # left of the top, the second half a step right of it
    ang = [-pi / 2 - pi / n + 2 * pi * k / n for k in range(n)]
    els = [dict(E[i]) for i in path]
    gap = lambda p, q: max(p[0] - q[2], q[0] - p[2], p[1] - q[3], q[1] - p[3])
    ry = 100
    while True:
        rx = OVAL_ASPECT * ry
        for e, a in zip(els, ang):
            e["x"], e["y"] = rx * cos(a), ry * sin(a)
        bxs = boxes({"elements": els})
        centres = {e["id"]: (e["x"], e["y"]) for e in els}
        curves = [q for k in range(n) for q in link_curve(
            centres[path[k]], centres[path[(k + 1) % n]],
            bend_through(centres[path[k]], centres[path[(k + 1) % n]], (rx * cos(ang[k] + pi / n), ry * sin(ang[k] + pi / n))))]
        if (label_fits(OVAL_MARK, kumu_label_half(loop), [b[:4] for b in bxs.values()], curves)
                and all(gap(bxs[p], bxs[q]) >= OVAL_GAP for k, p in enumerate(path) for q in path[k + 1:])):
            break
        ry += 10
    at = lambda t: (rx * cos(t), ry * sin(t))

    def border(t0, t1, box):
        """Where the ellipse crosses box's border, between t0 inside it and t1 outside."""
        for _ in range(40):
            tm = (t0 + t1) / 2
            t0, t1 = (tm, t1) if inside(at(tm), box) else (t0, tm)
        return (t0 + t1) / 2

    pieces = {}
    for k in range(n):
        a, b, step = path[k], path[(k + 1) % n], 2 * pi / n
        t0, t1 = border(ang[k], ang[k] + step, bxs[a]), border(ang[k] + step, ang[k], bxs[b])
        m = ceil(abs(t1 - t0) / (pi / 4))
        h = (t1 - t0) / (2 * m)
        # a circle's arc of half-angle h has its control point on its middle radius, 1 / cos(h) out;
        # the ellipse is a stretched circle, and stretching keeps where tangents meet
        pieces[a, b] = [(at(t0 + 2 * h * i), (rx * cos(t0 + 2 * h * i + h) / cos(h), ry * sin(t0 + 2 * h * i + h) / cos(h)),
                         at(t0 + 2 * h * (i + 1))) for i in range(m)]
    middles = {(path[k], path[(k + 1) % n]): at(ang[k] + pi / n) for k in range(n)}
    return els, bxs, pieces, middles


OVAL_MARK = (0, 0)  # a one-loop figure's mark: the oval's centre


# How Kumu draws a curvature, measured on its own arcs in a restored export (README's Kumu): an arc
# through both box centres, bowing left of the link's direction for a positive curvature, about
# curvature x half the centres' distance out at its middle; under KUMU_STRAIGHT a straight line
KUMU_STRAIGHT = 0.1


def oval_layout(cld, loop):
    """(places, bends, marks): the oval of loop_figure() in the shape of a group's `places`, `bends`
    and `marks` in cld.json, for build.py's Kumu map of the loop. Kumu draws a link from centre to
    centre, so each bend is the curvature (link_path()) whose curve passes through the oval midway
    between its two elements, and the link runs along the oval as in the figure."""
    els, _, _, middles = oval(cld, loop)
    at = {e["id"]: (e["x"], e["y"]) for e in els}
    bends = {}
    for (a, b), m in middles.items():
        (ax, ay), (bx, by) = at[a], at[b]
        dx, dy = bx - ax, by - ay
        # a quadratic curve passes (start + 2 control + end) / 4 halfway, so through m its control
        # lies 2 (m - chord middle) from the chord's middle; link_path() moves it curvature (dy, -dx)
        ox, oy = 2 * (m[0] - (ax + bx) / 2), 2 * (m[1] - (ay + by) / 2)
        k = round((ox * dy - oy * dx) / (dx * dx + dy * dy), 3)
        # Kumu draws a bow under KUMU_STRAIGHT straight, so the smallest it draws, on the oval's side
        bends[f"{a} -> {b}"] = k if abs(k) >= KUMU_STRAIGHT else (KUMU_STRAIGHT if k > 0 else -KUMU_STRAIGHT)
    return {i: [round(x), round(y)] for i, (x, y) in at.items()}, bends, {loop["id"]: list(OVAL_MARK)}


def loop_figure(cld, loop):
    """One named loop on its own, for the report: laid out as an oval (oval()), its elements and links
    drawn as svg() draws them, its mark at the oval's centre, turning clockwise as the oval does. No
    regions and no legend: the figure stands beside the full drawing."""
    els, bxs, pieces, _ = oval(cld, loop)
    sub = {"elements": els, "connections": [c for c in cld["connections"] if (c["from"], c["to"]) in pieces]}
    ring = [bezier(*p, t / 10) for ps in pieces.values() for p in ps for t in range(11)]
    # the frame: the boxes and the curves, with room for a sign on a curve
    xs = [b[k] for b in bxs.values() for k in (0, 2)] + [p[0] for p in ring]
    ys = [b[k] for b in bxs.values() for k in (1, 3)] + [p[1] for p in ring]
    pad = MARGIN + SIGN_SIZE
    vb = (min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
    parts = [*head(vb), *links_and_elements(sub, bxs, pieces), loop_svg(loop, OVAL_MARK), "</svg>"]
    return "\n".join(parts) + "\n"


def group_links(cld, group):
    """The (from, to) of each link on the group's loops, in the order the loops run."""
    paths = {loop["id"]: loop["path"] for loop in cld["loops"]}
    seen = {}
    for name in group["loops"]:
        p = paths[name]
        seen.update(((a, b), None) for a, b in zip(p, p[1:] + p[:1]))
    return list(seen)


def group_cld(cld, group):
    """The group's own small drawing, in cld.json's shape: only its loops' elements and links, at
    its places and bends. A link keeps no `delay at`: that is a place on the full drawing's curve."""
    by_id, by_link = {e["id"]: e for e in cld["elements"]}, {(c["from"], c["to"]): c for c in cld["connections"]}
    elements = [dict(by_id[i], x=x, y=y) for i, (x, y) in group["places"].items()]
    connections = [{**{k: v for k, v in by_link[a, b].items() if k != "delay at"}, "curvature": group["bends"][f"{a} -> {b}"]}
                   for a, b in group_links(cld, group)]
    return {"elements": elements, "connections": connections}


def group_frame(cld, group):
    """(x0, y0, x1, y1): what group_figure() draws, its boxes, curves and marks, with a margin."""
    sub = group_cld(cld, group)
    bxs = boxes(sub)
    curve = [bezier(*p, t / 10) for ps in group_pieces(sub, bxs).values() for p in ps for t in range(11)]
    # each mark with its label as Kumu draws it there (kumu_label_half())
    loops = {loop["id"]: loop for loop in cld["loops"]}
    marks = [(m, kumu_label_half(loops[i])) for i, m in group["marks"].items()]
    pad = MARGIN + SIGN_SIZE
    return (min(*(b[0] for b in bxs.values()), *(p[0] for p in curve), *(m[0] - h[0] for m, h in marks)) - pad,
            min(*(b[1] for b in bxs.values()), *(p[1] for p in curve), *(m[1] - h[1] for m, h in marks)) - pad,
            max(*(b[2] for b in bxs.values()), *(p[0] for p in curve), *(m[0] + h[0] for m, h in marks)) + pad,
            max(*(b[3] for b in bxs.values()), *(p[1] for p in curve), *(m[1] + h[1] for m, h in marks)) + pad)


def kumu_pieces(a, b, k, box_a, box_b):
    """The link from centre a to centre b drawn as Kumu draws curvature k (KUMU_STRAIGHT): the
    circular arc through both centres, k times half their distance out at its middle, straight
    under KUMU_STRAIGHT, cut where it leaves box_a and enters box_b; as quadratic pieces of at most
    45 degrees, each with its control point where the circle's tangents at its ends meet (oval())."""
    s = k * hypot(b[0] - a[0], b[1] - a[1]) / 2 if abs(k) >= KUMU_STRAIGHT else 0
    arc = arc_at(a, b, s)

    def border(u0, u1, box):
        """Where the arc crosses box's border, between u0 inside it and u1 outside."""
        for _ in range(40):
            um = (u0 + u1) / 2
            u0, u1 = (um, u1) if inside(arc(um), box) else (u0, um)
        return (u0 + u1) / 2
    u0, u1 = border(0, 0.5, box_a), border(1, 0.5, box_b)
    if s == 0:
        p, q = arc(u0), arc(u1)
        return [(p, ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), q)]
    cx, cy, r, a0, sweep = circle_of(a, b, s)
    t0, t1 = a0 + sweep * u0, a0 + sweep * u1
    m = ceil(abs(t1 - t0) / (pi / 4))
    h = (t1 - t0) / (2 * m)
    at = lambda t, rr=r: (cx + rr * cos(t), cy + rr * sin(t))
    return [(at(t0 + 2 * h * i), at(t0 + 2 * h * i + h, r / cos(h)), at(t0 + 2 * h * (i + 1))) for i in range(m)]


def group_pieces(sub, bxs):
    """{(from, to): pieces}: each link of a group's own drawing (group_cld()) as Kumu draws it
    (kumu_pieces()), so the page's figure of a combined loop shows what Kumu's map of it shows."""
    centre = lambda i: ((bxs[i][0] + bxs[i][2]) / 2, (bxs[i][1] + bxs[i][3]) / 2)
    return {(c["from"], c["to"]): kumu_pieces(centre(c["from"]), centre(c["to"]), c["curvature"], bxs[c["from"]], bxs[c["to"]])
            for c in sub["connections"]}


def group_tangles(cld, group):
    """tangles() of the group's figure, its links as group_figure() and Kumu draw them."""
    sub = group_cld(cld, group)
    return tangles(sub, group_pieces(sub, boxes(sub)))


def group_figure(cld, group, vb=None):
    """One group of named loops, for the report: the loops joined at their shared variables, its
    boxes, signs and delays as svg() draws them and its links as Kumu does (group_pieces()), each
    loop's mark in the part of the figure that is its own. The places are the group's, never the
    full drawing's, where the same loops run long and lopsided (the same reason as oval()). No
    regions and no legend: the figure stands beside the full drawing. vb, the viewBox (x, y, width,
    height), defaults to group_frame()'s."""
    sub = group_cld(cld, group)
    bxs = boxes(sub)
    paths = group_pieces(sub, bxs)
    loops = {loop["id"]: loop for loop in cld["loops"]}
    if vb is None:
        x0, y0, x1, y1 = group_frame(cld, group)
        vb = (x0, y0, x1 - x0, y1 - y0)
    areas = loop_areas(cld, group)
    parts = [*head(vb), *links_and_elements(sub, bxs, paths),
             *(loop_svg(loops[name], tuple(group["marks"][name]), turns_clockwise(areas[name])) for name in group["loops"]),
             "</svg>"]
    return "\n".join(parts) + "\n"


# --- a combined loop's layout: each loop its own area ---------------------------------------------
# A combined loop draws each of its loops as its own area, never one inside another, since a loop
# drawn inside another puts the outer loop's mark inside the inner one (cld-drawing.md). Two loops
# sharing one element are two rings touching at that box; two sharing a chain are two areas side
# by side, the chain the wall between them. Each loop's mark sits at the centre of its own area,
# the boxes evenly along smooth arcs as on a named loop's oval (oval()). Where three loops share
# one chain, one wraps one of the others, its mark in the band that is its own.


def link_curve(a, b, k, n=20):
    """n + 1 points on the link from centre a to centre b at curvature k, as Kumu draws it
    (kumu_pieces()) before cutting it at the boxes."""
    arc = arc_at(a, b, k * hypot(b[0] - a[0], b[1] - a[1]) / 2 if abs(k) >= KUMU_STRAIGHT else 0)
    return [arc(t / n) for t in range(n + 1)]


def loop_areas(cld, group):
    """{loop id: polygon}: each of the group's loops as the area its links enclose at the group's
    places and bends, its links followed from centre to centre in the loop's order."""
    out = {}
    for loop in cld["loops"]:
        if loop["id"] in group["loops"]:
            p = loop["path"]
            out[loop["id"]] = [q for a, b in zip(p, p[1:] + p[:1])
                               for q in link_curve(group["places"][a], group["places"][b], group["bends"][f"{a} -> {b}"])[:-1]]
    return out


def turns_clockwise(poly):
    """Whether the polygon runs clockwise on the page: its shoelace sum is positive with y downwards."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])) > 0


def in_polygon(p, poly):
    """Whether p lies inside poly, by the even-odd rule."""
    x, y = p
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def wraps(outer, inner):
    """Whether area outer holds all of area inner, each point of inner inside it or on its border."""
    def near(p, poly):
        return any(hypot(p[0] - q[0], p[1] - q[1]) < 1 for q in poly)
    return all(in_polygon(p, outer) or near(p, outer) for p in inner)


def marks_astray(cld, group):
    """Each of the group's marks that lies outside its own loop's area or inside another's, but for
    a loop wrapped by another (cld-drawing.md), and each loop's label as Kumu draws it at its mark
    (kumu_label_half()) that lies on a box or a link, as lines for build.py's warnings."""
    areas = loop_areas(cld, group)
    loops = {loop["id"]: loop for loop in cld["loops"]}
    sub = group_cld(cld, group)
    bxs = boxes(sub)
    pts = [p for c in sub["connections"] for p in link_curve(group["places"][c["from"]], group["places"][c["to"]], c["curvature"])]
    out = []
    for name, area in areas.items():
        m = group["marks"][name]
        if not in_polygon(m, area):
            out.append(f"group {group['id']}: {name}'s mark lies outside its own loop's area")
        out += [f"group {group['id']}: {name}'s mark lies inside {other}'s area"
                for other, a in areas.items() if other != name and in_polygon(m, a) and not wraps(a, area)]
        half = kumu_label_half(loops[name])
        if not label_fits(m, (half[0] - LABEL_CLEAR_BOX + 1, half[1] - LABEL_CLEAR_BOX + 1), [b[:4] for b in bxs.values()], []) or \
                not label_fits(m, (half[0] - LABEL_CLEAR_LINK + 1, half[1] - LABEL_CLEAR_LINK + 1), [], pts):
            out.append(f"group {group['id']}: {name}'s label lies on a box or a link in Kumu")
    return out


def circle_of(p, q, s):
    """(cx, cy, r, a0, sweep): the circle of the arc from p to q whose middle lies s off the chord's
    middle, to the left of p -> q as link_path() bows a positive curvature (a major arc where |s|
    exceeds half the chord); a0 the angle of p from its centre, sweep the angle the arc turns."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    c = hypot(dx, dy)
    nx, ny = dy / c, -dx / c
    r = (c * c / 4 + s * s) / (2 * abs(s))
    off = s - (r if s > 0 else -r)  # the circle's centre, from the chord's middle along the normal
    cx, cy = (p[0] + q[0]) / 2 + off * nx, (p[1] + q[1]) / 2 + off * ny
    a0 = atan2(p[1] - cy, p[0] - cx)
    half = (atan2((p[1] + q[1]) / 2 + s * ny - cy, (p[0] + q[0]) / 2 + s * nx - cx) - a0 + pi) % (2 * pi) - pi
    return cx, cy, r, a0, 2 * half


def arc_at(p, q, s):
    """u in [0, 1] -> the point at fraction u along that arc (circle_of()), evenly by length; a
    straight line at s = 0."""
    if s == 0:
        return lambda u: (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)
    cx, cy, r, a0, sweep = circle_of(p, q, s)
    return lambda u: (cx + r * cos(a0 + sweep * u), cy + r * sin(a0 + sweep * u))


def bend_through(a, b, m):
    """The curvature (link_path()) whose curve from centre a to centre b passes through m halfway,
    the smallest Kumu bends (KUMU_STRAIGHT) on its side where it is less, 0 on a straight line.
    A quadratic curve passes (start + 2 control + end) / 4 halfway, so through m its control lies
    2 (m - chord middle) from the chord's middle; link_path() moves it curvature (dy, -dx)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ox, oy = 2 * (m[0] - (a[0] + b[0]) / 2), 2 * (m[1] - (a[1] + b[1]) / 2)
    k = round((ox * dy - oy * dx) / (dx * dx + dy * dy), 3)
    return k if abs(k) >= KUMU_STRAIGHT or k == 0 else (KUMU_STRAIGHT if k > 0 else -KUMU_STRAIGHT)


def area_centre(poly):
    """The centroid of a polygon: a convex area's centre."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        f = x0 * y1 - x1 * y0
        a, cx, cy = a + f, cx + (x0 + x1) * f, cy + (y0 + y1) * f
    return cx / (3 * a), cy / (3 * a)


SPINE_TRIES = 8  # how many of the spine's layouts group_layout() tries, from the least cost


def theta(cld, names):
    """(chain, routes): the loops `names` sharing one chain, each coming back from its last element to
    its first by a route of its own ({loop id: the route's elements, in the loop's order}), no
    element on two routes and at most one route with none; None where they do not.

    >>> cld = {"loops": [{"id": "A", "path": ["p", "q", "x"]}, {"id": "B", "path": ["q", "y", "p"]},
    ...                  {"id": "C", "path": ["p", "q"]}]}
    >>> theta(cld, ["A", "B", "C"])
    (['p', 'q'], {'A': ['x'], 'B': ['y'], 'C': []})
    >>> theta(cld, ["A"]) is None, theta({"loops": [{"id": "A", "path": ["p", "q", "x", "r"]}, {"id": "D", "path": ["p", "q", "y", "x"]}]}, ["A", "D"])
    (True, None)
    """
    paths = {loop["id"]: loop["path"] for loop in cld["loops"]}
    if len(names) < 2:
        return None
    common = set.intersection(*(set(zip(paths[n], paths[n][1:] + paths[n][:1])) for n in names))
    starts = {a for a, _ in common} - {b for _, b in common}
    if len(starts) != 1:
        return None
    nxt, chain = dict(common), list(starts)
    while chain[-1] in nxt and len(chain) <= len(common):
        chain.append(nxt[chain[-1]])
    if len(chain) != len(common) + 1:
        return None
    routes = {}
    for n in names:
        p = paths[n]
        k = p.index(chain[0])
        p = p[k:] + p[:k]
        if p[:len(chain)] != chain:
            return None
        routes[n] = p[len(chain):]
    own = [x for r in routes.values() for x in r]
    if len(own) != len(set(own)) or set(own) & set(chain) or sum(not r for r in routes.values()) > 1:
        return None
    return chain, routes


def group_layout(cld, group, stacked=None):
    """(places, bends, marks) for a group of named loops, in the shape of its fields in cld.json, each
    loop its own area (cld-drawing.md), each mark with room for Kumu's label of its loop
    (kumu_label_half()); None for a group it cannot lay out. stacked lays the figure's spine
    across, False upright, None whichever of the two gives the frame nearer a square, so the
    report's panels of one size waste the least room.

    Two loops sharing one element: each its own oval as oval() lays out a named loop, the two
    touching at that element, both clockwise, each mark at its oval's centre (ring_layout()).

    Otherwise its spine is the most loops sharing one chain (theta()), the chain on a straight wall
    and each loop's route an arc from the chain's end back to its start (theta_layout()); the
    group's other loops then join it where they meet it (join_loop())."""
    paths = {loop["id"]: loop["path"] for loop in cld["loops"]}
    if stacked is None:
        def squareness(lay):
            x0, y0, x1, y1 = group_frame(cld, {**group, "places": lay[0], "bends": lay[1], "marks": lay[2]})
            return max(x1 - x0, y1 - y0) / min(x1 - x0, y1 - y0)
        both = [lay for lay in (group_layout(cld, group, False), group_layout(cld, group, True)) if lay]
        return min(both, key=squareness) if both else None
    names = group["loops"]
    spines = [(c, t) for k in range(len(names), 1, -1) for c in combinations(names, k) if (t := theta(cld, list(c)))]
    if not spines:
        if len(names) == 2 and len(set(paths[names[0]]) & set(paths[names[1]])) == 1:
            return ring_layout(cld, group, stacked)
        return None
    # the most loops, then the most elements
    core, (chain, routes) = max(spines, key=lambda s: (len(s[0]), len({x for n in s[0] for x in paths[n]})))
    # the spine's layouts from the least cost (theta_layout()), the first on which every other loop
    # of the group finds room (join_loop())
    for lay in theta_layout(cld, group, chain, routes, stacked)[:SPINE_TRIES]:
        lay = dict(lay)
        left = [n for n in names if n not in lay["marks"]]
        while left:
            placed = next((n for n in left if join_loop(cld, lay, n, paths[n])), None)
            if placed is None:
                break
            left.remove(placed)
        if not left:
            break
    else:
        return None
    turn = (lambda u, v: (u, v)) if stacked else (lambda u, v: (-v, u))
    places = {i: turn(*p) for i, p in lay["at"].items()}
    bends = {f"{a} -> {b}": 0 if m is None else bend_through(places[a], places[b], turn(*m)) for (a, b), m in lay["mid"].items()}
    marks = {i: turn(*m) for i, m in lay["marks"].items()}
    return ({i: [round(x), round(y)] for i, (x, y) in places.items()}, bends,
            {i: [round(x), round(y)] for i, (x, y) in marks.items()})


# The layouts below work in (u, v): the spine's wall along u, v across it; group_layout() turns
# them to the page, (x, y) = (u, v) stacked or (-v, u) upright, a quarter turn that keeps each
# loop's direction. Each element's half size is taken along u and v there.


def halves(cld, ids, stacked):
    els = {e["id"]: e for e in cld["elements"]}
    out = {}
    for i, (x0, y0, x1, y1, _) in boxes({"elements": [dict(els[i], x=0, y=0) for i in ids]}).items():
        w, h = (x1 - x0) / 2, (y1 - y0) / 2
        out[i] = (w, h) if stacked else (h, w)
    return out


def rect(at, half, i):
    return (at[i][0] - half[i][0], at[i][1] - half[i][1], at[i][0] + half[i][0], at[i][1] + half[i][1])


_CURVES = {}
LINK_END_GAP = 30  # two links' ends on one box border keep this far apart in a laid-out figure: a Kumu arrowhead is 23 wide


def kumu_curve(at, a, b, m):
    """Points on the link a -> b as Kumu draws it: straight where m is None, else bent through m."""
    key = (at[a], at[b], m)
    if key not in _CURVES:
        k = 0 if m is None else bend_through(at[a], at[b], m)
        # a point every 40 units or so, as a long bow is followed closely enough to find its crossings
        n = max(20, ceil(hypot(at[b][0] - at[a][0], at[b][1] - at[a][1]) * (1 + abs(k)) / 40))
        _CURVES[key] = link_curve(at[a], at[b], k, n)
    return _CURVES[key]


def clear(lay, new):
    """Whether the elements in `new` keep OVAL_GAP from every other box, and no link touching them
    crosses another link or runs through a box it does not connect, the links as Kumu draws them."""
    at, half = lay["at"], lay["half"]
    gap = lambda i, j: max(abs(at[i][0] - at[j][0]) - half[i][0] - half[j][0], abs(at[i][1] - at[j][1]) - half[i][1] - half[j][1])
    if any(gap(i, j) < OVAL_GAP for i in new for j in at if j != i and (j not in new or j > i)):
        return False
    rects = {i: rect(at, half, i) + (None,) for i in at}

    def cut(curve, a, b):
        """The curve from where it leaves box a to where it enters box b, its ends on the borders."""
        def edge(p, q, box):  # p inside box, q outside
            for _ in range(20):
                m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                p, q = (m, q) if inside(m, box) else (p, m)
            return q
        out = [i for i, p in enumerate(curve) if not inside(p, rects[a]) and not inside(p, rects[b])]
        if not out:
            return []
        i, j = out[0], out[-1]
        head = [edge(curve[i - 1], curve[i], rects[a])] if i > 0 else []
        tail = [edge(curve[j + 1], curve[j], rects[b])] if j < len(curve) - 1 else []
        return head + curve[i:j + 1] + tail
    pts = {k: cut(kumu_curve(at, *k, m), *k) for k, m in lay["mid"].items()}
    frame = {k: (min(x for x, _ in p), min(y for _, y in p), max(x for x, _ in p), max(y for _, y in p)) if p else None
             for k, p in pts.items()}
    apart = lambda f, g: f is None or g is None or f[2] < g[0] or g[2] < f[0] or f[3] < g[1] or g[3] < f[1]
    mine = [k for k in pts if k[0] in new or k[1] in new]
    # two links meeting one box reach its border apart, or their ends and arrowheads lie on each other
    ends = {}
    for k in pts:
        if pts[k]:
            ends.setdefault(k[0], []).append((k, pts[k][0]))
            ends.setdefault(k[1], []).append((k, pts[k][-1]))
    for i, es in ends.items():
        for x, (k, p) in enumerate(es):
            for j, q in es[x + 1:]:
                if (k in mine or j in mine) and hypot(p[0] - q[0], p[1] - q[1]) < LINK_END_GAP:
                    return False
    for k in mine:
        for j in pts:
            if j == k or (j in mine and j < k) or set(j) == set(k) or apart(frame[k], frame[j]):
                continue
            if any(meet(pts[k][u], pts[k][u + 1], pts[j][w], pts[j][w + 1]) for u in range(len(pts[k]) - 1) for w in range(len(pts[j]) - 1)):
                return False
    # no link through a box, its corners included: each box grown by a little for the test
    grown = {i: (r[0] - 10, r[1] - 10, r[2] + 10, r[3] + 10, None) for i, r in rects.items()}
    for k in pts:
        for i in at:
            if i not in k and (i in new or k in mine) and not apart(frame[k], grown[i][:4]) and any(inside(p, grown[i]) for p in pts[k]):
                return False
    return True


def label_room(lay, name, m):
    """Whether loop name's label fits at m, clear of every box and every link."""
    at, half = lay["at"], lay["half"]
    pts = [p for k, mm in lay["mid"].items() for p in kumu_curve(at, *k, mm)]
    return label_fits(m, lay["label"][name], [rect(at, half, i) for i in at], pts)


def across(arc, u):
    """How far the arc lies from the wall (v = 0) where it passes u, 0 where it does not reach u."""
    pts = [arc(t / 400) for t in range(401)]
    if not min(p[0] for p in pts) <= u <= max(p[0] for p in pts):
        return 0.0
    return abs(min(pts, key=lambda p: abs(p[0] - u))[1])


def theta_layout(cld, group, chain, routes, stacked):
    """The spine (theta()) in (u, v): the chain on a straight wall along u, an even gap between each
    two of its boxes, each route an arc from the chain's end back to its start, its boxes evenly
    along it. One route each side of the wall; a third arcs round one of those two, on its outer
    side (the wrap, cld-drawing.md: three loops on one chain cannot each lie beside it), round one
    whose elements no other loop of the group meets, so those stay outside, and it is the route
    with the most elements. A group loop whose shared links all lie on the wall arcs over them
    between the wall and that side's route, the route wrapping it. The routes on the +v side, the
    larger loop's, run clockwise. Each mark sits midway between its route's middle and what lies
    inside it there (the wall, or the arc it wraps), and each arc bulges just enough that its boxes
    keep OVAL_GAP from every other and its label fits. A list of the layouts for every gap on the
    wall, the least first by its frame times its longest link over its shortest, so the figure stays
    small and its links alike."""
    paths = {loop["id"]: loop["path"] for loop in cld["loops"]}
    loops = {loop["id"]: loop for loop in cld["loops"]}
    names = group["loops"]
    links = lambda p: list(zip(p, p[1:] + p[:1]))
    wall_links = set(zip(chain, chain[1:]))
    # group loops that arc over part of the wall: their shared links all on it, their own elements none drawn
    inner = {}
    for n in names:
        if n in routes:
            continue
        mine = [l for l in links(paths[n]) if l in wall_links]
        rest = [x for x in paths[n] if x not in chain]
        if mine and len(mine) < len(chain) - 1 and not set(rest) & {x for r in routes.values() for x in r}:
            sub = [mine[0][0]] + [b for _, b in mine]
            if all(l in mine for l in zip(sub, sub[1:])) and len(mine) == len(sub) - 1:
                p = paths[n]
                k = p.index(sub[0])
                p = p[k:] + p[:k]
                if p[:len(sub)] == sub:
                    inner[n] = (sub, p[len(sub):])
    ids = set(chain) | {x for r in routes.values() for x in r} | {x for _, r in inner.values() for x in r}
    half = halves(cld, ids, stacked)
    others = {x for n in names if n not in routes and n not in inner for x in paths[n]}
    by_size = sorted(routes, key=lambda n: (-len(routes[n]), names.index(n)))
    configs = []
    if len(routes) == 2:
        configs.append({by_size[0]: (1, None), by_size[1]: (-1, None)})
    elif len(routes) == 3:
        w, x, y = by_size
        for wrapped, other in ((x, y), (y, x)):
            configs.append({wrapped: (1, None), other: (-1, None), w: (1, wrapped), "_free": not set(routes[wrapped]) & others})
        if any(c["_free"] for c in configs):
            configs = [c for c in configs if c["_free"]]
    else:
        return None
    for c in configs:
        c.pop("_free", None)
    # each arc over part of the wall goes to one side, tried both ways
    for n in inner:
        configs = [{**c, n: (side, "inner")} for c in configs for side in (1, -1)]

    def lay(config, between):
        along = [2 * half[x][0] for x in chain]
        spots = [0.0]
        for i in range(len(chain) - 1):
            spots.append(spots[-1] + along[i] / 2 + between + along[i + 1] / 2)
        at = {x: (t - spots[-1] / 2, 0.0) for x, t in zip(chain, spots)}
        out = {"at": at, "half": half, "mid": {l: None for l in wall_links}, "marks": {}, "arcs": {}, "stacked": stacked,
               # each label's half size along u and v
               "label": {n: kumu_label_half(loops[n])[::1 if stacked else -1] for n in names}, "paths": paths,
               "names": names}
        if not clear(out, set(chain)):
            return None
        # inner arcs first, then each side's routes inside out
        order = ([n for n, (_, w) in config.items() if w == "inner"] + [n for n, (_, w) in config.items() if w is None]
                 + [n for n, (_, w) in config.items() if w not in (None, "inner")])
        for n in order:
            side, wraps = config[n]
            if wraps == "inner":
                sub, own = inner[n]
            else:
                sub, own = chain, routes[n]
            a, b = at[sub[0]], at[sub[-1]]
            um = (a[0] + b[0]) / 2
            # what lies inside this arc on its side at its middle: the wall, or the arcs it wraps
            base = max([0.0] + [across(arc, um) for sd, arc in out["arcs"].values() if sd == side])
            for h in range(int(base) + 60, int(base) + 4000, 10):
                arc = arc_at(b, a, side * h)
                trial = {**out, "at": {**at, **{x: arc((i + 1) / (len(own) + 1)) for i, x in enumerate(own)}},
                         "mid": dict(out["mid"])}
                seq = [sub[-1], *own, sub[0]]
                for i, (x, y) in enumerate(zip(seq, seq[1:])):
                    trial["mid"][x, y] = arc((i + 0.5) / (len(seq) - 1))
                m = (um, side * (base + h) / 2)
                if label_room(trial, n, m) and clear(trial, set(own) | {sub[0], sub[-1]}):
                    at, out = trial["at"], trial
                    out["marks"] = {**out["marks"], n: m}
                    out["arcs"] = {**out["arcs"], n: (side, arc)}
                    break
            else:
                return None
        return out

    def cost(found):
        at = found["at"]
        xs = [at[i][0] + d * half[i][0] for i in at for d in (-1, 1)]
        ys = [at[i][1] + d * half[i][1] for i in at for d in (-1, 1)]
        lengths = [hypot(at[x][0] - at[y][0], at[x][1] - at[y][1]) for x, y in found["mid"]]
        return (max(xs) - min(xs)) * (max(ys) - min(ys)) * max(lengths) / min(lengths)

    found = [f for config in configs for f in (lay(config, between) for between in range(OVAL_GAP, 2001, 25)) if f]
    return sorted(found, key=cost)


def join_loop(cld, lay, name, path):
    """Add loop name to the layout where it meets it, True once placed: an arc of its own over the
    drawn links it shares (a lens on the drawing's outer side), or, meeting it at one element, its
    own oval touching there, pointing away from the drawing (a petal); each just large enough that its
    boxes keep OVAL_GAP from every other box, its links cross none and its label fits."""
    at = lay["at"]
    drawn = [k for k in lay["mid"] if k in set(zip(path, path[1:] + path[:1]))]
    centre = (sum(p[0] for p in at.values()) / len(at), sum(p[1] for p in at.values()) / len(at))
    new_ids = [x for x in path if x not in at]
    half = {**lay["half"], **(halves(cld, new_ids, lay["stacked"]) if new_ids else {})}

    def area(t, p):
        return [q for x, y in zip(p, p[1:] + p[:1]) for q in kumu_curve(t["at"], x, y, t["mid"][x, y])[:-1]]

    def accept(trial_at, mids, mark):
        trial = {**lay, "at": {**at, **trial_at}, "half": half, "mid": {**lay["mid"], **mids}}
        if not label_room(trial, name, mark):
            return False
        # its own area, holding no other mark, and its mark in no other area
        mine = area(trial, path)
        if any(in_polygon(m, mine) for m in lay["marks"].values()) or any(
                in_polygon(mark, area(trial, lay["paths"][n])) for n in lay["marks"]):
            return False
        if clear(trial, set(trial_at) | {x for k in mids for x in k}):
            lay.update(trial)
            lay["marks"] = {**lay["marks"], name: mark}
            return True
        return False

    if drawn:
        # the shared run: its links in the loop's order, from its first element to its last
        p = path
        k = next((i for i in range(len(p)) if (p[i - 1], p[i]) not in drawn and (p[i], p[(i + 1) % len(p)]) in drawn), None)
        if k is None:
            return False
        p = p[k:] + p[:k]
        run = [p[0]]
        while len(run) < len(p) and (run[-1], p[len(run)]) in drawn:
            run.append(p[len(run)])
        own = p[len(run):]
        if any(x in at for x in own):
            return False
        a, b = at[run[0]], at[run[-1]]
        pts = [q for x, y in zip(run, run[1:]) for q in kumu_curve(at, x, y, lay["mid"][x, y])]
        lengths = [0.0] + [hypot(q[0] - r[0], q[1] - r[1]) for q, r in zip(pts, pts[1:])]
        total, acc, cm = sum(lengths), 0.0, pts[0]
        for q, l in zip(pts, lengths):
            acc += l
            if acc >= total / 2:
                cm = q
                break
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        c = hypot(b[0] - a[0], b[1] - a[1])
        n = (-(b[1] - a[1]) / c, (b[0] - a[0]) / c)
        out_side = 1 if (cm[0] - centre[0]) * n[0] + (cm[1] - centre[1]) * n[1] >= 0 else -1
        for side in (out_side, -out_side):
            nn = (n[0] * side, n[1] * side)
            off = (cm[0] - mid[0]) * nn[0] + (cm[1] - mid[1]) * nn[1]
            for h in range(60, 4000, 10):
                tip = (mid[0] + nn[0] * (max(off, 0) + h), mid[1] + nn[1] * (max(off, 0) + h))
                # arc_at(b, a, s) bows s to the left of b -> a
                left = ((a[1] - b[1]) / c, -(a[0] - b[0]) / c)
                s = (tip[0] - mid[0]) * left[0] + (tip[1] - mid[1]) * left[1]
                arc = arc_at(b, a, s)
                seq = [run[-1], *own, run[0]]
                trial_at = {x: arc((i + 1) / (len(own) + 1)) for i, x in enumerate(own)}
                mids = {(x, y): arc((i + 0.5) / (len(seq) - 1)) for i, (x, y) in enumerate(zip(seq, seq[1:]))}
                mark = ((cm[0] + tip[0]) / 2, (cm[1] + tip[1]) / 2)
                if accept(trial_at, mids, mark):
                    return True
        return False
    shared = [x for x in path if x in at]
    if len(shared) != 1:
        return False
    (s,) = shared
    k = path.index(s)
    p = path[k:] + path[:k]
    d = (at[s][0] - centre[0], at[s][1] - centre[1])
    out = atan2(d[1], d[0])
    # loops that touch the drawing only at s fan out from it, 90 degrees apart, in the group's order
    fan = [n for n in lay["names"] if n == name or (n not in lay["marks"] and set(lay["paths"][n]) & set(at) == {s})]
    fan = sorted(set(fan) | set(lay.setdefault("petals", {}).get(s, [])), key=lay["names"].index)
    pref = (fan.index(name) - (len(fan) - 1) / 2) * 90
    turns = (0, 20, -20, 40, -40, 60, -60, 80, -80, 100, -100, 120, -120, 140, -140)

    def placed():
        lay["petals"] = {**lay.get("petals", {}), s: lay.get("petals", {}).get(s, []) + [name]}
        return True
    if len(p) == 2:
        # two elements: a narrow lens straight out from s, its two links bowing apart just enough for
        # the label between them, so they leave s close to that one direction and cut no link arriving there
        def lens(turn, length):
            phi = out + (pref + turn) * pi / 180
            e, n = (cos(phi), sin(phi)), (-sin(phi), cos(phi))
            far = (at[s][0] + length * e[0], at[s][1] + length * e[1])
            mid = ((at[s][0] + far[0]) / 2, (at[s][1] + far[1]) / 2)
            for h in range(40, length // 2, 30):
                mids = {(p[0], p[1]): (mid[0] + h * n[0], mid[1] + h * n[1]), (p[1], p[0]): (mid[0] - h * n[0], mid[1] - h * n[1])}
                if accept({p[1]: far}, mids, mid):
                    return True
            return False
        # the direction nearest its own in the fan first, so the lenses at one element share out
        # the room round it, then the smallest lens in any direction
        if any(lens(turn, length) for turn in turns for length in range(200, 1600, 40)):
            return placed()
        if any(lens(turn, length) for length in range(1600, 4000, 40) for turn in turns):
            return placed()
        return False
    for r in range(100, 3000, 10):
        for turn in turns:
            phi = out + (pref + turn) * pi / 180
            ru, rv = (OVAL_ASPECT * r, r) if lay["stacked"] else (r, OVAL_ASPECT * r)
            c = (at[s][0] + ru * cos(phi), at[s][1] + rv * sin(phi))
            t0 = atan2(-sin(phi), -cos(phi))
            ang = {x: t0 + 2 * pi * i / len(p) for i, x in enumerate(p)}
            pos = lambda t: (c[0] + ru * cos(t), c[1] + rv * sin(t))
            trial_at = {x: pos(ang[x]) for x in p[1:]}
            mids = {(x, y): pos(ang[x] + pi / len(p)) for x, y in zip(p, p[1:] + p[:1])}
            if accept(trial_at, mids, c):
                return placed()
    return False


def ring_layout(cld, group, stacked):
    """(places, bends, marks) for two loops sharing one element: each its own oval as oval() lays out
    a named loop, the two touching at that element, both clockwise, each mark at its oval's centre
    with room for its label (kumu_label_half()); the larger loop, by its elements, on the left or
    below, the shared element on its right or bottom."""
    paths = {loop["id"]: loop["path"] for loop in cld["loops"]}
    loops = {loop["id"]: loop for loop in cld["loops"]}
    a, b = sorted(group["loops"], key=lambda i: -len(paths[i]))
    pa, pb = paths[a], paths[b]
    (s,) = set(pa) & set(pb)
    els = {e["id"]: e for e in cld["elements"]}
    half = {i: ((x1 - x0) / 2, (y1 - y0) / 2) for i, (x0, y0, x1, y1, _) in
            boxes({"elements": [dict(els[i], x=0, y=0) for i in set(pa) | set(pb)]}).items()}
    gap = lambda i, j, at: max(abs(at[i][0] - at[j][0]) - half[i][0] - half[j][0], abs(at[i][1] - at[j][1]) - half[i][1] - half[j][1])
    apart = lambda at, xs, ys: all(gap(i, j, at) >= OVAL_GAP for i in xs for j in ys if i != j)
    # where the shared element sits on each oval: the first's right or bottom, the second's left or top
    sides = {a: pi / 2 if stacked else 0, b: -pi / 2 if stacked else pi}

    def ring(name, ry):
        """({id: (x, y)}, centre, {id: angle}, rx, {link: its middle on the oval}): name's oval through s at its side."""
        p, t = paths[name], sides[name]
        rx, k0 = OVAL_ASPECT * ry, p.index(s)
        centre = (-rx * cos(t), -ry * sin(t))
        ang = {x: t + 2 * pi * ((k - k0) % len(p)) / len(p) for k, x in enumerate(p)}
        at = {x: (centre[0] + rx * cos(u), centre[1] + ry * sin(u)) for x, u in ang.items()}
        mids = {(x, y): (centre[0] + rx * cos(ang[x] + pi / len(p)), centre[1] + ry * sin(ang[x] + pi / len(p)))
                for x, y in zip(p, p[1:] + p[:1])}
        return at, centre, mids

    def room(name, ry):
        at, centre, mids = ring(name, ry)
        pts = [q for (x, y), m in mids.items() for q in link_curve(at[x], at[y], bend_through(at[x], at[y], m))]
        rects = [(at[i][0] - half[i][0], at[i][1] - half[i][1], at[i][0] + half[i][0], at[i][1] + half[i][1]) for i in at]
        return label_fits(centre, kumu_label_half(loops[name]), rects, pts)

    size = {}
    for name in (a, b):
        ry = 100
        while not (apart(ring(name, ry)[0], paths[name], paths[name]) and room(name, ry)):
            ry += 10
        size[name] = ry
    while not apart({**ring(a, size[a])[0], **{k: v for k, v in ring(b, size[b])[0].items() if k != s}}, pa, pb):
        size[b] += 10
    places, bends, marks = {}, {}, {}
    for name in (a, b):
        at, centre, mids = ring(name, size[name])
        places.update(at)
        marks[name] = centre
        bends.update({f"{x} -> {y}": bend_through(at[x], at[y], m) for (x, y), m in mids.items()})
    return ({i: [round(x), round(y)] for i, (x, y) in places.items()}, bends,
            {i: [round(x), round(y)] for i, (x, y) in marks.items()})


# The report sets combined loops side by side as panels of one size with one text size (Jordy,
# chosen between rendered versions: panels of different sizes and proportions looked
# unprofessional). So each group's box centres are spread linearly over one frame, the boxes
# keeping their size; a smaller frame crowded C3.
PANEL_FRAME = (2300, 1350)


def spread_group(group, frame=PANEL_FRAME):
    """The group with its places and marks mapped linearly onto frame (width, height), centred on 0, 0."""
    xs, ys = [p[0] for p in group["places"].values()], [p[1] for p in group["places"].values()]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sx, sy = frame[0] / (max(xs) - min(xs)), frame[1] / (max(ys) - min(ys))
    at = lambda p: [(p[0] - cx) * sx, (p[1] - cy) * sy]
    return {**group, "places": {k: at(p) for k, p in group["places"].items()},
            "marks": {k: at(p) for k, p in group["marks"].items()}}


def report_panels(cld):
    """{group id: svg}: each group spread onto PANEL_FRAME and drawn by group_figure() in one
    viewBox size, the largest any group needs, centred on its own drawing, so every panel prints
    at one size with one text size (build.py writes docs/figures/report-panels/<id>.svg)."""
    groups = {g["id"]: spread_group(g) for g in cld.get("groups", [])}
    frames = {i: group_frame(cld, g) for i, g in groups.items()}
    w = max(f[2] - f[0] for f in frames.values()) if frames else 0
    h = max(f[3] - f[1] for f in frames.values()) if frames else 0
    return {i: group_figure(cld, g, ((f[0] + f[2] - w) / 2, (f[1] + f[3] - h) / 2, w, h))
            for (i, g), f in zip(groups.items(), frames.values())}


# --- overlap warnings -----------------------------------------------------------------------
def turn(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def meet(p, q, r, s):
    """Whether the segments p-q and r-s cross."""
    return turn(p, q, r) * turn(p, q, s) < 0 and turn(r, s, p) * turn(r, s, q) < 0


def tangles(cld, pieces=None):
    """(crossings, through): the points where two links cross, as pairs of links, and each link
    that passes through a box it does not connect, which reads as if that element mediates it, as
    (link, element); build.py's report counts both, the eye's measure of a layout. Each link is
    sampled at 30 points, or 10 per piece where `pieces` gives each link's ({(from, to): [(p0,
    ctrl, p2), ...]}, group_tangles()), and tested segment by segment, a pair of links only where
    their frames meet."""
    bxs = boxes(cld)
    if pieces is None:
        pts = {k: [bezier(*p, i / 30) for i in range(31)] for k, p in link_paths(cld, bxs).items()}
    else:
        pts = {k: [ps[0][0]] + [bezier(*p, i / 10) for p in ps for i in range(1, 11)] for k, ps in pieces.items()}
    frame = {k: (min(x for x, _ in p), min(y for _, y in p), max(x for x, _ in p), max(y for _, y in p))
             for k, p in pts.items()}
    apart = lambda f, g: f[2] < g[0] or g[2] < f[0] or f[3] < g[1] or g[3] < f[1]
    keys = list(pts)
    crossings = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if not apart(frame[a], frame[b])
                 for u in range(len(pts[a]) - 1) for v in range(len(pts[b]) - 1) if meet(pts[a][u], pts[a][u + 1], pts[b][v], pts[b][v + 1])]

    def cuts(p, q, box):
        """Whether the segment p-q enters box: an end inside it, or a crossing with one of its sides."""
        x0, y0, x1, y1 = box[:4]
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return (inside(p, box) or inside(q, box)
                or any(meet(p, q, corners[k], corners[(k + 1) % 4]) for k in range(4)))
    through = [(k, e) for k in keys for e, b in bxs.items() if e not in k and not apart(frame[k], b)
               and any(cuts(pts[k][u], pts[k][u + 1], b) for u in range(len(pts[k]) - 1))]
    return crossings, through


def overlaps(cld):
    """Pairs of element boxes that intersect, a link and its reverse drawn on one curve, an
    element on the wrong side of the regions' border, and a named loop whose own links cross."""
    bxs = boxes(cld)
    ids = [e["id"] for e in cld["elements"]]
    out = []
    # the regions' border needs room between the two subsystems in every row: an element of the
    # first subsystem right of one of the second, at about the same height, leaves it none
    names = list(REGION)
    left = [(e["id"], bxs[e["id"]]) for e in cld["elements"] if e["subsystem"] == names[0]]
    right = [(e["id"], bxs[e["id"]]) for e in cld["elements"] if e["subsystem"] == names[1]]
    pad = BORDER_GAP / 2 + BORDER_CLEAR
    for a, p in left:
        for b, q in right:
            if p[1] - pad < q[3] + pad and q[1] - pad < p[3] + pad and p[2] + pad > q[0] - pad:
                out.append(f"regions: {a} ({names[0]}) is not left of {b} ({names[1]}) with room for the border")
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            p, q = bxs[a], bxs[b]
            if p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]:
                out.append(f"boxes overlap: {a} and {b}")
    # a -> b at curvature k and b -> a at -k share one curve, so the loop reads as one line with
    # two arrowheads; they read as two once their middles lie a sign's height apart
    paths = link_paths(cld, bxs)
    for c in cld["connections"]:
        p0, _, p2 = paths[c["from"], c["to"]]
        if c["delay"] and hypot(p0[0] - p2[0], p0[1] - p2[1]) < DELAY_MIN:
            out.append(f"{c['from']} -> {c['to']}: too short to hold its delay and its sign apart")
    for (a, b), p in paths.items():
        q = paths.get((b, a))
        if q and a < b:
            m, n = bezier(*p, 0.5), bezier(*q, 0.5)
            if hypot(m[0] - n[0], m[1] - n[1]) < SIGN_SIZE:
                out.append(f"links on one curve: {a} -> {b} and back (give both curvatures one sign)")
    # a region name over a link hides it; no box reaches a name, which sits in the frame's margin
    allb = list(bxs.values())
    frame = (min(b[0] for b in allb) - FRAME_PAD, min(b[1] for b in allb) - FRAME_PAD,
             max(b[2] for b in allb) + FRAME_PAD, max(b[3] for b in allb) + FRAME_PAD)
    for k, n in enumerate(names):
        nb = name_box(n, frame, k == 0)
        hit = lambda p: nb[0] < p[0] < nb[2] and nb[1] < p[1] < nb[3]
        out += [f"region name {n!r} over the link {a} -> {b}" for (a, b), p in paths.items()
                if any(hit(bezier(*p, t / 40)) for t in range(41))]
    # a named loop whose own links cross reads as a figure eight, which cannot be followed round;
    # each link sampled at 30 points, every pair of the loop's links tested segment by segment
    pts = {k: [bezier(*p, i / 30) for i in range(31)] for k, p in paths.items()}
    for loop in cld["loops"]:
        path = loop["path"]
        steps = [(path[i], path[(i + 1) % len(path)]) for i in range(len(path))]
        for i, a in enumerate(steps):
            for b in steps[i + 1:]:
                p, q = pts[a], pts[b]
                if any(meet(p[u], p[u + 1], q[v], q[v + 1]) for u in range(30) for v in range(30)):
                    out.append(f"loop crosses itself: {loop['id']}, {a[0]} -> {a[1]} and {b[0]} -> {b[1]}")
    return out
