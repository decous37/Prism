// Exercise the independent main page with the same asynchronous bridge as WebKit.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set();
    elements.set(id, { textContent: '', value: '', dataset: {},
      classList: { add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x),
        toggle(x, enabled) { enabled ? classes.add(x) : classes.delete(x); } },
      blur() { this.blurred = true; },
    });
  }
  return elements.get(id);
}
const buttons = ['apple', 'light', 'ai'].map(eng => Object.assign(element(eng), { dataset: { eng } }));
const calls = [];
const events = {};
let config = { hotkey_display: '⌘ ⌥ X', engine: 'apple', ai_model: 'qwen2.5:7b' };
const bridge = {
  async save_config(updates) { calls.push(['save', updates]); config = { ...config, ...updates }; return { ok: true, config }; },
  async hide_window() { calls.push(['hide']); },
  async quit_app() { calls.push(['quit']); },
  async request_accessibility() { calls.push(['permissions']); return { ok: true }; },
  async set_recording(value) { calls.push(['recording', value]); },
  async start_ai_model() { calls.push(['model', config.ai_model]); return { ok: true, state: 'ready', message: '模型已就绪' }; },
};
const window = { pywebview: { api: bridge }, addEventListener(name, fn) { events[name] = fn; } };
const document = { getElementById: element, querySelectorAll: () => buttons };
vm.runInNewContext(fs.readFileSync('main.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1], { window, document });
async function key(key, target = { tagName: 'BODY' }, extra = {}) {
  await events.keydown({ key, target, preventDefault() {}, isComposing: false, ...extra });
}
(async () => {
  window.initConfig(config);
  window.updateAppStatus({ authorized: false });
  assert.equal(element('permissionStatus').textContent, '权限未生效');
  window.updateAppStatus({ authorized: true });
  assert.equal(element('permissionStatus').textContent, '已授权');
  await element('permissionBtn').onclick();
  assert.deepEqual(calls.pop(), ['permissions']);
  await buttons[2].onclick();
  assert.equal(element('aiPanel').classList.contains('show'), true);
  // Startup must wait for an in-flight model edit to be persisted.
  element('aiModelInput').onchange({ target: { value: 'qwen2.5:14b' } });
  await element('startModelBtn').onclick();
  assert.deepEqual(calls.at(-1), ['model', 'qwen2.5:14b']);
  assert.equal(element('aiStatus').textContent, '模型已就绪');
  calls.length = 0;
  await key('Enter');
  assert.equal(calls.length, 0); // Main page has no popup copy/dismiss behavior.
  const input = Object.assign(element('aiModelInput'), { tagName: 'INPUT' });
  await key('Enter', input);
  assert.equal(input.blurred, true);
  assert.equal(calls.length, 0);
  await element('hideBtn').onclick();
  assert.equal(calls.some(c => c[0] === 'hide'), true);
  assert.equal(calls.some(c => c[0] === 'quit'), false);
  calls.length = 0;
  await element('quitBtn').onclick();
  assert.deepEqual(calls, [['quit']]);
  console.log('Main page passed: permission updates, shared settings, model save before startup, independent Enter, hide versus full quit.');
})().catch(error => { console.error(error); process.exit(1); });
