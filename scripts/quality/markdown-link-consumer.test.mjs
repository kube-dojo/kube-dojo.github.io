import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import test from 'node:test';
import assert from 'node:assert/strict';
import { consumeMarkdownLinks } from './markdown-link-consumer.mjs';

test('consumeMarkdownLinks handles various fixtures', (t) => {
  const tmpdir = fs.mkdtempSync(path.join(os.tmpdir(), 'md-links-test-'));
  
  const manifest = {
    schemaVersion: 1,
    scope: 'starlight-document-routes',
    config: {
      site: 'https://site.test',
      base: '/',
      trailingSlash: 'always',
      buildFormat: 'directory'
    },
    redirects: [],
    routes: [
      {
        id: 'dir1/module-a.md',
        url: 'https://site.test/dir1/module-a/',
        pathname: '/dir1/module-a/',
        source: 'src/content/docs/dir1/module-a.md',
        sourceSha256: 'a'.repeat(64),
        isFallback: false,
        locale: 'en',
        lang: 'en'
      },
      {
        id: 'dir1/module-b.md',
        url: 'https://site.test/dir1/module-b/',
        pathname: '/dir1/module-b/',
        source: 'src/content/docs/dir1/module-b.md',
        sourceSha256: 'b'.repeat(64),
        isFallback: false,
        locale: 'en',
        lang: 'en'
      },
      {
        id: 'index.md',
        url: 'https://site.test/',
        pathname: '/',
        source: 'src/content/docs/index.md',
        sourceSha256: 'c'.repeat(64),
        isFallback: false,
        locale: 'en',
        lang: 'en'
      },
      {
        id: 'uk/dir1/module-b.md',
        url: 'https://site.test/uk/dir1/module-b/',
        pathname: '/uk/dir1/module-b/',
        source: 'src/content/docs/dir1/module-b.md',
        sourceSha256: 'b'.repeat(64),
        isFallback: true,
        locale: 'uk',
        lang: 'uk'
      },
      {
        id: 'uk/module-c.md',
        url: 'https://site.test/uk/module-c/',
        pathname: '/uk/module-c/',
        source: 'src/content/docs/uk/module-c.md',
        sourceSha256: 'c'.repeat(64),
        isFallback: false,
        locale: 'uk',
        lang: 'uk'
      }
    ]
  };

  const mdContent = `
[broken sibling](./module-b/)
[correct sibling](../module-b/)
[UK relative](../../uk/dir1/module-b/)
[index](../../)
[explicit slug](/dir1/module-b/)
[root-relative](/dir1/module-b/)
[fragment](#section)
[unsupported form](ftp://invalid)
\`\`\`
[fenced link](/should/not/exist)
\`\`\`
  `;
  
  fs.mkdirSync(path.join(tmpdir, 'dir1'), { recursive: true });
  fs.writeFileSync(path.join(tmpdir, 'dir1/module-a.md'), mdContent);
  fs.writeFileSync(path.join(tmpdir, 'dir1/module-b.md'), 'b content');
  fs.writeFileSync(path.join(tmpdir, 'index.md'), 'index content');
  
  fs.mkdirSync(path.join(tmpdir, 'uk/dir1'), { recursive: true });
  fs.writeFileSync(path.join(tmpdir, 'uk/dir1/module-b.md'), 'uk b content');
  
  fs.mkdirSync(path.join(tmpdir, 'uk'), { recursive: true });
  fs.writeFileSync(path.join(tmpdir, 'uk/module-c.md'), '[UK Source internal](../../dir1/module-a/)');
  
  const report = consumeMarkdownLinks(manifest, tmpdir);
  fs.rmSync(tmpdir, { recursive: true, force: true });
  
  const findReport = (text) => report.find(r => r.href === text || mdContent.split('\n')[r.line - 1].includes(text));

  const brokenSibling = findReport('broken sibling');
  assert.equal(brokenSibling.disposition, 'missing', 'Wrong sibling false-pass reported as missing');
  assert.equal(brokenSibling.target, 'https://site.test/dir1/module-a/module-b/');

  const correctSibling = findReport('correct sibling');
  assert.equal(correctSibling.disposition, 'present');
  assert.equal(correctSibling.target, 'https://site.test/dir1/module-b/');

  const ukRelative = findReport('UK relative');
  assert.equal(ukRelative.disposition, 'present-fallback');
  assert.equal(ukRelative.target, 'https://site.test/uk/dir1/module-b/');

  const indexPage = findReport('index');
  assert.equal(indexPage.disposition, 'present');
  assert.equal(indexPage.target, 'https://site.test/');

  const explicitSlug = findReport('explicit slug');
  assert.equal(explicitSlug.disposition, 'present');
  assert.equal(explicitSlug.target, 'https://site.test/dir1/module-b/');

  const rootRelative = findReport('root-relative');
  assert.equal(rootRelative.disposition, 'present');
  assert.equal(rootRelative.target, 'https://site.test/dir1/module-b/');

  const fragment = findReport('fragment');
  assert.equal(fragment.disposition, 'fragment-only');
  assert.equal(fragment.target, 'https://site.test/dir1/module-a/#section');

  const unsupported = findReport('unsupported form');
  assert.equal(unsupported.disposition, 'unsupported');
  assert.equal(unsupported.target, null);

  const fencedLink = report.find(r => r.href === '/should/not/exist');
  assert.ok(!fencedLink, 'Fenced link should not appear in the report');

  const ukSourceInternal = report.find(r => r.source === 'src/content/docs/uk/module-c.md' && r.href === '../../dir1/module-a/');
  assert.ok(ukSourceInternal, 'UK Source link not found');
  assert.equal(ukSourceInternal.disposition, 'present');
  assert.equal(ukSourceInternal.target, 'https://site.test/dir1/module-a/');
});
