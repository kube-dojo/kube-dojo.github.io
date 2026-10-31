"""The monitor renderer supplies only page structure; APIs remain the data source."""
import importlib.util
from pathlib import Path


def test_monitor_shells_are_separate_and_use_shared_assets():
    path = Path(__file__).resolve().parents[1] / 'scripts/local_api_monitor.py'
    spec = importlib.util.spec_from_file_location('monitor_renderer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    overview = module.render_monitor_page(top_nav='<nav>Nav</nav>', chrome='<div>Search</div>', nav_css='.nav{}')
    operations = module.render_monitor_page(operations=True)
    assert '<nav>Nav</nav><div>Search</div>' in overview and '<style>.nav{}</style>' in overview
    assert 'data-monitor-view="overview"' in overview and 'id="coverage-body"' in overview and 'id="work-body"' in overview
    assert 'data-monitor-view="operations"' in operations and all(f'id="{name}-body"' in operations for name in ('leases', 'pipeline', 'services', 'activity'))
    for page in (overview, operations):
        assert '/static/content-coverage.js' in page and '/static/monitor.js' in page and '/static/monitor.css' in page
        assert '<form' not in page and 'method="post"' not in page.lower()
