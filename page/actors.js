// The Actor Map's page: a click on an actor or a relation opens a panel with its fields and
// sources; Esc or a click on the background closes it. The data is the JSON in <script id="data">
// (build.py writes it); the drawing is the inline SVG, its actors and relations in actors.json's order.
"use strict";

const data = JSON.parse(document.getElementById("data").textContent);
const svg = document.querySelector("#map svg");
const panel = document.getElementById("panel");
const panelBody = document.getElementById("panel-body");
document.getElementById("version").textContent = data.version;

function row(dl, name, value) {
  const dt = document.createElement("dt");
  dt.textContent = name;
  const dd = document.createElement("dd");
  if (Array.isArray(value)) value.forEach((v, i) => { if (i) dd.append(document.createElement("br")); dd.append(v); });
  else dd.textContent = value;
  dl.append(dt, dd);
}

function sources(list) {
  const h = document.createElement("h3");
  h.textContent = "Sources";
  const ul = document.createElement("ul");
  for (const s of list) {
    const li = document.createElement("li");
    li.textContent = s;
    ul.append(li);
  }
  return [h, ul];
}

function open(title, fields, refs) {
  panelBody.replaceChildren();
  const h = document.createElement("h2");
  h.textContent = title;
  const dl = document.createElement("dl");
  for (const [name, value] of fields) if (value !== "" && value !== null && !(Array.isArray(value) && !value.length)) row(dl, name, value);
  panelBody.append(h, dl, ...sources(refs));
  panel.hidden = false;
}

const actors = [...svg.querySelectorAll("g.actor")];
actors.forEach((g, i) => g.addEventListener("click", event => {
  event.stopPropagation();
  const a = data.actors[i];
  open(a.label, [["Type", a.type], ["Level", a.level], ["Sector", a.sector], ["Interest", a.interest],
                 ["Influence", a.influence], ["How it is affected", a.affected], ["Influence score", String(a["influence score"])], ["Client", a.client],
                 ["Decides in the CLD", a["decides in the CLD"]]], a.sources);
}));
[...svg.querySelectorAll("g.relation")].forEach((g, i) => g.addEventListener("click", event => {
  event.stopPropagation();
  const r = data.relations[i];
  open(`${r.from} ${r.kind} ${r.to}`, [["Description", r.description]], r.sources);
}));

const close = () => { panel.hidden = true; };
document.getElementById("close").addEventListener("click", close);
svg.addEventListener("click", close);
document.addEventListener("keydown", event => { if (event.key === "Escape") close(); });
