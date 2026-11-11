// Moving and zooming a drawing, and the bar and the menu over it: the CLD's page and the Actor
// Map's share this file, so the two work alike.
// The drawing fills the window and the viewBox is the window onto it. On a trackpad two fingers
// move the map and a pinch zooms at the fingers; a mouse wheel zooms at the cursor; on a touch
// screen one finger moves it and two zoom. Dragging moves the map, from a box or a link too, and a
// press that barely moves stays a click. A double click on the background zooms in; "Fit" shows the
// whole drawing below the bar. The map moves freely, but part of the window always stays on the
// drawing, so it cannot be lost.
"use strict";

const MAX_ZOOM = 16;   // how far in, against Fit
const MIN_ZOOM = 0.5;  // how far out, against Fit
const KEEP = 0.15;     // the share of the window that always stays on the drawing
const CLICK_SLOP = 4;  // the pixels a press may move and still be a click

function svgPoint(svg, ev) {
  const p = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(svg.getScreenCTM().inverse());
  return [p.x, p.y];
}

// grab(pointerdown event) returns a function that handles the pointer's moves, returning true when
// it moved something, or null for a press that moves the map. It returns { wasDragged }, which a
// click handler asks, since a drag is not a click.
function mapControls(svg, map, grab = () => null) {
  const b = svg.viewBox.baseVal;
  const base = { x: b.x, y: b.y, w: b.width, h: b.height };
  const view = { ...base };
  const bar = document.querySelector(".bar");
  let fitted = true;  // a window resized while the drawing is fitted fits it again

  const applyView = () => svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
  const unitsPerPixel = () => Math.max(view.w / svg.clientWidth, view.h / svg.clientHeight);
  const clampAxis = (pos, size, start, span) =>
    Math.min(start + span - size * KEEP, Math.max(start - size * (1 - KEEP), pos));
  function clampView() {
    view.x = clampAxis(view.x, view.w, base.x, base.w);
    view.y = clampAxis(view.y, view.h, base.y, base.h);
  }
  function fitView() {  // the window's view that shows the whole drawing below the bar
    const top = bar.getBoundingClientRect().bottom + 6;
    const width = svg.clientWidth, height = svg.clientHeight;
    const k = Math.max(base.w / width, base.h / (height - top));
    const w = width * k;
    return { x: base.x - (w - base.w) / 2, y: base.y - top * k - ((height - top) * k - base.h) / 2, w, h: height * k };
  }
  function fit() { Object.assign(view, fitView()); fitted = true; applyView(); }
  function zoomAt(point, factor) {
    const whole = fitView().w;
    const w = Math.min(whole / MIN_ZOOM, Math.max(whole / MAX_ZOOM, view.w / factor));
    const applied = view.w / w;
    view.w /= applied;
    view.h /= applied;
    view.x = point[0] - (point[0] - view.x) / applied;
    view.y = point[1] - (point[1] - view.y) / applied;
    fitted = false;
    clampView();
    applyView();
  }
  function panBy(dxPixels, dyPixels) {
    const k = unitsPerPixel();
    view.x += dxPixels * k;
    view.y += dyPixels * k;
    fitted = false;
    clampView();
    applyView();
  }
  fit();
  addEventListener("resize", () => { if (fitted) fit(); });

  // a trackpad's scroll reports wheelDeltaY as -3 times deltaY, a mouse wheel's as multiples of 120
  const fromTrackpad = ev => ev.deltaX !== 0
    || (ev.wheelDeltaY ? Math.abs(ev.wheelDeltaY + 3 * ev.deltaY) < 3 : ev.deltaMode === 0);
  svg.addEventListener("wheel", ev => {
    ev.preventDefault();
    if (ev.ctrlKey) zoomAt(svgPoint(svg, ev), Math.exp(-ev.deltaY * 0.012));  // a pinch arrives as ctrl + wheel
    else if (fromTrackpad(ev)) panBy(ev.deltaX, ev.deltaY);
    else zoomAt(svgPoint(svg, ev), Math.exp(-ev.deltaY * 0.002));
  }, { passive: false });
  svg.addEventListener("dblclick", ev => {
    if (!ev.target.closest("g.element, g.link, g.actor, g.relation")) zoomAt(svgPoint(svg, ev), 2);
  });

  // --- pressing and dragging ----------------------------------------------------------------
  let drag = null, dragged = false;
  const fingers = new Map();  // on a touch screen: pointer id -> [x, y]
  const between = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
  svg.addEventListener("pointerdown", ev => {
    if (ev.pointerType === "touch") fingers.set(ev.pointerId, [ev.clientX, ev.clientY]);
    if (fingers.size === 2) { drag = null; return; }  // two fingers zoom, below
    const move = grab(ev);
    drag = move ? { move } : { start: [ev.clientX, ev.clientY], last: [ev.clientX, ev.clientY] };
    dragged = false;
    ev.preventDefault();
  });
  svg.addEventListener("pointermove", ev => {
    if (fingers.has(ev.pointerId)) {
      const before = [...fingers.values()];
      fingers.set(ev.pointerId, [ev.clientX, ev.clientY]);
      if (before.length === 2) {
        const [p, q] = [...fingers.values()];
        dragged = true;
        zoomAt(svgPoint(svg, { clientX: (p[0] + q[0]) / 2, clientY: (p[1] + q[1]) / 2 }), between(p, q) / between(before[0], before[1]));
        return;
      }
    }
    if (!drag) return;
    if (!drag.move && !dragged && between(drag.start, [ev.clientX, ev.clientY]) < CLICK_SLOP) return;
    // capture only once the pointer moves: a captured pointer's click goes to the svg itself,
    // so a plain click on an element or a link would no longer find them
    if (!svg.hasPointerCapture(ev.pointerId)) svg.setPointerCapture(ev.pointerId);
    if (drag.move) { if (drag.move(ev)) dragged = true; return; }
    dragged = true;
    map.classList.add("panning");
    panBy(drag.last[0] - ev.clientX, drag.last[1] - ev.clientY);
    drag.last = [ev.clientX, ev.clientY];
  });
  function endDrag(ev) {
    fingers.delete(ev.pointerId);
    map.classList.remove("panning");
    drag = null;
    setTimeout(() => { dragged = false; }, 0);
  }
  svg.addEventListener("pointerup", endDrag);
  svg.addEventListener("pointercancel", endDrag);

  // --- the bar and the menu -----------------------------------------------------------------
  const centre = () => [view.x + view.w / 2, view.y + view.h / 2];
  document.getElementById("zoom-in").addEventListener("click", () => zoomAt(centre(), 1.4));
  document.getElementById("zoom-out").addEventListener("click", () => zoomAt(centre(), 1 / 1.4));
  document.getElementById("fit").addEventListener("click", fit);
  const fullscreen = document.getElementById("fullscreen");
  fullscreen.hidden = !document.fullscreenEnabled;
  fullscreen.addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  });
  // the menu stays open until its button or Esc closes it, so several loops can be pressed and
  // the map moved beside it
  const menu = document.getElementById("menu");
  const menuButton = document.getElementById("menu-button");
  function toggleMenu() {
    menu.hidden = !menu.hidden;
    menuButton.setAttribute("aria-expanded", String(!menu.hidden));
  }
  menuButton.addEventListener("click", toggleMenu);
  document.addEventListener("keydown", ev => {  // Esc closes what lies on top
    if (ev.key !== "Escape") return;
    if (location.hash === "#about") location.hash = "";
    else if (!document.getElementById("panel").hidden) document.getElementById("close").click();
    else if (!menu.hidden) toggleMenu();
  });
  return { wasDragged: () => dragged };
}
