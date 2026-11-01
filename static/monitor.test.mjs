import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag = '') { this.tag = tag; this.children = []; this.style = {}; this.events = {}; this.attributes = {}; this.dataset = {}; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  addEventListener(name, fn) { this.events[name] = fn; }
  setAttribute(name, value) { this.attributes[name] = value; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return (this.ownText || '') + this.children.map(x => x.textContent).join(''); }
  set innerHTML(_) { throw Error('Unsafe HTML'); }
}
const script = readFileSync(new URL('./monitor.js', import.meta.url), 'utf8');
const helper = readFileSync(new URL('./content-coverage.js', import.meta.url), 'utf8');
const tick = () => new Promise(setImmediate);
function setup(view, responder) {
  const ids = ['monitor-refresh', 'coverage-body', 'coverage-time', 'work-body', ...['leases', 'pipeline', 'services', 'activity'].flatMap(x => [`${x}-body`, `${x}-time`])];
  const nodes = Object.fromEntries(ids.map(id => [id, new Element()]));
  const context = {document: {body: {dataset: {monitorView: view}}, getElementById: id => nodes[id], createElement: tag => new Element(tag)},
    fetch: responder, setInterval() {}, Date};
  vm.runInNewContext(helper, context); vm.runInNewContext(script, context);
  return nodes;
}
const response = body => ({ok: true, json: async () => body});
const en = {total: 3, acceptance_recorded: 1, review_recorded: 2, needs_revision: 0, unreviewed: 1, stale: 0, invalid: 0};
const uk = {total: 1, acceptance_recorded: 0, review_recorded: 0, needs_revision: 0, unreviewed: 1, stale: 0, invalid: 0};
const coverage = {status: 'needs_attention', coverage_health: 'known', parked_locales: ['uk'], locales: {en, uk},
  tracks: {en: {prerequisites: en}, uk: {linux: uk}}, work_errors: [], pages: [
    {path: 'prerequisites/full lesson.md', locale: 'en', acceptance_recorded: false, work: {state: 'reviewing', summary: '<script>literal</script>', next_action: 'Wait', updated_at: '2026-10-31T09:00:00Z', review: {spent: 4, ceiling: 5}}},
    {path: 'linux/unknown.md', locale: 'en', acceptance_recorded: false, work: {state: 'unknown'}},
    {path: 'linux/accepted.md', locale: 'en', acceptance_recorded: true, work: {state: 'accepted'}},
    {path: 'uk/linux/index.md', locale: 'uk', acceptance_recorded: false, work: {state: 'parked'}}]};
let current = response(coverage);
const overview = setup('overview', async () => current);
await tick();
assert.match(overview['coverage-body'].textContent, /1 of 3 pages accepted/);
assert.match(overview['coverage-body'].textContent, /Ukrainian \(parked\)/);
assert.match(overview['coverage-body'].textContent, /Current unaccepted.*Stale \/ invalid.*No current review/);
assert.equal(overview['coverage-body'].children[0].children[0].children[3].children[0].href, '/quality?locale=en&search=prerequisites%2F');
const parked = overview['coverage-body'].children[0].children[1];
assert.equal(parked.tag, 'details'); assert.equal(parked.open, false);
parked.open = true; parked.events.toggle();
assert.match(overview['work-body'].textContent, /<script>literal<\/script>/);
assert.match(overview['work-body'].textContent, /Review calls: 4\/5 total allowance; not launch permission/);
assert.match(overview['work-body'].textContent, /accepted: 1.*unknown: 1/);
assert.doesNotMatch(overview['work-body'].textContent, /linux\/unknown/);
assert.equal(overview['work-body'].children[0].children[1].children[0].children[1].href, '/quality?locale=en&search=prerequisites%2Ffull%20lesson.md');
await overview['monitor-refresh'].events.click();
assert.equal(overview['coverage-body'].children[0].children[1].open, true);
current = {ok: false, status: 503}; await overview['monitor-refresh'].events.click();
assert.match(overview['coverage-body'].textContent, /Unavailable: HTTP 503/);
assert.match(overview['work-body'].textContent, /unavailable/);
current = response({...coverage, tracks: {en: {}, uk: {linux: uk}}}); await overview['monitor-refresh'].events.click();
assert.match(overview['coverage-body'].textContent, /Invalid track counters/);
current = response({...coverage, pages: [{...coverage.pages[0], work: {state: 'accepted'}}, ...coverage.pages.slice(1)]});
await overview['monitor-refresh'].events.click();
assert.match(overview['coverage-body'].textContent, /Invalid recorded-work response/);

let releaseOld; let count = 0;
const race = setup('overview', () => ++count === 1 ? new Promise(resolve => { releaseOld = resolve; }) : Promise.resolve(response(coverage)));
await race['monitor-refresh'].events.click(); releaseOld({ok: false, status: 500}); await tick();
assert.match(race['coverage-body'].textContent, /1 of 3 pages accepted/);

const payloads = {
  '/api/pipeline/leases': {exists: true, count: 1, active: [{module_key: '<lease>', phase: 'review', leased_by: 'worker', lease_expires_at: 1800000000}]},
  '/api/pipeline/v2/status': {total_modules: 1, counts: {done: 1}},
  '/api/runtime/services': {total: 1, services: [{label: '<service>', status: 'running'}]},
  '/api/activity?limit=15': {count: 1, items: [{summary: '<event>', source: 'commit', at: 1800000000}]},
};
let failPipeline = false;
const ops = setup('operations', async url => failPipeline && url === '/api/pipeline/v2/status' ? {ok: false, status: 503} : response(payloads[url]));
await tick();
assert.match(ops['leases-body'].textContent, /<lease>/);
assert.match(ops['services-body'].textContent, /not a service-health/);
assert.match(ops['activity-body'].textContent, /<event>/);
assert.match(ops['pipeline-body'].textContent, /not page acceptance/);
failPipeline = true; await ops['monitor-refresh'].events.click();
assert.match(ops['pipeline-body'].textContent, /Unavailable: HTTP 503/);
assert.doesNotMatch(ops['pipeline-body'].textContent, /done/);
assert.match(ops['leases-body'].textContent, /<lease>/);
payloads['/api/pipeline/leases'] = {exists: false, count: 0, active: []};
await ops['monitor-refresh'].events.click();
assert.match(ops['leases-body'].textContent, /Lease data unavailable/);
console.log('monitor UI: coverage, safe text, race protection and independent operational failures passed');
