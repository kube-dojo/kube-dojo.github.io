/**
 * Daily Dojo browser-only state engine.
 *
 * Stores all progress in one localStorage key (`kubedojo-daily-v1`).
 * No cookies, accounts, server calls, or analytics.
 *
 * Follows Design Charter #7 (fail closed and say why): malformed storage or
 * invalid dates/unit IDs return typed errors and never silently clobber saved data.
 */

export const DAILY_STORAGE_KEY = 'kubedojo-daily-v1';
export const DAILY_STATE_VERSION = 1 as const;
export const REVIEW_INTERVALS_DAYS = [1, 3, 7, 14, 30] as const;
export const SESSION_BUDGET_MINUTES = 5;

export type SessionOutcome = 'correct' | 'missed';

export interface UnitProgress {
  completedAt: string;
  lastReviewedAt: string;
  nextReviewAt: string;
  intervalIndex: number;
  reviewCount: number;
  lastOutcome: SessionOutcome;
}

export interface StreakState {
  current: number;
  best: number;
  lastActiveDate: string | null;
  resumedAfterGap: boolean;
}

export interface DailyProgressState {
  version: typeof DAILY_STATE_VERSION;
  streak: StreakState;
  units: Record<string, UnitProgress>;
}

export interface DailyUnitSummary {
  id: string;
  number: number;
  title: string;
  estimatedMinutes: number;
  reviewMinutes: number;
}

export type DailyStorage = () => Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export type DailyStateResult =
  | { ok: true; state: DailyProgressState }
  | {
      ok: false;
      reason: 'unavailable' | 'invalid' | 'write' | 'unknown-unit' | 'invalid-date';
      detail: string;
      raw?: string;
    };

export type SessionPlanMode = 'new' | 'review' | 'choice' | 'both' | 'caught-up';

export interface DailyRecommendation {
  mode: SessionPlanMode;
  today: string;
  budgetMinutes: number;
  dueUnits: DailyUnitSummary[];
  nextNewUnit: DailyUnitSummary | null;
  nextReviewMinutes: number;
  nextNewMinutes: number;
  combinedMinutes: number;
  nextScheduledDate: string | null;
}

