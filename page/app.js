// The page around the drawing: highlight buttons, the panel per element or link, and drag mode.
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

// --- model texts and version --------------------------------------------------------------
const model = document.getElementById("model");
for (const [name, text] of Object.entries(data.model)) {
  const dt = document.createElement("dt");
  dt.textContent = name[0].toUpperCase() + name.slice(1);
  const dd = document.createElement("dd");
  dd.textContent = text || "not written yet";
  if (!text) dd.className = "empty";
  model.append(dt, dd);
}
document.getElementById("version").textContent = data.version;

// --- highlight buttons ----------------------------------------------------------------------
// A rule names the elements and the links that match; pressed rules are united, none means all.
const linksAmong = ids => data.connections.filter(c => ids.has(c.from) && ids.has(c.to)).map(linkKey);
const endsOf = keys => new Set(keys.flatMap(k => [byKey[k].from, byKey[k].to]));
const elementRule = test => () => {
  const ids = new Set(data.elements.filter(test).map(e => e.id));
  return { elements: ids, links: new Set(linksAmong(ids)) };
};
const linkRule = test => () => {
  const keys = data.connections.filter(test).map(linkKey);
  return { elements: endsOf(keys), links: new Set(keys) };
};
const rules = [
  ["Social", elementRule(e => e["sets domain"] === "Social")],
  ["Ecological", elementRule(e => e["sets domain"] === "Ecological")],
  ["Technological", elementRule(e => e["sets domain"] === "Technological")],
  ["Cross-SETS links", linkRule(c => c["sets scope"] === "Cross-domain")],
  ["Adaptive practices", elementRule(e => e["adaptive practice"] === "yes")],
  ["Unsourced", () => ({
    elements: new Set(data.elements.filter(e => e.sourced === "no").map(e => e.id)),
    links: new Set(data.connections.filter(c => c.sourced === "no").map(linkKey)),
  })],
  ["Delays", linkRule(c => c.delay === "yes")],
  ...data.loops.map(loop => [loop.id, () => {
    const path = loop.path;
    const keys = path.map((id, i) => `${id}--${path[(i + 1) % path.length]}`);
    return { elements: new Set(path), links: new Set(keys) };
  }]),
];
const nav = document.getElementById("buttons");
const pressed = new Set();
for (const [label, rule] of rules) {
  const button = document.createElement("button");
  button.textContent = label;
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", () => {
    if (pressed.has(label)) pressed.delete(label); else pressed.add(label);
    button.setAttribute("aria-pressed", String(pressed.has(label)));
    applyHighlight();
  });
  nav.append(button);
}
function applyHighlight() {
  const active = rules.filter(([label]) => pressed.has(label)).map(([, rule]) => rule());
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
const SHOWN_ELEMENT = ["element type", "adaptive practice", "sets domain", "subquestion", "description"];
const SHOWN_LINK = ["delay", "loop id", "sets link", "description"];
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
  const h2 = document.createElement("h2");
  h2.append(...title);
  const dl = document.createElement("dl");
  for (const name of fields) row(dl, name, item[name]);
  if (item.sources) row(dl, "sources", item.sources); else row(dl, "sources", "no source yet", "none");
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
function closePanel() { panel.hidden = true; }
document.getElementById("close").addEventListener("click", closePanel);
document.addEventListener("keydown", ev => { if (ev.key === "Escape") closePanel(); });
document.addEventListener("click", ev => {
  if (panel.contains(ev.target)) return;
  const g = ev.target.closest("g.element, g.link");
  if (g && svg.contains(g)) return;  // handled on the svg, below
  closePanel();
});
svg.addEventListener("click", ev => {
  if (dragged) return;  // a drag is not a click
  const g = ev.target.closest("g.element, g.link");
  if (!g) { closePanel(); return; }
  if (g.classList.contains("element")) showElement(g.dataset.id);
  else showLink(g.dataset.from, g.dataset.to);
});

// --- drag mode ------------------------------------------------------------------------------
// The link formula is draw.py's link_path(), sign_position() and delay_path(): keep them the same.
const ARROW = 14;
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
function signPosition(p0, ctrl, p2, back = 26, out = 16) {
  const [tx, ty] = tangent(p0, ctrl, p2, 0.92);
  const n = Math.hypot(tx, ty) || 1;
  const ux = tx / n, uy = ty / n;
  const mx = (p0[0] + p2[0]) / 2, my = (p0[1] + p2[1]) / 2;
  let side = (ctrl[0] - mx) * -(p2[1] - p0[1]) + (ctrl[1] - my) * (p2[0] - p0[0]);
  if (Math.abs(side) < 1e-6) side = -1;
  const s = side > 0 ? 1 : -1;
  return [p2[0] - ux * back + -uy * s * out, p2[1] - uy * back + ux * s * out];
}
function delayPath(p0, ctrl, p2, half = 9, gap = 4) {
  const [x, y] = bezier(p0, ctrl, p2, 0.5);
  const [tx, ty] = tangent(p0, ctrl, p2, 0.5);
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
function redrawLink(g) {
  const [p0, ctrl, p2] = linkPath(boxOf(groupOf[g.dataset.from]), boxOf(groupOf[g.dataset.to]), +g.dataset.curvature);
  const f = v => v.toFixed(1);
  g.querySelector("path.link-path").setAttribute("d", `M ${f(p0[0])} ${f(p0[1])} Q ${f(ctrl[0])} ${f(ctrl[1])} ${f(p2[0])} ${f(p2[1])}`);
  const [sx, sy] = signPosition(p0, ctrl, p2);
  const sign = g.querySelector("text.sign");
  sign.setAttribute("x", f(sx));
  sign.setAttribute("y", f(sy));
  const delay = g.querySelector("path.delay");
  if (delay) delay.setAttribute("d", delayPath(p0, ctrl, p2));
}
function moveElement(g, dx, dy) {
  for (const node of g.querySelectorAll("rect, text")) {
    node.setAttribute("x", (+node.getAttribute("x") + dx).toFixed(1));
    node.setAttribute("y", (+node.getAttribute("y") + dy).toFixed(1));
  }
  for (const l of links) if (l.dataset.from === g.dataset.id || l.dataset.to === g.dataset.id) redrawLink(l);
}
const toSvg = ev => {
  const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(svg.getScreenCTM().inverse());
  return [p.x, p.y];
};
const moveToggle = document.getElementById("move");
const download = document.getElementById("download");
const map = document.getElementById("map");
let drag = null, dragged = false;
moveToggle.addEventListener("change", () => {
  map.classList.toggle("moving", moveToggle.checked);
  download.disabled = !moveToggle.checked;
});

// --- pan and zoom ---------------------------------------------------------------------------
// The drawing is far larger than a screen: the viewBox is the window onto it. Wheel or pinch
// zooms at the cursor, dragging the background pans, "Fit" shows the whole drawing again.
const base = (() => { const v = svg.viewBox.baseVal; return { x: v.x, y: v.y, w: v.width, h: v.height }; })();
const view = { ...base };
const applyView = () => svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
const unitsPerPixel = () => Math.max(view.w / svg.clientWidth, view.h / svg.clientHeight);
function zoomAt(point, factor) {
  view.w /= factor;
  view.h /= factor;
  view.x = point[0] - (point[0] - view.x) / factor;
  view.y = point[1] - (point[1] - view.y) / factor;
  applyView();
}
svg.addEventListener("wheel", ev => {
  ev.preventDefault();
  zoomAt(toSvg(ev), Math.exp(-ev.deltaY * 0.002));
}, { passive: false });
const centre = () => [view.x + view.w / 2, view.y + view.h / 2];
document.getElementById("zoom-in").addEventListener("click", () => zoomAt(centre(), 1.4));
document.getElementById("zoom-out").addEventListener("click", () => zoomAt(centre(), 1 / 1.4));
document.getElementById("fit").addEventListener("click", () => { Object.assign(view, base); applyView(); });

svg.addEventListener("pointerdown", ev => {
  const g = ev.target.closest("g.element");
  if (moveToggle.checked && g) drag = { kind: "element", g, last: toSvg(ev) };
  else drag = { kind: "pan", last: [ev.clientX, ev.clientY] };
  dragged = false;
  svg.setPointerCapture(ev.pointerId);
  ev.preventDefault();
});
svg.addEventListener("pointermove", ev => {
  if (!drag) return;
  if (drag.kind === "element") {
    const p = toSvg(ev);
    const dx = p[0] - drag.last[0], dy = p[1] - drag.last[1];
    if (dx === 0 && dy === 0) return;
    dragged = true;
    moveElement(drag.g, dx, dy);
    drag.last = p;
  } else {
    const k = unitsPerPixel();
    const dx = (ev.clientX - drag.last[0]) * k, dy = (ev.clientY - drag.last[1]) * k;
    if (dx === 0 && dy === 0) return;
    dragged = true;
    view.x -= dx;
    view.y -= dy;
    applyView();
    drag.last = [ev.clientX, ev.clientY];
  }
});
svg.addEventListener("pointerup", () => { drag = null; setTimeout(() => { dragged = false; }, 0); });
download.addEventListener("click", () => {
  const layout = {};
  for (const g of elements) {
    const b = boxOf(g);
    layout[g.dataset.id] = { x: Math.round((b[0] + b[2]) / 2), y: Math.round((b[1] + b[3]) / 2) };
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(layout, null, 2) + "\n"], { type: "application/json" }));
  a.download = "layout.json";
  a.click();
  URL.revokeObjectURL(a.href);
});
