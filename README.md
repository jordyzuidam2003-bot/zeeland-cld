# Zeeland CLD

The causal loop diagram of our Challenge Based Project: adapting Zeeland's arable farming to
salinisation and freshwater scarcity towards 2050, with the Delta Climate Center and the Ministry
of LVVN. This repository is the single source of truth for the diagram. The Kumu map reads it
from GitHub; nothing is edited in Kumu itself.

## Files

| File | What it holds | Edit? |
| --- | --- | --- |
| `cld.json` | elements, connections, named loops, layout (x, y) and link curvature | yes |
| `references.json` | the sources, as `"key": "full APA reference"` | yes |
| `view.scss` | the Kumu view: colours, shapes, legend, buttons | yes |
| `build.py` | checks the model and writes `dist/` (how: its docstring) | — |
| `import_kumu.py` | pulls a Kumu project export into `cld.json`, or only its layout | — |
| `kumu-place.js` | sets the Kumu map's positions from `cld.json` (how: its comment) | — |
| `dist/` | what Kumu reads: `kumu.json`, `view.scss` | never: `build.py` writes it |

## Working on the diagram

1. Edit `cld.json` (or `references.json`, `view.scss`).
2. `python3 build.py` checks the model and rebuilds `dist/`. It stops on an error (an
   unknown element, a source missing from `references.json`, a named loop that is not closed or
   whose R/B does not match its polarities) and prints the source coverage and any warnings.
3. Commit, `dist/` included, and push. The pre-commit hook refuses a commit whose `dist/` is
   out of date.
4. Refresh the Kumu map. GitHub caches the raw file for up to 5 minutes.
5. Only when `dist/view.scss` changed (style or curvature): paste it into Kumu's
   Advanced Editor and save. Kumu cannot fetch a view.

### `cld.json`

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
- `element type`: `Constant`, `Auxiliary` or `Stock`. `adaptive practice`: true on an auxiliary
  that is an adaptive practice (a measure farmers take). `sets domain`: `Social`, `Ecological` or `Technological`.
- `x` and `y` are map positions; y grows downwards.

A connection: `from` and `to` (element ids), `polarity` (`"+"` or `"-"`), `delay` (true/false),
`loop id` (the old Kumu tag), `description`, `sources`, `curvature` (0 is straight; the sign picks
the side). The SETS fields Kumu shows ("Cross-domain", "E to S" …) are derived by `build.py`,
never typed.

The top-level `model` object holds the texts the group writes: `purpose`, `spatial scale`,
`time horizon`, `system boundary`. `build.py` warns while one is empty.

A named loop: `{"id": "R1", "name": "…", "path": ["element-a", "element-b", …]}`, the path in
causal order without repeating the first element. `build.py` checks that every step is a
connection and that the id starts with R for an even number of `-` links, B for an odd one.

## Setup after cloning

`git config core.hooksPath hooks` turns on the pre-commit check. The scripts need only Python 3.

## How Kumu is connected

Kumu's "Link map to remote JSON" (green + → Import) points the map at
<https://raw.githubusercontent.com/jordyzuidam2003-bot/zeeland-cld/main/dist/kumu.json>.
A remote blueprint carries elements, connections and loops only, not positions or a view. The
map itself keeps those: the view code is pasted from `dist/view.scss`, and the positions are
set from `cld.json` with `kumu-place.js`, pasted into the browser console on the map (Chrome:
Cmd+Opt+J). It pins every element at its `x` and `y` fields, and Kumu keeps pinned positions
across refreshes. It uses Kumu's internal objects, so a Kumu update may break it.

Layout tuning: drag elements in Kumu, export the project (JSON), then
`python3 import_kumu.py <export.json> --layout` copies the positions back into `cld.json`.
Curvature is edited in `cld.json` only: the view sets every link's curve, so dragging a curve
in Kumu has no effect.
