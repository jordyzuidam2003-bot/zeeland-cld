"""List what the working version changes against the CLD, as markdown for the group's Drive.

    python3 changes.py                  # model/cld.json against model/cld-working.json
    python3 changes.py OLD.json NEW.json  # any two CLD files, OLD the one agreed

The working version (model/cld-working.json, README's "The working version") holds the changes
tried before they enter model/cld.json, and in its top-level list `changes` each change's argument:

    {"change": "<what it does, in a few words>", "argument": "<why>", "items": ["<id>", …]}

an item named as model/cld.json names it: an element or a named or combined loop by its id, a link
as "from-id -> to-id". The list prints each change with its argument, then what it does to each of
its items (gone, new, or each field changed, was and now), labels for ids and in-text citations for
sources, as markdown Jordy pastes into a Google Doc for Lenne (the Study router's "What the group
shares"). Layout alone (a place, a bend, a delay mark, a combined loop's figure) is no change to
decide: it is counted in one line at the end. Two files that hold the same model print nothing.

problems() is what build.py stops on: an item that changes without a change naming it, a change
naming an item that does not change, an item in two changes (one change, one argument), and a
`changes` list in model/cld.json, whose changes are agreed (AGREED, which build.py checks itself, as
it does with no working version). This script prints the list even then, the items without an
argument under their own heading, and exits 1.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAYOUT = {"x", "y", "curvature", "delay at", "places", "bends", "marks"}  # drawing, not content
KINDS = [("elements", "element"), ("connections", "link"), ("loops", "named loop"), ("groups", "combined loop")]
AGREED = ("model/cld.json holds changes: their arguments belong in the working version until Jordy and "
          "Lenne agree, then in the commit that moves them")


def key(kind, item):
    return f"{item['from']} -> {item['to']}" if kind == "connections" else item["id"]


def items(cld):
    """{name: (kind, item)} for every element, link, named loop and combined loop."""
    return {key(kind, i): (kind, i) for kind, _ in KINDS for i in cld.get(kind, [])}


def content(item):
    return {k: v for k, v in item.items() if k not in LAYOUT}


def differ(old, new):
    """({name: (kind, old item or None, new item or None)} for each item whose content differs,
    [names of the items whose layout alone differs])."""
    a, b = items(old), items(new)
    changed, moved = {}, []
    for name in list(a) + [n for n in b if n not in a]:
        kind = (a.get(name) or b.get(name))[0]
        x, y = a.get(name, (None, None))[1], b.get(name, (None, None))[1]
        if x is None or y is None or content(x) != content(y):
            changed[name] = (kind, x, y)
        elif x != y:
            moved.append(name)
    return changed, moved


def problems(old, new):
    """What build.py stops on (the docstring): each a line naming its item or change."""
    out = [AGREED] if "changes" in old else []
    changes = new.get("changes", [])
    if not isinstance(changes, list):
        return out + ["changes must be a list"]
    changed, _ = differ(old, new)
    named = {}
    for n, c in enumerate(changes, 1):
        if not (isinstance(c, dict) and set(c) == {"change", "argument", "items"}
                and all(isinstance(c[k], str) and c[k].strip() for k in ("change", "argument"))
                and isinstance(c["items"], list) and c["items"] and all(isinstance(i, str) for i in c["items"])):
            out.append(f"change {n}: needs exactly a change and an argument, each in words, and a list of items")
            continue
        for i in c["items"]:
            if i in named:
                out.append(f"{i} is in two changes ({named[i]!r} and {c['change']!r}): one change, one argument")
            named[i] = c["change"]
            if i not in changed:
                out.append(f"change {c['change']!r} names {i}, which the working version does not change")
    out += [f"{i} changes in the working version, but no change names it with its argument"
            for i in changed if i not in named]
    return out


def show(field, value, labels, actors, cites):
    """A field's value in words: labels for ids, in-text citations for sources."""
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if field == "polarity":
        return "−" if value == "-" else value
    if field == "sources":
        return "; ".join(f"{cites[k][0]}, {cites[k][1]}" if k in cites else k for k in value) or "(none)"
    if field == "path":
        return " → ".join(labels.get(i, i) for i in value)
    if field == "actor":
        return actors.get(value, value)
    if field == "actors":
        return ", ".join(actors.get(a, a) for a in value) or "(none)"
    if field == "ask actors":
        return "; ".join(f"{actors.get(a['actor'], a['actor'])}: {a['for']} (through {', '.join(a['through'])})"
                         for a in value)
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value)


