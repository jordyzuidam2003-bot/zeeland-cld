"""Draw the CLD as an SVG, from cld.json's own coordinates (y downwards).

Imported by build.py, which writes docs/cld.svg and puts the same drawing inline in
docs/index.html. svg(cld) returns the drawing as a string; overlaps(cld) the warnings about
boxes that intersect, for build.py's report; boxes(cld) the geometry build.py gives Kumu's
elements.

What is drawn, from back to front:
  links     a quadratic Bezier from box border to box border, the sign beside the arrowhead on
            the outside of the curve, a delay as two short strokes across the midpoint
  elements  the label in a box filled with the pale tint of its SETS domain, the one place the
            domain shows in the drawing (the layout follows the loops, not the domains):
            square corners for a Stock, rounded for an Auxiliary, dashed for a Constant, a
            thick stroke for an adaptive practice
  loops     a named loop's id with a circular arrow at the centroid of its path's elements
  legend    bottom-left

The link formula is duplicated in page/app.js (drag mode recomputes a moved element's links):
keep link_path() and its JS twin the same.
"""

from math import cos, hypot, pi, sin

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
LINK_COLOUR = {"+": "#2166AC", "-": "#B2182B"}
SIGN_TEXT = {"+": "+", "-": "−"}
SIGN_SIZE = 34
LEGEND_SIZE = 36               # the legend reads at a glance, so larger than the labels (Jordy)
ARROW = 14                     # arrowhead length, in drawing units
TINT = {  # each box's fill: the hue of Figure 1 in the group's Project Plan, as a pale tint
    "Ecological": "#BDE3C7", "Social": "#C5DAF4", "Technological": "#F9D2AB"}
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


def lerp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def sub_curve(p0, p1, p2, t0, t1):
    """The piece [t0, t1] of a quadratic Bezier is one too: split at t0, keep the right piece
    (B(t0), lerp(p1, p2, t0), p2), split that at s and keep the left piece."""
    r0, r1 = bezier(p0, p1, p2, t0), lerp(p1, p2, t0)
    s = (t1 - t0) / (1 - t0) if t0 < 1 else 0
    return r0, lerp(r0, r1, s), bezier(p0, p1, p2, t1)


def link_svg(c, a, b):
    p0, ctrl, p2 = link_path(a, b, c["curvature"])
    colour = LINK_COLOUR[c["polarity"]]
    parts = [f'<g class="link" data-from="{c["from"]}" data-to="{c["to"]}" data-sign="{c["polarity"]}" '
             f'data-delay="{"true" if c["delay"] else "false"}" data-curvature="{c["curvature"]}">',
             f'<path class="link-path" d="M {p0[0]:.1f} {p0[1]:.1f} Q {ctrl[0]:.1f} {ctrl[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}" '
             f'fill="none" stroke="{colour}" stroke-width="{LINK_WIDTH}" marker-end="url(#arrow-{"plus" if c["polarity"] == "+" else "minus"})"/>']
    sx, sy = sign_position(p0, ctrl, p2)
    parts.append(f'<text class="sign" x="{sx:.1f}" y="{sy:.1f}" text-anchor="middle" dominant-baseline="central" '
                 f'font-size="{SIGN_SIZE}" font-weight="bold" fill="{colour}">{SIGN_TEXT[c["polarity"]]}</text>')
    if c["delay"]:
        parts.append(f'<path class="delay" d="{delay_path(p0, ctrl, p2)}" stroke="{STROKE_COLOUR}" stroke-width="2.5" fill="none"/>')
    parts.append("</g>")
    return "\n".join(parts)


def sign_position(p0, ctrl, p2, back=26, out=16):
    """Beside the arrowhead: `back` units before the end, `out` units to the outside of the curve."""
    tx, ty = tangent(p0, ctrl, p2, 0.92)
    n = hypot(tx, ty) or 1
    ux, uy = tx / n, ty / n
    # the outside of the bow is the side the control point lies on, relative to the chord
    mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2
    side = (ctrl[0] - mx) * -(p2[1] - p0[1]) + (ctrl[1] - my) * (p2[0] - p0[0])
    if abs(side) < 1e-6:
        side = -1.0  # a straight link: its left, seen along the arrow
    s = 1 if side > 0 else -1
    nx, ny = -uy * s, ux * s
    return p2[0] - ux * back + nx * out, p2[1] - uy * back + ny * out


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
def loop_svg(loop, bxs):
    pts = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in bxs]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    r = 24
    # a three-quarter circle, clockwise, ending with the arrowhead
    a0, a1 = -pi / 2, pi
    start = (cx + r * cos(a0), cy + r * sin(a0))
    end = (cx + r * cos(a1), cy + r * sin(a1))
    return "\n".join([
        f'<g class="loop" data-id="{loop["id"]}">',
        f'<path d="M {start[0]:.1f} {start[1]:.1f} A {r} {r} 0 1 1 {end[0]:.1f} {end[1]:.1f}" fill="none" '
        f'stroke="{STROKE_COLOUR}" stroke-width="2" marker-end="url(#arrow-grey)"/>',
        f'<text class="loop-id" x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="central" '
        f'font-weight="bold">{esc(loop["id"])}</text>',
        "</g>"])


# --- legend ---------------------------------------------------------------------------------
def legend_svg(x, y):
    """Bottom-left legend; returns (svg, width, height)."""
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
def svg(cld):
    bxs = boxes(cld)
    x0 = min(b[0] for b in bxs.values())
    y0 = min(b[1] for b in bxs.values())
    x1 = max(b[2] for b in bxs.values())
    y1 = max(b[3] for b in bxs.values())
    legend, lw, lh = legend_svg(x0, y1 + MARGIN)
    y1 += MARGIN + lh
    x1 = max(x1, x0 + lw)
    vb = (x0 - MARGIN, y0 - MARGIN, x1 - x0 + 2 * MARGIN, y1 - y0 + 2 * MARGIN)

    arrow = lambda name, colour: (f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="{ARROW}" '
                                  f'markerHeight="{ARROW}" markerUnits="userSpaceOnUse" orient="auto">'
                                  f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{colour}"/></marker>')
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb[0]:.0f} {vb[1]:.0f} {vb[2]:.0f} {vb[3]:.0f}" '
        f'font-family="{FONT}" font-size="{FONT_SIZE}" fill="black">',
        "<defs>", arrow("plus", LINK_COLOUR["+"]), arrow("minus", LINK_COLOUR["-"]), arrow("grey", STROKE_COLOUR), "</defs>",
        f'<rect x="{vb[0]:.0f}" y="{vb[1]:.0f}" width="{vb[2]:.0f}" height="{vb[3]:.0f}" fill="white"/>',
        '<g class="links">', *(link_svg(c, bxs[c["from"]], bxs[c["to"]]) for c in cld["connections"]), "</g>",
        '<g class="elements">', *(element_svg(e, bxs[e["id"]]) for e in cld["elements"]), "</g>",
        '<g class="loops">', *(loop_svg(l, [bxs[i] for i in l["path"]]) for l in cld["loops"]), "</g>",
        legend,
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


# --- overlap warnings -----------------------------------------------------------------------
def overlaps(cld):
    """Pairs of element boxes that intersect."""
    bxs = boxes(cld)
    ids = [e["id"] for e in cld["elements"]]
    out = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            p, q = bxs[a], bxs[b]
            if p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]:
                out.append(f"boxes overlap: {a} and {b}")
    return out
