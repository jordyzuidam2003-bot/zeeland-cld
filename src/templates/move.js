// Move mode, for both pages: with "Move" on, drag a box to move it or a link to bend it, its middle
// following the pointer; "Download layout" then saves layout.json, every box's place and every
// link's curvature, which build.py --layout writes into the model. Dragging redraws the links but
// never the CLD's regions or the Actor Map's bands, which build.py draws again from the new places.
// The link formula is draw_cld.py's link_path() and link_paths(): keep them the same.
"use strict";

const bezier = (p0, p1, p2, t) => {
  const s = 1 - t;
  return [s * s * p0[0] + 2 * s * t * p1[0] + t * t * p2[0], s * s * p0[1] + 2 * s * t * p1[1] + t * t * p2[1]];
};
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
const boxOf = g => {
  const r = g.querySelector("rect");
  const x = +r.getAttribute("x"), y = +r.getAttribute("y");
  return [x, y, x + +r.getAttribute("width"), y + +r.getAttribute("height")];
};
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
// a bend as layout.json keeps it: from -1 to 1, in hundredths
const roundBend = k => Math.round(Math.max(-1, Math.min(1, k)) * 100) / 100;

// moveMode(svg, page) wires the bar's Move toggle and Download button and returns { grab, paths }:
// grab(pointerdown event), a press in Move mode, for mapControls(); paths(), every link's
// [p0, ctrl, p2] from the boxes' places now. page names the drawing's parts and gives what differs
// between the two pages:
//   box, link        the selectors of a box's group (with data-id) and a link's (with data-from,
//                    data-to and data-curvature, its line a path.link-path)
//   key(g)           a link's name in layout.json
//   bend(g, k)       the curvature a link keeps when its middle is dragged to bend k; roundBend(k)
//                    if left out
//   redraw(g, path)  draws what a link carries besides its line (the CLD's sign and delay mark)
//   grab(ev, paths)  a press on what only the page has (the CLD's delay marks), or null
//   extra()          the page's own fields in layout.json
function moveMode(svg, page) {
  const boxes = [...svg.querySelectorAll(page.box)];
  const links = [...svg.querySelectorAll(page.link)];
  const groupOf = Object.fromEntries(boxes.map(g => [g.dataset.id, g]));
  // every link's [p0, ctrl, p2]: the ends spread along the box edges, as draw_cld.py's link_paths()
  function paths() {
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
  function redraw(g, [p0, ctrl, p2]) {
    const f = v => v.toFixed(1);
    const d = `M ${f(p0[0])} ${f(p0[1])} Q ${f(ctrl[0])} ${f(ctrl[1])} ${f(p2[0])} ${f(p2[1])}`;
    for (const path of g.querySelectorAll("path.link-path, path.link-grip")) path.setAttribute("d", d);
    if (page.redraw) page.redraw(g, [p0, ctrl, p2]);
  }
  // a moved box or a bent link changes where the other links on its edges end, so every link is redrawn
  const redrawAll = () => { for (const [g, path] of paths()) redraw(g, path); };
  // each link gets a wide invisible copy of its line under it, so the thin line can be grabbed
  for (const g of links) {
    const grip = g.querySelector("path.link-path").cloneNode();
    grip.setAttribute("class", "link-grip");
    grip.removeAttribute("marker-end");
    grip.removeAttribute("stroke-dasharray");
    grip.setAttribute("stroke", "transparent");
    grip.setAttribute("stroke-width", "18");
    g.insertBefore(grip, g.firstChild);
  }
  // a dragged link bends so its middle follows the pointer: the middle of the curve lies half
  // the control point's offset from the chord, so curvature = 2 (p - mid) . (dy, -dx) / chord²
  function bendLink(g, p) {
    const [p0, , p2] = paths().get(g);
    const dx = p2[0] - p0[0], dy = p2[1] - p0[1];
    const mid = [(p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2];
    const k = 2 * ((p[0] - mid[0]) * dy - (p[1] - mid[1]) * dx) / (dx * dx + dy * dy || 1);
    g.dataset.curvature = String(page.bend ? page.bend(g, k) : roundBend(k));
    redrawAll();
  }
  function moveBox(g, dx, dy) {
    for (const node of g.querySelectorAll("rect, text")) {
      node.setAttribute("x", (+node.getAttribute("x") + dx).toFixed(1));
      node.setAttribute("y", (+node.getAttribute("y") + dy).toFixed(1));
    }
    redrawAll();
  }

  const toggle = document.getElementById("move");
  const download = document.getElementById("download");
  toggle.addEventListener("change", () => {
    document.getElementById("map").classList.toggle("moving", toggle.checked);
    download.hidden = !toggle.checked;
  });
  const toSvg = ev => svgPoint(svg, ev);
  function grab(ev) {
    if (!toggle.checked) return null;
    const own = page.grab ? page.grab(ev, paths) : null;
    if (own) return own;
    const g = ev.target.closest(page.box), l = ev.target.closest(page.link);
    if (g) {
      let last = toSvg(ev);
      return move => {
        const p = toSvg(move), dx = p[0] - last[0], dy = p[1] - last[1];
        if (dx === 0 && dy === 0) return false;
        moveBox(g, dx, dy);
        last = p;
        return true;
      };
    }
    if (l) return move => { bendLink(l, toSvg(move)); return true; };
    return null;
  }
  download.addEventListener("click", () => {
    const layout = {};
    for (const g of boxes) {
      const b = boxOf(g);
      layout[g.dataset.id] = { x: Math.round((b[0] + b[2]) / 2), y: Math.round((b[1] + b[3]) / 2) };
    }
    layout.curvature = Object.fromEntries(links.map(g => [page.key(g), +g.dataset.curvature]));
    if (page.extra) Object.assign(layout, page.extra());
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(layout, null, 2) + "\n"], { type: "application/json" }));
    a.download = "layout.json";
    a.click();
    URL.revokeObjectURL(a.href);
  });
  return { grab, paths };
}
