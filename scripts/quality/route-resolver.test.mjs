import assert from 'node:assert/strict';
import test from 'node:test';
import { resolveRoute, UnsupportedRoute } from './route-resolver.mjs';

const ORIGIN = 'https://site.test';
const resolve = (href, source = '/source/page/', routes = ['/source/page/']) => resolveRoute(href, source, ORIGIN, routes);

test('manifest routes are explicit: EN, UK, index, slug, dotted file, redirect alias', () => {
  const cases = [
    ['/en/page/', '../../uk/page/', ['/uk/page/'], '/uk/page/', true],
    ['/index/', './', ['/index/'], '/index/', true],
    ['/source/', '../custom-slug/', ['/custom-slug/'], '/custom-slug/', true],
    ['/docs/source/', './module-1.1-dotted.md', ['/docs/source/module-1.1-dotted/'], '/docs/source/module-1.1-dotted.md', false],
    ['/canonical/', '/old-route/', ['/old-route/'], '/old-route/', true],
  ];
  for (const [source, href, routes, path, exists] of cases) {
    const result = resolveRoute(href, source, ORIGIN, routes);
    assert.equal(result.url, ORIGIN + path);
    assert.equal(result.kind, 'internal');
    assert.equal(result.routeExists, exists);
  }
});

test('native URL resolves one root, parent, nested, and slash-policy target', () => {
  const cases = [
    ['/section/page/', '../correct/', '/section/correct/'],
    ['/section/page/', './nestedbad/', '/section/page/nestedbad/'],
    ['/section/page', './nested/', '/section/nested/'],
    ['/section/page/', '/root/', '/root/'],
  ];
  for (const [source, href, path] of cases) {
    const result = resolve(href, source, [path]);
    assert.equal(result.url, ORIGIN + path);
    assert.equal(result.routeExists, true);
  }
});

test('relative sibling resolution does not invent a parent route', () => {
  for (const locale of ['en', 'uk']) {
    const source = `/${locale}/section/page/`;
    const routes = [`/${locale}/section/sibling/`];
    assert.equal(resolveRoute('./sibling/', source, ORIGIN, routes).routeExists, false);
    assert.equal(resolveRoute('../sibling/', source, ORIGIN, routes).routeExists, true);
  }
});

test('same-origin, external HTTP, and mailto remain separate', () => {
  const same = resolve('//site.test/known/?q=1#missing-anchor', '/source/', ['/known/']);
  assert.deepEqual(same, { url: 'https://site.test/known/?q=1#missing-anchor', kind: 'internal', path: '/known/', routeExists: true });
  assert.equal(resolve('https://other.test/known/').kind, 'external-http');
  assert.equal(resolve('mailto:ops@example.test').kind, 'mailto');
  assert.equal(resolve('mailto:ops@example.test').routeExists, null);
});

test('query and fragment references clear or preserve state without anchor checks', () => {
  const source = 'https://site.test/source/page/?old=1#old';
  assert.equal(resolveRoute('?', source, ORIGIN, ['/source/page/']).url, 'https://site.test/source/page/?');
  const fragment = resolveRoute('#', source, ORIGIN, ['/source/page/']);
  assert.equal(fragment.url, 'https://site.test/source/page/?old=1#');
  assert.equal(fragment.routeExists, true);
});

test('base path comes from the actual canonical URL', () => {
  const result = resolveRoute('../next/?q=1#part', 'https://site.test/kube-dojo/en/page/', ORIGIN, ['/kube-dojo/en/next/']);
  assert.equal(result.url, 'https://site.test/kube-dojo/en/next/?q=1#part');
  assert.equal(result.routeExists, true);
});

test('former Python divergences follow native WHATWG URL output', () => {
  const cases = [
    ['/✓/', 'https://site.test/%E2%9C%93/'],
    ['./a//b/', 'https://site.test/source/page/a//b/'],
    ['https://%73ite.test/known/', 'https://site.test/known/'],
    ['..\\next/', 'https://site.test/source/next/'],
    ['/x/%2e%2e/y', 'https://site.test/y'],
    ['/x/%ZZ', 'https://site.test/x/%ZZ'],
  ];
  for (const [href, expected] of cases) {
    const path = new URL(expected).pathname;
    const result = resolve(href, '/source/page/', [path]);
    assert.equal(result.url, expected);
    assert.equal(result.routeExists, true);
  }
});

test('unsupported schemes fail closed', () => {
  for (const href of ['javascript:alert(1)', 'ftp://other.test/file']) {
    assert.throws(() => resolve(href), UnsupportedRoute);
  }
});

test('explicit inputs and manifest paths must be canonical', () => {
  for (const path of ['/a/../b/', '/a/\u0000b/', '/a/\tb/', '/✓/']) {
    assert.throws(() => resolveRoute('/b/', '/source/', ORIGIN, [path]), { name: 'TypeError', message: /serialized pathname/ });
  }
  assert.throws(() => resolveRoute('/x/', 'relative', ORIGIN, ['/x/']), { name: 'TypeError', message: /absolute URL/ });
  assert.throws(() => resolveRoute('/x/', '/x/', `${ORIGIN}/base/`, ['/x/']), { name: 'TypeError', message: /HTTP\(S\) origin/ });
  assert.throws(() => resolveRoute('/x/', '/x/', ORIGIN, '/x/'), { name: 'TypeError', message: /non-string iterable/ });
});

test('redirect source resolves to the final canonical pathname', () => {
  const redirects = [{ source: '/old/', target: '/mid/' }, { source: '/mid/', target: '/final/' }];
  const chained = resolveRoute('/old/?q=1#part', '/source/', ORIGIN, ['/final/'], redirects);
  assert.deepEqual(chained, { url: 'https://site.test/final/?q=1#part', kind: 'internal', path: '/final/', routeExists: true });
  const relative = resolveRoute('../old/', '/section/page/', ORIGIN, ['/new/'], [{ source: '/section/old/', target: '/new/' }]);
  assert.equal(relative.path, '/new/');
  assert.equal(relative.routeExists, true);
  const missing = resolveRoute('/old/', '/source/', ORIGIN, ['/elsewhere/'], [{ source: '/old/', target: '/gone/' }]);
  assert.equal(missing.path, '/gone/');
  assert.equal(missing.routeExists, false);
});

test('redirect chains fail closed and do not invent filename-derived URLs', () => {
  assert.equal(resolveRoute('/docs/old-name/', '/source/', ORIGIN, ['/docs/new-name/']).path, '/docs/old-name/');
  assert.equal(resolveRoute('/docs/old-name/', '/source/', ORIGIN, ['/docs/new-name/']).routeExists, false);
  assert.equal(resolveRoute('/old', '/source/', ORIGIN, ['/new/'], [{ source: '/old/', target: '/new/' }]).path, '/old');
  assert.throws(() => resolveRoute('/a/', '/source/', ORIGIN, ['/a/'], [{ source: '/a/', target: '/b/' }, { source: '/b/', target: '/a/' }]), UnsupportedRoute);
  assert.throws(() => resolveRoute('/a/', '/source/', ORIGIN, ['/b/'], [{ source: '/a/', target: '../b/' }]), UnsupportedRoute);
  assert.throws(() => resolveRoute('/a/', '/source/', ORIGIN, ['/b/'], [{ source: '/old/[...slug]/', target: '/b/' }]), UnsupportedRoute);
  assert.throws(() => resolveRoute('/a/', '/source/', ORIGIN, ['/b/'], [{ source: '/a/', target: '/b/' }, { source: '/a/', target: '/c/' }]), UnsupportedRoute);
});
