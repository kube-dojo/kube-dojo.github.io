import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; this.style = {}; this.events = {}; this.dataset = {}; this.scrollTop = 0; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(event, callback) { this.events[event] = callback; }
  setAttribute(key, value) { this[key] = value; }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text || ''; }
  set innerHTML(_) { throw new Error('Unsafe HTML rendering'); }
}
const elements = Object.fromEntries(['cc-summary', 'cc-note', 'cc-tracks', 'cc-rows', 'cc-count', 'cc-search', 'cc-locale', 'cc-status', 'cc-work', 'cc-work-summary', 'refresh'].map(id => [id, new Element(id)]));
const row = {path: '<img onerror=alert(1)>.mdx', locale: 'en', type: 'hub', receipt_status: 'stale', disposition: null,
  acceptance_recorded: false, unreviewed: true, reasons: ['receipt: stale'], layers: {technical_source: 'unknown'},
  references: {acceptance_refs: ['javascript:alert(1)', '<script>bad()</script>']}, work: {state: 'reviewing', summary: '<script>work</script>', next_action: 'Wait', updated_at: '2026-10-31T09:00:00Z', evidence_refs: ['issue:1'], review: {spent: 4, ceiling: 5}}};
const data = {pages: [row, {...row, path: 'uk/index.md', locale: 'uk', receipt_status: 'missing'}],
  locales: {en: {acceptance_recorded: 10, total: 1089, review_recorded: 41, needs_revision: 30, unreviewed: 1048, stale: 1, invalid: 0},
    uk: {acceptance_recorded: 0, total: 1, review_recorded: 0, needs_revision: 0, unreviewed: 1, stale: 0, invalid: 0}},
  tracks: {en: {shared: {acceptance_recorded: 10, total: 1089, review_recorded: 41, needs_revision: 30, unreviewed: 1048, stale: 1, invalid: 0}},
    uk: {shared: {acceptance_recorded: 0, total: 1, review_recorded: 0, needs_revision: 0, unreviewed: 1, stale: 0, invalid: 0}}},
  parked_locales: ['uk'], status: 'needs_attention', coverage_health: 'unknown', caveat: 'Supplied assertion only', work_summary: {reviewing: 2}, work_errors: []};
let response = {ok: true, json: async () => data};
const context = {URLSearchParams, window: {location: {search: ''}}, document: {getElementById: id => elements[id], createElement: tag => new Element(tag)},
  fetch: async () => response, setInterval() {}, Date};
vm.runInNewContext(readFileSync(new URL('./content-coverage.js', import.meta.url), 'utf8'), context);
const corpus = {total: 1089, acceptance_recorded: 10, review_recorded: 41, needs_revision: 30, stale: 1, invalid: 0, unreviewed: 1048};
context.corpus = corpus;
assert.deepEqual(Array.from(vm.runInNewContext('coveragePartition(corpus)', context)), [10, 1, 30, 1, 0, 1047]);
assert.equal(vm.runInNewContext('coveragePercent(corpus)', context), '0.9');
assert.equal(vm.runInNewContext('coveragePartition({...corpus, unreviewed: 1000})', context), null);
assert.equal(vm.runInNewContext('coveragePartition({...corpus, needs_revision: 99})', context), null);
vm.runInNewContext(readFileSync(new URL('./quality-coverage.js', import.meta.url), 'utf8'), context);
await new Promise(setImmediate);
assert.match(elements['cc-summary'].textContent, /health unknown/);
assert.equal(elements['cc-rows'].children.length, 2);
assert.equal(elements['cc-tracks'].children.length, 2);
assert.match(elements['cc-tracks'].children[1].children[0].textContent, /UK \(parked\)/);
const en = elements['cc-tracks'].children[0], uk = elements['cc-tracks'].children[1];
assert.equal(uk.open, false);
assert.match(en.children[0].textContent, /10\/1089 accepted/);
assert.deepEqual(en.children[1].children.map(segment => Number.parseFloat(segment.style.width)), [10, 1, 30, 1, 0, 1047].map(n => n / 1089 * 100));
assert.match(en.children[1]['aria-label'], /No review recorded 1047/);
assert.deepEqual(en.children[2].children.map(item => item.textContent), ['Accepted: 10', 'Current unaccepted: 1', 'Revision: 30', 'Stale: 1', 'Invalid: 0', 'No review recorded: 1047']);
uk.open = true;
en.children[3].children[0].events.click();
assert.equal(elements['cc-rows'].children.length, 1);
assert.equal(en.children[3].children[0]['aria-pressed'], 'true');
assert.match(elements['cc-count'].children[0].textContent, /EN Shared/);
elements['cc-count'].children[0].events.click();
assert.equal(en.children[3].children[0]['aria-pressed'], 'false');
elements['cc-locale'].value = ''; elements['cc-locale'].events.input();
assert.equal(elements['cc-rows'].children.length, 2);
const details = elements['cc-rows'].children[0];
assert.equal(details.tag, 'details');
assert.equal(details.children[0].tag, 'summary');
assert.match(details.children[0].textContent, /<img onerror=alert\(1\)>/);
assert.equal(details.className, 'cc-page cc-page3');
assert.equal(details.children.at(-1).children[0].textContent, 'javascript:alert(1)');
assert.equal(details.children.at(-1).children[0].tag, 'li');
assert.match(elements['cc-work-summary'].textContent, /reviewing 2/);
assert.match(details.children[3].textContent, /<script>work<\/script>.*Review calls: 4\/5.*not launch permission/);
details.open = true;
elements['cc-rows'].scrollTop = 42;
let releaseRefresh;
response = {ok: true, json: () => new Promise(resolve => { releaseRefresh = resolve; })};
const pending = elements.refresh.events.click();
await new Promise(setImmediate);
assert.match(elements['cc-summary'].textContent, /refreshing/);
assert.equal(elements['cc-rows'].children[0], details);
releaseRefresh(data); await pending;
assert.equal(elements['cc-rows'].children[0], details);
assert.equal(elements['cc-tracks'].children[0].children[3].children[0], en.children[3].children[0]);
assert.equal(elements['cc-tracks'].children[1].open, true);
assert.equal(details.open, true);
assert.equal(elements['cc-rows'].scrollTop, 42);
response = {ok: true, json: async () => ({...data, pages: [{...row, disposition: 'revise'}, data.pages[1]]})};
await elements.refresh.events.click();
assert.notEqual(elements['cc-rows'].children[0], details);
assert.equal(elements['cc-rows'].children[0].open, true);
assert.equal(elements['cc-rows'].scrollTop, 42);
assert.match(elements['cc-rows'].children[0].children[1].textContent, /revise/);
elements['cc-work'].value = 'blocked'; elements['cc-work'].events.input(); assert.equal(elements['cc-count'].textContent, '0 pages shown');
elements['cc-work'].value = 'reviewing'; elements['cc-work'].events.input(); assert.equal(elements['cc-count'].textContent, '2 pages shown');
elements['cc-work'].value = ''; elements['cc-work'].events.input();
elements['cc-locale'].value = 'uk'; elements['cc-locale'].events.input();
assert.equal(elements['cc-rows'].children.length, 1);
elements['cc-status'].value = 'stale'; elements['cc-status'].events.input();
assert.equal(elements['cc-count'].textContent, '0 pages shown');
elements['cc-locale'].value = ''; elements['cc-status'].value = 'unreviewed';
elements['cc-search'].value = '.mdx'; elements['cc-search'].events.input();
assert.equal(elements['cc-count'].textContent, '1 pages shown');
response = {ok: false, status: 503};
const failed = elements.refresh.events.click();
assert.match(elements['cc-summary'].textContent, /refreshing/);
assert.equal(elements['cc-rows'].children.length, 1);
await failed;
assert.match(elements['cc-summary'].textContent, /unavailable \/ unknown: HTTP 503/);
assert.equal(elements['cc-count'].textContent, '');
assert.equal(elements['cc-rows'].children.length, 0);
assert.equal(elements['cc-tracks'].children.length, 0);
elements['cc-search'].events.input();
assert.equal(elements['cc-count'].textContent, '');
assert.equal(elements['cc-rows'].children.length, 0);
response = {ok: true, json: async () => data};
await elements.refresh.events.click();
assert.equal(elements['cc-rows'].children.length, 1);
const one = {acceptance_recorded: 0, total: 1, review_recorded: 0, needs_revision: 0, unreviewed: 1, stale: 0, invalid: 0};
const split = {...data, pages: [row, {...row, path: 'uk/prerequisites/start.mdx', locale: 'uk'}],
  tracks: {...data.tracks, uk: {prerequisites: one}}};
