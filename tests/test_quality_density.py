"""Density measurement tests (#388; the density numbers are diagnostics, #3744)."""
from __future__ import annotations

from scripts.quality.density import evaluate_text


def test_evaluate_text_strips_code_blocks_from_prose():
    """Code blocks must NOT count toward prose_words — they are scaffolding."""
    text = """\
A short opening paragraph that should count as prose.

```bash
this is a code block with many words none of which should be in prose_words
this is a code block with many words none of which should be in prose_words
```

A second prose paragraph that also counts.
"""
    m = evaluate_text(text)
    # Two paragraphs, each ~10 words → ~20 prose words; code block excluded.
    assert m.prose_paragraphs == 2
    assert m.prose_words < 30  # well below the code block's word count
