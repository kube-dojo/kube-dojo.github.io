import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; this.style = {}; this.events = {}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(event, callback) { this.events[event] = callback; }
  set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
}
const elements = Object.fromEntries(['cc-summary', 'cc-note', 'cc-rows', 'cc-count', 'cc-search', 'cc-locale', 'cc-status', 'refresh'].map(id => [id, new Element(id)]));
const row = {path: '<img onerror=alert(1)>.mdx', locale: 'en', type: 'hub', receipt_status: 'stale', disposition: null,
  acceptance_recorded: false, unreviewed: true, reasons: ['receipt: stale'], layers: {technical_source: 'unknown'},
  references: {acceptance_refs: ['javascript:alert(1)', '<script>bad()</script>']}};
const data = {pages: [row, {...row, path: 'uk/index.md', locale: 'uk', receipt_status: 'missing'}],
  locales: {en: {acceptance_recorded: 0, total: 1, review_recorded: 0, needs_revision: 0, unreviewed: 1, stale: 1, invalid: 0}},
  parked_locales: ['uk'], status: 'needs_attention', coverage_health: 'unknown', caveat: 'Supplied assertion only'};
let response = {ok: true, json: async () => data};
const context = {document: {getElementById: id => elements[id], createElement: tag => new Element(tag)},
  fetch: async () => response, setInterval() {}, Date};
vm.runInNewContext(readFileSync(new URL('./quality-coverage.js', import.meta.url), 'utf8'), context);
await new Promise(setImmediate);
assert.match(elements['cc-summary'].textContent, /health unknown/);
assert.equal(elements['cc-rows'].children.length, 2);
const details = elements['cc-rows'].children[0];
assert.equal(details.tag, 'details');
assert.equal(details.children[0].tag, 'summary');
assert.match(details.children[0].textContent, /<img onerror=alert\(1\)>/);
assert.equal(details.children.at(-1).children[0].textContent, 'javascript:alert(1)');
assert.equal(details.children.at(-1).children[0].tag, 'li');
elements['cc-locale'].value = 'uk'; elements['cc-locale'].events.input();
assert.equal(elements['cc-rows'].children.length, 1);
elements['cc-status'].value = 'stale'; elements['cc-status'].events.input();
assert.equal(elements['cc-count'].textContent, '0 pages shown');
elements['cc-locale'].value = ''; elements['cc-status'].value = 'unreviewed';
elements['cc-search'].value = '.mdx'; elements['cc-search'].events.input();
assert.equal(elements['cc-count'].textContent, '1 pages shown');
response = {ok: false, status: 503};
const failed = elements.refresh.events.click();
assert.equal(elements['cc-summary'].textContent, 'Loading canonical coverage…');
assert.equal(elements['cc-rows'].children.length, 0);
await failed;
assert.match(elements['cc-summary'].textContent, /unavailable \/ unknown: HTTP 503/);
response = {ok: true, json: async () => ({})};
await elements.refresh.events.click();
assert.match(elements['cc-summary'].textContent, /Invalid coverage response/);
let release;
response = {ok: true, json: () => new Promise(resolve => { release = resolve; })};
const older = elements.refresh.events.click();
await new Promise(setImmediate);
response = {ok: false, status: 503};
await elements.refresh.events.click();
release(data); await older;
assert.match(elements['cc-summary'].textContent, /HTTP 503/);
assert.equal(elements['cc-rows'].children.length, 0);
