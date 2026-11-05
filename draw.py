"""Draw the CLD as an SVG, from cld.json's own coordinates (y downwards).

Imported by build.py, which writes docs/cld.svg and puts the same drawing inline in
docs/index.html. svg(cld) returns the drawing as a string; overlaps(cld) the warnings about
boxes that intersect and other layout faults, and tangles(cld) the crossings between links and
the links through a box, for build.py's report; boxes(cld) the geometry
build.py gives Kumu's elements; regions_svg(cld) the regions alone, Kumu's background image.

What is drawn, from back to front:
  regions   one faint region per subsystem, split by one smooth border with a white gap, each
            named in its top outer corner
  links     a quadratic Bezier from a point on the source box's edge to one on the target's,
            the ends on one edge spread along it; the sign on the link just before the
            arrowhead, a delay as two short strokes across the midpoint
  elements  the label in a box filled with the pale tint of its SETS domain, the one place the
            domain shows in the drawing (the layout follows the loops, not the domains):
            square corners for a Stock, rounded for an Auxiliary, dashed for a Constant, a
            thick stroke for an adaptive practice
  legend    in the first bottom corner inside the frame with room for it, else below the frame
No loop marks on the full drawing: the page highlights a named loop by its button.
loop_figure(cld, loop) draws one named loop on its own (build.py writes docs/loops/<id>.svg): its
elements evenly round one oval, clockwise from the top left, its links along it, drawn as svg()
draws them, with its mark, turning clockwise, at the oval's centre.

The link formulas are duplicated in page/app.js (drag mode redraws every link when an element
moves): keep link_path(), link_paths(), sign_position() and their JS twins the same.
"""

from math import ceil, cos, hypot, pi, sin

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
    rx = 0 if kind == "Stock" else 9
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
    """The curve from box a's border to box b's border; see the JS twin in page/app.js.

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


def link_paths(cld, bxs):
    """{(from, to): (p0, c, p2)} for every connection; see the JS twin linkPaths() in page/app.js.

    Each end starts where link_path() cuts the curve between the two centres; the ends on one
    edge of a box are then spread along it, in the order they arrive, so arrowheads do not
    converge on the box's centre. The curve between the two end points has its control point
    at the chord's midpoint, moved perpendicular by curvature x chord length, as in link_path().
    """
    ends = {}
    for c in cld["connections"]:
        key = (c["from"], c["to"])
        p0, _, p2 = link_path(bxs[c["from"]], bxs[c["to"]], c["curvature"])
        for which, eid, p in ((0, c["from"], p0), (1, c["to"], p2)):
            e = edge_of(p, bxs[eid])
            ends.setdefault((eid, e), []).append((p[0] if e in (0, 2) else p[1], key, which))
    anchor = {}
    for (eid, e), lst in ends.items():
        x0, y0, x1, y1 = bxs[eid][:4]
        lst.sort(key=lambda t: t[0])
        lo, hi = (x0 + INSET, x1 - INSET) if e in (0, 2) else (y0 + INSET, y1 - INSET)
        for (_, key, which), v in zip(lst, spread([t[0] for t in lst], lo, hi, GAP)):
            anchor[key, which] = ((v, y0) if e == 0 else (x1, v) if e == 1 else (v, y1) if e == 2 else (x0, v))
    out = {}
    for c in cld["connections"]:
        key = (c["from"], c["to"])
        p0, p2 = anchor[key, 0], anchor[key, 1]
        dx, dy = p2[0] - p0[0], p2[1] - p0[1]
        k = c["curvature"]
        out[key] = (p0, ((p0[0] + p2[0]) / 2 + k * dy, (p0[1] + p2[1]) / 2 - k * dx), p2)
    return out


def lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def sub_curve(p0, p1, p2, t0, t1):
    """The piece [t0, t1] of a quadratic Bezier is one too: split at t0, keep the right piece
    (B(t0), lerp(p1, p2, t0), p2), split that at s and keep the left piece."""
    r0, r1 = bezier(p0, p1, p2, t0), lerp(p1, p2, t0)
    s = (t1 - t0) / (1 - t0) if t0 < 1 else 0
    return r0, lerp(r0, r1, s), bezier(p0, p1, p2, t1)


def link_svg(c, pieces):
    """The link as joined quadratic Beziers, pieces [(p0, ctrl, p2), ...]: one in the full drawing,
    several along a one-loop figure's oval; the sign on the last piece, a delay on the middle one."""
    colour = LINK_COLOUR[c["polarity"]]
    d = f"M {pieces[0][0][0]:.1f} {pieces[0][0][1]:.1f} " + " ".join(f"Q {q[0]:.1f} {q[1]:.1f} {r[0]:.1f} {r[1]:.1f}" for _, q, r in pieces)
    parts = [f'<g class="link" data-from="{c["from"]}" data-to="{c["to"]}" data-sign="{c["polarity"]}" '
             f'data-delay="{"true" if c["delay"] else "false"}" data-curvature="{c["curvature"]}">',
             f'<path class="link-path" d="{d}" '
             f'fill="none" stroke="{colour}" stroke-width="{LINK_WIDTH}" marker-end="url(#arrow-{"plus" if c["polarity"] == "+" else "minus"})"/>']
    sx, sy = sign_position(*pieces[-1])
    parts.append(f'<text class="sign" x="{sx:.1f}" y="{sy:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="{SIGN_SIZE}" font-weight="bold" fill="{colour}" stroke="white" stroke-width="{SIGN_HALO}" paint-order="stroke">{SIGN_TEXT[c["polarity"]]}</text>')
    if c["delay"]:
        parts.append(f'<path class="delay" d="{delay_path(*pieces[len(pieces) // 2])}" stroke="{STROKE_COLOUR}" stroke-width="2.5" fill="none"/>')
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


