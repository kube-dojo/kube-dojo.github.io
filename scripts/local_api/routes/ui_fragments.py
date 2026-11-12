from __future__ import annotations


DESIGN_SYSTEM_LINK = '<link rel="stylesheet" href="/static/design-system.css">'

POLL_STALE_CSS = """
    .poll-stale { opacity: 0.72; }
    .poll-stale[data-poll-ts]::after { content: " · stale"; color: var(--amber, #f59e0b); font-size: 0.85em; font-weight: 700; }
"""


def render_poll_stale_script() -> str:
    return """
<script>
(() => {
  const STALE_MS = 24 * 60 * 60 * 1000;
  window.setPollTs = function setPollTs(el, payload) {
    if (!el) return;
    let ts = payload?.generated_at ?? payload?.snapshot?.generated_at ?? payload?.freshness?.refresh_completed_at;
    if (ts == null || !Number.isFinite(Number(ts))) ts = Math.floor(Date.now() / 1000);
    const tsSec = Math.floor(Number(ts));
    el.dataset.pollTs = String(tsSec);
    const tsMs = tsSec * 1000;
    const stale = Number.isFinite(tsMs) && tsMs > 0 && Date.now() - tsMs > STALE_MS;
    el.classList.toggle("poll-stale", stale);
  };
  function markStalePolls() {
    document.querySelectorAll("[data-poll-ts]").forEach((el) => {
      const ts = Number(el.dataset.pollTs) * 1000;
      if (Number.isFinite(ts) && ts > 0 && Date.now() - ts > STALE_MS) {
        el.classList.add("poll-stale");
      }
    });
  }
  markStalePolls();
  setInterval(markStalePolls, 60000);
})();
</script>"""
