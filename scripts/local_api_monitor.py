"""Read-only overview and operations page shells for the local monitor."""


def render_monitor_page(*, operations=False, top_nav='', chrome='', nav_css='') -> str:
    title = 'Operations' if operations else 'Site overview'
    if operations:
        sections = '''
        <div class="monitor-heading"><div><h1>Operations</h1><p>Independent snapshots from the local services.</p></div>
          <button id="monitor-refresh" type="button">Refresh</button></div>
        <div class="monitor-ops">
          <section id="leases"><div class="section-title"><h2>Active leases</h2><span id="leases-time">Not fetched</span></div><div id="leases-body" role="status">Loading…</div></section>
          <section id="pipeline"><div class="section-title"><h2>Pipeline snapshot</h2><span id="pipeline-time">Not fetched</span></div><div id="pipeline-body" role="status">Loading…</div></section>
          <section id="services"><div class="section-title"><h2>Runtime services</h2><span id="services-time">Not fetched</span></div><div id="services-body" role="status">Loading…</div></section>
          <section id="activity"><div class="section-title"><h2>Recent activity</h2><span id="activity-time">Not fetched</span></div><div id="activity-body" role="status">Loading…</div></section>
        </div>
        <details class="monitor-diagnostics"><summary>Diagnostics</summary><p>Raw read-only snapshots:</p>
          <a href="/api/pipeline/leases">Leases</a> · <a href="/api/pipeline/v2/status">Pipeline</a> ·
          <a href="/api/runtime/services">Services</a> · <a href="/api/activity?limit=15">Activity</a></details>'''
    else:
        sections = '''
        <div class="monitor-heading"><div><h1>Site overview</h1><p>Recorded acceptance and the work currently documented for this site.</p></div>
          <button id="monitor-refresh" type="button">Refresh</button></div>
        <div class="monitor-overview"><section class="monitor-coverage" aria-labelledby="coverage-heading">
          <div class="section-title"><div><h2 id="coverage-heading">Coverage by track</h2><p>Acceptance is separate from preparation and review.</p></div><span id="coverage-time">Not fetched</span></div>
          <div id="coverage-body" role="status">Loading canonical coverage…</div>
        </section>
        <section class="monitor-work" aria-labelledby="work-heading">
          <div class="section-title"><div><h2 id="work-heading">Recorded work</h2><p>As recorded at the time shown; this is not a live heartbeat.</p></div><a href="/quality">All pages</a></div>
          <div id="work-body" role="status">Loading recorded work…</div>
        </section></div>'''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · KubeDojo Local Monitor</title><link rel="stylesheet" href="/static/design-system.css">
<link rel="stylesheet" href="/static/monitor.css"><style>{nav_css}</style></head>
<body data-monitor-view="{'operations' if operations else 'overview'}">{top_nav}{chrome}<main class="monitor-shell">
{sections}</main><script src="/static/content-coverage.js"></script><script src="/static/monitor.js"></script></body></html>'''
