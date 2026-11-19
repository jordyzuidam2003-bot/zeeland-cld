"""Jordy's drawings behind the CLD and the Actor Map: the subsystem regions and the level bands.

He drew them in Affinity (backgrounds/cbp1-cld.af, cbp1-actors.af) over a Kumu export of each map, so
each PNG covers exactly that export's frame. The page (draw_cld.svg(), draw_actor_map.svg()) and the
Kumu export (build.py's project(), actors_project()) both place a PNG at its frame, the PNG one unit
per pixel, so a box sits in its region in both as in his drawing (the drawing is
his own; rejected: the regions and bands build.py generated). A box moved off its place in the drawing
keeps no region: a session checks the boxes against the drawings after a move (README's Kumu).
"""

import base64
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (PNG, the centre of its frame in the model's coordinates): the centre of the Kumu export's frame
# he drew over, measured from the export's boxes, whose model places it holds to 0.0 units
BACKDROPS = {
    "cld": ("backgrounds/background-cld.png", (91.5, 35.6)),
    "actors": ("backgrounds/background-actor.png", (1773.0, 932.0)),
}


def size(name):
    """(width, height) of the PNG, read from its header: its size in the model's units."""
    head = (ROOT / BACKDROPS[name][0]).read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{BACKDROPS[name][0]} is not a PNG")
    return struct.unpack(">II", head[16:24])


def frame(name):
    """(x0, y0, x1, y1): the PNG's frame in the model's coordinates."""
    (cx, cy), (w, h) = BACKDROPS[name][1], size(name)
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def data_url(name):
    """The PNG as a data URL: inside the page and the Kumu export, so neither depends on a host and
    nothing in Kumu links to this repository."""
    return "data:image/png;base64," + base64.b64encode((ROOT / BACKDROPS[name][0]).read_bytes()).decode()


def image_svg(name):
    """The PNG as an SVG <image> at its frame, for the page's drawing."""
    x0, y0, x1, y1 = frame(name)
    return (f'<image href="{data_url(name)}" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.0f}" '
            f'height="{y1 - y0:.0f}" preserveAspectRatio="none"/>')