response = {ok: true, json: async () => split};
await elements.refresh.events.click();
elements['cc-locale'].value = 'en'; elements['cc-locale'].events.input();
const ukTrack = elements['cc-tracks'].children[1].children[3].children[0];
ukTrack.events.click();
assert.equal(elements['cc-locale'].value, 'uk');
assert.equal(ukTrack['aria-pressed'], 'true');
assert.equal(elements['cc-rows'].children.length, 1);
assert.match(elements['cc-rows'].children[0].children[0].textContent, /uk\/prerequisites\/start.mdx · UK/);
assert.match(elements['cc-count'].children[0].textContent, /UK Prerequisites/);
elements['cc-locale'].value = 'en'; elements['cc-locale'].events.input();
assert.equal(ukTrack['aria-pressed'], 'false');
assert.equal(elements['cc-count'].children.length, 0);
ukTrack.events.click();
elements['cc-search'].value = 'absent'; elements['cc-search'].events.input();
assert.equal(elements['cc-count'].textContent, '0 pages shown');
elements['cc-count'].children[0].events.click();
elements['cc-search'].value = '.mdx'; elements['cc-search'].events.input();
const unknown = {...data, pages: [{...row, path: 'extra/index.mdx', receipt_status: 'invalid', acceptance_recorded: true}],
  tracks: {...data.tracks, en: {extra: data.tracks.en.shared}}};
response = {ok: true, json: async () => unknown};
await elements.refresh.events.click();
elements['cc-tracks'].children[0].children[3].children[0].events.click();
assert.equal(elements['cc-rows'].children[0].className, 'cc-page cc-page4');
assert.match(elements['cc-rows'].children[0].children[0].textContent, /extra\/index.mdx · EN · Invalid/);
assert.match(elements['cc-rows'].children[0].children[1].textContent, /extra\/index.mdx/);
elements['cc-count'].children[0].events.click();
response = {ok: true, json: async () => ({...data, locales: {en: {...data.locales.en, total: -1}}})};
await elements.refresh.events.click();
assert.match(elements['cc-summary'].textContent, /Invalid coverage response/);
assert.equal(elements['cc-count'].textContent, '');
assert.equal(elements['cc-rows'].children.length, 0);
response = {ok: true, json: async () => ({...data, tracks: {...data.tracks, en: {}}})};
await elements.refresh.events.click();
assert.match(elements['cc-summary'].textContent, /Invalid coverage counters/);
assert.equal(elements['cc-tracks'].children.length, 0);
response = {ok: true, json: async () => ({...data, status: 'unavailable'})};
await elements.refresh.events.click();
assert.match(elements['cc-summary'].textContent, /Coverage unavailable/);
assert.equal(elements['cc-tracks'].children.length, 0);
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
