// The page around the drawing: highlight buttons, the panel per element or link, and Move mode
// (move.js: elements move, links bend) with what only the CLD has in it: Constants, signs, delay marks.
// The data is the JSON in <script id="data"> (build.py writes it); the drawing is the inline SVG.
"use strict";

const data = JSON.parse(document.getElementById("data").textContent);
const svg = document.querySelector("#map svg");
const elements = [...svg.querySelectorAll("g.element")];
const links = [...svg.querySelectorAll("g.link")];
const loops = [...svg.querySelectorAll("g.loop")];
const byId = Object.fromEntries(data.elements.map(e => [e.id, e]));
const linkKey = l => `${l.from}--${l.to}`;
const byKey = Object.fromEntries(data.connections.map(c => [linkKey(c), c]));

// --- version --------------------------------------------------------------------------------
document.getElementById("version").textContent = data.version;

// --- highlight buttons ----------------------------------------------------------------------
// A button per named loop, and one per group of named loops, names its elements and links; pressed
// buttons are united, none means all. A button reads "R1 Its name"; its key is the id. Pressing it
// also opens the panel with its figure (docs/figures/named-loops/<id>.svg, docs/figures/combined-loops/<id>.svg); releasing it
// closes that panel.
const linksOf = path => path.map((id, i) => `${id}--${path[(i + 1) % path.length]}`);
const loopRules = data.loops.map(loop => [`${loop.id} ${loop.name}`, () => (
  { elements: new Set(loop.path), links: new Set(linksOf(loop.path)) }
), loop.id]);
const groupRules = data.groups.map(group => [`${group.id} ${group.name}`, () => {
  const paths = group.loops.map(id => data.loops.find(l => l.id === id).path);
  return { elements: new Set(paths.flat()), links: new Set(paths.flatMap(linksOf)) };
}, group.id]);
const rules = [...loopRules, ...groupRules];
const nav = document.getElementById("buttons");
const pressed = new Set();  // the ids of the pressed loops and groups
for (const [heading, section] of [["Individual loops", loopRules], ["Combined loops", groupRules]]) {
  if (!section.length) continue;
  const row = document.createElement("div");
  row.className = "button-row";
  const name = document.createElement("span");
  name.className = "button-heading";
  name.textContent = heading;
  row.append(name);
  for (const [label, rule, key = label] of section) {
    const button = document.createElement("button");
    const [id, ...words] = label.split(" ");
    for (const [cls, text] of [["id", id], ["name", words.join(" ")]]) {
      const part = document.createElement("span");
      part.className = cls;
      part.textContent = text;
      button.append(part, " ");
    }
    button.title = label;
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      if (pressed.has(key)) pressed.delete(key); else pressed.add(key);
      button.setAttribute("aria-pressed", String(pressed.has(key)));
      applyHighlight();
      if (pressed.has(key)) showLoop(key);
      else if (panel.dataset.loop === key) closePanel();
    });
    row.append(button);
  }
  nav.append(row);
}
// with the menu closed, the bar says which loops are highlighted, and clears them
const shown = document.getElementById("shown");
shown.addEventListener("click", () => {
  pressed.clear();
  for (const b of nav.querySelectorAll("button")) b.setAttribute("aria-pressed", "false");
  applyHighlight();
  if (panel.dataset.loop) closePanel();
});
function applyHighlight() {
  shown.hidden = pressed.size === 0;
  shown.textContent = `${[...pressed].join(", ")} ×`;
  const active = rules.filter(([label, , key = label]) => pressed.has(key)).map(([, rule]) => rule());
  const none = active.length === 0;
  const keepE = new Set(active.flatMap(r => [...r.elements]));
  const keepL = new Set(active.flatMap(r => [...r.links]));
  for (const g of elements) g.classList.toggle("faded", !none && !keepE.has(g.dataset.id));
  for (const g of links) g.classList.toggle("faded", !none && !keepL.has(`${g.dataset.from}--${g.dataset.to}`));
  for (const g of loops) g.classList.toggle("faded", !none && !pressed.has(g.dataset.id));
}

