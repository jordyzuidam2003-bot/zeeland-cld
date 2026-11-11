# Zeeland CLD

The causal loop diagram of our Challenge Based Project: adapting Zeeland's arable farming to
salinisation and freshwater scarcity towards 2050, with the Delta Climate Center and the Ministry
of LVVN. This repository is the single source of truth for the diagram: `build.py` draws it as a
web page, <https://jordyzuidam2003-bot.github.io/zeeland-cld/>, served by GitHub Pages from
`docs/`, so a push publishes the current model. Beside it, the same way, the Actor Map:
<https://jordyzuidam2003-bot.github.io/zeeland-cld/actors.html>, with the actors' table as a
spreadsheet.

## Layout

```text
build.py        checks the model and writes docs/: every route runs python3 build.py from here
model/          what the group edits: the CLD, the Actor Map, their sources and the model texts
src/            what build.py uses: the drawing code, and the templates and views it fills
  templates/    the pages around the drawings, copied or filled into docs/
  kumu/         the Kumu views, inside the export in docs/kumu/
docs/           built by build.py and never edited; GitHub Pages publishes it, and allows no other folder name
  assets/       the pages' scripts and style
  figures/      the drawings for the report: the CLD, the Actor Map, each loop on its own
    named-loops/     each named loop
    combined-loops/  each group of named loops
  tables/       the CLD's and the actors' tables, for Google Sheets
  kumu/         the Kumu project export
hooks/          the pre-commit check
```

The files sit in folders by what they are for, and their names say which model each belongs to
(Jordy: "do what you think is best"). `docs/` keeps its name, since GitHub Pages publishes only
the repository's root or `docs/`. `docs/index.html` and `docs/actors.html` stay at the top of
`docs/`, since their addresses may already be shared.

## Files

| File | What it holds | Edit? |
| --- | --- | --- |
| `model/cld.json` | the elements, connections, named loops, layout (x, y) and link curvature | yes |
| `model/actor-map.json` | the Actor Map: the actors, their columns, their relations and places, the one list of actors the CLD names | yes |
| `model/references.json` | the sources, as CSL JSON, from which `build.py` writes each APA reference | yes |
| `model/references.zotero.json` | the Use note in Zotero that `push` wrote for each source, with a fingerprint of its text, so a push never replaces a note somebody changed | never: `push` writes it |
| `model/cld-texts.md` | the model texts the page shows: spatial scale, time horizon, purpose, system boundary, assumptions, the named loops | yes |
| `src/kumu/cld-view.scss`, `src/kumu/actor-map-view.scss` | the Kumu views inside `docs/kumu/kumu-project.json` | yes |
| `src/templates/` | the pages around the drawings: `index.html` and `actors.html` (templates), `app.js`, `actors.js`, `map.js` (moving and zooming, the bar and the menu, for both pages), `style.css` | yes |
| `build.py` | checks the model and the actors and writes `docs/` (how: its docstring) | — |
| `src/draw_cld.py` | draws the CLD's SVG, imported by `build.py` | — |
| `src/draw_actor_map.py` | draws the Actor Map and lays out its table, imported by `build.py` | — |
| `src/write_xlsx.py` | writes the table as an `.xlsx` with the standard library | — |
| `docs/` | what GitHub Pages serves: `index.html`, `actors.html`; `assets/` (`app.js`, `actors.js`, `map.js`, `style.css`); `figures/` (`cld.svg`, `actor-map.svg`, `named-loops/<id>.svg`, `combined-loops/<id>.svg`); `tables/` (`cld-table.xlsx`, `actor-map-table.xlsx`); `kumu/` (`kumu-project.json`) | never: `build.py` writes it |

## Version 1

`model/cld.json` is version 2, built from version 1 and Jordy's review of it, which Jordy and Lenne
chose whole as the final CLD before the group model building session. Version 1, the one Lenne
approved first, is kept only by the git tag `v1` (`git show v1:cld.json`: the tag keeps it at the root), with no published
page.

## Working on the diagram

