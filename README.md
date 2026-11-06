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
| `actors.json` | the Actor Map: the actors, their columns and their relations, the one list of actors the CLD names | yes |
| `references.json` | the sources, as `"key": "full APA reference"` | yes |
| `model-texts.md` | the model texts the page shows: spatial scale, time horizon, purpose, system boundary, assumptions, the named loops | yes |
| `view.scss` | the Kumu view inside `docs/project.json` | yes |
| `page/` | the page around the drawing: `index.html` (a template), `app.js`, `style.css` | yes |
| `build.py` | checks the model and writes `docs/` (how: its docstring) | — |
| `draw.py` | draws the SVG, imported by `build.py` | — |
| `docs/` | what GitHub Pages serves: `index.html`, `app.js`, `style.css`, `cld.svg`, `loops/<id>.svg`, `regions.svg`, `project.json` | never: `build.py` writes it |

## Version 1

`cld.json` is version 2, built from version 1 and Jordy's review of it, which Jordy and Lenne
chose whole as the final CLD before the group model building session. Version 1, the one Lenne
approved first, is kept only by the git tag `v1` (`git show v1:cld.json`), with no published
page.

## Working on the diagram

Teammates work through the page: read it, click elements and links, and send Jordy the change
in words (a new or wrong link, a better description, a source). Jordy edits the repository,
builds and pushes, so nobody else needs git or Python.

1. Edit `cld.json` (or `actors.json`, `references.json`, `view.scss`, `page/`).
2. `python3 build.py` checks the model and rebuilds `docs/`. It stops on an error (an unknown
   element or actor, a source missing from `references.json`, a link marked a hypothesis that has
   sources, a named loop that is not closed or whose
   R/B does not match its polarities) and prints the source coverage, hypotheses apart, the layout's
   crossings between links and links through a box they do not connect, and any warnings: a model
   text still empty, an element without links, two boxes that overlap, a link and its reverse
   drawn on one curve, an element on the wrong side of the border between the two subsystems,
   a named loop whose own links cross, a link under a region's name, a loop's figure with no
   room inside the loop for its mark, a link through a box it does not connect.
3. Commit, `docs/` included, and push: the push publishes the page. The pre-commit hook refuses
   a commit whose `docs/` is out of date.

Layout tuning: on the page, turn on "Move elements and links": drag an element to move it, drag
a link to bend it (its middle follows the pointer; within 0.03 of straight a Constant's link snaps to
straight and any other keeps that bend), then "Download layout" saves `layout.json`
with every element's position and every link's curvature.
`python3 build.py --layout ~/Downloads/layout.json` writes both into `cld.json` and rebuilds; it
fails on an id or a link that is not in `cld.json`. Dragging redraws the links but not the
regions, which `build.py` draws again from the new positions. Each link has its own bow, chosen
so a reader can follow every connection: every arrowhead and sign clear, each crossing at a wide
angle and away from the arrowheads and signs (how links cross matters more than how often), no
two links running close side by side, a named loop leaving each element about the way it
arrived, the whole drawing readable on one A4 page, no link through
an element it does not connect, which would read as if that element
mediates it, and no named loop whose links cross each other, a figure eight that cannot be
followed round; `build.py` warns on the last. A Constant's links run straight, and `build.py`
warns on a bent one; every other link has some bend (Jordy), and it warns on a straight one. A
Constant sits beside what it drives, its box at most 300 units from each box it drives
(Jordy), and `build.py` warns on one further away.

A picture for the report: `docs/cld.svg` is the drawing on its own, and `docs/loops/<id>.svg`
each named loop on its own, `docs/loops/R1.svg` for R1: its elements evenly round one oval in
the loop's order, clockwise, its path's first element at the top left and the second at the top
right, its links along the oval, and its mark, turning clockwise, at the oval's centre. Google Docs takes no SVG; a PNG, with
Chrome (not part of the build, since Chrome is not on every machine), `svg` the file to convert:

```sh
svg=docs/cld.svg  # or docs/loops/R1.svg
size=$(python3 -c "import re, sys; w, h = re.search(r'viewBox=\"\S+ \S+ (\S+) (\S+)\"', open(sys.argv[1]).read()).groups(); print(f'{int(w) // 2},{int(h) // 2}')" $svg)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --screenshot=$(basename $svg .svg).png --window-size=$size file://$PWD/$svg
```

The window size sets the picture's size; the second line takes half the SVG's `viewBox`, so
the ratio matches and the layout can change. For a sharper picture, divide by less.

### The page

