import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

// Regression test for issue #2266: custom home header overflow at ~1027px.
// Production QA measured document.scrollWidth 1268 vs clientWidth 1027, with
// `.kd-right` / `.kd-search` past the viewport and the search label clipped.

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const header = readFileSync(resolve(repoRoot, 'src/components/Header.astro'), 'utf8');

function mediaBlock(source: string, query: string): string {
  const needle = `@media (${query})`;
  const start = source.indexOf(needle);
  expect(start, `missing ${needle}`).toBeGreaterThan(-1);
  const open = source.indexOf('{', start);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    if (source[i] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(open, i + 1);
    }
  }
  throw new Error(`unclosed ${needle}`);
}

describe('home header overflow (#2266)', () => {
  it('marks the standalone homepage header so collapse can be scoped', () => {
    expect(header).toContain("'kd-header-standalone': standalone");
  });

  it('collapses the standalone home nav at 80rem (covers 1027px / 1268px)', () => {
    const rem = 80;
    expect(rem * 16).toBeGreaterThan(1027);
    expect(rem * 16).toBeGreaterThanOrEqual(1268);

    const block = mediaBlock(header, 'max-width: 80rem');
    expect(block).toContain('.kd-header-standalone .kd-nav');
    expect(block).toMatch(/\.kd-header-standalone \.kd-nav[\s\S]*display:\s*none/);
    expect(block).toContain('.kd-header-standalone .kd-menu-toggle');
  });

  it('keeps Starlight content pages on the 50rem collapse', () => {
    const block = mediaBlock(header, 'max-width: 50rem');
    expect(block).toMatch(/\.kd-nav[^{]*\{|display:\s*none/);
    expect(block).toContain('.kd-nav');
    expect(block).not.toContain('.kd-header-standalone');
  });

  it('lets standalone search size to its label instead of clipping to Sear…', () => {
    expect(header).toMatch(
      /\.kd-header-standalone \.kd-search :global\(button\)\s*\{[^}]*max-width:\s*none[^}]*width:\s*auto/,
    );
    expect(header).toMatch(/\.kd-header-standalone \.kd-search\s*\{[^}]*min-width:\s*0/);
    expect(header).toMatch(/\.kd-header-standalone \.kd-search :global\(kbd\)\s*\{[^}]*display:\s*none/);
  });

  it('keeps the JS menu closer in sync with the CSS collapse queries', () => {
    expect(header).toContain("'(max-width: 80rem)'");
    expect(header).toContain("'(max-width: 50rem)'");
    expect(header).toMatch(/classList\.contains\('kd-header-standalone'\)/);
    expect(header).not.toMatch(/innerWidth\s*>\s*800/);
  });
});
