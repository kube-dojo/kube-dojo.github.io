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
  let selectedTrack = null, ukOpen = false;
  let trackButtons = [];
  const labels = ['Accepted', 'Current unaccepted', 'Revision', 'Stale', 'Invalid', 'No review recorded'];
  const order = ['prerequisites', 'linux', 'k8s', 'cloud', 'platform', 'on-premises', 'ai', 'ai-ml-engineering', 'ai-history', 'shared'];
  const names = {'prerequisites': 'Prerequisites', 'linux': 'Linux', 'k8s': 'Kubernetes', 'cloud': 'Cloud', 'platform': 'Platform', 'on-premises': 'On-Premises', 'ai': 'AI', 'ai-ml-engineering': 'AI/ML Engineering', 'ai-history': 'AI History', 'shared': 'Shared'};
  function processTime(info) {
    if (!info || !['running', 'completed'].includes(info.status) || !Number.isSafeInteger(info.elapsed_seconds) || info.elapsed_seconds < 0) return 'Not measured';
    const seconds = info.elapsed_seconds, hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds % 3600 / 60);
    return `${info.status} · ${hours ? `${hours}h ` : ''}${minutes ? `${minutes}m ` : ''}${seconds % 60}s · ${info.scope}`;
  }
  function meter(values, title) {
    const bar = document.createElement('div'), parts = coveragePartition(values);
    bar.className = 'cc-meter';
    bar.setAttribute('aria-label', `${title}: ${labels.map((label, i) => `${label} ${parts[i]}`).join(', ')}`);
    bar.setAttribute('role', 'img');
    parts.forEach((count, i) => {
      const segment = document.createElement('span');
      segment.className = `cc-segment cc-s${i}`;
      segment.style.width = `${values.total ? count / values.total * 100 : 0}%`;
      segment.title = `${labels[i]}: ${count}`;
      bar.append(segment);
    });
    return bar;
  }
  function pageTrack(page) {
    const path = page.locale === 'uk' ? page.path.replace(/^uk\//, '') : page.path;
    return path.includes('/') ? path.split('/')[0] : 'shared';
  }
  function renderVisuals(data, rebuild) {
    const container = find('cc-tracks');
    if (rebuild) {
      if (container.children[1]) ukOpen = container.children[1].open;
      container.replaceChildren(); trackButtons = [];
    }
    for (const locale of ['en', 'uk']) {
      const totals = data.locales[locale], tracks = data.tracks[locale];
      if (!coveragePartition(totals) || !tracks || typeof tracks !== 'object' || Array.isArray(tracks))
        throw new Error('Invalid coverage counters');
      const values = Object.values(tracks), fields = ['total', 'acceptance_recorded', 'review_recorded', 'needs_revision', 'stale', 'invalid', 'unreviewed'];
      if (values.some(value => !coveragePartition(value)) ||
          fields.some(key => values.reduce((sum, track) => sum + track[key], 0) !== totals[key]))
        throw new Error('Invalid coverage counters');
      if (!rebuild) continue;
      const section = document.createElement(locale === 'uk' ? 'details' : 'section');
      if (locale === 'uk') { section.open = ukOpen; section.addEventListener('toggle', () => { if (container.children[1] === section) ukOpen = section.open; }); }
      section.append(text(locale === 'uk' ? 'summary' : 'h3', `${locale.toUpperCase()}${locale === 'uk' ? ' (parked)' : ''}: ${totals.acceptance_recorded}/${totals.total} accepted`));
      section.append(meter(totals, `${locale.toUpperCase()} all pages`));
      const legend = document.createElement('div'); legend.className = 'cc-legend';
      coveragePartition(totals).forEach((count, i) => {
        const item = text('span', `${labels[i]}: ${count}`); item.className = `cc-key cc-k${i}`; legend.append(item);
      });
      section.append(legend);
      const grid = document.createElement('div'); grid.className = 'cc-track-grid';
      const sorted = Object.entries(tracks).sort(([a], [b]) => (order.indexOf(a) < 0 ? order.length : order.indexOf(a)) - (order.indexOf(b) < 0 ? order.length : order.indexOf(b)) || a.localeCompare(b));
      for (const [name, values] of sorted) {
        const card = document.createElement('button'); card.type = 'button'; card.className = 'cc-track';
        card.append(text('strong', names[name] || name), text('span', `${values.acceptance_recorded}/${values.total} accepted`), meter(values, `${locale.toUpperCase()} ${name}`), text('small', `${values.review_recorded} reviews · ${values.needs_revision} need revision`));
        trackButtons.push({card, locale, name});
        card.addEventListener('click', () => { selectedTrack = {locale, name}; find('cc-locale').value = locale; updateSelection(); render(); });
        grid.append(card);
      }
      section.append(grid);
      container.append(section);
    }
    updateSelection();
  }
  function updateSelection() {
    for (const item of trackButtons) item.card.setAttribute('aria-pressed', String(!!selectedTrack && item.locale === selectedTrack.locale && item.name === selectedTrack.name));
  }
  function render() {
    if (!report) return;
    const rows = find('cc-rows');
    const opened = new Set(Array.from(rows.children).filter(row => row.open).map(row => row.dataset.path));
    const scroll = rows.scrollTop;
    rows.replaceChildren();
    const query = find('cc-search').value.toLowerCase().trim();
    const locale = find('cc-locale').value;
    const status = find('cc-status').value;
    const work = find('cc-work').value;
    const pages = (report?.pages || []).filter(page =>
      (!locale || page.locale === locale) && (!selectedTrack || (page.locale === selectedTrack.locale && pageTrack(page) === selectedTrack.name)) && (!query || page.path.toLowerCase().includes(query)) &&
      (!status || page.receipt_status === status || page[status] === true) && (!work || page.work.state === work));
    find('cc-count').textContent = `${pages.length} pages shown`;
    if (selectedTrack) {
      const clear = text('button', `Track: ${selectedTrack.locale.toUpperCase()} ${names[selectedTrack.name] || selectedTrack.name} · Clear`);
      clear.type = 'button'; clear.className = 'cc-clear'; clear.addEventListener('click', () => { selectedTrack = null; updateSelection(); render(); });
      find('cc-count').append(clear);
    }
    for (const page of pages) {
      const detail = document.createElement('details');
      detail.dataset.path = page.path;
      detail.open = opened.has(page.path);
      const state = page.receipt_status === 'stale' ? 3 : page.receipt_status === 'invalid' ? 4 : page.acceptance_recorded ? 0 : page.needs_revision ? 2 : page.receipt_status === 'current' ? 1 : 5;
      detail.className = `cc-page cc-page${state}`;
      detail.append(text('summary', `${page.path} · ${page.locale.toUpperCase()} · ${labels[state]} · work: ${page.work.state} · process time: ${processTime(page.process_time)}`));
      detail.append(text('p', `${page.path} · ${page.type} · ${page.receipt_status} · ${page.disposition || 'unreviewed'} · ${page.acceptance_recorded ? 'acceptance recorded' : 'acceptance not recorded'}`));
      detail.append(text('p', `Acceptance blockers: ${page.reasons.join('; ') || 'none recorded; see supplied assertion caveat'}`));
      detail.append(text('p', `Recorded work: ${page.work.state} · ${page.work.summary || 'No current work record'} · Next: ${page.work.next_action || 'unknown'} · Updated: ${page.work.updated_at || 'unknown'} · Review calls: ${page.work.review.spent ?? 'unknown'}/${page.work.review.ceiling ?? 'unknown'} (recorded total, not launch permission)`));
      detail.append(text('p', `Process time: ${processTime(page.process_time)}. Elapsed time includes waits and queue; active effort is not measured.`));
      detail.append(text('p', `Work evidence: ${page.work.evidence_refs.join('; ') || 'none recorded'}`));
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
          !data.parked_locales.includes('uk') || data.parked_locales.includes('en') ||
          !['known', 'unknown'].includes(data.coverage_health) || !Object.keys(data.locales).length ||
          Object.values(data.locales).some(value => !value || ['acceptance_recorded', 'total', 'review_recorded', 'needs_revision', 'unreviewed', 'stale', 'invalid']
            .some(key => !Number.isInteger(value[key]) || value[key] < 0))) throw new Error('Invalid coverage response');
      const changed = !report || JSON.stringify(report.pages) !== JSON.stringify(data.pages);
      const visualsChanged = !report || JSON.stringify([report.locales, report.tracks]) !== JSON.stringify([data.locales, data.tracks]);
      renderVisuals(data, visualsChanged);
      report = data;
      summary = `${data.status} · health ${data.coverage_health} · fetched ${new Date().toLocaleTimeString()}`;
      find('cc-summary').textContent = summary;
      find('cc-work-summary').textContent = `Recorded work: ${Object.entries(data.work_summary).map(([state, count]) => `${state} ${count}`).join(' · ')}`;
      find('cc-note').textContent = [data.caveat, ...(data.errors || []), ...(data.receipt_errors || []), ...(data.work_errors || [])].join(' ');
      if (changed) render();
    } catch (error) {
      if (version !== requestVersion) return;
      report = null;
      find('cc-rows').replaceChildren();
      find('cc-tracks').replaceChildren();
      find('cc-count').textContent = '';
      find('cc-work-summary').textContent = '';
      find('cc-summary').textContent = `Canonical coverage unavailable / unknown: ${error.message}`;
      find('cc-note').textContent = 'No current canonical result. Legacy pipeline progress below remains separate.';
    }
  }
  for (const id of ['cc-search', 'cc-locale', 'cc-status', 'cc-work']) find(id).addEventListener('input', () => {
    if (id === 'cc-locale') { selectedTrack = null; updateSelection(); }
    render();
  });
  find('refresh').addEventListener('click', refreshCoverage);
  refreshCoverage();
  setInterval(refreshCoverage, 60000);
})();
