import assert from 'node:assert/strict';
import test from 'node:test';
import { proveCustomAstroPages } from './custom-astro-page-proof.mjs';

const hash = (digit = 'a') => digit.repeat(64);
const doc = (overrides = {}) => ({ id: 'guide/one', url: 'https://site.test/docs/guide/one/', pathname: '/docs/guide/one/', source: 'guide/one.md', sourceSha256: hash(), isFallback: false, locale: null, lang: null, ...overrides });
const manifest = (routes = [doc()], overrides = {}) => ({ schemaVersion: 1, scope: 'starlight-document-routes', config: { site: 'https://site.test/contained/', base: '/docs/', trailingSlash: 'always', buildFormat: 'directory' }, routes, redirects: [], ...overrides });
const html = (canonical, extra = '') => `<!doctype html><html><head><link rel="canonical" href="${canonical}" />${extra}</head></html>`;
const rejects = (fn, pattern) => assert.throws(fn, { name: 'TypeError', message: pattern });

test('proves EN and UK custom pages from rendered canonicals, not document fallbacks', () => {
  const fallback = doc({ id: 'uk/guide/one', url: 'https://site.test/docs/uk/guide/one/', pathname: '/docs/uk/guide/one/', isFallback: true, locale: 'uk', lang: 'uk' });
  const result = proveCustomAstroPages(manifest([doc(), fallback]), [
    { html: html('https://site.test/docs/', '<link rel="shortcut icon" href="/favicon.svg" />'), source: 'src/pages/index.astro' },
    { html: html('https://site.test/docs/uk/'), source: 'src/pages/uk/index.astro' },
  ]);
  assert.deepEqual([...result.targetPaths], ['/docs/', '/docs/uk/']);
  assert.equal(result.pages[0].source, 'src/pages/index.astro');
  assert.equal(result.pages[1].pathname, '/docs/uk/');
  assert.equal(result.targetPaths.has('/docs/guide/one/'), false);
  assert.equal(result.targetPaths.has('/docs/uk/guide/one/'), false);
});

test('derives the route from the canonical and ignores claimed pathnames or filenames', () => {
  const sneaky = proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/uk/'), pathname: '/docs/', source: 'src/pages/index.astro' }]);
  assert.deepEqual([...sneaky.targetPaths], ['/docs/uk/']);
  rejects(() => proveCustomAstroPages(manifest(), [{ source: 'src/pages/index.astro' }]), /rendered HTML must be non-empty/);
  rejects(() => proveCustomAstroPages(manifest(), [{ source: 'src/pages/index.astro', html: '<html></html>' }]), /exactly one canonical/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/'), source: 'src/content/docs/index.md' }]), /custom Astro page/);
});

test('accepts root-base EN/UK homepages and href-first canonical tags', () => {
  const root = manifest([doc({ url: 'https://site.test/guide/one/', pathname: '/guide/one/' })], { config: { site: 'https://site.test/', base: '/', trailingSlash: 'always', buildFormat: 'directory' } });
  const result = proveCustomAstroPages(root, [
    { html: '<link href="https://site.test/" rel="canonical">' },
    { html: html('https://site.test/uk/') },
  ]);
  assert.deepEqual([...result.targetPaths], ['/', '/uk/']);
});

test('rejects missing, multiple, colliding, or non-serialized canonicals', () => {
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://other.test/docs/') }]), /same-origin/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: `${html('https://site.test/docs/')}${html('https://site.test/docs/uk/')}` }]), /exactly one canonical/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/?q=1') }]), /query/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: '<link href="https://site.test/docs/" rel="canonical"><link rel="canonical">' }]), /missing href/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/guide/one/') }]), /collides with document/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/') }, { html: html('https://site.test/docs/') }]), /duplicate custom/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/\u2713/') }]), /serialized URL/);
});

test('rejects unsupported config, pages outside base, and treats redirects as non-targets', () => {
  rejects(() => proveCustomAstroPages(manifest([doc()], { schemaVersion: 2 }), [{ html: html('https://site.test/docs/') }]), /schema or scope/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/') }]), /lie under config.base/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/uk') }]), /trailingSlash always/);
  rejects(() => proveCustomAstroPages(manifest(), [{ html: html('https://site.test/docs/'), source: '../pages/index.astro' }]), /safe relative/);
  const redirected = proveCustomAstroPages(manifest([doc()], { redirects: [{ source: '/docs/old/', target: '/docs/guide/one/', status: 301 }] }), [{ html: html('https://site.test/docs/') }]);
  assert.equal(redirected.targetPaths.has('/docs/old/'), false);
  assert.equal(redirected.targetPaths.has('/docs/'), true);
});
