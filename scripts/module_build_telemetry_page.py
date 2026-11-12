"""HTML page for the KubeDojo module-build telemetry dashboard (#1973).

Renders module-build token rollups from the ``/api/telemetry/module-builds``
JSON endpoint. Kept out of ``local_api.py`` so the HTML/JS blob stays separate.
"""
from __future__ import annotations

# Dark-theme: consume the shared design-system tokens (static/design-system.css,
# loaded via ds_link) so this page matches the rest of the Local Monitor. The old
# hardcoded light-theme hex (#fff cards, #1e3a8a headings, #64748b text) rendered
# dark-on-dark and was unreadable — kube-dojo/kube-dojo.github.io#1976.
_PAGE_CSS = """
.mb-main{max-width:1180px;margin:0 auto;padding:1.2rem}
.mb-head h1{font-size:1.4rem;margin:0 0 .2rem;color:var(--text)}
.mb-sub{color:var(--text-secondary);font-size:.9rem;margin-bottom:1rem}
.mb-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.75rem;margin:1rem 0 1.4rem}
.mb-card{background:var(--surface-0);border:1px solid var(--border);border-radius:.5rem;padding:.65rem .75rem}
.mb-card .label{color:var(--text-dim);font-size:.75rem;text-transform:uppercase;letter-spacing:.03em}
.mb-card .value{font-size:1.15rem;font-weight:700;color:var(--accent);margin-top:.15rem}
.mb-section{margin:1.6rem 0}
.mb-section h2{font-size:1.05rem;color:var(--text);margin:0 0 .5rem}
table.mb{border-collapse:collapse;width:100%;font-size:.84rem;background:var(--surface-0);color:var(--text)}
table.mb th,table.mb td{border:1px solid var(--border);padding:.35rem .5rem;text-align:right;vertical-align:top}
table.mb th:first-child,table.mb td:first-child,
table.mb th:nth-child(2),table.mb td:nth-child(3),
table.mb td.meta{text-align:left}
table.mb th{background:var(--surface-1);color:var(--text-secondary);font-weight:600}
table.mb td.k{font-weight:600;text-align:left}
table.mb td.meta{color:var(--text-secondary);font-size:.8rem}
table.mb td.yes{color:var(--green);font-weight:600}
table.mb td.no{color:var(--text-dim)}
.mb-legend{color:var(--text-secondary);font-size:.8rem;margin-top:1.2rem;border-top:1px solid var(--border);padding-top:.6rem}
.empty{color:var(--text-dim);font-style:italic;padding:.5rem}
"""

_PAGE_JS = """
function fmt(v){return v==null?'\\u2014':String(v);}
function money(v){return v==null?'\\u2014':'$'+Number(v).toFixed(4);}
function el(tag,text,cls){var e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;}
function renderTotals(t){
  var host=document.getElementById('mb-totals');
  host.textContent='';
  var cards=[
    ['runs',t.runs],['swarm',t.swarm_runs],['solo',t.solo_runs],['participants',t.participants],
    ['prompt tok',t.prompt_tokens],['response tok',t.response_tokens],['total tok',t.total_tokens],['cost est',money(t.cost_usd_est)]
  ];
  cards.forEach(function(pair){
    var card=el('div',null,'mb-card');
    card.appendChild(el('div',pair[0],'label'));
    card.appendChild(el('div',fmt(pair[1]),'value'));
    host.appendChild(card);
  });
}
function renderRuns(rows){
  var host=document.getElementById('mb-runs');
  host.textContent='';
  if(!rows||!rows.length){host.appendChild(el('div','no module-build records yet','empty'));return;}
  var table=el('table',null,'mb');
  var thead=el('thead'),htr=el('tr');
  ['track','slug','run','swarm','tokens','cost','participants','source'].forEach(function(c){htr.appendChild(el('th',c));});
  thead.appendChild(htr);table.appendChild(thead);
  var tb=el('tbody');
  rows.forEach(function(r){
    var tr=el('tr');
    tr.appendChild(el('td',r.track,'meta'));
    tr.appendChild(el('td',r.slug,'meta'));
    tr.appendChild(el('td',r.run_id,'k'));
    var sw=el('td',r.swarm_used?'yes ('+r.swarm_label+')':'no',r.swarm_used?'yes':'no');
    tr.appendChild(sw);
    tr.appendChild(el('td',fmt((r.totals||{}).total_tokens)));
    tr.appendChild(el('td',money((r.totals||{}).cost_usd_est)));
    tr.appendChild(el('td',fmt((r.totals||{}).participants)));
    tr.appendChild(el('td',r.source,'meta'));
    tb.appendChild(tr);
  });
  table.appendChild(tb);host.appendChild(table);
}
async function loadModuleBuilds(){
  try{
    var r=await fetch('/api/telemetry/module-builds?limit=100');
    var d=await r.json();
    document.getElementById('mb-summary').textContent=
      d.records_total+' module-build records \\u00b7 generated '+d.generated_at;
    renderTotals(d.totals||{});
    renderRuns(d.runs||[]);
  }catch(e){document.getElementById('mb-summary').textContent='failed to load module builds: '+e;}
}
loadModuleBuilds();
"""


def render_module_builds_page_html(*, top_nav: str = "", nav_css: str = "", ds_link: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Build telemetry - KubeDojo Local Monitor</title>
  {ds_link}
  <style>
{nav_css}
{_PAGE_CSS}
  </style>
</head>
<body>
  {top_nav}
  <main class="mb-main">
    <div class="mb-head">
      <h1>Build telemetry</h1>
      <div class="mb-sub" id="mb-summary">loading module builds&hellip;</div>
    </div>

    <div id="mb-totals" class="mb-cards"></div>

    <div class="mb-section">
      <h2>Module build runs</h2>
      <div id="mb-runs"><div class="empty">loading&hellip;</div></div>
    </div>

    <div class="mb-legend">
      Module builds: record finalize-time token rollups with
      <code>scripts/finalize_module.sh</code> (which calls
      <code>python scripts/agent_telemetry.py record-build</code>) or
      <code>POST /api/telemetry/module-builds</code>.
    </div>
  </main>
  <script>
{_PAGE_JS}
  </script>
</body>
</html>"""