Teammates work through the page: read it, click elements and links, and send Jordy the change
in words (a new or wrong link, a better description, a source). Jordy edits the repository,
builds and pushes, so nobody else needs git or Python.

1. Edit `model/cld.json` (or `model/actor-map.json`, `model/references.json`, `src/kumu/cld-view.scss`, `src/templates/`).
2. `python3 build.py` checks the model and rebuilds `docs/`. It stops on an error (an unknown
   element or actor, a source missing from `model/references.json` or an item there lacking a field its
   APA reference needs, a link marked a hypothesis that has
   sources, a named loop that is not closed or whose
   R/B does not match its polarities, a feedback loop with no stock) and prints the source coverage, hypotheses apart, the layout's
   crossings between links and links through a box they do not connect, and any warnings: a model
   text still empty, an element without links, two boxes that overlap, a link and its reverse
   drawn on one curve, an element on the wrong side of the border between the two subsystems,
   a named loop whose own links cross, a link under a region's name, a loop's figure with no
   room inside the loop for its mark, a link through a box it does not connect.
3. Commit, `docs/` included, and push: the push publishes the page. The pre-commit hook refuses
   a commit whose `docs/` is out of date.

Layout tuning: on the page, turn on "Move": drag an element to move it, drag
a delay mark to shift it along its own line, a link to bend it (its middle follows the pointer; within 0.03 of straight a Constant's link snaps to
straight and any other keeps that bend), then "Download layout" saves `layout.json`
with every element's position, every link's curvature and each delay mark that was dragged.
`python3 build.py --layout ~/Downloads/layout.json` writes both into `model/cld.json` and rebuilds; it
fails on an id or a link that is not in `model/cld.json`. Dragging redraws the links but not the
regions, which `build.py` draws again from the new positions. Each link has its own bow, chosen
so a reader can follow every connection: every arrowhead and sign clear, each crossing at a wide
angle and away from the arrowheads and signs (how links cross matters more than how often), no
two links running close side by side, a named loop leaving each element about the way it
arrived, the whole drawing readable on one A4 page, no link through
an element it does not connect, which would read as if that element
mediates it, and no named loop whose links cross each other, a figure eight that cannot be
followed round; `build.py` warns on the last. A Constant's links run straight, and `build.py`
warns on a bent one; every other link has some bend (Jordy), and it warns on a straight one. A
Constant sits beside what it drives, its box at most 400 units from each box it drives
(Jordy), and `build.py` warns on one further away.

A picture for the report: `docs/figures/cld.svg` is the drawing on its own, and `docs/figures/named-loops/<id>.svg`
each named loop on its own, `docs/figures/named-loops/R1.svg` for R1: its elements evenly round one oval in
the loop's order, clockwise, its path's first element at the top left and the second at the top
right, its links along the oval, and its mark, turning clockwise, at the oval's centre. Google Docs takes no SVG; a PNG, with
Chrome (not part of the build, since Chrome is not on every machine), `svg` the file to convert:

```sh
svg=docs/figures/cld.svg  # or docs/figures/named-loops/R1.svg
size=$(python3 -c "import re, sys; w, h = re.search(r'viewBox=\"\S+ \S+ (\S+) (\S+)\"', open(sys.argv[1]).read()).groups(); print(f'{int(w) // 2},{int(h) // 2}')" $svg)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --screenshot=$(basename $svg .svg).png --window-size=$size file://$PWD/$svg
```

The window size sets the picture's size; the second line takes half the SVG's `viewBox`, so
the ratio matches and the layout can change. For a sharper picture, divide by less.

### The page