// --- the panel ------------------------------------------------------------------------------
const panel = document.getElementById("panel");
const panelBody = document.getElementById("panel-body");
const SHOWN_ELEMENT = ["element type", "actor", "adaptive practice", "sets domain", "subsystem", "subquestion", "description", "simplification"];
const SHOWN_LINK = ["delay", "sets link", "description", "simplification"];
function row(dl, name, value, className) {
  const dt = document.createElement("dt");
  dt.textContent = name;
  const dd = document.createElement("dd");
  dd.textContent = value;
  if (className) dd.className = className;
  dl.append(dt, dd);
}
function showPanel(title, item, fields) {
  panelBody.replaceChildren();
  delete panel.dataset.loop;
  const h2 = document.createElement("h2");
  h2.append(...title);
  const dl = document.createElement("dl");
  // a field only some items have (actor, on a decision variable; simplification) shows where an item has it
  for (const name of fields) if (name in item) row(dl, name, item[name]);
  if (item.sources) row(dl, "sources", item.sources);
  else if (item.hypothesis === "yes") row(dl, "sources", "none: a hypothesis about behaviour, for the group model building session", "none");
  else row(dl, "sources", "no source yet", "none");
  panelBody.append(h2, dl);
  panel.hidden = false;
}
function showElement(id) {
  const e = byId[id];
  showPanel([e.label], e, SHOWN_ELEMENT);
}
function showLink(from, to) {
  const c = byKey[`${from}--${to}`];
  const sign = document.createElement("span");
  sign.className = c.polarity === "positive" ? "sign-plus" : "sign-minus";
  sign.textContent = c.label;
  showPanel([byId[from].label, " → ", byId[to].label, " ", sign], c, SHOWN_LINK);
}
function showLoop(id) {
  const group = data.groups.find(g => g.id === id);
  const loop = group || data.loops.find(l => l.id === id);
  panelBody.replaceChildren();
  const h2 = document.createElement("h2");
  h2.textContent = `${loop.id} ${loop.name}`;
  const a = document.createElement("a");
  a.href = `figures/${group ? "combined-loops" : "named-loops"}/${loop.id}.svg`;
  a.target = "_blank";
  const img = document.createElement("img");
  img.src = a.href;
  img.alt = group ? `The loops ${group.loops.join(", ")} together` : `The loop ${loop.id} on its own`;
  a.append(img);
  const description = document.createElement("p");
  description.textContent = loop.description;
  const p = document.createElement("p");
  p.className = "note";
  p.textContent = `${group ? `The loops ${group.loops.join(", ")} together` : "The loop on its own"}, the figure for the report: click it to open it full size.`;
  panelBody.append(h2, a, description, p);
  panel.dataset.loop = loop.id;
  panel.hidden = false;
}
function closePanel() { panel.hidden = true; delete panel.dataset.loop; }
document.getElementById("close").addEventListener("click", closePanel);
document.addEventListener("click", ev => {
  if (panel.contains(ev.target) || nav.contains(ev.target) || ev.target.closest(".chrome")) return;  // a loop's button opens its own panel
  const g = ev.target.closest("g.element, g.link");
  if (g && svg.contains(g)) return;  // handled on the svg, below
  closePanel();
});
svg.addEventListener("click", ev => {
  if (controls.wasDragged()) return;  // a drag is not a click
  const g = ev.target.closest("g.element, g.link");
  if (!g) { closePanel(); return; }
  if (g.classList.contains("element")) showElement(g.dataset.id);
  else showLink(g.dataset.from, g.dataset.to);
});

// --- Move mode: move.js; what only the CLD has in it ----------------------------------------
// The sign and the delay mark are draw_cld.py's sign_position() and delay_path(): keep them the same.
const ARROW = 22;
const tangent = (p0, p1, p2, t) =>
  [2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0]), 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])];