def delay_path(p0, ctrl, p2, half=9, gap=4):
    x, y = bezier(p0, ctrl, p2, 0.5)
    tx, ty = tangent(p0, ctrl, p2, 0.5)
    n = hypot(tx, ty) or 1
    ux, uy = tx / n, ty / n
    nx, ny = -uy, ux
    d = []
    for k in (-gap, gap):
        cx, cy = x + ux * k, y + uy * k
        d.append(f"M {cx - nx * half:.1f} {cy - ny * half:.1f} L {cx + nx * half:.1f} {cy + ny * half:.1f}")
    return " ".join(d)


# --- loops ----------------------------------------------------------------------------------
def loop_svg(loop, centre):
    """The loop's mark at centre: its id in a three-quarter circle that ends in an arrowhead,
    turning clockwise on the page, as the one-loop figure runs."""
    cx, cy = centre
    r = MARK_R
    # from the top clockwise round to the left; y grows downwards
    a0, a1 = -pi / 2, pi
    start = (cx + r * cos(a0), cy + r * sin(a0))
    end = (cx + r * cos(a1), cy + r * sin(a1))
    return "\n".join([
        f'<g class="loop" data-id="{loop["id"]}">',
        f'<path d="M {start[0]:.1f} {start[1]:.1f} A {r} {r} 0 1 1 {end[0]:.1f} {end[1]:.1f}" fill="none" '
        f'stroke="{STROKE_COLOUR}" stroke-width="{LINK_WIDTH}" marker-end="url(#arrow-grey)"/>',
        f'<text class="loop-id" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="{SIGN_SIZE}" font-weight="bold">{esc(loop["id"])}</text>',
        "</g>"])


# --- regions ----------------------------------------------------------------------------------
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


