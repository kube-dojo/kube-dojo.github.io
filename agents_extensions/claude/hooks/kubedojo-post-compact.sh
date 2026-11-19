#!/bin/bash
# Hook: PostCompact — injects context after compaction so Claude doesn't lose track.

# Skip in non-interactive mode
if [ -n "$CLAUDE_NON_INTERACTIVE" ] || [ -n "$KUBEDOJO_PIPELINE" ] || [ -n "$GEMINI_SESSION" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
CONTEXT=""

# 1. Pipeline status
if [ -f "$PROJECT_DIR/.pipeline/state.yaml" ]; then
  PIPELINE_STATUS=$(.venv/bin/python -c "
import yaml
state = yaml.safe_load(open('$PROJECT_DIR/.pipeline/state.yaml').read()) or {}
modules = state.get('modules', {})
by_phase = {}
for m in modules.values():
    p = m.get('phase', 'unknown')
    by_phase[p] = by_phase.get(p, 0) + 1
parts = [f'{v} {k}' for k, v in sorted(by_phase.items())]
print(', '.join(parts))
" 2>/dev/null)
  if [ -n "$PIPELINE_STATUS" ]; then
    CONTEXT="$CONTEXT
PIPELINE STATUS: $PIPELINE_STATUS"
  fi
fi

# 2. Key reminders
CONTEXT="$CONTEXT
KEY REMINDERS:
  - .venv/bin/python only (hook enforces this)
  - Quality: 33/40 sum + every dimension >= 4 (D1-D8)
  - Workflow: Gemini writes, Claude reviews strictly
  - Pipeline: .venv/bin/python scripts/v1_pipeline.py status
  - UK sync: .venv/bin/python scripts/uk_sync.py detect
  - STATUS.md: read first, update before ending
  - MEMORY: Read this checkout's Claude project memory."

printf '{"additionalContext": %s}' "$(printf '%s' "CONTEXT RESTORED AFTER COMPACTION:$CONTEXT" | jq -Rs '.')"
exit 0