Both pages are built alike (`src/templates/map.js`, `src/templates/style.css`). The drawing fills the window and
all else floats over it, so a gesture on the map moves the map and never the page: the bar at
the top left holds the menu button, +, −, Fit, Move (on the CLD, with "Download layout" beside it
while it is on) and true fullscreen, which a browser allows only after a click. The menu holds
the rest and stays open until its button or Esc closes it, so several loops can be pressed; with
it closed the bar names the highlighted loops. On a
trackpad two fingers move the map and a pinch zooms at the fingers; a mouse wheel zooms at the
cursor; on a touch screen one finger moves it and two zoom. Dragging moves the map, from a box or
a link too, and a press that barely moves stays a click; a double click on the background zooms
in, and "Fit" shows the whole drawing below the bar. A
button per named loop highlights its
elements and links, several pressed show their union, and opens a panel with the loop's figure
on its own, `docs/figures/named-loops/<id>.svg`; the buttons are a list in the menu, Individual loops and Combined
loops, and a group's button does the same for all its loops, its figure `docs/figures/combined-loops/<id>.svg`. A click on an element or a link opens a panel with its fields
and sources; Esc or a click on the background closes it. The menu shows the model version, the
first seven characters of the SHA-256 of `model/cld.json`, so teammates can tell which model they are
looking at.

### The table

`docs/tables/cld-table.xlsx`, linked from the page, is the table that explains the CLD, which Jordy imports
into Google Drive as a Google Sheet, as the actors' table (Jordy; rejected: an HTML page, whose
tables lost their columns pasted into Google Docs). `build.py` writes it from `model/cld.json`, so it
never drifts from the drawing: the Elements sheet (by subsystem, then by label: type, SETS
domain, subsystem, description, simplification, the actor that decides it, the actors that
decide or shape it, sources), the Links sheet (by their ends: polarity, delay, description,
simplification, sources or that it is a hypothesis), the Named loops sheet (R or B, the elements
in order, the description), the Combined loops sheet once `model/cld.json` holds them, and the
References sheet. The sources are in-text citations, the letter after a year the one
`year-suffix` sets.

### `model/cld.json`

