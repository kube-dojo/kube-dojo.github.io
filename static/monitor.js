/* Read-only local snapshots. Acceptance is determined by the coverage API. */
(() => {
  const find = id => document.getElementById(id);
  const el = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = String(value);
    if (className) node.className = className;
    return node;
  };
  const safeText = value => typeof value === 'string' && value.trim() ? value.slice(0, 1000) : 'unknown';
  const nonnegative = value => Number.isSafeInteger(value) && value >= 0;
  const timestamp = value => nonnegative(value) && Number.isFinite(new Date(value * 1000).getTime()) ? new Date(value * 1000).toLocaleString() : null;
  const states = new Set(['preparing', 'prepared', 'awaiting_review', 'reviewing', 'review_failed', 'blocked']);
  const order = ['prerequisites', 'linux', 'k8s', 'cloud', 'platform', 'on-premises', 'ai', 'ai-ml-engineering', 'ai-history', 'shared'];
  const names = {prerequisites: 'Prerequisites', linux: 'Linux', k8s: 'Kubernetes', cloud: 'Cloud', platform: 'Platform', 'on-premises': 'On-Premises', ai: 'AI', 'ai-ml-engineering': 'AI/ML Engineering', 'ai-history': 'AI History', shared: 'Shared'};
  const severity = {blocked: 0, review_failed: 1, reviewing: 2, awaiting_review: 3, prepared: 4, preparing: 5};
  let version = 0;
  let ukOpen = false, ukSection = null;

  function requireCoverage(data) {
    if (!data || !['ok', 'needs_attention'].includes(data.status) || !['known', 'unknown'].includes(data.coverage_health) ||
        !Array.isArray(data.pages) || !Array.isArray(data.parked_locales) || !data.parked_locales.includes('uk') || data.parked_locales.includes('en')) throw Error('Invalid coverage response');
    for (const locale of ['en', 'uk']) {
      const total = data.locales?.[locale], tracks = data.tracks?.[locale];
      if (!coveragePartition(total) || !tracks || typeof tracks !== 'object' || Array.isArray(tracks)) throw Error('Invalid coverage counters');
      const values = Object.values(tracks);
      for (const field of ['total', 'acceptance_recorded', 'review_recorded', 'needs_revision', 'unreviewed', 'stale', 'invalid']) {
        if (values.some(x => !coveragePartition(x)) || values.reduce((sum, x) => sum + x[field], 0) !== total[field]) throw Error('Invalid track counters');
      }
    }
    if (data.pages.some(p => !p || typeof p.path !== 'string' || !['en', 'uk'].includes(p.locale) || !p.work ||
        typeof p.acceptance_recorded !== 'boolean' || (p.work.state === 'accepted') !== p.acceptance_recorded ||
        !['accepted', 'parked', 'unknown', ...states].includes(p.work.state))) throw Error('Invalid recorded-work response');
    for (const locale of ['en', 'uk']) {
      const pages = data.pages.filter(p => p.locale === locale);
      if (pages.length !== data.locales[locale].total || pages.filter(p => p.acceptance_recorded).length !== data.locales[locale].acceptance_recorded) throw Error('Invalid page totals');
    }
  }

  function renderCoverage(data) {
    requireCoverage(data);
    const coverage = el('div'), work = el('div');
    if (data.coverage_health === 'unknown') coverage.append(el('p', 'Coverage health is unknown; recorded counts may be incomplete.', 'monitor-error'));
    for (const locale of ['en', 'uk']) {
      const total = data.locales[locale], section = el(locale === 'uk' ? 'details' : 'section');
      if (locale === 'uk') { ukSection = section; section.open = ukOpen; section.addEventListener('toggle', () => { if (ukSection === section) ukOpen = section.open; }); }
      section.append(el(locale === 'uk' ? 'summary' : 'h3', locale === 'en' ? 'English' : 'Ukrainian (parked)'));
      section.append(el('p', `${total.acceptance_recorded} of ${total.total} pages accepted · ${total.review_recorded} current reviews`, 'monitor-total'));
      const legend = el('div', undefined, 'track-legend');
      for (const [name, label] of [['accepted', 'Accepted'], ['current', 'Current unaccepted'], ['revision', 'Revision'], ['stale', 'Stale / invalid'], ['unreviewed', 'No current review']]) {
        const item = el('span'), swatch = el('span', undefined, `legend-swatch bar-${name}`);
        item.append(swatch, el('span', label)); legend.append(item);
      }
      section.append(legend);
      const tracks = Object.entries(data.tracks[locale]).sort(([a], [b]) => {
        const index = name => order.includes(name) ? order.indexOf(name) : order.length;
        return index(a) - index(b) || a.localeCompare(b);
      });
      if (!tracks.length) section.append(el('p', 'No pages recorded in this locale.', 'monitor-note'));
      for (const [key, values] of tracks) {
        const row = el('div', undefined, 'track-row'), bar = el('div', undefined, 'track-bar');
        const parts = coveragePartition(values), classes = ['accepted', 'current', 'revision', 'stale', 'invalid', 'unreviewed'];
        const labels = ['accepted', 'current unaccepted', 'revision', 'stale', 'invalid', 'no current review'];
        bar.setAttribute('role', 'img');
        bar.setAttribute('aria-label', labels.map((label, i) => `${label}: ${parts[i]}`).join(', '));
        parts.forEach((count, i) => {
          const segment = el('span', undefined, `bar-${classes[i]}`);
          segment.style.width = `${values.total ? count / values.total * 100 : 0}%`;
          bar.append(segment);
        });
        const link = el('a', names[key] || key);
        link.href = key === 'shared' ? `/quality?locale=${locale}&track=shared` : `/quality?locale=${locale}&search=${encodeURIComponent((locale === 'uk' ? 'uk/' : '') + key + '/')}`;
        row.append(link, bar,
          el('span', `${values.acceptance_recorded}/${values.total} accepted · ${values.review_recorded} reviewed`, 'track-count'));
        section.append(row);
      }
      coverage.append(section);
    }
    coverage.append(el('p', 'A current review is evidence, not acceptance. No current review does not mean the page is missing.', 'monitor-note'));
    const english = data.pages.filter(page => page.locale === 'en');
    const counts = ['accepted', ...states, 'unknown'].map(state => [state, english.filter(p => p.work.state === state).length]);
    work.append(el('p', counts.filter(([, count]) => count > 0).map(([state, count]) => `${state.replaceAll('_', ' ')}: ${count}`).join(' · '), 'monitor-note'));
    if (Array.isArray(data.work_errors) && data.work_errors.length) work.append(el('p', 'Some work records are invalid or stale. See Quality for details.', 'monitor-error'));
    const queue = data.pages.filter(page => page.locale === 'en' && states.has(page.work.state));
    queue.sort((a, b) => severity[a.work.state] - severity[b.work.state] || safeText(b.work.updated_at).localeCompare(safeText(a.work.updated_at)) || a.path.localeCompare(b.path));
    if (!queue.length) work.append(el('p', 'No current work records. Unrecorded pages remain unknown.', 'monitor-note'));
    for (const page of queue) {
      const row = el('div', undefined, 'work-row'), top = el('div', undefined, 'work-top');
      const label = page.work.state.replaceAll('_', ' '), link = el('a', page.path);
      link.href = `/quality?locale=en&search=${encodeURIComponent(page.path)}`;
      top.append(el('span', label, `work-state ${page.work.state}`), link);
      const spent = page.work.review?.spent, ceiling = page.work.review?.ceiling;
      row.append(top, el('p', safeText(page.work.summary)), el('p', `Next: ${safeText(page.work.next_action)}`),
        el('p', `Recorded ${safeText(page.work.updated_at)} · Review calls: ${nonnegative(spent) ? spent : 'unknown'}/${nonnegative(ceiling) ? ceiling : 'unknown'} total allowance; not launch permission`, 'work-date'));
      work.append(row);
    }
    find('coverage-body').replaceChildren(coverage);
    find('work-body').replaceChildren(work);
  }

  function listRow(title, detail, time) {
    const row = el('div', undefined, 'ops-row');
    row.append(el('strong', title));
    if (detail) row.append(el('p', detail));
    if (time) row.append(el('p', time, 'ops-meta'));
    return row;
  }
  function renderLeases(data) {
    if (!data || data.exists !== true || !Array.isArray(data.active) || !nonnegative(data.count) || data.count !== data.active.length) throw Error('Lease data unavailable');
    const out = el('div');
    if (!data.active.length) out.append(el('p', 'No active leases in this snapshot.', 'monitor-note'));
    for (const lease of data.active) out.append(listRow(safeText(lease.module_key), `Phase: ${safeText(lease.phase)} · Holder: ${safeText(lease.leased_by)}`, timestamp(lease.lease_expires_at) ? `Expires at ${timestamp(lease.lease_expires_at)}` : 'Expiry unknown'));
    return out;
  }
  function renderPipeline(data) {
    if (!data || !data.counts || typeof data.counts !== 'object' || Array.isArray(data.counts) || !nonnegative(data.total_modules)) throw Error('Invalid pipeline snapshot');
    const entries = Object.entries(data.counts);
    if (!entries.length || entries.some(([, n]) => !nonnegative(n)) || entries.reduce((sum, [, n]) => sum + n, 0) !== data.total_modules) throw Error('Invalid pipeline counts');
    const out = el('div'); out.append(el('p', `${data.total_modules} modules in the pipeline snapshot. Queue completion is not page acceptance.`, 'monitor-note'));
    entries.forEach(([key, value]) => out.append(listRow(key.replaceAll('_', ' '), String(value))));
    return out;
  }
  function renderServices(data) {
    if (!data || !Array.isArray(data.services) || !nonnegative(data.total) || data.total !== data.services.length) throw Error('Invalid service snapshot');
    const out = el('div');
    if (!data.services.length) out.append(el('p', 'No services listed in this snapshot.', 'monitor-note'));
    for (const service of data.services) out.append(listRow(safeText(service.label || service.name), `Reported process status: ${safeText(service.status)}`));
    out.append(el('p', 'Process status is not a service-health or provider-health verdict.', 'monitor-note'));
    return out;
  }
  function renderActivity(data) {
    if (!data || !Array.isArray(data.items) || !nonnegative(data.count) || data.count !== data.items.length) throw Error('Invalid activity snapshot');
    const out = el('div');
    if (data.errors && Object.keys(data.errors).length) out.append(el('p', 'Some activity sources are unavailable; this list may be incomplete.', 'monitor-error'));
    if (!data.items.length) out.append(el('p', 'No recent activity in the available sources.', 'monitor-note'));
    for (const item of data.items) out.append(listRow(safeText(item.summary || item.kind), `Source: ${safeText(item.source)}${item.module_key ? ` · ${safeText(item.module_key)}` : ''}`, timestamp(item.at) ? `Recorded ${timestamp(item.at)}` : 'Recorded time unknown'));
    return out;
  }

  async function fetchSection(id, url, render, request) {
    const body = find(`${id}-body`), stamp = find(`${id}-time`);
    stamp.textContent = 'Refreshing…';
    try {
      const response = await fetch(url, {cache: 'no-store'});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (request !== version) return;
      if (id === 'coverage') render(data); else body.replaceChildren(render(data));
      stamp.textContent = `Fetched ${new Date().toLocaleTimeString()}`;
    } catch (error) {
      if (request !== version) return;
      body.replaceChildren(el('p', `Unavailable: ${safeText(error.message)}`, 'monitor-error'));
      if (id === 'coverage') find('work-body').replaceChildren(el('p', 'Recorded work unavailable.', 'monitor-error'));
      stamp.textContent = 'Unavailable';
    }
  }
  function refresh() {
    const request = ++version;
    if (document.body.dataset.monitorView === 'operations') {
      return Promise.all([
        fetchSection('leases', '/api/pipeline/leases', renderLeases, request),
        fetchSection('pipeline', '/api/pipeline/v2/status', renderPipeline, request),
        fetchSection('services', '/api/runtime/services', renderServices, request),
        fetchSection('activity', '/api/activity?limit=15', renderActivity, request),
      ]);
    }
    return fetchSection('coverage', '/api/content/coverage', renderCoverage, request);
  }
  find('monitor-refresh').addEventListener('click', refresh);
  refresh();
  setInterval(refresh, 60000);
})();
