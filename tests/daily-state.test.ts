import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  CKA_MODULE_5_1_PACK,
  CKA_MODULE_5_1_UNITS,
  DAILY_FEATURE_NAME,
  DAILY_MAX_UNIT_WORDS,
  PARENT_LAB_ID,
  PARENT_LAB_URL,
  countUnitWords,
} from '../src/data/daily/cka-module-5.1';
import {
  DAILY_STORAGE_KEY,
  REVIEW_INTERVALS_DAYS,
  SESSION_BUDGET_MINUTES,
  addDays,
  applyUnitSession,
  createEmptyState,
  daysBetween,
  formatLocalDate,
  getDailyRecommendation,
  isValidCalendarDate,
  parseDailyState,
  readDailyState,
  recordUnitSession,
  resetDailyState,
  type DailyStorage,
} from '../src/scripts/daily-state';
import { mountDailyPlayer } from '../src/scripts/daily-player';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const validUnitIds = new Set(CKA_MODULE_5_1_UNITS.map((u) => u.id));

function memoryStorage(initial: string | null = null, opts: { failRead?: boolean; failWrite?: boolean } = {}) {
  let raw = initial;
  const writes: string[] = [];
  const storage: DailyStorage = () => ({
    getItem(key: string) {
      expect(key).toBe(DAILY_STORAGE_KEY);
      if (opts.failRead) throw new Error('SecurityError');
      return raw;
    },
    setItem(key: string, value: string) {
      expect(key).toBe(DAILY_STORAGE_KEY);
      if (opts.failWrite) throw new Error('QuotaExceededError');
      writes.push(value);
      raw = value;
    },
    removeItem(key: string) {
      expect(key).toBe(DAILY_STORAGE_KEY);
      if (opts.failWrite) throw new Error('QuotaExceededError');
      raw = null;
    },
  });
  return { storage, writes, raw: () => raw };
}

describe('calendar date helpers', () => {
  it('validates real calendar dates and rejects impossible ones', () => {
    expect(isValidCalendarDate('2026-11-28')).toBe(true);
    expect(isValidCalendarDate('2024-02-29')).toBe(true);
    expect(isValidCalendarDate('2026-02-29')).toBe(false);
    expect(isValidCalendarDate('2026-02-30')).toBe(false);
    expect(isValidCalendarDate('2026-13-01')).toBe(false);
    expect(isValidCalendarDate('not-a-date')).toBe(false);
  });

  it('adds days cleanly across month and year boundaries without DST drift', () => {
    expect(addDays('2026-11-30', 1)).toBe('2026-12-01');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(addDays('2026-03-07', 3)).toBe('2026-03-10');
    expect(daysBetween('2026-11-28', '2026-12-01')).toBe(3);
    expect(formatLocalDate(new Date(2026, 10, 28, 23, 30))).toBe('2026-11-28');
  });
});

