"""Import a full Kumu project export ("Export JSON") into cld.json.

    .venv/bin/python import_kumu.py ~/Downloads/kumu-cld.json            # rewrite cld.json
    .venv/bin/python import_kumu.py ~/Downloads/kumu-cld.json --layout   # only x, y and curvature

Positions and curvature come from the export's default map (its "defaultMap" id), which is
not necessarily maps[0]. Elements are matched to an existing cld.json by label, so their ids
survive a re-import; new elements get an id made from their label.

--layout is for tuning the layout by dragging in a Kumu project with a fixed layout: export
that project, then pull only the positions and curves back into cld.json.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLD = ROOT / "cld.json"

# Kumu field name -> cld.json key, in the order cld.json lists them
ELEMENT_FIELDS = ["element type", "sets subsystem", "focus area", "subquestion", "description"]
CONNECTION_FIELDS = ["loop id", "description"]


def slug(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower().replace("'", "")).strip("-")


def load_export(path):
    data = json.loads(Path(path).read_text())
    kumu_map = next(m for m in data["maps"] if m["_id"] == data["defaultMap"])
    positions = {e["element"]: e["position"] for e in kumu_map["elements"]}
    curvature = {c["connection"]: c.get("curvature", 0) for c in kumu_map["connections"]}
    elements = [e for e in data["elements"]
                if e["attributes"].get("element type") != "Background"]
    # cld.json lists elements by focus area, in the order Kumu's "Focus area" field lists them
    areas = next(a["values"] for a in data["attributes"] if a["name"] == "Focus area")
    elements.sort(key=lambda e: (areas.index(e["attributes"]["focus area"]), e["attributes"]["label"]))
    order = {e["_id"]: i for i, e in enumerate(elements)}
    connections = sorted(data["connections"], key=lambda c: (order[c["from"]], order[c["to"]]))
    return elements, connections, positions, curvature


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("export", help="path to the Kumu project export (.json)")
    parser.add_argument("--layout", action="store_true", help="only update x, y and curvature")
    args = parser.parse_args()

    elements, connections, positions, curvature = load_export(args.export)
    old = json.loads(CLD.read_text()) if CLD.exists() else {"elements": [], "connections": [], "loops": []}
    id_by_label = {e["label"]: e["id"] for e in old["elements"]}

    kumu_to_id = {}
    for e in elements:
        label = e["attributes"]["label"]
        kumu_to_id[e["_id"]] = id_by_label.get(label) or slug(label)

    if args.layout:
        by_id = {e["id"]: e for e in old["elements"]}
        by_pair = {(c["from"], c["to"]): c for c in old["connections"]}
        missing = []
        for e in elements:
            target = by_id.get(kumu_to_id[e["_id"]])
            if target is None:
                missing.append(e["attributes"]["label"])
                continue
            p = positions[e["_id"]]
            target["x"], target["y"] = round(p["x"]), round(p["y"])
        for c in connections:
            target = by_pair.get((kumu_to_id[c["from"]], kumu_to_id[c["to"]]))
            if target is None:
                missing.append(f'{c["from"]} -> {c["to"]}')
                continue
            target["curvature"] = round(curvature.get(c["_id"], 0), 2)
        new = old
        if missing:
            print("not in cld.json, skipped:", *missing, sep="\n  ")
    else:
        new = {"elements": [], "connections": [], "loops": old.get("loops", [])}
        for e in elements:
            a = e["attributes"]
            p = positions[e["_id"]]
            item = {"id": kumu_to_id[e["_id"]], "label": a["label"]}
            item.update({k: a.get(k, "") for k in ELEMENT_FIELDS})
            item.update({"sources": [], "x": round(p["x"]), "y": round(p["y"])})
            new["elements"].append(item)
        for c in connections:
            a = c["attributes"]
            item = {"from": kumu_to_id[c["from"]], "to": kumu_to_id[c["to"]],
                    "polarity": "+" if a["polarity"] == "positive" else "-",
                    "delay": bool(c.get("delayed"))}
            item.update({k: a.get(k.replace(" ", "_"), a.get(k, "")) for k in CONNECTION_FIELDS})
            item.update({"sources": [], "curvature": round(curvature.get(c["_id"], 0), 2)})
            new["connections"].append(item)

    CLD.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
    print(f'cld.json: {len(new["elements"])} elements, {len(new["connections"])} connections')


if __name__ == "__main__":
    main()
