const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function load(fetch) {
  const root = { querySelector: () => null, querySelectorAll: () => [] };
  const timers = new Map();
  let id = 0;
  const context = {
    document: { getElementById: () => root, querySelector: () => null,
      addEventListener() {}, visibilityState: 'visible' },
    window: { localStorage: { getItem() {} }, location: { origin: 'http://localhost' }, addEventListener() {} },
    URL, AbortController, AbortSignal, fetch,
    setTimeout(fn) { timers.set(++id, fn); return id; },
    clearTimeout(id) { timers.delete(id); },
  };
  let source = fs.readFileSync(path.join(__dirname, '../src/pinballctl/app/modules/logs/static/logs.js'), 'utf8');
  // Keep production functions intact; omit automatic startup and expose test hooks.
  source = source.replace('  reload();\n  setScrollHeight();', '');
  source = source.replace(/\}\)\(\);\s*$/, 'globalThis.api = {state, appendChunk, applyFilter, fetchChunk, stopTail}; })();');
  vm.runInNewContext(source, context);
  return { ...context.api, timers };
}
const response = (data, next_offset = 10, rotated = false) => ({ok: true, json: async () => ({data, next_offset, rotated})});

test('last unterminated line is visible and joins its continuation', () => {
  const ui = load();
  ui.appendChunk('first\npart');
  ui.applyFilter();
  assert.deepEqual(Array.from(ui.state.visible), ['part', 'first']);
  ui.appendChunk('ial\n');
  ui.applyFilter();
  assert.deepEqual(Array.from(ui.state.visible), ['partial', 'first']);
});

test('changing filters retains lines fetched while another filter was active', async () => {
  let url;
  const ui = load(async value => { url = new URL(value); return response('alpha\nbeta\n'); });
  ui.state.keyword = 'alpha';
  await ui.fetchChunk();
  assert.equal(url.searchParams.has('filter'), false);
  assert.deepEqual(Array.from(ui.state.visible), ['alpha']);
  ui.state.keyword = 'beta';
  ui.applyFilter();
  assert.deepEqual(Array.from(ui.state.visible), ['beta']);
});

test('late response from a cancelled source cannot overwrite the current view', async () => {
  let resolve;
  const ui = load(() => new Promise(r => { resolve = r; }));
  const pending = ui.fetchChunk();
  ui.stopTail();
  ui.state.target = 'bridge';
  resolve(response('old source\n', 99));
  await pending;
  assert.equal(ui.state.offset, 0);
  assert.equal(ui.state.buffer.length, 0);
});

test('hung request is aborted and a later poll can recover', async () => {
  let calls = 0;
  const ui = load((url, {signal}) => {
    if (++calls > 1) return Promise.resolve(response('recovered\n'));
    return new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(Object.assign(new Error(), {name: 'AbortError'})));
    });
  });
  const pending = ui.fetchChunk();
  Array.from(ui.timers.values())[0]();
  await pending;
  assert.equal(ui.state.controller, null);
  assert.equal(ui.timers.size, 0);
  await ui.fetchChunk();
  assert.deepEqual(Array.from(ui.state.visible), ['recovered']);
});

test('rotation discards partial text from the previous file', async () => {
  const ui = load(async () => response('fresh\n', 6, true));
  ui.appendChunk('old partial');
  await ui.fetchChunk();
  assert.deepEqual(Array.from(ui.state.visible), ['fresh']);
});
