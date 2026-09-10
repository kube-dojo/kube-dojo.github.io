import { describe, expect, it } from 'vitest';
import { isStatusPage, summarizeFlags } from '../src/scripts/public-status';

describe('public status scope', () => {
  it('includes English modules, chapters and reference pages', () => {
    for (const id of ['k8s/cka/module-1.1-intro', 'ai-history/ch-05-the-neural-abstraction', 'linux/reference']) {
      expect(isStatusPage(`src/content/docs/${id}.md`)).toBe(true);
    }
  });
  it('excludes Ukrainian sources, index pages and shared pages', () => {
    for (const id of ['uk/k8s/cka/module-1.1-intro', 'k8s/cka/index', 'index', 'status', 'glossary']) {
      expect(isStatusPage(`src/content/docs/${id}.mdx`)).toBe(false);
    }
  });
  it('uses the source filename when Astro collapses an index ID', () => {
    const entry = { id: 'ai-history', filePath: 'src/content/docs/ai-history/index.md' };
    expect(isStatusPage(entry.filePath)).toBe(false);
  });
  it('refuses to publish a denominator with unknown source identity', () => {
    expect(() => isStatusPage(undefined)).toThrow('known docs source path');
    expect(() => isStatusPage('elsewhere/ai/history.md')).toThrow('known docs source path');
  });
});

describe('queue flags are not acceptance', () => {
  it('counts overlap once and preserves both category counts', () => {
    expect(summarizeFlags([
      {}, { revisionPending: true }, { qaPending: true }, { revisionPending: true, qaPending: true },
    ])).toEqual({ total: 4, rework: 2, review: 2, flagged: 3, unflagged: 1 });
  });
  it('makes no acceptance claim from missing, false or malformed flags', () => {
    expect(summarizeFlags([{}, { revisionPending: false }, { qaPending: 'true' }]))
      .toEqual({ total: 3, rework: 0, review: 0, flagged: 0, unflagged: 3 });
  });
  it('does not consume unbound verification flags or stale receipts', () => {
    const entries = [{ revisionPending: false, citations_verified: true, receipt: { revision: 'old' } }];
    expect(summarizeFlags(entries)).toEqual(summarizeFlags([{}]));
    expect(summarizeFlags(entries)).not.toHaveProperty('accepted');
  });
  it('keeps an empty scope at zero without a completion percentage', () => {
    expect(summarizeFlags([])).toEqual({ total: 0, rework: 0, review: 0, flagged: 0, unflagged: 0 });
  });
});