def title(kind, name, item, labels):
    if kind == "elements":
        return f"element *{item['label']}*"
    if kind == "connections":
        return f"link *{labels.get(item['from'], item['from'])}* → *{labels.get(item['to'], item['to'])}*"
    noun = dict(KINDS)[kind]
    return f"{noun} {name} *{item['name']}*"


def describe(name, kind, old, new, labels, actors, cites):
    """The markdown lines of one item's change."""
    say = lambda f, v: show(f, v, labels, actors, cites)
    if old is None:
        lines = [f"- New {title(kind, name, new, labels)}"]
        lines += [f"    - {f}: {say(f, v)}" for f, v in content(new).items() if f not in ("id", "from", "to")]
        return lines
    if new is None:
        return [f"- Gone: {title(kind, name, old, labels)}"]
    t = title(kind, name, new, labels)
    lines = [f"- {t[0].upper()}{t[1:]}"]
    x, y = content(old), content(new)
    for f in list(x) + [f for f in y if f not in x]:
        if x.get(f) != y.get(f):
            lines += [f"    - its {f}", f"        - was: {say(f, x.get(f))}", f"        - now: {say(f, y.get(f))}"]
    return lines


def listing(old, new, actor_map, cites):
    """The markdown list, or "" where the two hold the same model."""
    changed, moved = differ(old, new)
    if not changed and not moved:
        return ""
    # a label from the working version where it has one, so a renamed element reads as it will
    labels = {e["id"]: e["label"] for e in old["elements"]}
    labels.update({e["id"]: e["label"] for e in new["elements"]})
    actors = {a["id"]: a["label"] for a in actor_map["actors"]}
    lines = ["# The working version against the CLD", "",
             "Each change with its argument, then what it does in the CLD. A change enters the CLD once "
             "Jordy and Lenne both agree; a change rejected is undone in the working version."]
    done = set()
    for n, c in enumerate(new.get("changes", []) if isinstance(new.get("changes"), list) else [], 1):
        if not isinstance(c, dict):
            continue
        lines += ["", f"## {n}. {c.get('change', '')}", "", str(c.get("argument", "")), ""]
        for i in c.get("items", []):
            if i in changed and i not in done:
                lines += describe(i, *changed[i], labels, actors, cites)
                done.add(i)
    rest = [i for i in changed if i not in done]
    if rest:
        lines += ["", "## Changed with no argument yet", ""]
        for i in rest:
            lines += describe(i, *changed[i], labels, actors, cites)
    if moved:
        kinds = {}
        for i in moved:
            kinds.setdefault(dict(KINDS)[items(new)[i][0]], []).append(i)
        lines += ["", "Layout alone, nothing to decide: " + "; ".join(
            f"{len(v)} {k}{'s' if len(v) > 1 else ''} moved or redrawn" for k, v in kinds.items()) + "."]
    return "\n".join(lines) + "\n"


def main():
    args = sys.argv[1:]
    if len(args) not in (0, 2):
        sys.exit(__doc__.split("\n\n")[1])
    old_path, new_path = (Path(a) for a in args) if args else (ROOT / "model/cld.json", ROOT / "model/cld-working.json")
    if not new_path.exists():
        sys.exit(f"{new_path} does not exist: there is no working version")
    old, new = json.loads(old_path.read_text()), json.loads(new_path.read_text())
    import build  # its references and citations; build.py imports this module, so not at the top
    import draw_actor_map
    refs, _ = build.references()
    keys = sorted({k for m in (old, new) for kind in ("elements", "connections", "groups")
                   for i in m.get(kind, []) for k in i.get("sources", []) if k in refs})
    cites = draw_actor_map.citations(keys, refs)
    sys.stdout.write(listing(old, new, json.loads(build.ACTORS.read_text()), cites))
    wrong = problems(old, new)
    if wrong:
        sys.exit("\n".join(wrong))


if __name__ == "__main__":
    main()
