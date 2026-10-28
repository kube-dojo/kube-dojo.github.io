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
  function render() {
    const rows = find('cc-rows');
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
      const accepted = page.acceptance_recorded ? 'acceptance recorded' : 'acceptance not recorded';
      detail.append(text('summary', `${page.locale.toUpperCase()} · ${page.path} · ${page.type} · ${page.receipt_status} · ${page.disposition || 'unreviewed'} · ${accepted}`));
      detail.append(text('p', `Acceptance blockers: ${page.reasons.join('; ') || 'none recorded; see supplied assertion caveat'}`));
      const layers = text('pre', Object.entries(page.layers).map(([key, value]) => `${key}: ${value}`).join('\n'));
      layers.style.whiteSpace = 'pre-wrap';
      detail.append(layers);
      for (const [kind, refs] of Object.entries(page.references)) {
        detail.append(text('strong', `${kind} (recorded references; not proof; up to 30, each limited to 1000 characters):`));
        const list = document.createElement('ul');
        for (const ref of refs) list.append(text('li', ref)); // Plain text: never executable links.
        if (!refs.length) list.append(text('li', 'None recorded'));
        detail.append(list);
      }
      rows.append(detail);
    }
    if (!pages.length) rows.append(text('p', 'No pages match filters.'));
  }
  async function refreshCoverage() {
    const version = ++requestVersion;
    report = null;
    find('cc-summary').textContent = 'Loading canonical coverage…';
    find('cc-rows').replaceChildren();
    find('cc-count').textContent = '';
    try {
      const response = await fetch('/api/content/coverage', {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (version !== requestVersion) return;
      if (!data.locales || !Array.isArray(data.pages)) throw new Error('Invalid coverage response');
      report = data;
      const counts = Object.entries(data.locales).map(([locale, value]) =>
        `${locale.toUpperCase()}${data.parked_locales.includes(locale) ? ' (parked)' : ''}: ${value.acceptance_recorded}/${value.total} acceptance recorded; ${value.review_recorded} current reviews; ${value.needs_revision} need revision; ${value.unreviewed} without current review; ${value.stale} stale; ${value.invalid} invalid`);
      find('cc-summary').textContent = `${data.status} · health ${data.coverage_health} · fetched ${new Date().toLocaleTimeString()}. ${counts.join(' | ')}`;
      find('cc-note').textContent = [data.caveat, ...(data.errors || []), ...(data.receipt_errors || [])].join(' ');
      render();
    } catch (error) {
      if (version !== requestVersion) return;
      report = null;
      find('cc-rows').replaceChildren();
      find('cc-summary').textContent = `Canonical coverage unavailable / unknown: ${error.message}`;
      find('cc-note').textContent = 'No current canonical result. Legacy pipeline progress below remains separate.';
    }
  }
  for (const id of ['cc-search', 'cc-locale', 'cc-status']) find(id).addEventListener('input', render);
  find('refresh').addEventListener('click', refreshCoverage);
  refreshCoverage();
  setInterval(refreshCoverage, 60000);
})();
