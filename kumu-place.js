// Paste into the browser console (Chrome: Cmd+Opt+J) on the Kumu map that is linked to
// dist/kumu.json. Pins every element at its x and y fields, so the layout in cld.json becomes
// the map's layout; Kumu keeps pinned positions across refreshes. Run it once after linking,
// and again after a layout change made in cld.json. It uses Kumu's internal objects
// (currentMap, savePosition), so a Kumu update may break it.
const nodes = window.currentMap.graph.nodes;
const list = Array.isArray(nodes) ? nodes : nodes.models || Object.values(nodes);
let placed = 0;
for (const node of list) {
  const fields = node.entity.ownAttrs || {};
  if (typeof fields.x !== "number" || typeof fields.y !== "number") continue;
  node.position.x = fields.x;
  node.position.y = fields.y;
  node.set("pinned", true);
  node.savePosition();
  placed++;
}
console.log(`placed ${placed} of ${list.length} elements`);
