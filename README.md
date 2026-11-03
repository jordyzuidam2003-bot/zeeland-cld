# Zeeland CLD

The causal loop diagram of our Challenge Based Project: adapting Zeeland's arable farming to
salinisation and freshwater scarcity towards 2050, with the Delta Climate Center and the Ministry
of LVVN. This repository is the single source of truth for the diagram: `build.py` draws it as a
web page, served by GitHub Pages from `docs/`, so a push publishes the current model.

## Files

| File | What it holds | Edit? |
| --- | --- | --- |
| `cld.json` | the model texts, elements, connections, named loops, layout (x, y) and link curvature | yes |
| `references.json` | the sources, as `"key": "full APA reference"` | yes |
| `view.scss` | the Kumu view inside `docs/project.json` | yes |
| `page/` | the page around the drawing: `index.html` (a template), `app.js`, `style.css` | yes |
| `build.py` | checks the model and writes `docs/` (how: its docstring) | — |
| `draw.py` | draws the SVG, imported by `build.py` | — |
| `docs/` | what GitHub Pages serves: `index.html`, `app.js`, `style.css`, `cld.svg`, `project.json` | never: `build.py` writes it |

## Working on the diagram

Teammates work through the page: read it, click elements and links, and send Jordy the change
in words (a new or wrong link, a better description, a source). Jordy edits the repository,
builds and pushes, so nobody else needs git or Python.

1. Edit `cld.json` (or `references.json`, `view.scss`, `page/`).
2. `python3 build.py` checks the model and rebuilds `docs/`. It stops on an error (an unknown
   element, a source missing from `references.json`, a named loop that is not closed or whose
   R/B does not match its polarities) and prints the source coverage and any warnings: a model
   text still empty, an element without links, boxes or SETS regions that overlap, a link
   between two elements of one domain that bows out of its region (fix: a smaller `curvature`).
3. Commit, `docs/` included, and push: the push publishes the page. The pre-commit hook refuses
   a commit whose `docs/` is out of date.

Layout tuning: on the page, turn on "Move elements", drag elements, then "Download layout"
saves `layout.json` with every element's position. `python3 build.py --layout ~/Downloads/layout.json`
writes those positions into `cld.json` and rebuilds; it fails on an id that is not in
`cld.json`. Curvature is edited in `cld.json` only. The SETS regions follow the elements only
after a rebuild.

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
background to pan, "Fit" shows the whole drawing again. Buttons highlight a part of the diagram: a SETS domain, the links that cross a SETS boundary,
the adaptive practices, what has no source yet, the links with a delay, and each named loop;
several pressed show their union. A click on an element or a link opens a panel with its fields
and sources; Esc or a click on the background closes it. The footer shows the model version, the
first seven characters of the SHA-256 of `cld.json`, so teammates can tell which model they are
looking at.

### `cld.json`

The top-level `model` object holds the texts the group writes: `purpose`, `spatial scale`,
`time horizon`, `system boundary`. The page shows them; `build.py` warns while one is empty.

An element:

```json
{
  "id": "root-zone-salinity",
  "label": "Root zone salinity",
  "element type": "Auxiliary",
  "adaptive practice": false,
  "sets domain": "Ecological",
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
  `Technological`; the drawing puts a tinted region around each domain.
- `x` and `y` are positions in the drawing; y grows downwards.

A connection: `from` and `to` (element ids), `polarity` (`"+"` or `"-"`), `delay` (true/false,
drawn as two strokes across the link), `loop id` (the old Kumu tag), `description`, `sources`,
`curvature` (0 is straight; a positive value bows the link to the left of its direction).
The SETS fields the page and Kumu show ("Cross-domain", "E to S" …) are derived by `build.py`,
never typed.

A named loop: `{"id": "R1", "name": "…", "path": ["element-a", "element-b", …]}`, the path in
causal order without repeating the first element. `build.py` checks that every step is a
connection and that the id starts with R for an even number of `-` links, B for an odd one; the
drawing marks the loop at the centre of its elements, and the page gets a button for it.

## Setup after cloning

`git config core.hooksPath hooks` turns on the pre-commit check. The scripts need only Python 3.

## Kumu

Kumu holds a copy for milestones, in the project `cbp-cld`, and is never edited: an import never
updates what a project already holds, so each update means emptying the project first. Jordy
empties `cbp-cld`, then: green `+` → Import → Advanced → "Import JSON file" → `docs/project.json`
→ "Import JSON" → "Save Changes". Kumu restores the elements at their positions, the curved
links and the view from `view.scss`.

The view follows the page's look as far as Kumu can: white boxes with the label inside, square
corners for a stock and a pill for the others, a second outer border for a constant (Kumu has no
dashed border), a thick border for an adaptive practice; links of one width, blue `+` and red
`−`. Each SETS region is a background element: a pill in the region's tint that covers the
page's region, with the domain's name. `build.py` adds the rules that size each box and each
region below `view.scss`, and a double space where the page breaks a label's line (Kumu's manual
line break). The project's description and the map's name carry the model version, so Kumu says
which model it holds.
