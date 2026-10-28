/* All acceptance decisions and counts come from the canonical report. */
function coveragePartition(v) {
  const keys = ['total', 'acceptance_recorded', 'review_recorded', 'needs_revision', 'stale', 'invalid', 'unreviewed'];
  if (!v || keys.some(key => !Number.isSafeInteger(v[key]) || v[key] < 0)) return null;
  const parts = [v.acceptance_recorded, v.review_recorded - v.acceptance_recorded - v.needs_revision,
    v.needs_revision, v.stale, v.invalid, v.unreviewed - v.stale - v.invalid];
  return parts.every(n => n >= 0) && parts.reduce((a, b) => a + b, 0) === v.total ? parts : null;
}
function coveragePercent(v) {
  return v.total ? Math.min(v.acceptance_recorded < v.total ? 99.9 : 100, 100 * v.acceptance_recorded / v.total).toFixed(1) : '0.0';
}
function renderCoverage(briefing) {
  const c = briefing?.content_coverage, en = c?.locales?.en, uk = c?.locales?.uk;
  const b = $('#coverage-badge'), line = $('#coverage-counts'), milestone = $('#coverage-milestone');
  const qb = $('#quality-summary-badge'), qc = $('#quality-summary-counts'), bar = $('#coverage-progress');
  const parts = coveragePartition(en);
  if (!parts || !coveragePartition(uk) || !Array.isArray(c?.parked_locales) ||
      !c.parked_locales.includes('uk') || c.parked_locales.includes('en') ||
      !['ok', 'needs_attention'].includes(c.status) || !['known', 'unknown'].includes(c.coverage_health)) {
    b.textContent = qb.textContent = 'Unknown';
    line.textContent = qc.textContent = 'Coverage evidence unavailable';
    milestone.textContent = 'No acceptance inferred'; bar.hidden = true;
    bar.value = 0; bar.max = 1; tone(b, 'amber'); tone(qb, 'amber'); return;
  }
  b.textContent = qb.textContent = c.coverage_health === 'known' ? 'Recorded evidence' : 'Health unknown';
  tone(b, 'amber'); tone(qb, 'amber');
  line.textContent = qc.textContent = `${en.acceptance_recorded} / ${en.total} accepted · ${coveragePercent(en)}%`;
  milestone.textContent = `${parts[1]} current unaccepted · ${parts[2]} need revision · ${parts[3]} stale · UK parked: ${uk.acceptance_recorded}/${uk.total}`;
  bar.max = en.total || 1; bar.value = en.acceptance_recorded; bar.hidden = !en.total;
}
