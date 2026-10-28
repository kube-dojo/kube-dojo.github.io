/* Canonical all-page reporting; acceptance is evaluated only by the server. */
(() => {
  const find = id => document.getElementById(id);
  const text = (tag, value) => {
    const element = document.createElement(tag);
    element.textContent = value;
    return element;
  };
  let report = null;
  let requestVersion = 0;
  let summary = '';
  function render() {
    if (!report) return;
    const rows = find('cc-rows');
    const opened = new Set(Array.from(rows.children).filter(row => row.open).map(row => row.dataset.path));
    const scroll = rows.scrollTop;
    rows.replaceChildren();
    const query = find('cc-search').value.toLowerCase().trim();
    const locale = find('cc-locale').value;
    const status = find('cc-status').value;
    const pages = (report?.pages || []).filter(page =>
      (!locale || page.locale === locale) && (!query || page.path.toLowerCase().includes(query)) &&
      (!status || page.receipt_status === status || page[status] === true));
    find('cc-count').textContent = `${pages.length} pages shown`;
    for (const page of pages) {
      const detail = document.createElement('details');
      detail.dataset.path = page.path;
      detail.open = opened.has(page.path);
      const accepted = page.acceptance_recorded ? 'acceptance recorded' : 'acceptance not recorded';
      detail.append(text('summary', `${page.locale.toUpperCase()} · ${page.path} · ${page.type} · ${page.receipt_status} · ${page.disposition || 'unreviewed'} · ${accepted}`));
      detail.append(text('p', `Acceptance blockers: ${page.reasons.join('; ') || 'none recorded; see supplied assertion caveat'}`));
      const layers = text('pre', Object.entries(page.layers).map(([key, value]) => `${key}: ${value}`).join('\n'));
      layers.style.whiteSpace = 'pre-wrap';
      detail.append(layers);
      for (const [kind, refs] of Object.entries(page.references)) {
        detail.append(text('strong', `${kind} (${page.receipt_status} receipt; recorded references, not proof; up to 30, each limited to 1000 characters):`));
        const list = document.createElement('ul');
        for (const ref of refs) list.append(text('li', ref)); // Plain text: never executable links.
        if (!refs.length) list.append(text('li', 'None recorded'));
        detail.append(list);
      }
      rows.append(detail);
    }
    if (!pages.length) rows.append(text('p', 'No pages match filters.'));
    rows.scrollTop = scroll;
  }
  async function refreshCoverage() {
    const version = ++requestVersion;
    find('cc-summary').textContent = report ? `${summary} · refreshing…` : 'Loading canonical coverage…';
    try {
      const response = await fetch('/api/content/coverage', {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (version !== requestVersion) return;
      if (data.status === 'unavailable') throw new Error('Coverage unavailable');
      if (!data.locales || Array.isArray(data.locales) || !Array.isArray(data.pages) ||
          !Array.isArray(data.parked_locales) || !['ok', 'needs_attention'].includes(data.status) ||
          !['known', 'unknown'].includes(data.coverage_health) || !Object.keys(data.locales).length ||
          Object.values(data.locales).some(value => !value || ['acceptance_recorded', 'total', 'review_recorded', 'needs_revision', 'unreviewed', 'stale', 'invalid']
            .some(key => !Number.isInteger(value[key]) || value[key] < 0))) throw new Error('Invalid coverage response');
      const changed = !report || JSON.stringify(report.pages) !== JSON.stringify(data.pages);
      report = data;
      const counts = Object.entries(data.locales).map(([locale, value]) =>
        `${locale.toUpperCase()}${data.parked_locales.includes(locale) ? ' (parked)' : ''}: ${value.acceptance_recorded}/${value.total} acceptance recorded; ${value.review_recorded} current reviews; ${value.needs_revision} need revision; ${value.unreviewed} without current review; ${value.stale} stale; ${value.invalid} invalid`);
      summary = `${data.status} · health ${data.coverage_health} · fetched ${new Date().toLocaleTimeString()}. ${counts.join(' | ')}`;
      find('cc-summary').textContent = summary;
      find('cc-note').textContent = [data.caveat, ...(data.errors || []), ...(data.receipt_errors || [])].join(' ');
      if (changed) render();
    } catch (error) {
      if (version !== requestVersion) return;
      report = null;
      find('cc-rows').replaceChildren();
      find('cc-count').textContent = '';
      find('cc-summary').textContent = `Canonical coverage unavailable / unknown: ${error.message}`;
      find('cc-note').textContent = 'No current canonical result. Legacy pipeline progress below remains separate.';
    }
  }
  for (const id of ['cc-search', 'cc-locale', 'cc-status']) find(id).addEventListener('input', render);
  find('refresh').addEventListener('click', refreshCoverage);
  refreshCoverage();
  setInterval(refreshCoverage, 60000);
})();
