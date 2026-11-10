// The page around the drawing: highlight buttons, the panel per element or link, and drag mode
// (elements move, links bend).
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
// also opens the panel with its figure (docs/loops/<id>.svg, docs/groups/<id>.svg); releasing it
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
  a.href = `${group ? "groups" : "loops"}/${loop.id}.svg`;
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

// --- drag mode ------------------------------------------------------------------------------
// The link formula is draw.py's link_path(), link_paths(), sign_position() and delay_path(): keep them the same.
const ARROW = 22;
const bezier = (p0, p1, p2, t) => {
  const s = 1 - t;
  return [s * s * p0[0] + 2 * s * t * p1[0] + t * t * p2[0], s * s * p0[1] + 2 * s * t * p1[1] + t * t * p2[1]];
};
const tangent = (p0, p1, p2, t) =>
  [2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0]), 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])];
const inside = (p, box) => box[0] <= p[0] && p[0] <= box[2] && box[1] <= p[1] && p[1] <= box[3];
const lerp = (p, q, t) => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
function linkPath(a, b, curvature) {
  const ca = [(a[0] + a[2]) / 2, (a[1] + a[3]) / 2];
  const cb = [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
  const dx = cb[0] - ca[0], dy = cb[1] - ca[1];
  const ctrl = [(ca[0] + cb[0]) / 2 + curvature * dy, (ca[1] + cb[1]) / 2 - curvature * dx];
  const crossing = (box, p, q, r) => {
    let lo = 0, hi = 0.5;
    for (let i = 0; i < 30; i++) {
      const mid = (lo + hi) / 2;
      if (inside(bezier(p, q, r, mid), box)) lo = mid; else hi = mid;
    }
    return hi;
  };
  const middle = bezier(ca, ctrl, cb, 0.5);
  const t0 = inside(middle, a) ? 0 : crossing(a, ca, ctrl, cb);
  const t1 = inside(middle, b) ? 1 : 1 - crossing(b, cb, ctrl, ca);
  const r0 = bezier(ca, ctrl, cb, t0), r1 = lerp(ctrl, cb, t0);
  const s = t0 < 1 ? (t1 - t0) / (1 - t0) : 0;
  return [r0, lerp(r0, r1, s), bezier(ca, ctrl, cb, t1)];
}
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
const boxOf = g => {
  const r = g.querySelector("rect");
  const x = +r.getAttribute("x"), y = +r.getAttribute("y");
  return [x, y, x + +r.getAttribute("width"), y + +r.getAttribute("height")];
};
const groupOf = Object.fromEntries(elements.map(g => [g.dataset.id, g]));
const GAP = 34, INSET = 10;
function edgeOf(p, box) {
  const d = [Math.abs(p[1] - box[1]), Math.abs(p[0] - box[2]), Math.abs(p[1] - box[3]), Math.abs(p[0] - box[0])];
  return d.indexOf(Math.min(...d));
}
function spread(xs, lo, hi, gap) {
  const n = xs.length;
  gap = Math.min(gap, (hi - lo) / Math.max(n - 1, 1));
  const p = xs.map(x => Math.min(Math.max(x, lo), hi));
  for (let i = 1; i < n; i++) p[i] = Math.max(p[i], p[i - 1] + gap);
  if (p[n - 1] > hi) {
    p[n - 1] = hi;
    for (let i = n - 2; i >= 0; i--) p[i] = Math.min(p[i], p[i + 1] - gap);
  }
  return p;
}
// every link's [p0, ctrl, p2]: the ends spread along the box edges, as draw.py's link_paths()
function linkPaths() {
  const ends = new Map();
  for (const g of links) {
    const a = boxOf(groupOf[g.dataset.from]), b = boxOf(groupOf[g.dataset.to]);
    const [p0, , p2] = linkPath(a, b, +g.dataset.curvature);
    for (const [which, id, box, p] of [[0, g.dataset.from, a, p0], [1, g.dataset.to, b, p2]]) {
      const e = edgeOf(p, box), k = `${id} ${e}`;
      if (!ends.has(k)) ends.set(k, { box, e, list: [] });
      ends.get(k).list.push([e % 2 === 0 ? p[0] : p[1], g, which]);
    }
  }
  const anchor = new Map();
  for (const { box, e, list } of ends.values()) {
    const [x0, y0, x1, y1] = box;
    list.sort((u, v) => u[0] - v[0]);
    const [lo, hi] = e % 2 === 0 ? [x0 + INSET, x1 - INSET] : [y0 + INSET, y1 - INSET];
    spread(list.map(t => t[0]), lo, hi, GAP).forEach((v, i) => {
      const [, g, which] = list[i];
      anchor.set(g, Object.assign(anchor.get(g) || [], { [which]: e === 0 ? [v, y0] : e === 1 ? [x1, v] : e === 2 ? [v, y1] : [x0, v] }));
    });
  }
  return new Map(links.map(g => {
    const [p0, p2] = anchor.get(g), k = +g.dataset.curvature;
    const dx = p2[0] - p0[0], dy = p2[1] - p0[1];
    return [g, [p0, [(p0[0] + p2[0]) / 2 + k * dy, (p0[1] + p2[1]) / 2 - k * dx], p2]];
  }));
}
function redrawLink(g, [p0, ctrl, p2]) {
  const f = v => v.toFixed(1);
  const d = `M ${f(p0[0])} ${f(p0[1])} Q ${f(ctrl[0])} ${f(ctrl[1])} ${f(p2[0])} ${f(p2[1])}`;
  g.querySelector("path.link-path").setAttribute("d", d);
  g.querySelector("path.link-grip").setAttribute("d", d);
  const [sx, sy] = signPosition(p0, ctrl, p2);
  const sign = g.querySelector("text.sign");
  sign.setAttribute("x", f(sx));
  sign.setAttribute("y", f(sy));
  for (const delay of g.querySelectorAll("path.delay, path.delay-cut")) delay.setAttribute("d", delayPath(p0, ctrl, p2, g.dataset.delayT === undefined ? undefined : +g.dataset.delayT));
}
// each link gets a wide invisible copy of its path under it, so the 2.5-unit line can be grabbed
for (const g of links) {
  const grip = g.querySelector("path.link-path").cloneNode();
  grip.setAttribute("class", "link-grip");
  grip.removeAttribute("marker-end");
  grip.setAttribute("stroke", "transparent");
  grip.setAttribute("stroke-width", "18");
  g.insertBefore(grip, g.firstChild);
}
// a dragged link bends so its middle follows the pointer: the middle of the curve lies half
// the control point's offset from the chord, so curvature = 2 (p - mid) . (dy, -dx) / chord²
function bendLink(g, p) {
  const [p0, , p2] = linkPaths().get(g);
  const dx = p2[0] - p0[0], dy = p2[1] - p0[1];
  const mid = [(p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2];
  const k = 2 * ((p[0] - mid[0]) * dy - (p[1] - mid[1]) * dx) / (dx * dx + dy * dy || 1);
  // within 0.03 of straight a Constant's link snaps to straight, since a hand cannot reach 0
  // exactly; every other link keeps at least that bend (Jordy: every link but a Constant's bends)
  const constant = groupOf[g.dataset.from].dataset.type === "Constant";
  const bend = Math.round(Math.max(-1, Math.min(1, k)) * 100) / 100;
  g.dataset.curvature = String(Math.abs(k) >= 0.03 ? bend : constant ? 0 : (k < 0 ? -0.03 : 0.03));
  for (const [l, path] of linkPaths()) redrawLink(l, path);
}
function moveElement(g, dx, dy) {
  for (const node of g.querySelectorAll("rect, text")) {
    node.setAttribute("x", (+node.getAttribute("x") + dx).toFixed(1));
    node.setAttribute("y", (+node.getAttribute("y") + dy).toFixed(1));
  }
  // a moved box changes where the other links on its edges end, so every link is redrawn
  for (const [l, path] of linkPaths()) redrawLink(l, path);
}
const toSvg = ev => svgPoint(svg, ev);
const moveToggle = document.getElementById("move");
const download = document.getElementById("download");
const map = document.getElementById("map");
moveToggle.addEventListener("change", () => {
  map.classList.toggle("moving", moveToggle.checked);
  download.hidden = !moveToggle.checked;
});

// --- moving and zooming: map.js; a press in Move mode is this page's --------------------------
function grabInMoveMode(ev) {
  if (!moveToggle.checked) return null;
  const g = ev.target.closest("g.element"), l = ev.target.closest("g.link");
  if (ev.target.closest("path.delay, path.delay-cut")) return move => {
    // the mark stays on its own line: the point of the curve nearest the pointer
    const p = toSvg(move), [p0, ctrl, p2] = linkPaths().get(l);
    let best = Infinity, at = 0.5;
    for (let i = 5; i <= 95; i++) {
      const q = bezier(p0, ctrl, p2, i / 100), d = Math.hypot(q[0] - p[0], q[1] - p[1]);
      if (d < best) { best = d; at = i / 100; }
    }
    l.dataset.delayT = String(at);
    l.dataset.delayMoved = "1";
    redrawLink(l, linkPaths().get(l));
    return true;
  };
  if (g) {
    let last = toSvg(ev);
    return move => {
      const p = toSvg(move), dx = p[0] - last[0], dy = p[1] - last[1];
      if (dx === 0 && dy === 0) return false;
      moveElement(g, dx, dy);
      last = p;
      return true;
    };
  }
  if (l) return move => { bendLink(l, toSvg(move)); return true; };
  return null;
}
const controls = mapControls(svg, map, grabInMoveMode);
download.addEventListener("click", () => {
  const layout = {};
  for (const g of elements) {
    const b = boxOf(g);
    layout[g.dataset.id] = { x: Math.round((b[0] + b[2]) / 2), y: Math.round((b[1] + b[3]) / 2) };
  }
  layout.curvature = Object.fromEntries(links.map(g => [`${g.dataset.from}->${g.dataset.to}`, +g.dataset.curvature]));
  layout.delay = Object.fromEntries(links.filter(g => g.dataset.delayMoved).map(g => [`${g.dataset.from}->${g.dataset.to}`, +g.dataset.delayT]));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(layout, null, 2) + "\n"], { type: "application/json" }));
  a.download = "layout.json";
  a.click();
  URL.revokeObjectURL(a.href);
});