The drawing is larger than a screen: scroll or pinch to zoom at the cursor, drag the
background to pan, "Fit" shows the whole drawing again. A button per named loop highlights its
elements and links, several pressed show their union, and opens a panel with the loop's figure
on its own, `docs/loops/<id>.svg`. A click on an element or a link opens a panel with its fields
and sources; Esc or a click on the background closes it. The footer shows the model version, the
first seven characters of the SHA-256 of `cld.json`, so teammates can tell which model they are
looking at.

### `cld.json`

The model texts are in `model-texts.md`, which `build.py` renders on the page
(Jordy: someone opening the page reads the scale, horizon and assumptions with the drawing). A
word in braces, such as `{feedback loops}`, is a number `build.py` counts in the model; a
`<!-- comment -->` is not shown, and `<!-- Draft, for the team to check. -->` marks a text the
team has not checked yet.

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
- `actor`: on a decision variable, the one actor that decides it, by its `id` in
  `actors.json`, which names every actor at the grain the group set (a public body by its name,
  the island's arable farmers as one); `build.py` stops on an id not there. The page's panel
  shows the actor's label, and Kumu gets it as a field.

A connection: `from` and `to` (element ids), `polarity` (`"+"` or `"-"`), `delay` (true/false,
drawn as two strokes across the link), `description`, `sources`, `hypothesis` (optional, `true`
on a claim about why an actor decides as it does that has no source: a question for the group
model building session, shown in the link's panel and in Kumu's fields, never on the drawing;
a link that finds a source loses it), `curvature` (0 is straight; a positive value bows the
link to the left of its direction).
The drawing runs a link from a point on its source box's edge to one on its target's, the ends
on one edge spread along it, and puts the sign on the side of the arrowhead clear of boxes.
The SETS fields the page and Kumu show ("Cross-domain", "E to S" …) are derived by `build.py`,
never typed.

A named loop: `{"id": "R1", "name": "…", "path": ["element-a", "element-b", …]}`, the path in
causal order without repeating the first element. `build.py` checks that every step is a
connection and that the id starts with R for an even number of `-` links, B for an odd one; the
page gets a button for it, which highlights its elements and links, and `docs/loops/<id>.svg`
draws it on its own, with its mark. The full drawing carries no loop marks: of its 353 feedback
loops no mark could be traced there.

### `actors.json`

The Actor Map's data, by the course's actor analysis guidelines, and the one list of actors:
the CLD's `actor` fields name its ids. At the top, `header` (`working title`, `names`, the
group members as authors, and `partner`) and `question`, the actor analysis's own question.
Then `actors`, each:

- `id` never changes; `label` is its name on the map.
- `scale`: `inside` or `outside`, by the CLD's boundary test (`model-texts.md`, System
  boundary): inside when the island's farms move its decisions and it moves them back before
  2050.
- `type`, `level`, `sector`, `influence score` (1, little, to 5) and `client` (`yes` for the
  group's partners) take the values of the group's old Actor Table, listed in `build.py`, and
  Financial institution and Finance for the banks, which it lacked (Jordy); `interest` and
  `influence` are words, describing, never judging. No paradigm: the course's paradigms are
  the researchers' own, for the group's positionality statement.
- `influence score` rates what the actor's `influence` shows, from its sources, against the
  actor analysis's question (Jordy; no source scores an actor, so `influence` gives each score's
  reason):
  - 5: decides binding rules or plans for the island's farms (the water board's water levels,
    the municipality's land-use plans, EU banking rules), or decides the adaptation itself (the
    farmers);
  - 4: decides something many of the island's farms depend on, without binding them (banks'
    credit, buyers' contracts);
  - 3: shapes those decisions directly: advice, representation, funding;
  - 2: shapes them indirectly;
  - 1: little effect on the island's adaptation by 2050.
- `relations`: each `{"to": <actor id>, "kind": …, "description": …, "sources": […]}`, read
  as "this actor *kind* that one", so the actor holding it influences `to` by it; the kinds are
  the ones a source names, listed in `build.py`: authority over, finances, buys from, advises,
  represents, works with. A cooperation runs both ways, so "works with" is recorded once, on the
  actor that leads it (the municipality for the Living Lab Schouwen-Duiveland), and the table
  shows the other side as influenced by it (Jordy; rejected: on both actors, which draws every
  such pair twice).
- `sources`: keys in `references.json`, as for the CLD.

A field no source carries stays empty (`""`, `null` or `[]`), never a guess, and `python3
build.py` lists each one still empty; it stops on a value outside its list, a relation to an
unknown actor or a source not in `references.json`. The CLD variables each actor decides are
derived from the CLD's `actor` fields, never typed here.

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