describe('Daily Dojo state transitions (AC-02)', () => {
  it('schedules tomorrow on first completion, advances on correct reviews, and resets to tomorrow on miss', () => {
    const unitId = CKA_MODULE_5_1_UNITS[0].id;
    let state = createEmptyState();

    // First completion on day 1 -> interval index 0 (+1 day)
    const r1 = applyUnitSession(state, unitId, 'correct', '2026-11-28', validUnitIds);
    expect(r1.ok).toBe(true);
    if (!r1.ok) throw new Error('expected ok');
    state = r1.state;
    expect(state.units[unitId]).toEqual({
      completedAt: '2026-11-28',
      lastReviewedAt: '2026-11-28',
      nextReviewAt: '2026-11-29',
      intervalIndex: 0,
      reviewCount: 1,
      lastOutcome: 'correct',
    });

    // Review on day 2 (correct) -> advances to index 1 (+3 days)
    const r2 = applyUnitSession(state, unitId, 'correct', '2026-11-29', validUnitIds);
    expect(r2.ok).toBe(true);
    if (!r2.ok) throw new Error('expected ok');
    state = r2.state;
    expect(state.units[unitId].intervalIndex).toBe(1);
    expect(state.units[unitId].nextReviewAt).toBe('2026-12-02');
    expect(state.units[unitId].reviewCount).toBe(2);

    // Review on day 5 (correct) -> advances to index 2 (+7 days)
    const r3 = applyUnitSession(state, unitId, 'correct', '2026-12-02', validUnitIds);
    expect(r3.ok).toBe(true);
    if (!r3.ok) throw new Error('expected ok');
    state = r3.state;
    expect(state.units[unitId].intervalIndex).toBe(2);
    expect(state.units[unitId].nextReviewAt).toBe('2026-12-09');

    // Review on day 12 (missed) -> resets to index 0 (due tomorrow)
    const r4 = applyUnitSession(state, unitId, 'missed', '2026-12-09', validUnitIds);
    expect(r4.ok).toBe(true);
    if (!r4.ok) throw new Error('expected ok');
    state = r4.state;
    expect(state.units[unitId].intervalIndex).toBe(0);
    expect(state.units[unitId].nextReviewAt).toBe('2026-12-10');
    expect(state.units[unitId].lastOutcome).toBe('missed');
    expect(state.units[unitId].completedAt).toBe('2026-11-28');

    // Caps interval index at the highest step (30 days)
    let capped = state;
    let day = '2026-12-10';
    for (let i = 0; i < REVIEW_INTERVALS_DAYS.length + 3; i += 1) {
      const step = applyUnitSession(capped, unitId, 'correct', day, validUnitIds);
      if (!step.ok) throw new Error('expected ok');
      capped = step.state;
      day = capped.units[unitId].nextReviewAt;
    }
    expect(capped.units[unitId].intervalIndex).toBe(REVIEW_INTERVALS_DAYS.length - 1);
  });

  it('tracks a gentle streak across same-day, consecutive-day, multi-day gap, and backward clock', () => {
    const u1 = CKA_MODULE_5_1_UNITS[0].id;
    const u2 = CKA_MODULE_5_1_UNITS[1].id;
    let state = createEmptyState();

    // Day 1
    let res = applyUnitSession(state, u1, 'correct', '2026-11-28', validUnitIds);
    if (!res.ok) throw new Error('expected ok');
    state = res.state;
    expect(state.streak).toEqual({ current: 1, best: 1, lastActiveDate: '2026-11-28', resumedAfterGap: false });

    // Same day second unit does not double-count streak
    res = applyUnitSession(state, u2, 'correct', '2026-11-28', validUnitIds);
    if (!res.ok) throw new Error('expected ok');
    state = res.state;
    expect(state.streak.current).toBe(1);

    // Next day increments streak and best
    res = applyUnitSession(state, u1, 'correct', '2026-11-29', validUnitIds);
    if (!res.ok) throw new Error('expected ok');
    state = res.state;
    expect(state.streak).toEqual({ current: 2, best: 2, lastActiveDate: '2026-11-29', resumedAfterGap: false });

    // 4-day gap: gentle resume resets current to 1, preserves best=2 and completed units
    res = applyUnitSession(state, u2, 'correct', '2026-12-03', validUnitIds);
    if (!res.ok) throw new Error('expected ok');
    state = res.state;
    expect(state.streak).toEqual({ current: 1, best: 2, lastActiveDate: '2026-12-03', resumedAfterGap: true });
    expect(Object.keys(state.units)).toHaveLength(2);

    // Backward device clock does not corrupt streak
    res = applyUnitSession(state, u1, 'correct', '2026-12-01', validUnitIds);
    if (!res.ok) throw new Error('expected ok');
    state = res.state;
    expect(state.streak.current).toBe(1);
    expect(state.streak.lastActiveDate).toBe('2026-12-03');
  });

  it('offers the review-or-new choice when a due review plus next new unit exceeds 5 minutes', () => {
    const u1 = CKA_MODULE_5_1_UNITS[0].id;
    const base = createEmptyState();
    const afterDay1 = applyUnitSession(base, u1, 'correct', '2026-11-28', validUnitIds);
    if (!afterDay1.ok) throw new Error('expected ok');

    // Same day: no due review yet -> mode is 'new'
    const sameDay = getDailyRecommendation(CKA_MODULE_5_1_UNITS, afterDay1.state, '2026-11-28', SESSION_BUDGET_MINUTES);
    expect(sameDay.mode).toBe('new');
    expect(sameDay.dueUnits).toHaveLength(0);
    expect(sameDay.nextNewUnit?.id).toBe(CKA_MODULE_5_1_UNITS[1].id);

    // Next day: Unit 1 is due (2 min) + Unit 2 is new (4 min) = 6 min > 5 min -> mode is 'choice'
    const nextDay = getDailyRecommendation(CKA_MODULE_5_1_UNITS, afterDay1.state, '2026-11-29', SESSION_BUDGET_MINUTES);
    expect(nextDay.mode).toBe('choice');
    expect(nextDay.dueUnits.map((u) => u.id)).toEqual([u1]);
    expect(nextDay.nextNewUnit?.id).toBe(CKA_MODULE_5_1_UNITS[1].id);
    expect(nextDay.combinedMinutes).toBe(6);

    // With a higher budget (6 min), both fit -> mode is 'both'
    const wider = getDailyRecommendation(CKA_MODULE_5_1_UNITS, afterDay1.state, '2026-11-29', 6);
    expect(wider.mode).toBe('both');

    // All 10 completed on day 1 -> caught-up on day 1, review-only on day 2
    let allDone = createEmptyState();
    for (const unit of CKA_MODULE_5_1_UNITS) {
      const r = applyUnitSession(allDone, unit.id, 'correct', '2026-11-28', validUnitIds);
      if (!r.ok) throw new Error('expected ok');
      allDone = r.state;
    }
    const caughtUp = getDailyRecommendation(CKA_MODULE_5_1_UNITS, allDone, '2026-11-28');
    expect(caughtUp.mode).toBe('caught-up');
    expect(caughtUp.nextScheduledDate).toBe('2026-11-29');

    const reviewOnly = getDailyRecommendation(CKA_MODULE_5_1_UNITS, allDone, '2026-11-29');
    expect(reviewOnly.mode).toBe('review');
    expect(reviewOnly.dueUnits).toHaveLength(10);
    expect(reviewOnly.nextNewUnit).toBeNull();
  });

  it('fails closed on corrupt storage, unavailable storage, write failure, and unknown units without clobbering', () => {
    const corrupt = memoryStorage('{"version":99}');
    const readCorrupt = readDailyState(corrupt.storage);
    expect(readCorrupt.ok).toBe(false);
    if (readCorrupt.ok) throw new Error('expected failure');
    expect(readCorrupt.reason).toBe('invalid');
    expect(corrupt.writes).toHaveLength(0);

    const recordOnCorrupt = recordUnitSession(
      corrupt.storage,
      CKA_MODULE_5_1_UNITS[0].id,
      'correct',
      '2026-11-28',
      validUnitIds,
    );
    expect(recordOnCorrupt).toMatchObject({ ok: false, reason: 'invalid' });
    expect(corrupt.raw()).toBe('{"version":99}');

    expect(parseDailyState('not json')).toMatchObject({ ok: false, reason: 'invalid' });
    expect(
      parseDailyState(
        JSON.stringify({
          version: 1,
          streak: { current: 2, best: 1, lastActiveDate: '2026-11-28', resumedAfterGap: false },
          units: {},
        }),
      ),
    ).toMatchObject({ ok: false, reason: 'invalid' });

    const unavail = memoryStorage(null, { failRead: true });
    expect(readDailyState(unavail.storage)).toMatchObject({ ok: false, reason: 'unavailable' });

    const failWrite = memoryStorage(null, { failWrite: true });
    expect(
      recordUnitSession(failWrite.storage, CKA_MODULE_5_1_UNITS[0].id, 'correct', '2026-11-28', validUnitIds),
    ).toMatchObject({ ok: false, reason: 'write' });

    const clean = memoryStorage(null);
    expect(recordUnitSession(clean.storage, 'does-not-exist', 'correct', '2026-11-28', validUnitIds)).toMatchObject({
      ok: false,
      reason: 'unknown-unit',
    });
    expect(
      recordUnitSession(clean.storage, CKA_MODULE_5_1_UNITS[0].id, 'correct', '2026-02-30', validUnitIds),
    ).toMatchObject({ ok: false, reason: 'invalid-date' });
    expect(clean.writes).toHaveLength(0);

    // Explicit reset clears corrupted data cleanly
    const resetRes = resetDailyState(corrupt.storage);
    expect(resetRes.ok).toBe(true);
    expect(corrupt.raw()).toBeNull();
  });
});

