const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function load() {
  const frames = [];
  function node() {
    return {children: [], style: {setProperty() {}}, classList: {add() {}},
      appendChild(child) { child.parentNode = this; this.children.push(child); },
      remove() { const a = this.parentNode.children; a.splice(a.indexOf(this), 1); },
      get lastElementChild() { return this.children.at(-1); }};
  }
  const table = node();
  table.querySelector = () => table.children[0] || null;
  const state = {lightingFixtures: [{id: 'strip', points: [{x: 0, y: 0}, {x: 1, y: 1}]}], tableRect: {width: 100, height: 100}};
  const context = {state, tableEl: table, root: {classList: {contains: () => false}},
    document: {createElement: node}, requestAnimationFrame: cb => {frames.push(cb); return frames.length;},
    activeLightingByFixtureId: () => ({}), normalizeHexColor: (c, fallback) => c || fallback,
    fixturePixels: f => f.points, fixtureMarkerColor: () => '#fff', fixtureMarkerSizePx: (f, scale) => scale,
    hexToRgba: () => 'rgba(0,0,0,1)'};
  const source = fs.readFileSync('src/pinballctl/app/modules/liveview/static/js/liveview.js', 'utf8');
  vm.runInNewContext(source.slice(source.indexOf('  let lightingRenderFrame'), source.indexOf('  function toCssUrl')), context);
  return {state, table, frames, render: context.renderLightingOverlay};
}

test('event bursts paint once per browser frame with the latest scale', () => {
  const ui = load();
  ui.render(1); ui.render(2); ui.render(3);
  assert.equal(ui.frames.length, 1);
  ui.frames.shift()();
  assert.equal(ui.table.children[0].children[0].style.width, '3px');
});

test('lighting updates retain existing markers and remove obsolete markers', () => {
  const ui = load();
  ui.render(1); ui.frames.shift()();
  const overlay = ui.table.children[0], marker = overlay.children[0];
  ui.state.lightingFixtures[0].points.pop();
  ui.render(2); ui.frames.shift()();
  assert.equal(ui.table.children[0], overlay);
  assert.equal(overlay.children[0], marker);
  assert.equal(overlay.children.length, 1);
  ui.state.lightingFixtures = [];
  ui.render(1); ui.frames.shift()();
  assert.equal(ui.table.children.length, 0);
});