def regions_svg(cld):
    """(svg, frame): the regions alone, their viewBox the frame in the elements' coordinates, for
    Kumu's background image (build.py writes it as docs/regions.svg). Its width and height are the
    frame's, one pixel per unit: with a viewBox alone a browser gives the image 250 by 150 pixels,
    and Kumu stretched that to the frame, blurring the region names and the border."""
    bxs = boxes(cld)
    region_svg, frame, _, _ = regions(cld, bxs)
    x0, y0, x1, y1 = frame
    w, h = x1 - x0, y1 - y0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" '
            f'width="{w:.0f}" height="{h:.0f}" font-family="{FONT}">\n{region_svg}\n</svg>\n'), frame


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
        swatch(i, lambda xx, yy, t=tint: box(xx, yy, "", 9, fill=t), f"{domain} domain")
    n = len(TINT)
    swatch(n, lambda xx, yy: box(xx, yy, "", 0), "Stock")
    swatch(n + 1, lambda xx, yy: box(xx, yy, "", 9), "Auxiliary")
    swatch(n + 2, lambda xx, yy: box(xx, yy, 'stroke-dasharray="8 5"', 9), "Constant (exogenous)")
    swatch(n + 3, lambda xx, yy: box(xx, yy, "", 9, STROKE_THICK), "Adaptive practice")
    line = lambda xx, yy, colour, name: (f'<path d="M {xx:.1f} {yy:.1f} L {xx + sw - ARROW:.1f} {yy:.1f}" stroke="{colour}" '
                                         f'stroke-width="{LINK_WIDTH}" fill="none" marker-end="url(#arrow-{name})"/>')
    swatch(n + 4, lambda xx, yy: line(xx, yy, LINK_COLOUR["+"], "plus"), "+ : change in the same direction")
    swatch(n + 5, lambda xx, yy: line(xx, yy, LINK_COLOUR["-"], "minus"), "− : change in the opposite direction")
    swatch(n + 6, lambda xx, yy: (f'<path d="M {xx:.1f} {yy:.1f} L {xx + sw:.1f} {yy:.1f}" stroke="{STROKE_COLOUR}" stroke-width="{LINK_WIDTH}"/>'
                                  f'<path d="M {xx + sw / 2 - 4:.1f} {yy - 9:.1f} L {xx + sw / 2 - 4:.1f} {yy + 9:.1f} M {xx + sw / 2 + 4:.1f} {yy - 9:.1f} L {xx + sw / 2 + 4:.1f} {yy + 9:.1f}" '
                                  f'stroke="{STROKE_COLOUR}" stroke-width="2.5"/>'), "Delay")
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