function signPosition(p0, ctrl, p2, back = 50) {
  let lo = 0, hi = 1;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2, q = bezier(p0, ctrl, p2, mid);
    if (Math.hypot(q[0] - p2[0], q[1] - p2[1]) > back) lo = mid; else hi = mid;
  }
  return bezier(p0, ctrl, p2, hi);
}
function delayT(p0, ctrl, p2, back = 50 + 55) {
  const mid = bezier(p0, ctrl, p2, 0.5);
  if (Math.hypot(mid[0] - p2[0], mid[1] - p2[1]) >= back || Math.hypot(p0[0] - p2[0], p0[1] - p2[1]) < back) return 0.5;
  let lo = 0, hi = 0.5;
  for (let i = 0; i < 40; i++) {
    const m = (lo + hi) / 2, q = bezier(p0, ctrl, p2, m);
    if (Math.hypot(q[0] - p2[0], q[1] - p2[1]) > back) lo = m; else hi = m;
  }
  return lo;
}
function delayPath(p0, ctrl, p2, at, half = 24, gap = 8) {
  const t = at === undefined ? delayT(p0, ctrl, p2) : at;
  const [x, y] = bezier(p0, ctrl, p2, t);
  const [tx, ty] = tangent(p0, ctrl, p2, t);
  const n = Math.hypot(tx, ty) || 1;
  const ux = tx / n, uy = ty / n, nx = -uy, ny = ux;
  return [-gap, gap].map(k => {
    const cx = x + ux * k, cy = y + uy * k;
    return `M ${(cx - nx * half).toFixed(1)} ${(cy - ny * half).toFixed(1)} L ${(cx + nx * half).toFixed(1)} ${(cy + ny * half).toFixed(1)}`;
  }).join(" ");
}
// a link's sign and delay mark, at their places on its curve
function drawMarks(g, [p0, ctrl, p2]) {
  const f = v => v.toFixed(1);
  const [sx, sy] = signPosition(p0, ctrl, p2);
  const sign = g.querySelector("text.sign");
  sign.setAttribute("x", f(sx));
  sign.setAttribute("y", f(sy));
  for (const delay of g.querySelectorAll("path.delay, path.delay-cut")) delay.setAttribute("d", delayPath(p0, ctrl, p2, g.dataset.delayT === undefined ? undefined : +g.dataset.delayT));
}
const mover = moveMode(svg, {
  box: "g.element",
  link: "g.link",
  key: g => `${g.dataset.from}->${g.dataset.to}`,
  // within 0.03 of straight a Constant's link snaps to straight, since a hand cannot reach 0
  // exactly; every other link keeps at least that bend (Jordy: every link but a Constant's bends)
  bend: (g, k) => {
    const constant = elements.find(e => e.dataset.id === g.dataset.from).dataset.type === "Constant";
    return Math.abs(k) >= 0.03 ? roundBend(k) : constant ? 0 : (k < 0 ? -0.03 : 0.03);
  },
  redraw: drawMarks,
  // a dragged delay mark stays on its own line: the point of the curve nearest the pointer
  grab: (ev, paths) => {
    if (!ev.target.closest("path.delay, path.delay-cut")) return null;
    const l = ev.target.closest("g.link");
    return move => {
      const p = svgPoint(svg, move), [p0, ctrl, p2] = paths().get(l);
      let best = Infinity, at = 0.5;
      for (let i = 5; i <= 95; i++) {
        const q = bezier(p0, ctrl, p2, i / 100), d = Math.hypot(q[0] - p[0], q[1] - p[1]);
        if (d < best) { best = d; at = i / 100; }
      }
      l.dataset.delayT = String(at);
      l.dataset.delayMoved = "1";
      drawMarks(l, paths().get(l));
      return true;
    };
  },
  extra: () => ({ delay: Object.fromEntries(links.filter(g => g.dataset.delayMoved).map(g => [`${g.dataset.from}->${g.dataset.to}`, +g.dataset.delayT])) }),
});

// --- moving and zooming: map.js; a press in Move mode is move.js's ----------------------------
const controls = mapControls(svg, document.getElementById("map"), mover.grab);