The model texts are in `model/cld-texts.md`, which `build.py` renders into the page, where the link
"Purpose, boundary and assumptions" in the menu opens them over the drawing and Esc closes them (Jordy:
the map fills the page; rejected: the texts below the drawing). A
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
  or `Stock` (square corners). `adaptive practice`: true on a variable that is a measure
  farmers take, drawn with a thick stroke. `sets domain`: `Social`, `Ecological` or
  `Technological`; the drawing fills the box with the domain's tint. `subsystem`: `Water and
  soil` or `Agricultural economy`, the project's two subsystems, drawn as two faint regions
  behind the boxes split by one smooth border (water and soil left), each named in its top
  corner; the group proposes the split and the names from the CLD, and the Project Plan
  follows it.
- `x` and `y` are positions in the drawing; y grows downwards.
- `actor`: on a decision variable, the one actor that decides it, by its `id` in
  `model/actor-map.json`, which names every actor at the grain the group set (a public body by its name,
  the island's arable farmers as one); `build.py` stops on an id not there. The page's panel
  shows the actor's label, and Kumu gets it as a field.
- `actors`: the ids in `model/actor-map.json` of the actors outside the CLD's scale whose decisions
  shape the element directly, each shown by a source in the element's `sources`, a national body
  only where a source shows a direct effect. The actors inside the scale are derived, never
  typed: an element's own `actor` and the `actor` of each decision variable linked into it,
  since an actor inside the scale acts through its decisions and each link carries its source
  (Jordy; rejected: typing every actor, a second record of the links that goes stale when a link
  moves). `build.py` stops on an id not in `model/actor-map.json` or an actor inside the scale, and lists
  each element no actor decides or shapes directly; the table shows the actors, derived and
  typed, by their labels, and Kumu gets them as a field. It names who shapes the element, never
  whose lever it is.
- `simplification`: only on an element or a connection that folds or idealizes something (a
  step of a chain folded into a link, several things counted as one), saying what it leaves out
  or distorts and why the loops through it still hold (Jordy; rejected: the field on every
  element, most of which would read "none"). The page's panel shows it and Kumu gets it as a
  field; `build.py` stops on an empty one. What holds for every element (island totals, the
  farmers as one actor) is in the model texts' Assumptions, and why the CLD simplifies at all
  in their Simplifications.

A connection: `from` and `to` (element ids), `polarity` (`"+"` or `"-"`), `delay` (true/false,
drawn as two strokes across the link), `description`, `sources`, `hypothesis` (optional, `true`
on a claim about why an actor decides as it does that has no source: a question for the group
model building session, shown in the link's panel and in Kumu's fields, never on the drawing;
a link that finds a source loses it, and a named loop's or group's description that calls one of its
links a hypothesis changes with that link's mark in the same commit, since no check reads the prose:
the descriptions say which links are hypotheses), `simplification` (optional, as on an element),
`delay at` (optional, set by dragging a delay mark on the page: where on the curve the mark sits, from 0 to 1; without it `build.py` puts the mark at the clearest place along the link, away from other links and boxes and at least 55 units from its sign, Jordy),
`curvature` (0 is straight; a positive value bows the link to the left of its direction).
The drawing runs a link from a point on its source box's edge to one on its target's, the ends
on one edge spread along it, and puts the sign on the side of the arrowhead clear of boxes.
The SETS fields the page and Kumu show ("Cross-domain", "E to S" …) are derived by `build.py`,
never typed.

A named loop: `{"id": "R1", "name": "…", "path": ["element-a", "element-b", …], "description": "…"}`,
the path in causal order without repeating the first element. `build.py` checks that every step is a
connection and that the id starts with R for an even number of `-` links, B for an odd one; the
page gets a button for it, which highlights its elements and links, and `docs/figures/named-loops/<id>.svg`
draws it on its own, with its mark. The full drawing carries no loop marks: of its many feedback
loops, which `build.py` counts (`{feedback loops}` above), no mark could be traced there. `description` says what the loop does, traced round its path
in words each actor in it would accept: what a balancing loop seeks, how the loop drives or holds
back adopting adaptive practices, and which response's unintended consequence it shows, where it
shows one. `build.py` stops on a named loop without one and on any description naming a loop id
that is not a named loop; the page's panel for the loop, the Named loops sheet and Kumu show it.

A group of named loops: `{"id": "C1", "name": "…", "loops": ["R3", "B4"], "description": "…"}`, in
the top-level list `groups`: loops that together form a behaviour none of them shows alone, joined at
the variables they share. Its `name` says what the loops do together, in words each actor would
accept. `build.py` stops on a group naming a loop that is not a named loop, on a group of fewer than
two loops and on a loop sharing no variable with the group's others; the page's button, the table's
Combined loops sheet and a Kumu map of its own show each group. `places` (`{"element-id": [x, y]}`), `bends`
(`{"from-id -> to-id": curvature}`) and `marks` (`{"R3": [x, y]}`) lay out its figure,
`docs/figures/combined-loops/<id>.svg`: its own, never the full drawing's, on the same axes and signs as `x`, `y` and
`curvature`. Each must hold exactly the group's elements, links and loops, so `build.py` stops when a
loop's path changes, and it warns of a crossing or a link through a box in a figure; `--check` names a
stale or orphaned one. `model/cld-texts.md`'s `{combined loops list}` shows each group's description, so the
page's text and the data cannot differ. `sources` (optional) holds what the group's own claim rests on,
such as the archetype it matches; each link's source stays on the link.

### `model/actor-map.json`

The Actor Map's data, by the course's actor analysis guidelines, and the one list of actors:
the CLD's `actor` fields name its ids. At the top, `header` (`working title`, `names`, the
group members as authors, and `partner`) and `question`, the actor analysis's own question.
Then `actors`, each:

- `id` never changes; `label` is its name on the map.
- `scale`: `inside` or `outside`, by the CLD's boundary test (`model/cld-texts.md`, System
  boundary): inside when the island's farms move its decisions and it moves them back before
  2050.
- `type`, `level` and `sector` take a value from their lists in `build.py`, the Actor Map's
  own, which start from the values the group's old Actor Table used and are bound by none of
  them (Jordy: the old table gave the columns only); `influence score` is 1, little, to 5, and
  `client` `yes` for the group's partners; `interest` and `influence` are words, describing,
  never judging. No paradigm: the course's paradigms are the researchers' own, for the group's
  positionality statement.
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
  such pair twice). A cooperation whose sources name no leader stays in each actor's
  `influence` and is not drawn (Jordy), such as the knowledge programme on salt that LVVN, IenW,
  Rijkswaterstaat and STOWA had drawn up.
- `affected`: how salinisation and freshwater scarcity on the island, and the farms' adaptation
  to them, affect the actor (the guidelines ask how each actor influences the issue and how it is
  affected by it), in words, from sources.
- `sources`: keys in `model/references.json`, as for the CLD.
- `x` and `y`: the actor's place on the Actor Map, y downwards; each relation's `curvature`, its
  bow, as a CLD link's. An actor sits in its level's band (`build.py` warns otherwise).

A field no source carries stays empty (`""`, `null` or `[]`), never a guess, and `python3
build.py` lists each one still empty; it stops on a value outside its list, a relation to an
unknown actor or a source not in `model/references.json`. The CLD variables each actor decides are
derived from the CLD's `actor` fields, never typed here.

### `model/references.json`

The sources of the CLD and the Actor Map, as CSL JSON, the format Zotero imports: a list of items,
each with `id` (the key a `sources` field names, never changed), `type` (one of `REF_TYPES` in
`build.py`) and the fields its reference needs: `author` (`family` and `given`, or `literal` for an
organisation), `issued` and `accessed` (`date-parts`), `title`, `container-title` (the journal,
news site, website or a chapter's book, left out where it is the author), `editor` (a chapter's), `volume`, `issue`, `page`, `genre` and
`number` (a report's kind and number), `collection-title` and `collection-number` (a series or a
gazette, and the number in it), `version`, `publisher` (left out where it is the author), and
`DOI` or `URL`. `build.py` writes each APA reference from them (`apa()`), which the page, Kumu and
the table show; a Dutch law (`legislation`) is cited by the version in force on its `issued`
date, and `year-suffix` holds a letter a description cites (van Beekom et al., 1953a). Zotero
holds a copy of each item, in Jordy's group library ChallengeBasedProject1, where the PDFs are
attached, never here, since this repository is public. A session pushes each new item into its
collection CLD and Actor Map, and once into its subcollection CLD or Actor Map, or both, by
which file cites it, with a Use note written from `model/cld.json` and `model/actor-map.json`, by the
Study repository's `zotero` skill, from this folder (the key through `op run`, as its `SKILL.md`
says):

```sh
python3 ../../.claude/skills/zotero/zotero.py push ChallengeBasedProject1 "CLD and Actor Map" model/references.json --uses model/cld.json model/actor-map.json
```

`push` records each note it wrote and each subcollection it put an item into in
`model/references.zotero.json`, committed with it; it never takes an item out of a collection, so what
anyone adds, moves or removes there stays. `diff` with the same arguments lists what changed there, with who and when, for Jordy to take
into `model/references.json` or not. A session runs it after every push and puts each line to Jordy: an
item `push` finds held outside CLD and Actor Map it leaves where it is, printing "held outside",
and only `diff` keeps listing it.

### The Actor Map

`docs/actors.html` is the Actor Map, a page beside the CLD's and linked from it: the actors'
network in one band per level, Global at the top and Local / Provincial / Regional at the bottom
(Jordy, chosen between rendered versions; rejected: rings by the CLD's scale, clusters by type,
boxes shaded by influence score), each relation in its kind's colour and dash. A click on an actor
or a relation opens its fields and sources. The CLD's scale is not drawn (Jordy). `docs/figures/actor-map.svg`
is the network on its own, the picture for the report (a PNG with the CLD's Chrome command,
`svg=docs/figures/actor-map.svg`).

The actors' table is `docs/tables/actor-map-table.xlsx` (Jordy: a sheet he imports into Google Drive as a Google
Sheet; rejected: a table on the page, which took seven printed pages): the Actors sheet, a row per
actor with its columns, whom it influences and is influenced by, and the CLD variables it decides;
the Relations sheet, a row per relation, read "From relation To", with its description; the
References sheet, the full references the two cite, whose in-text citations they carry; the
Columns sheet, what each column holds. The scale is not a column: the course's actor analysis
guidelines do not ask for it (Jordy).

## Setup after cloning

`git config core.hooksPath hooks` turns on the pre-commit check. The scripts need only Python 3.

## Kumu

Kumu holds a copy for milestones, at <https://kumu.io/JordyZuidam/cbp1>, public and never
edited: the one place outsiders see the model, so nothing in it links to the page or this
repository (Jordy). One project, `cbp1`, holds every map, each picked from Kumu's map list, with
no showcase buttons, so its name names no single map (Jordy; rejected: `cbp-cld`, the name of the
CLD's own project before the Actor Map joined it):

- the full CLD, the default map: the elements at their positions, the curved links, the view from
  `src/kumu/cld-view.scss`, and the named loops, each its links, its "R1 …" label hidden on the
  map by the view, as the page has no loop marks;
- the Actor Map: the actors at their places with their fields, the relations with their curves,
  each kind as its connection type in its colour and dash (`src/kumu/actor-map-view.scss` and the
  rules `build.py` adds);
- a map per combined loop, C1 to C10, then per named loop in `model/cld.json`'s order, named
  `<id> <name>`, its description the group's or the loop's: exactly its loops' elements and links,
  at the places of its figure in `docs/figures/` (a group's `places`, `bends` and `marks`, a named
  loop's oval), each loop's label at its mark. Kumu draws a link from centre to centre, so a named
  loop's link bends through the oval midway between its two elements (`draw_cld.oval_layout()`).
  Their view is the CLD's without the rule that hides the loop labels.

Kumu lists the maps sorted by name as plain text, whatever their order in the file (B10 before
B2), so each map's name starts with its place in this order, in two digits: `01 CLD model`,
`02 Actor Map`, then the loop maps (Jordy; rejected: zero-padded loop ids, which keep
the list grouped by letter, and the names alone). `build.py` stops when the names would sort into
another order.

The two models share Kumu's fields, one per name: a list to pick from where its values over both
are 20 or fewer.

An import never updates what a project already holds, and Kumu cannot empty a project, so each
update is a new project under the same name, which keeps the URL. Jordy deletes the previous
`cbp1` (Jordy: a past copy is kept nowhere in Kumu; rejected: renaming it), then on the Kumu
dashboard: New Project → name `cbp1`, public → the next screen →
"restore backup" (the link at the bottom) → `docs/kumu/kumu-project.json`, once: the file holds
every map with its view and both background images, so nothing is uploaded after it. Only a
brand-new project restores a project export; the green `+` → Import route brings in the elements
and connections alone. The restore sets the project's name, which the export sets to `cbp1`.

The view follows the page's look as far as Kumu can: boxes tinted by SETS domain with the label
inside, square corners for a stock and rounded ones for the others, an italic label for a
constant (Kumu has no dashed border), a thick border for an adaptive practice; links of one
width, blue `+` and red `−`. Kumu draws each link from centre to centre. The regions reach Kumu
as a background image inside the file: the CLD's map holds an element labelled `background`,
pinned at the centre of the regions' frame with the frame's width and height, which the
`#background` rule in `src/kumu/cld-view.scss` shows behind the map, its `url(IMAGE)` replaced by
`build.py` with a data URL of the regions alone (`draw_cld.regions_svg()`), never a URL on the
published page, so a copy shows its own version's regions and depends on no host (Jordy). The
Actor Map's level bands reach it the same way, its element `elem-actors-background`. The subsystem is also
a field there. `build.py` adds the rules that tint and size each box below `src/kumu/cld-view.scss`, and
a double space where the page breaks a label's line (Kumu's manual line break). Kumu holds no
version, in the project's description or a map's name, so the link to each map stays the same
from one copy to the next, such as `https://kumu.io/JordyZuidam/cbp1#01-cld-model`: the versions
are this repository's (Jordy; rejected: the versions in the description and in the CLD's and the
Actor Map's map names, which changed each map's link with every copy).