def links_and_elements(cld, bxs, paths):
    """The links, then the elements over them: what svg() and loop_figure() both draw; paths gives
    each link its pieces (link_svg())."""
    return ['<g class="links">', *(link_svg(c, paths[c["from"], c["to"]]) for c in cld["connections"]), "</g>",
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
    region_svg, frame, _, border = regions(cld, bxs)
    x0, y0, x1, y1 = frame  # the frame holds every box
    _, lw, lh = legend_svg(0, 0)
    spot = legend_spot(bxs, paths, frame, border, lw, lh)
    if spot:
        legend, _, _ = legend_svg(*spot)
    else:
        legend, lw, lh = legend_svg(x0, y1 + MARGIN)
        y1 += MARGIN + lh
        x1 = max(x1, x0 + lw)
    vb = (x0 - MARGIN, y0 - MARGIN, x1 - x0 + 2 * MARGIN, y1 - y0 + 2 * MARGIN)
    parts = [*head(vb), '<g class="regions">', region_svg, "</g>", *links_and_elements(cld, bxs, {k: [p] for k, p in paths.items()}), legend, "</svg>"]
    return "\n".join(parts) + "\n"


MARK_R = 48  # the loop mark's radius: it reads at the size of the signs


OVAL_ASPECT = 1.5  # a one-loop figure's oval, its width over its height: the boxes are wider than tall
OVAL_GAP = 150     # the least gap between two boxes of a one-loop figure: room for an arrowhead and its sign


def oval(cld, loop):
    """(elements, bxs, pieces): one named loop laid out as an oval for its figure.

    Its elements evenly spaced on an ellipse round (0, 0), in the loop's order, clockwise, the
    path's first element at the top left and the second at the top right, so the eye starts left
    and reads to the right (Jordy, who disliked the anticlockwise figures that turning the way
    the loop runs in the full drawing gave); the ellipse just large enough that every two boxes keep
    OVAL_GAP apart and the mark has room at its centre. Each link is the piece of the ellipse from
    its source's box border to its target's, as quadratic Beziers of at most 45 degrees, each with
    its control point where the ellipse's tangents at its two ends meet, so the links run along the
    oval (Jordy, chosen between rendered versions: the loop at its places in the full drawing drew
    R3 and R6 lopsided, with long sweeping links)."""
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
        room = min(hypot(max(b[0], 0, -b[2]), max(b[1], 0, -b[3])) for b in bxs.values())
        if room >= MARK_R + 50 and all(gap(bxs[p], bxs[q]) >= OVAL_GAP for k, p in enumerate(path) for q in path[k + 1:]):
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
    return els, bxs, pieces


def loop_figure(cld, loop):
    """One named loop on its own, for the report: laid out as an oval (oval()), its elements and links
    drawn as svg() draws them, its mark at the oval's centre, turning clockwise as the oval does. No
    regions and no legend: the figure stands beside the full drawing."""
    els, bxs, pieces = oval(cld, loop)
    sub = {"elements": els, "connections": [c for c in cld["connections"] if (c["from"], c["to"]) in pieces]}
    ring = [bezier(*p, t / 10) for ps in pieces.values() for p in ps for t in range(11)]
    # the frame: the boxes and the curves, with room for a sign on a curve
    xs = [b[k] for b in bxs.values() for k in (0, 2)] + [p[0] for p in ring]
    ys = [b[k] for b in bxs.values() for k in (1, 3)] + [p[1] for p in ring]
    pad = MARGIN + SIGN_SIZE
    vb = (min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
    parts = [*head(vb), *links_and_elements(sub, bxs, pieces), loop_svg(loop, (0, 0)), "</svg>"]
    return "\n".join(parts) + "\n"


# --- overlap warnings -----------------------------------------------------------------------
def turn(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def meet(p, q, r, s):
    """Whether the segments p-q and r-s cross."""
    return turn(p, q, r) * turn(p, q, s) < 0 and turn(r, s, p) * turn(r, s, q) < 0


def tangles(cld):
    """(crossings, through): the points where two links cross, as pairs of links, and each link
    that passes through a box it does not connect, which reads as if that element mediates it, as
    (link, element); build.py's report counts both, the eye's measure of a layout. Each link is
    sampled at 30 points and tested segment by segment, a pair of links only where their frames meet."""
    bxs = boxes(cld)
    pts = {k: [bezier(*p, i / 30) for i in range(31)] for k, p in link_paths(cld, bxs).items()}
    frame = {k: (min(x for x, _ in p), min(y for _, y in p), max(x for x, _ in p), max(y for _, y in p))
             for k, p in pts.items()}
    apart = lambda f, g: f[2] < g[0] or g[2] < f[0] or f[3] < g[1] or g[3] < f[1]
    keys = list(pts)
    crossings = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if not apart(frame[a], frame[b])
                 for u in range(30) for v in range(30) if meet(pts[a][u], pts[a][u + 1], pts[b][v], pts[b][v + 1])]

    def cuts(p, q, box):
        """Whether the segment p-q enters box: an end inside it, or a crossing with one of its sides."""
        x0, y0, x1, y1 = box[:4]
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return (inside(p, box) or inside(q, box)
                or any(meet(p, q, corners[k], corners[(k + 1) % 4]) for k in range(4)))
    through = [(k, e) for k in keys for e, b in bxs.items() if e not in k and not apart(frame[k], b)
               and any(cuts(pts[k][u], pts[k][u + 1], b) for u in range(30))]
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
