# Zeeland CLD

The causal loop diagram of our Challenge Based Project: adapting Zeeland's arable farming to
salinisation and freshwater scarcity towards 2050, with the Delta Climate Center and the Ministry
of LVVN. This repository is the single source of truth for the diagram: `build.py` draws it as a
web page, <https://jordyzuidam2003-bot.github.io/zeeland-cld/>, served by GitHub Pages from
`docs/`, so a push publishes the current model.

## Files

| File | What it holds | Edit? |
| --- | --- | --- |
| `cld.json` | the elements, connections, named loops, layout (x, y) and link curvature | yes |
| `references.json` | the sources, as `"key": "full APA reference"` | yes |
| `view.scss` | the Kumu view inside `docs/project.json` | yes |
| `page/` | the page around the drawing: `index.html` (a template), `app.js`, `style.css` | yes |
| `build.py` | checks the model and writes `docs/` (how: its docstring) | — |
| `draw.py` | draws the SVG, imported by `build.py` | — |
| `docs/` | what GitHub Pages serves: `index.html`, `app.js`, `style.css`, `cld.svg`, `regions.svg`, `project.json` | never: `build.py` writes it |

## Working on the diagram

Teammates work through the page: read it, click elements and links, and send Jordy the change
in words (a new or wrong link, a better description, a source). Jordy edits the repository,
builds and pushes, so nobody else needs git or Python.

1. Edit `cld.json` (or `references.json`, `view.scss`, `page/`).
2. `python3 build.py` checks the model and rebuilds `docs/`. It stops on an error (an unknown
   element, a source missing from `references.json`, a named loop that is not closed or whose
   R/B does not match its polarities) and prints the source coverage and any warnings: a model
   text still empty, an element without links, two boxes that overlap, a link and its reverse
   drawn on one curve, an element on the wrong side of the border between the two subsystems,
   a named loop whose own links cross, a link under a region's name.
3. Commit, `docs/` included, and push: the push publishes the page. The pre-commit hook refuses
   a commit whose `docs/` is out of date.

Layout tuning: on the page, turn on "Move elements and links": drag an element to move it, drag
a link to bend it (its middle follows the pointer; near straight it snaps to straight), then "Download layout" saves `layout.json`
with every element's position and every link's curvature.
`python3 build.py --layout ~/Downloads/layout.json` writes both into `cld.json` and rebuilds; it
fails on an id or a link that is not in `cld.json`. Dragging redraws the links but not the
regions, which `build.py` draws again from the new positions. Each link has its own bow, chosen
so a reader can follow every connection: every arrowhead and sign clear, as few crossings as
possible, no link through an element it does not connect, which would read as if that element
mediates it, and no named loop whose links cross each other, a figure eight that cannot be
followed round; `build.py` warns on the last. A Constant's links run straight, and `build.py`
warns on a bent one.

A picture for the report: `docs/cld.svg` is the drawing on its own. Google Docs takes no SVG; a
PNG, with Chrome (not part of the build, since Chrome is not on every machine):

```sh
size=$(python3 -c "import re; w, h = re.search(r'viewBox=\"\S+ \S+ (\S+) (\S+)\"', open('docs/cld.svg').read()).groups(); print(f'{int(w) // 2},{int(h) // 2}')")
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --screenshot=cld.png --window-size=$size file://$PWD/docs/cld.svg
```

The window size sets the picture's size; the first line takes half the SVG's `viewBox`, so
the ratio matches and the layout can change. For a sharper picture, divide by less.

### The page

The drawing is larger than a screen: scroll or pinch to zoom at the cursor, drag the
background to pan, "Fit" shows the whole drawing again. A button per named loop highlights its
elements and links; several pressed show their union. A click on an element or a link opens a panel with its fields
and sources; Esc or a click on the background closes it. The footer shows the model version, the
first seven characters of the SHA-256 of `cld.json`, so teammates can tell which model they are
looking at.

### `cld.json`

