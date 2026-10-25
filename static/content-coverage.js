function renderCoverage(briefing) {
  const c = briefing?.content_coverage, en = c?.locales?.en, m = c?.milestones?.prerequisites_linux;
  const b = $('#coverage-badge'), line = $('#coverage-counts'), milestone = $('#coverage-milestone');
  if (!en || !m || c.status === 'unavailable') {
    b.textContent = 'Unknown'; line.textContent = 'Coverage evidence unavailable'; milestone.textContent = 'No acceptance inferred'; tone(b, 'amber'); return;
  }
  b.textContent = c.coverage_health === 'known' ? 'Recorded evidence' : 'Evidence needs attention'; tone(b, 'amber');
  line.textContent = `${en.review_recorded} / ${en.total} pages with review records · ${en.needs_revision} need revision · ${en.acceptance_recorded} acceptance records`;
  milestone.textContent = `Prerequisites + Linux: ${m.review_recorded} / ${m.total} review records · ${m.acceptance_recorded} acceptance records. Ukrainian parked. Records are not exhaustive clearance.`;
}
