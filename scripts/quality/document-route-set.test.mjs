import assert from 'node:assert/strict';
import test from 'node:test';
import { buildDocumentRouteSet } from './document-route-set.mjs';

const hash = (digit = 'a') => digit.repeat(64);
const route = (overrides = {}) => ({ id: 'guide/one', url: 'https://site.test/docs/guide/one/', pathname: '/docs/guide/one/', source: 'guide/one.md', sourceSha256: hash(), isFallback: false, locale: null, lang: null, ...overrides });
const manifest = (routes = [route()], overrides = {}) => ({ schemaVersion: 1, scope: 'starlight-document-routes', config: { site: 'https://site.test/contained/', base: '/docs/', trailingSlash: 'always', buildFormat: 'directory' }, routes, redirects: [], ...overrides });
const rejects = (value, pattern) => assert.throws(() => buildDocumentRouteSet(value), { name: 'TypeError', message: pattern });

test('keeps primary and UK fallback target metadata separate', () => {
  const fallback = route({ id: 'uk/guide/one', url: 'https://site.test/docs/uk/guide/one/', pathname: '/docs/uk/guide/one/', isFallback: true, locale: 'uk', lang: 'uk' });
  const ukrainian = route({ id: 'uk/guide/two', url: 'https://site.test/docs/uk/guide/two/', pathname: '/docs/uk/guide/two/', source: 'uk/guide/two.md', locale: 'uk', lang: 'uk' });
  const result = buildDocumentRouteSet(manifest([route(), fallback, ukrainian]));
  assert.deepEqual([...result.targetPaths], ['/docs/guide/one/', '/docs/uk/guide/one/', '/docs/uk/guide/two/']);
  assert.equal(result.primaryBySource.get('guide/one.md').url, 'https://site.test/docs/guide/one/');
  assert.equal(result.primaryBySource.get('uk/guide/two.md').locale, 'uk');
  assert.deepEqual(result.fallbacks, [fallback]);
});

test('keeps a percent-serialized Unicode dotted pathname and accepts root base paths', () => {
  const unicode = route({ id: 'lab/naïve-1.2', url: 'https://site.test/docs/lab/na%C3%AFve-1.2/', pathname: '/docs/lab/na%C3%AFve-1.2/', source: 'lab/naïve-source.md' });
  assert.equal(buildDocumentRouteSet(manifest([unicode])).targetPaths.has(unicode.pathname), true);
  assert.equal(buildDocumentRouteSet(manifest([route({ url: 'https://site.test/elsewhere/', pathname: '/elsewhere/' })], { config: { ...manifest().config, base: '/' } })).targetPaths.has('/elsewhere/'), true);
});

test('rejects source hash conflicts and absent or ambiguous primaries', () => {
  rejects(manifest([route(), route({ id: 'alias', url: 'https://site.test/docs/alias/', pathname: '/docs/alias/', sourceSha256: hash('b') })]), /inconsistent sourceSha256/);
  rejects(manifest([route({ isFallback: true })]), /exactly one primary/);
  rejects(manifest([route(), route({ id: 'alias', url: 'https://site.test/docs/alias/', pathname: '/docs/alias/' })]), /exactly one primary/);
});

test('rejects duplicate paths and non-serialized or cross-origin route URLs', () => {
  rejects(manifest([route(), route({ id: 'two' })]), /duplicate route.pathname/);
  rejects(manifest([route({ pathname: '/docs/%E2%9C%93/', url: 'https://site.test/docs/✓/' })]), /serialized URL/);
  rejects(manifest([route({ url: 'https://other.test/docs/guide/one/' })]), /same-origin/);
  rejects(manifest([route({ pathname: '/docs/../escape/', url: 'https://site.test/escape/' })]), /serialized pathname/);
  rejects(manifest([route({ url: 'https://site.test/docs/other/' })]), /matching route.pathname/);
  rejects(manifest([route({ url: 'https://site.test/docs/guide/one/?q=1' })]), /same-origin serialized URL/);
  rejects(manifest([route({ url: 'https://site.test/elsewhere/', pathname: '/elsewhere/' })]), /lie under config.base/);
});

test('rejects unsupported schema/config/source metadata and leaves redirects out of targets', () => {
  rejects(manifest([route()], { schemaVersion: 2 }), /schema or scope/);
  rejects(manifest([route()], { scope: 'whole-site-routes' }), /schema or scope/);
  rejects(manifest([route()], { config: { ...manifest().config, buildFormat: 'file' } }), /buildFormat/);
  rejects(manifest([route()], { config: { ...manifest().config, base: '/✓/' } }), /serialized root-relative/);
  rejects(manifest([route()], { config: { ...manifest().config, site: 'https://user@site.test/' } }), /credentials/);
  rejects(manifest([route()], { config: { ...manifest().config, site: 'https://site.test/?q=1' } }), /query/);
  rejects(manifest([route({ source: '../outside.md' })]), /safe relative/);
  rejects(manifest([route({ source: 'bad\u0000name.md' })]), /safe relative/);
  rejects(manifest([route({ source: 'bad\u001fname.md' })]), /safe relative/);
  rejects(manifest([route({ sourceSha256: 'A'.repeat(64) })]), /SHA-256/);
  rejects(manifest([route({ sourceSha256: 1 })]), /sourceSha256/);
  rejects(manifest([route({ isFallback: 'false' })]), /isFallback/);
  rejects(manifest([route({ locale: 1 })]), /locale/);
  rejects(manifest([route()], { redirects: [{ source: '/old/', target: '/new/', status: 302.5 }] }), /3xx integer/);
  rejects(manifest([route()], { redirects: [{ source: '/old/', target: '/new/', status: Number.NaN }] }), /3xx integer/);
  rejects(manifest([route()], { redirects: [{ source: '/old/', target: '/new/', status: 200 }] }), /3xx integer/);
  rejects(manifest([route()], { redirects: [{ source: '/old/', target: '../new/', status: 301 }] }), /serialized pathname/);
  rejects(manifest([route()], { redirects: [{ source: '/old/[...slug]/', target: '/docs/guide/one/', status: 301 }] }), /unsupported/);
  rejects(manifest([route()], { redirects: [{ source: '/old/', target: '/docs/guide/one/', status: 301 }, { source: '/old/', target: '/docs/other/', status: 302 }] }), /duplicate/);
  const result = buildDocumentRouteSet(manifest([route()], { redirects: [{ source: '/old/', target: '/docs/guide/one/', status: 301 }] }));
  assert.equal(result.targetPaths.has('/old/'), false);
  assert.deepEqual(result.redirects, [{ source: '/old/', target: '/docs/guide/one/', status: 301 }]);
});
