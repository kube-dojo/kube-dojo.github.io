/**
 * Daily Dojo interactive client player.
 *
 * Renders the ten pilot units on the single /daily/ route using safe DOM APIs
 * (no innerHTML with dynamic content) and persists state strictly to
 * localStorage['kubedojo-daily-v1'] with zero network requests.
 */

import {
  CKA_MODULE_5_1_PACK,
  DAILY_FEATURE_NAME,
  type DailyCheck,
  type DailyCheckOption,
  type DailyPack,
  type DailyUnit,
} from '../data/daily/cka-module-5.1';
import {
  DAILY_STORAGE_KEY,
  SESSION_BUDGET_MINUTES,
  applyUnitSession,
  createEmptyState,
  formatLocalDate,
  getDailyRecommendation,
  readDailyState,
  resetDailyState,
  writeDailyState,
  type DailyProgressState,
  type DailyRecommendation,
  type DailyStorage,
  type SessionOutcome,
} from './daily-state';

export interface MountDailyPlayerOptions {
  pack?: DailyPack;
  storage?: DailyStorage;
  now?: () => Date;
}

interface ActiveUnitSession {
  unitId: string;
  firstAttemptCorrect: Record<string, boolean>;
  selectedOption: Record<string, string>;
  recorded: boolean;
  recordedOutcome: SessionOutcome | null;
  nextReviewAt: string | null;
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function clearNode(node: Element): void {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function defaultStorage(): Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> {
  return window.localStorage;
}

function pickInitialUnitId(pack: DailyPack, recommendation: DailyRecommendation): string {
  if (recommendation.mode === 'review' || recommendation.mode === 'both' || recommendation.mode === 'choice') {
    if (recommendation.dueUnits.length > 0) return recommendation.dueUnits[0].id;
  }
  if (recommendation.nextNewUnit) return recommendation.nextNewUnit.id;
  return pack.units[0].id;
}

function createUnitSession(unitId: string): ActiveUnitSession {
  return {
    unitId,
    firstAttemptCorrect: {},
    selectedOption: {},
    recorded: false,
    recordedOutcome: null,
    nextReviewAt: null,
  };
}

export function mountDailyPlayer(
  root: HTMLElement,
  options: MountDailyPlayerOptions = {},
): { destroy: () => void } {
  const pack = options.pack ?? CKA_MODULE_5_1_PACK;
  const storage = options.storage ?? defaultStorage;
  const now = options.now ?? (() => new Date());
  const validUnitIds = new Set(pack.units.map((unit) => unit.id));

  const statsEl = root.querySelector<HTMLElement>('[data-daily-stats]');
  const noticeEl = root.querySelector<HTMLElement>('[data-daily-notice]');
  const planEl = root.querySelector<HTMLElement>('[data-daily-plan]');
  const navEl = root.querySelector<HTMLElement>('[data-daily-nav]');
  const unitEl = root.querySelector<HTMLElement>('[data-daily-unit]');

  if (!statsEl || !noticeEl || !planEl || !navEl || !unitEl) {
    return { destroy: () => {} };
  }

  let storageBlockedReason: 'invalid' | 'unavailable' | 'write' | null = null;
  let storageBlockedDetail: string | null = null;
  let state: DailyProgressState = createEmptyState();

  function loadState(): void {
    const res = readDailyState(storage);
    if (res.ok) {
      state = res.state;
      storageBlockedReason = null;
      storageBlockedDetail = null;
    } else {
      state = createEmptyState();
      storageBlockedReason = res.reason === 'invalid' ? 'invalid' : 'unavailable';
      storageBlockedDetail = res.detail;
    }
  }

  loadState();

  const initialToday = formatLocalDate(now());
  const initialRec = getDailyRecommendation(pack.units, state, initialToday, SESSION_BUDGET_MINUTES);
  let activeUnitId = pickInitialUnitId(pack, initialRec);
  let chosenPlanTrack: 'review' | 'new' | null = null;
  let session = createUnitSession(activeUnitId);

  function getToday(): string {
    return formatLocalDate(now());
  }

  function findUnit(unitId: string): DailyUnit {
    return pack.units.find((u) => u.id === unitId) ?? pack.units[0];
  }

  function selectUnit(unitId: string, track: 'review' | 'new' | null = null): void {
    activeUnitId = unitId;
    chosenPlanTrack = track;
    session = createUnitSession(unitId);
    render();
  }

  function handleOptionSelect(unit: DailyUnit, check: DailyCheck, option: DailyCheckOption): void {
    if (!Object.hasOwn(session.firstAttemptCorrect, check.id)) {
      session.firstAttemptCorrect[check.id] = option.correct;
    }
    session.selectedOption[check.id] = option.id;

    const allAnswered = unit.checks.every((item) => Object.hasOwn(session.firstAttemptCorrect, item.id));
    if (allAnswered && !session.recorded) {
      const outcome: SessionOutcome = unit.checks.every((item) => session.firstAttemptCorrect[item.id])
        ? 'correct'
        : 'missed';
      const today = getToday();

      let baseState = state;
      if (storageBlockedReason === null) {
        const fresh = readDailyState(storage);
        if (fresh.ok) {
          baseState = fresh.state;
        } else {
          storageBlockedReason = fresh.reason === 'invalid' ? 'invalid' : 'unavailable';
          storageBlockedDetail = fresh.detail;
        }
      }

      const applied = applyUnitSession(baseState, unit.id, outcome, today, validUnitIds);
      if (applied.ok) {
        state = applied.state;
        session.recorded = true;
        session.recordedOutcome = outcome;
        session.nextReviewAt = state.units[unit.id]?.nextReviewAt ?? null;
        if (storageBlockedReason === null) {
          const written = writeDailyState(storage, state);
          if (!written.ok) {
            storageBlockedReason = 'write';
            storageBlockedDetail = written.detail;
          }
        }
      }
    }

    render();
  }

  function renderNotice(): void {
    clearNode(noticeEl!);
    if (!storageBlockedReason) {
      noticeEl!.hidden = true;
      return;
    }
    noticeEl!.hidden = false;
    const banner = el('div', 'dd-alert');
    banner.setAttribute('role', 'alert');
    const msg = el(
      'p',
      'dd-alert-text',
      storageBlockedReason === 'invalid'
        ? `Saved ${DAILY_FEATURE_NAME} progress in localStorage (${DAILY_STORAGE_KEY}) is corrupted (${storageBlockedDetail}). Existing data was left untouched so nothing is overwritten silently.`
        : `Browser storage is not writable (${storageBlockedDetail ?? 'unavailable'}). You can still complete lessons, but progress will not persist across reloads.`,
    );
    banner.appendChild(msg);

    if (storageBlockedReason === 'invalid') {
      const resetBtn = el('button', 'dd-btn dd-btn-secondary', 'Reset saved progress');
      resetBtn.type = 'button';
      resetBtn.dataset.resetStorage = '';
      resetBtn.addEventListener('click', () => {
        const cleared = resetDailyState(storage);
        if (cleared.ok) {
          state = cleared.state;
          storageBlockedReason = null;
          storageBlockedDetail = null;
          const rec = getDailyRecommendation(pack.units, state, getToday(), SESSION_BUDGET_MINUTES);
          selectUnit(pickInitialUnitId(pack, rec));
        } else {
          storageBlockedReason = 'write';
          storageBlockedDetail = cleared.detail;
          render();
        }
      });
      banner.appendChild(resetBtn);
    }

    noticeEl!.appendChild(banner);
  }

  function renderStats(rec: DailyRecommendation): void {
    clearNode(statsEl!);
    const completedCount = pack.units.filter((u) => Object.hasOwn(state.units, u.id)).length;

    const items: Array<{ label: string; value: string; testKey: string }> = [
      { label: 'Completed', value: `${completedCount} / ${pack.units.length}`, testKey: 'completed' },
      {
        label: 'Streak',
        value: `${state.streak.current} ${state.streak.current === 1 ? 'day' : 'days'}`,
        testKey: 'streak',
      },
      { label: 'Due today', value: `${rec.dueUnits.length}`, testKey: 'due' },
      { label: 'Best streak', value: `${state.streak.best} ${state.streak.best === 1 ? 'day' : 'days'}`, testKey: 'best' },
    ];

    for (const item of items) {
      const card = el('div', 'dd-stat');
      card.dataset.stat = item.testKey;
      const val = el('span', 'dd-stat-value', item.value);
      const lbl = el('span', 'dd-stat-label', item.label);
      card.append(val, lbl);
      statsEl!.appendChild(card);
    }

    if (state.streak.resumedAfterGap) {
      const gentleNote = el(
        'p',
        'dd-gentle-note',
        'Welcome back — fresh streak started. All previously completed units remain saved.',
      );
      gentleNote.dataset.gentleResume = '';
      statsEl!.appendChild(gentleNote);
    }
  }

  function renderPlan(rec: DailyRecommendation): void {
    clearNode(planEl!);
    const box = el('div', 'dd-plan-card');
    box.dataset.planMode = rec.mode;

    if (rec.mode === 'choice' && rec.dueUnits.length > 0 && rec.nextNewUnit) {
      const heading = el('h2', 'dd-plan-title', `Choose today's ${rec.budgetMinutes}-minute session`);
      const body = el(
        'p',
        'dd-plan-desc',
        `You have ${rec.dueUnits.length} due ${rec.dueUnits.length === 1 ? 'review' : 'reviews'} (~${rec.nextReviewMinutes} min) and a new unit (~${rec.nextNewMinutes} min). Doing both takes ~${rec.combinedMinutes} min (over the ${rec.budgetMinutes}-minute daily target). Pick one for today:`,
      );
      const actions = el('div', 'dd-plan-actions');

      const reviewBtn = el(
        'button',
        `dd-btn ${chosenPlanTrack === 'review' ? 'dd-btn-primary' : 'dd-btn-secondary'}`,
        `Review due: #${rec.dueUnits[0].number} ${rec.dueUnits[0].title} (~${rec.nextReviewMinutes} min)`,
      );
      reviewBtn.type = 'button';
      reviewBtn.dataset.planAction = 'review';
      reviewBtn.addEventListener('click', () => selectUnit(rec.dueUnits[0].id, 'review'));

      const newBtn = el(
        'button',
        `dd-btn ${chosenPlanTrack === 'new' ? 'dd-btn-primary' : 'dd-btn-secondary'}`,
        `Learn new: #${rec.nextNewUnit.number} ${rec.nextNewUnit.title} (~${rec.nextNewMinutes} min)`,
      );
      newBtn.type = 'button';
      newBtn.dataset.planAction = 'new';
      newBtn.addEventListener('click', () => selectUnit(rec.nextNewUnit!.id, 'new'));

      actions.append(reviewBtn, newBtn);
      box.append(heading, body, actions);
    } else if (rec.mode === 'review' && rec.dueUnits.length > 0) {
      const heading = el('h2', 'dd-plan-title', 'Due review ready');
      const body = el(
        'p',
        'dd-plan-desc',
        `${rec.dueUnits.length} ${rec.dueUnits.length === 1 ? 'unit is' : 'units are'} due for quick recall (~${rec.nextReviewMinutes} min).`,
      );
      const btn = el(
        'button',
        'dd-btn dd-btn-primary',
        `Open due review: #${rec.dueUnits[0].number} ${rec.dueUnits[0].title}`,
      );
      btn.type = 'button';
      btn.dataset.planAction = 'review';
      btn.addEventListener('click', () => selectUnit(rec.dueUnits[0].id, 'review'));
      box.append(heading, body, btn);
    } else if (rec.mode === 'both' && rec.dueUnits.length > 0 && rec.nextNewUnit) {
      const heading = el('h2', 'dd-plan-title', 'Quick review + next unit fit today');
      const body = el(
        'p',
        'dd-plan-desc',
        `Your due review (~${rec.nextReviewMinutes} min) and next new unit (~${rec.nextNewMinutes} min) fit within ${rec.budgetMinutes} minutes.`,
      );
      const actions = el('div', 'dd-plan-actions');
      const reviewBtn = el('button', 'dd-btn dd-btn-primary', `Start review #${rec.dueUnits[0].number}`);
      reviewBtn.type = 'button';
      reviewBtn.dataset.planAction = 'review';
      reviewBtn.addEventListener('click', () => selectUnit(rec.dueUnits[0].id, 'review'));
      const newBtn = el('button', 'dd-btn dd-btn-secondary', `Start new #${rec.nextNewUnit.number}`);
      newBtn.type = 'button';
      newBtn.dataset.planAction = 'new';
      newBtn.addEventListener('click', () => selectUnit(rec.nextNewUnit!.id, 'new'));
      actions.append(reviewBtn, newBtn);
      box.append(heading, body, actions);
    } else if (rec.mode === 'new' && rec.nextNewUnit) {
      const heading = el('h2', 'dd-plan-title', "Today's 3–5 minute lesson");
      const body = el(
        'p',
        'dd-plan-desc',
        `Up next: Unit ${rec.nextNewUnit.number} — ${rec.nextNewUnit.title} (~${rec.nextNewUnit.estimatedMinutes} min).`,
      );
      const btn = el('button', 'dd-btn dd-btn-primary', `Open Unit ${rec.nextNewUnit.number}`);
      btn.type = 'button';
      btn.dataset.planAction = 'new';
      btn.addEventListener('click', () => selectUnit(rec.nextNewUnit!.id, 'new'));
      box.append(heading, body, btn);
    } else {
      const heading = el('h2', 'dd-plan-title', 'All caught up for today');
      const nextText = rec.nextScheduledDate
        ? `Next scheduled review: ${rec.nextScheduledDate}. You can still revisit any unit below.`
        : 'All ten units are complete. Revisit any unit below anytime.';
      const body = el('p', 'dd-plan-desc', nextText);
      box.append(heading, body);
    }

    planEl!.appendChild(box);
  }

  function renderNav(today: string): void {
    clearNode(navEl!);
    const list = el('ol', 'dd-unit-list');
    for (const unit of pack.units) {
      const li = el('li');
      const progress = Object.hasOwn(state.units, unit.id) ? state.units[unit.id] : undefined;
      const isDue = progress !== undefined && progress.nextReviewAt <= today;
      const isActive = unit.id === activeUnitId;

      const btn = el('button', `dd-unit-pill${isActive ? ' is-active' : ''}${isDue ? ' is-due' : ''}${progress && !isDue ? ' is-done' : ''}`);
      btn.type = 'button';
      btn.dataset.unitSelect = unit.id;
      if (isActive) btn.setAttribute('aria-current', 'step');

      const num = el('span', 'dd-pill-num', String(unit.number));
      const title = el('span', 'dd-pill-title', unit.title);
      const badgeText = !progress
        ? 'New'
        : isDue
          ? 'Due'
          : `Done · ${progress.nextReviewAt}`;
      const badge = el('span', 'dd-pill-badge', badgeText);

      btn.append(num, title, badge);
      btn.addEventListener('click', () => selectUnit(unit.id));
      li.appendChild(btn);
      list.appendChild(li);
    }
    navEl!.appendChild(list);
  }

  function renderUnit(today: string, rec: DailyRecommendation): void {
    clearNode(unitEl!);
    const unit = findUnit(activeUnitId);
    const progress = Object.hasOwn(state.units, unit.id) ? state.units[unit.id] : undefined;
    const isDue = progress !== undefined && progress.nextReviewAt <= today;

    const article = el('article', 'dd-lesson');
    article.dataset.unitId = unit.id;

    // Header
    const header = el('header', 'dd-lesson-header');
    const meta = el('div', 'dd-lesson-meta');
    meta.appendChild(el('span', 'dd-tag dd-tag-num', `Unit ${unit.number} of ${pack.units.length}`));
    const duration = isDue ? `Due review · ~${unit.reviewMinutes} min` : `~${unit.estimatedMinutes} min`;
    meta.appendChild(el('span', `dd-tag ${isDue ? 'dd-tag-due' : 'dd-tag-time'}`, duration));
    if (progress) {
      meta.appendChild(
        el(
          'span',
          'dd-tag dd-tag-done',
          isDue ? `Due since ${progress.nextReviewAt}` : `Next review: ${progress.nextReviewAt}`,
        ),
      );
    }
    const title = el('h2', 'dd-lesson-title', unit.title);
    header.append(meta, title);
    article.appendChild(header);

    // Core idea
    const ideaSection = el('section', 'dd-section');
    ideaSection.appendChild(el('h3', 'dd-section-label', 'Core idea'));
    ideaSection.appendChild(el('p', 'dd-idea', unit.idea));
    article.appendChild(ideaSection);

    // Worked example
    const exSection = el('section', 'dd-section dd-example');
    exSection.appendChild(el('h3', 'dd-section-label', `Worked example: ${unit.workedExample.title}`));
    const pre = el('pre', 'dd-code');
    const code = el('code', undefined, unit.workedExample.code);
    pre.appendChild(code);
    exSection.append(pre, el('p', 'dd-takeaway', unit.workedExample.takeaway));
    article.appendChild(exSection);

    // Active checks
    const checksSection = el('section', 'dd-section dd-checks');
    checksSection.appendChild(
      el('h3', 'dd-section-label', unit.checks.length === 1 ? 'Quick check' : 'Quick checks'),
    );

    for (const check of unit.checks) {
      const fieldset = el('fieldset', 'dd-check');
      fieldset.dataset.checkId = check.id;
      const legend = el('legend', 'dd-check-prompt', check.prompt);
      fieldset.appendChild(legend);

      const optionsWrap = el('div', 'dd-options');
      const selectedId = session.selectedOption[check.id];

      for (const option of check.options) {
        const isSelected = selectedId === option.id;
        let stateClass = '';
        if (isSelected) {
          stateClass = option.correct ? ' is-correct' : ' is-incorrect';
        }
        const optBtn = el('button', `dd-option${stateClass}`);
        optBtn.type = 'button';
        optBtn.dataset.checkOption = `${check.id}:${option.id}`;
        optBtn.dataset.correct = String(option.correct);
        optBtn.setAttribute('aria-pressed', String(isSelected));
        optBtn.textContent = option.label;
        optBtn.addEventListener('click', () => handleOptionSelect(unit, check, option));
        optionsWrap.appendChild(optBtn);
      }
      fieldset.appendChild(optionsWrap);

      if (selectedId) {
        const chosen = check.options.find((o) => o.id === selectedId);
        if (chosen) {
          const feedback = el(
            'div',
            `dd-feedback ${chosen.correct ? 'dd-feedback-correct' : 'dd-feedback-incorrect'}`,
          );
          feedback.setAttribute('role', 'status');
          feedback.setAttribute('aria-live', 'polite');
          feedback.dataset.feedbackStatus = chosen.correct ? 'correct' : 'incorrect';
          feedback.appendChild(
            el('strong', undefined, chosen.correct ? 'Right answer: ' : 'Not quite: '),
          );
          feedback.appendChild(document.createTextNode(chosen.explanation));
          if (!chosen.correct) {
            const hint = el(
              'p',
              'dd-feedback-hint',
              'Select another option to compare explanations. This unit is scheduled for review tomorrow.',
            );
            feedback.appendChild(hint);
          }
          fieldset.appendChild(feedback);
        }
      }

      checksSection.appendChild(fieldset);
    }
    article.appendChild(checksSection);

    // Session completion result
    if (session.recorded && session.nextReviewAt) {
      const resultBox = el(
        'div',
        `dd-result ${session.recordedOutcome === 'correct' ? 'dd-result-pass' : 'dd-result-review'}`,
      );
      resultBox.dataset.unitResult = session.recordedOutcome ?? '';
      resultBox.setAttribute('role', 'status');
      resultBox.setAttribute('aria-live', 'polite');

      const summaryText =
        session.recordedOutcome === 'correct'
          ? `Unit complete! Saved locally — next review due ${session.nextReviewAt}.`
          : `Saved locally — because a check was missed, this unit is due tomorrow (${session.nextReviewAt}) for a quick refresher.`;
      resultBox.appendChild(el('p', 'dd-result-text', summaryText));

      const nextTarget =
        rec.dueUnits.find((u) => u.id !== unit.id) ??
        rec.nextNewUnit ??
        pack.units.find((u) => u.number === unit.number + 1) ??
        null;

      if (nextTarget) {
        const nextBtn = el(
          'button',
          'dd-btn dd-btn-primary',
          `Next: Unit ${nextTarget.number} — ${nextTarget.title}`,
        );
        nextBtn.type = 'button';
        nextBtn.dataset.nextUnit = nextTarget.id;
        nextBtn.addEventListener('click', () => selectUnit(nextTarget.id));
        resultBox.appendChild(nextBtn);
      }
      article.appendChild(resultBox);
    }

    // Deep-dive links & official sources
    const footer = el('footer', 'dd-lesson-footer');
    footer.dataset.unitLinks = '';

    const actionsRow = el('div', 'dd-deep-links');
    const parentLink = el('a', 'dd-link-card');
    parentLink.href = `${pack.parentModulePath}#${unit.parentAnchor}`;
    parentLink.dataset.parentLink = '';
    parentLink.append(
      el('span', 'dd-link-kicker', 'Full module section'),
      el('span', 'dd-link-main', `${unit.parentSectionTitle} →`),
    );

    const labLink = el('a', 'dd-link-card');
    labLink.href = unit.labUrl;
    labLink.target = '_blank';
    labLink.rel = 'noopener noreferrer';
    labLink.dataset.labLink = '';
    labLink.append(
      el('span', 'dd-link-kicker', 'Hands-on Killercoda lab'),
      el('span', 'dd-link-main', `Launch ${unit.labId} ↗`),
    );

    actionsRow.append(parentLink, labLink);
    footer.appendChild(actionsRow);

    const sourcesWrap = el('div', 'dd-sources');
    sourcesWrap.appendChild(el('span', 'dd-sources-label', 'Official documentation: '));
    unit.sources.forEach((src, index) => {
      if (index > 0) sourcesWrap.appendChild(document.createTextNode(' · '));
      const a = el('a', 'dd-source-link', src.title);
      a.href = src.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      sourcesWrap.appendChild(a);
    });
    footer.appendChild(sourcesWrap);

    article.appendChild(footer);
    unitEl!.appendChild(article);
  }

  function render(): void {
    const today = getToday();
    const rec = getDailyRecommendation(pack.units, state, today, SESSION_BUDGET_MINUTES);
    renderNotice();
    renderStats(rec);
    renderPlan(rec);
    renderNav(today);
    renderUnit(today, rec);
  }

  render();
  root.dataset.dailyMounted = 'true';

  return {
    destroy: () => {
      delete root.dataset.dailyMounted;
    },
  };
}

if (typeof document !== 'undefined') {
  const init = () => {
    const root = document.querySelector<HTMLElement>('[data-daily-root]');
    if (root && root.dataset.dailyMounted !== 'true') {
      mountDailyPlayer(root);
    }
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
}
