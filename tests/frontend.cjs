// Run the actual UI script with a minimal DOM and asynchronous bridge.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const html = fs.readFileSync('ui.html', 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set();
    elements.set(id, { style: {}, dataset: {}, textContent: '', value: '',
      classList: { add: x => classes.add(x), remove: x => classes.delete(x),
        contains: x => classes.has(x),
        toggle(x, enabled) { if (enabled === undefined) enabled = !classes.has(x); enabled ? classes.add(x) : classes.delete(x); } },
      getBoundingClientRect: () => ({ height: 100 }), blur() { this.blurred = true; },
    });
  }
  return elements.get(id);
}
const buttons = ['apple', 'light', 'ai'].map(eng => Object.assign(element(eng), { dataset: { eng } }));
const calls = [];
const events = {};
const bridge = {
  async copy_text(text) { calls.push(['copy', text]); return { ok: true }; },
  async hide_window() { calls.push(['hide']); },
  async set_recording(value) { calls.push(['recording', value]); },
  async resize_card() {},
  async start_ai_model() { calls.push(['model']); return { ok: true, state: 'ready', message: '模型已就绪' }; },
  async quit_app() { calls.push(['quit']); },
  async request_accessibility() { calls.push(['permissions']); },
};
const window = { pywebview: { api: bridge }, addEventListener(name, fn) { events[name] = fn; } };
const context = vm.createContext({ window, document: { getElementById: element,
  querySelectorAll: () => buttons, querySelector: () => element('card') },
  ResizeObserver: class { observe() {} },
  setTimeout(fn, delay) { if (delay < 500) return setTimeout(fn, 0); return 0; }, clearTimeout });
vm.runInContext(code, context);

async function key(key, target = { tagName: 'BODY' }) {
  await events.keydown({ key, target, preventDefault() {}, isComposing: false });
}
(async () => {
  window.renderTranslation({ badge: 'EN → 中文', result: '你好' });
  await element('copyBtn').onclick();
  assert.equal(element('langBadge').textContent, '✓ 已复制');
  assert.equal(calls.some(c => c[0] === 'hide'), false);
  calls.length = 0;
  await key('Enter');
  assert.deepEqual(calls.filter(c => ['copy', 'hide'].includes(c[0])), [['copy', '你好'], ['hide']]);
  calls.length = 0;
  window.renderMessage({ badge: '提示', result: 'No result yet' });
  await key('Enter');
  assert.deepEqual(calls.filter(c => ['copy', 'hide'].includes(c[0])), [['hide']]);
  calls.length = 0;
  window.showLoadingState();
  await key('Enter');
  assert.deepEqual(calls.filter(c => ['copy', 'hide'].includes(c[0])), [['hide']]);
  calls.length = 0;
  await element('closeBtn').onclick();
  assert.deepEqual(calls.filter(c => ['copy', 'hide'].includes(c[0])), [['hide']]);
  calls.length = 0;
  const input = Object.assign(element('aiModelInput'), { tagName: 'INPUT' });
  await key('Enter', input);
  assert.equal(input.blurred, true);
  assert.equal(calls.length, 0);
  await element('startModelBtn').onclick();
  assert.equal(element('aiStatus').textContent, '模型已就绪');
  assert.equal(element('startModelBtn').disabled, false);
  assert.equal(calls.some(c => c[0] === 'model'), true);
  calls.length = 0;
  bridge.copy_text = async () => ({ ok: false });
  window.renderTranslation({ badge: 'EN → 中文', result: '你好' });
  await element('copyBtn').onclick();
  assert.equal(element('langBadge').textContent, '复制失败，请重试');
  assert.equal(calls.some(c => c[0] === 'hide'), false);
  console.log('Frontend passed: explicit copy success/failure, copy before hide, empty/loading dismissal, ×, model startup status.');
})().catch(error => { console.error(error); process.exit(1); });