describe('Daily Dojo pilot content and zero-analytics invariants (AC-01, AC-03, AC-04)', () => {
  it('defines ten valid units within 450 words each with official version-neutral docs and real parent anchors', () => {
    expect(CKA_MODULE_5_1_UNITS).toHaveLength(10);
    const parentMd = readFileSync(
      resolve(repoRoot, 'src/content/docs/k8s/cka/part5-troubleshooting/module-5.1-methodology.md'),
      'utf8',
    );
    const seenIds = new Set<string>();

    for (const [index, unit] of CKA_MODULE_5_1_UNITS.entries()) {
      expect(unit.number).toBe(index + 1);
      expect(seenIds.has(unit.id)).toBe(false);
      seenIds.add(unit.id);

      const words = countUnitWords(unit);
      expect(words, `unit ${unit.id} exceeds ${DAILY_MAX_UNIT_WORDS} words (${words})`).toBeLessThanOrEqual(
        DAILY_MAX_UNIT_WORDS,
      );
      expect(words, `unit ${unit.id} is unexpectedly short (${words})`).toBeGreaterThanOrEqual(120);

      expect(unit.checks.length).toBeGreaterThanOrEqual(1);
      expect(unit.checks.length).toBeLessThanOrEqual(2);
      for (const check of unit.checks) {
        expect(check.options.some((o) => o.correct)).toBe(true);
        expect(check.options.some((o) => !o.correct)).toBe(true);
        for (const opt of check.options) {
          expect(opt.explanation.trim().length).toBeGreaterThan(15);
        }
      }

      expect(unit.labId).toBe(PARENT_LAB_ID);
      expect(unit.labUrl).toBe(PARENT_LAB_URL);
      expect(unit.sources.length).toBeGreaterThanOrEqual(1);
      for (const src of unit.sources) {
        expect(src.url).toMatch(/^https:\/\/kubernetes\.io\/docs\//);
        expect(src.url).not.toMatch(/v1-\d+\.docs\.kubernetes\.io/);
      }

      // Parent section title must exist as a heading in module-5.1-methodology.md
      expect(parentMd).toContain(`### ${unit.parentSectionTitle}`);
    }
  });

  it('keeps the feature name in one constant and omits all analytics from the standalone layout/route', () => {
    expect(DAILY_FEATURE_NAME).toBe('Daily Dojo');

    const layoutSrc = readFileSync(resolve(repoRoot, 'src/layouts/DailyDojo.astro'), 'utf8');
    const pageSrc = readFileSync(resolve(repoRoot, 'src/pages/daily/index.astro'), 'utf8');
    const stateSrc = readFileSync(resolve(repoRoot, 'src/scripts/daily-state.ts'), 'utf8');
    const playerSrc = readFileSync(resolve(repoRoot, 'src/scripts/daily-player.ts'), 'utf8');

    // No hardcoded duplicate feature-name string literal in layout, route, state, or player
    expect(layoutSrc).toContain('DAILY_FEATURE_NAME');
    expect(layoutSrc).not.toMatch(/['"`]Daily Dojo['"`]/);
    expect(pageSrc).toContain('DAILY_FEATURE_NAME');
    expect(pageSrc).not.toMatch(/['"`]Daily Dojo['"`]/);
    expect(stateSrc).not.toMatch(/['"`]Daily Dojo['"`]/);
    expect(playerSrc).toContain('DAILY_FEATURE_NAME');
    expect(playerSrc).not.toMatch(/['"`]Daily Dojo['"`]/);

    // Zero analytics script tags in standalone layout and route
    expect(layoutSrc).not.toMatch(/<script[^>]*count\.js/i);
    expect(layoutSrc).not.toMatch(/data-goatcounter/i);
    expect(pageSrc).not.toMatch(/count\.js|goatcounter/i);
  });
});

describe('Daily Dojo player DOM workflow', () => {
  it('completes a unit, persists across remount, and shows the 5-minute choice UI on the due date', () => {
    const store = memoryStorage(null);
    let currentDay = new Date(2026, 10, 28, 10, 0, 0);

    function createShell(): HTMLElement {
      const root = document.createElement('main');
      root.dataset.dailyRoot = '';
      root.innerHTML =
        '<div data-daily-stats></div><div data-daily-notice hidden></div><section data-daily-plan></section><nav data-daily-nav></nav><section data-daily-unit></section>';
      return root;
    }

    const root1 = createShell();
    mountDailyPlayer(root1, { pack: CKA_MODULE_5_1_PACK, storage: store.storage, now: () => currentDay });

    // Unit 1 is active and exposes parent anchor and lab links
    expect(root1.querySelector('[data-unit-id]')?.getAttribute('data-unit-id')).toBe(CKA_MODULE_5_1_UNITS[0].id);
    expect(root1.querySelector('[data-parent-link]')?.getAttribute('href')).toBe(
      `${CKA_MODULE_5_1_PACK.parentModulePath}#${CKA_MODULE_5_1_UNITS[0].parentAnchor}`,
    );
    expect(root1.querySelector('[data-lab-link]')?.getAttribute('href')).toBe(PARENT_LAB_URL);

    // Click the correct option on Unit 1
    const correctBtn = root1.querySelector<HTMLButtonElement>('[data-check-option][data-correct="true"]');
    expect(correctBtn).not.toBeNull();
    correctBtn!.click();

    expect(root1.querySelector('[data-feedback-status]')?.getAttribute('data-feedback-status')).toBe('correct');
    expect(root1.querySelector('[data-unit-result]')?.getAttribute('data-unit-result')).toBe('correct');
    expect(root1.querySelector('[data-stat="completed"] .dd-stat-value')?.textContent).toBe('1 / 10');
    expect(store.writes.length).toBe(1);

    // Advance clock to tomorrow and remount (simulating reload the next day)
    currentDay = new Date(2026, 10, 29, 10, 0, 0);
    const root2 = createShell();
    mountDailyPlayer(root2, { pack: CKA_MODULE_5_1_PACK, storage: store.storage, now: () => currentDay });

    expect(root2.querySelector('[data-stat="completed"] .dd-stat-value')?.textContent).toBe('1 / 10');
    expect(root2.querySelector('[data-stat="due"] .dd-stat-value')?.textContent).toBe('1');
    expect(root2.querySelector('[data-plan-mode]')?.getAttribute('data-plan-mode')).toBe('choice');

    // Choice UI lets learner switch between new unit and due review
    const learnNewBtn = root2.querySelector<HTMLButtonElement>('[data-plan-action="new"]');
    const reviewDueBtn = root2.querySelector<HTMLButtonElement>('[data-plan-action="review"]');
    expect(learnNewBtn).not.toBeNull();
    expect(reviewDueBtn).not.toBeNull();

    learnNewBtn!.click();
    expect(root2.querySelector('[data-unit-id]')?.getAttribute('data-unit-id')).toBe(CKA_MODULE_5_1_UNITS[1].id);

    reviewDueBtn!.click();
    expect(root2.querySelector('[data-unit-id]')?.getAttribute('data-unit-id')).toBe(CKA_MODULE_5_1_UNITS[0].id);
  });
});