The model texts (purpose, spatial scale, time horizon, system boundary) are drafted outside
this repository and not published for now (Jordy).

An element:

```json
{
  "id": "root-zone-salinity",
  "label": "Root zone salinity",
  "element type": "Auxiliary",
  "adaptive practice": false,
  "sets domain": "Ecological",
  "subsystem": "Water and soil",
  "subquestion": "SQ1",
  "description": "…",
  "sources": ["key-in-references-json"],
  "x": 1254,
  "y": 2928
}
```

- `id` never changes, so a label can: connections and loops refer to the id.
- `element type`: `Constant` (an exogenous driver, drawn dashed), `Auxiliary` (rounded corners)
  or `Stock` (square corners). `adaptive practice`: true on an auxiliary that is a measure
  farmers take, drawn with a thick stroke. `sets domain`: `Social`, `Ecological` or
  `Technological`; the drawing fills the box with the domain's tint. `subsystem`: `Water and
  soil` or `Agricultural economy`, the project's two subsystems, drawn as two faint regions
  behind the boxes split by one smooth border (water and soil left), each named in its top
  corner; the group proposes the split and the names from the CLD, and the Project Plan
  follows it.
- `x` and `y` are positions in the drawing; y grows downwards.

A connection: `from` and `to` (element ids), `polarity` (`"+"` or `"-"`), `delay` (true/false,
drawn as two strokes across the link), `description`, `sources`,
`curvature` (0 is straight; a positive value bows the link to the left of its direction).
The drawing runs a link from a point on its source box's edge to one on its target's, the ends
on one edge spread along it, and puts the sign on the side of the arrowhead clear of boxes.
The SETS fields the page and Kumu show ("Cross-domain", "E to S" …) are derived by `build.py`,
never typed.

A named loop: `{"id": "R1", "name": "…", "path": ["element-a", "element-b", …]}`, the path in
causal order without repeating the first element. `build.py` checks that every step is a
connection and that the id starts with R for an even number of `-` links, B for an odd one; the
page gets a button for it, which highlights its elements and links. The full drawing carries
no loop marks: of its 353 feedback loops no mark could be traced there.

## Setup after cloning

`git config core.hooksPath hooks` turns on the pre-commit check. The scripts need only Python 3.

## Kumu

Kumu holds a copy for milestones, at <https://kumu.io/JordyZuidam/cbp-cld>, and is never edited.
An import never updates what a project already holds, and Kumu cannot empty a project, so each
update is a new project under the same name, which keeps the URL. Jordy renames the previous
`cbp-cld`, then on the Kumu dashboard: New Project → name `cbp-cld`, public → the next screen →
"restore backup" (the link at the bottom) → `docs/project.json`. Only a brand-new project restores
a project export; the green `+` → Import route brings in the elements and connections alone.
Kumu restores the map with the elements at their positions, the view from `view.scss`, the named
loops (each its links, its "R1 …" label hidden on the map by the view, as the page has no loop
marks, and a showcase button per named loop, as on the page), and the project's name,
which the export sets to `cbp-cld`.

The view follows the page's look as far as Kumu can: boxes tinted by SETS domain with the label
inside, square corners for a stock and rounded ones for the others, an italic label for a
constant (Kumu has no dashed border), a thick border for an adaptive practice; links of one
width, blue `+` and red `−`. Kumu draws each link from centre to centre. The regions reach Kumu
as a background image: `build.py` writes them alone as `docs/regions.svg`, in the elements'
coordinates, and `project.json` holds an element labelled `background`, pinned at the centre of
the regions' frame with the frame's width and height, which the `#background` rule in
`view.scss` shows as that image, from its URL on the published page, behind the map. Every
showcase button selects it too, so it stays when a button fades the rest. The subsystem is also
a field there. `build.py` adds the rules that tint and size each box below `view.scss`, and
a double space where the page breaks a label's line (Kumu's manual line break). The project's
description and the map's name carry the model version, so Kumu says which model it holds.