const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function formatLocalDate(date: Date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function isValidCalendarDate(value: string): boolean {
  if (typeof value !== 'string') return false;
  const match = DATE_RE.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return false;
  const check = new Date(Date.UTC(year, month - 1, day));
  return (
    check.getUTCFullYear() === year &&
    check.getUTCMonth() === month - 1 &&
    check.getUTCDate() === day
  );
}

function toUtcDayNumber(dateStr: string): number {
  const match = DATE_RE.exec(dateStr);
  if (!match) throw new Error(`Invalid calendar date: ${dateStr}`);
  const ms = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Math.floor(ms / 86_400_000);
}

export function addDays(dateStr: string, days: number): string {
  if (!isValidCalendarDate(dateStr)) {
    throw new Error(`Invalid calendar date: ${dateStr}`);
  }
  if (!Number.isInteger(days)) {
    throw new Error(`Day offset must be an integer: ${days}`);
  }
  const match = DATE_RE.exec(dateStr)!;
  const next = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + days));
  const y = next.getUTCFullYear();
  const m = String(next.getUTCMonth() + 1).padStart(2, '0');
  const d = String(next.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function daysBetween(fromDate: string, toDate: string): number {
  if (!isValidCalendarDate(fromDate) || !isValidCalendarDate(toDate)) {
    throw new Error(`Invalid calendar date range: ${fromDate} -> ${toDate}`);
  }
  return toUtcDayNumber(toDate) - toUtcDayNumber(fromDate);
}

export function createEmptyState(): DailyProgressState {
  return {
    version: DAILY_STATE_VERSION,
    streak: {
      current: 0,
      best: 0,
      lastActiveDate: null,
      resumedAfterGap: false,
    },
    units: {},
  };
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function parseDailyState(raw: string | null): DailyStateResult {
  if (raw === null) {
    return { ok: true, state: createEmptyState() };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, reason: 'invalid', detail: 'Saved progress is not valid JSON.', raw };
  }
  if (!isPlainObject(parsed)) {
    return { ok: false, reason: 'invalid', detail: 'Saved progress must be a JSON object.', raw };
  }
  if (parsed.version !== DAILY_STATE_VERSION) {
    return {
      ok: false,
      reason: 'invalid',
      detail: `Unsupported daily state version: ${String(parsed.version)}.`,
      raw,
    };
  }
  if (!isPlainObject(parsed.streak) || !isPlainObject(parsed.units)) {
    return { ok: false, reason: 'invalid', detail: 'Saved progress is missing streak or units.', raw };
  }

  const streakRaw = parsed.streak;
  if (
    typeof streakRaw.current !== 'number' ||
    !Number.isInteger(streakRaw.current) ||
    streakRaw.current < 0 ||
    typeof streakRaw.best !== 'number' ||
    !Number.isInteger(streakRaw.best) ||
    streakRaw.best < 0 ||
    streakRaw.best < streakRaw.current
  ) {
    return { ok: false, reason: 'invalid', detail: 'Saved streak counts are invalid.', raw };
  }
  if (
    streakRaw.lastActiveDate !== null &&
    (typeof streakRaw.lastActiveDate !== 'string' || !isValidCalendarDate(streakRaw.lastActiveDate))
  ) {
    return { ok: false, reason: 'invalid', detail: 'Saved streak date is invalid.', raw };
  }
  if (typeof streakRaw.resumedAfterGap !== 'boolean') {
    return { ok: false, reason: 'invalid', detail: 'Saved streak resume flag is invalid.', raw };
  }

  const units: Record<string, UnitProgress> = {};
  for (const [unitId, entry] of Object.entries(parsed.units)) {
    if (!isPlainObject(entry)) {
      return { ok: false, reason: 'invalid', detail: `Unit progress entry "${unitId}" must be an object.`, raw };
    }
    if (
      typeof entry.completedAt !== 'string' ||
      !isValidCalendarDate(entry.completedAt) ||
      typeof entry.lastReviewedAt !== 'string' ||
      !isValidCalendarDate(entry.lastReviewedAt) ||
      typeof entry.nextReviewAt !== 'string' ||
      !isValidCalendarDate(entry.nextReviewAt)
    ) {
      return { ok: false, reason: 'invalid', detail: `Unit "${unitId}" contains an invalid date.`, raw };
    }
    if (
      typeof entry.intervalIndex !== 'number' ||
      !Number.isInteger(entry.intervalIndex) ||
      entry.intervalIndex < 0 ||
      entry.intervalIndex >= REVIEW_INTERVALS_DAYS.length
    ) {
      return { ok: false, reason: 'invalid', detail: `Unit "${unitId}" has an out-of-range interval index.`, raw };
    }
    if (
      typeof entry.reviewCount !== 'number' ||
      !Number.isInteger(entry.reviewCount) ||
      entry.reviewCount < 1
    ) {
      return { ok: false, reason: 'invalid', detail: `Unit "${unitId}" has an invalid review count.`, raw };
    }
    if (entry.lastOutcome !== 'correct' && entry.lastOutcome !== 'missed') {
      return { ok: false, reason: 'invalid', detail: `Unit "${unitId}" has an invalid outcome.`, raw };
    }
    units[unitId] = {
      completedAt: entry.completedAt,
      lastReviewedAt: entry.lastReviewedAt,
      nextReviewAt: entry.nextReviewAt,
      intervalIndex: entry.intervalIndex,
      reviewCount: entry.reviewCount,
      lastOutcome: entry.lastOutcome,
    };
  }

  return {
    ok: true,
    state: {
      version: DAILY_STATE_VERSION,
      streak: {
        current: streakRaw.current,
        best: streakRaw.best,
        lastActiveDate: streakRaw.lastActiveDate,
        resumedAfterGap: streakRaw.resumedAfterGap,
      },
      units,
    },
  };
}

export function readDailyState(storage: DailyStorage): DailyStateResult {
  let raw: string | null;
  try {
    raw = storage().getItem(DAILY_STORAGE_KEY);
  } catch {
    return {
      ok: false,
      reason: 'unavailable',
      detail: 'Browser storage is unavailable in this session.',
    };
  }
  return parseDailyState(raw);
}

export function writeDailyState(storage: DailyStorage, state: DailyProgressState): DailyStateResult {
  try {
    storage().setItem(DAILY_STORAGE_KEY, JSON.stringify(state));
  } catch {
    return {
      ok: false,
      reason: 'write',
      detail: 'Could not save progress to browser localStorage.',
    };
  }
  return { ok: true, state };
}

export function resetDailyState(storage: DailyStorage): DailyStateResult {
  try {
    storage().removeItem(DAILY_STORAGE_KEY);
  } catch {
    return {
      ok: false,
      reason: 'write',
      detail: 'Could not clear browser localStorage.',
    };
  }
  return { ok: true, state: createEmptyState() };
}

/**
 * Pure transition: update completion, gentle streak, and next due date.
 * - First completion (correct or missed): intervalIndex 0 -> due tomorrow (+1 day).
 * - Review answered correctly: advances intervalIndex (1 -> 3 -> 7 -> 14 -> 30 days).
 * - Any missed check: resets intervalIndex to 0 -> due tomorrow (+1 day).
 */
export function applyUnitSession(
  state: DailyProgressState,
  unitId: string,
  outcome: SessionOutcome,
  today: string,
  validUnitIds: ReadonlySet<string>,
): DailyStateResult {
  if (!validUnitIds.has(unitId)) {
    return { ok: false, reason: 'unknown-unit', detail: `Unknown daily unit: ${unitId}` };
  }
  if (!isValidCalendarDate(today)) {
    return { ok: false, reason: 'invalid-date', detail: `Invalid calendar date: ${today}` };
  }

  const nextStreak: StreakState = { ...state.streak };
  if (state.streak.lastActiveDate === null) {
    nextStreak.current = 1;
    nextStreak.best = Math.max(state.streak.best, 1);
    nextStreak.lastActiveDate = today;
    nextStreak.resumedAfterGap = false;
  } else {
    const gap = daysBetween(state.streak.lastActiveDate, today);
    if (gap === 0) {
      // Same calendar day: preserve streak without double-counting.
    } else if (gap === 1) {
      nextStreak.current = state.streak.current + 1;
      nextStreak.best = Math.max(state.streak.best, nextStreak.current);
      nextStreak.lastActiveDate = today;
      nextStreak.resumedAfterGap = false;
    } else if (gap > 1) {
      // Gentle resume: start a fresh streak without erasing prior completions or best streak.
      nextStreak.current = 1;
      nextStreak.best = Math.max(state.streak.best, 1);
      nextStreak.lastActiveDate = today;
      nextStreak.resumedAfterGap = true;
    }
    // If gap < 0 (device clock moved backward), keep streak and lastActiveDate intact.
  }

  const existing = Object.hasOwn(state.units, unitId) ? state.units[unitId] : undefined;
  let nextIntervalIndex: number;
  if (outcome === 'missed') {
    nextIntervalIndex = 0;
  } else if (!existing) {
    nextIntervalIndex = 0;
  } else {
    nextIntervalIndex = Math.min(existing.intervalIndex + 1, REVIEW_INTERVALS_DAYS.length - 1);
  }

  const nextUnit: UnitProgress = {
    completedAt: existing ? existing.completedAt : today,
    lastReviewedAt: today,
    nextReviewAt: addDays(today, REVIEW_INTERVALS_DAYS[nextIntervalIndex]),
    intervalIndex: nextIntervalIndex,
    reviewCount: existing ? existing.reviewCount + 1 : 1,
    lastOutcome: outcome,
  };

  return {
    ok: true,
    state: {
      version: DAILY_STATE_VERSION,
      streak: nextStreak,
      units: {
        ...state.units,
        [unitId]: nextUnit,
      },
    },
  };
}

export function recordUnitSession(
  storage: DailyStorage,
  unitId: string,
  outcome: SessionOutcome,
  today: string,
  validUnitIds: ReadonlySet<string>,
): DailyStateResult {
  const current = readDailyState(storage);
  if (!current.ok) return current;
  const updated = applyUnitSession(current.state, unitId, outcome, today, validUnitIds);
  if (!updated.ok) return updated;
  return writeDailyState(storage, updated.state);
}

/**
 * Determine what to show the learner today.
 * When at least one review is due AND a new unit remains, and doing one due review
 * plus the next new unit would exceed the 5-minute budget, return mode='choice' so
 * the learner picks review or new instead of being overloaded.
 */
export function getDailyRecommendation(
  units: readonly DailyUnitSummary[],
  state: DailyProgressState,
  today: string,
  budgetMinutes: number = SESSION_BUDGET_MINUTES,
): DailyRecommendation {
  if (!isValidCalendarDate(today)) {
    throw new Error(`Invalid calendar date: ${today}`);
  }

  const dueUnits = units
    .filter((unit) => {
      const progress = Object.hasOwn(state.units, unit.id) ? state.units[unit.id] : undefined;
      return progress !== undefined && progress.nextReviewAt <= today;
    })
    .sort((a, b) => {
      const dueA = state.units[a.id].nextReviewAt;
      const dueB = state.units[b.id].nextReviewAt;
      if (dueA !== dueB) return dueA < dueB ? -1 : 1;
      return a.number - b.number;
    });

  const nextNewUnit = units.find((unit) => !Object.hasOwn(state.units, unit.id)) ?? null;

  const nextReviewMinutes = dueUnits.length > 0 ? dueUnits[0].reviewMinutes : 0;
  const nextNewMinutes = nextNewUnit ? nextNewUnit.estimatedMinutes : 0;
  const combinedMinutes = nextReviewMinutes + nextNewMinutes;

  let nextScheduledDate: string | null = null;
  for (const unit of units) {
    const progress = Object.hasOwn(state.units, unit.id) ? state.units[unit.id] : undefined;
    if (!progress || progress.nextReviewAt <= today) continue;
    if (nextScheduledDate === null || progress.nextReviewAt < nextScheduledDate) {
      nextScheduledDate = progress.nextReviewAt;
    }
  }

  let mode: SessionPlanMode;
  if (dueUnits.length > 0 && nextNewUnit !== null) {
    mode = combinedMinutes > budgetMinutes ? 'choice' : 'both';
  } else if (dueUnits.length > 0) {
    mode = 'review';
  } else if (nextNewUnit !== null) {
    mode = 'new';
  } else {
    mode = 'caught-up';
  }

  return {
    mode,
    today,
    budgetMinutes,
    dueUnits,
    nextNewUnit,
    nextReviewMinutes,
    nextNewMinutes,
    combinedMinutes,
    nextScheduledDate,
  };
}
