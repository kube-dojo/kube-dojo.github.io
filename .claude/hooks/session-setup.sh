#!/bin/bash
# Hook: SessionStart — validates environment and reports project state.
# Skips in headless/pipeline mode.

# Skip in non-interactive mode
if [ -n "$CLAUDE_NON_INTERACTIVE" ] || [ -n "$KUBEDOJO_PIPELINE" ] || [ -n "$GEMINI_SESSION" ]; then
  exit 0
fi

REPO_HINT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
if ! REPO_ROOT=$(git -C "$REPO_HINT" rev-parse --show-toplevel 2>/dev/null); then
  exit 0
fi
PRIMARY_WORKTREE=$(git -C "$REPO_ROOT" worktree list --porcelain | awk '/^worktree / {sub(/^worktree /, ""); print; exit}')
PRIMARY_BRANCH=$(git -C "$PRIMARY_WORKTREE" rev-parse --abbrev-ref HEAD)
if [ "$PRIMARY_BRANCH" != "main" ]; then
  printf '%b\n' "\033[31m[session-setup] PRIMARY TREE NOT ON main (currently '${PRIMARY_BRANCH}') — fix with: git -C ${PRIMARY_WORKTREE} checkout main\033[0m" >&2
  exit 1
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
ISSUES=()
INFO=()

# 1. Check .venv exists
if [ ! -f "$PROJECT_DIR/.venv/bin/python" ]; then
  ISSUES+=("VENV MISSING: .venv/bin/python not found. Create: python3 -m venv .venv && .venv/bin/pip install pyyaml")
fi

# 2. Check KubeDojo local API.
API_STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:8768/api/runtime/services" 2>/dev/null)
if [ "$API_STATUS" != "200" ]; then
  ISSUES+=("KubeDojo local API not running (127.0.0.1:8768) — run: bash scripts/cold-start.sh")
fi

# 3. Check optional MCP RAG server (for Ukrainian translations).
RAG_STATUS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:8766/sse" 2>/dev/null)
if [ "$RAG_STATUS" = "000" ]; then
  INFO+=("MCP RAG server not running (127.0.0.1:8766) — Ukrainian translation tools unavailable")
fi

# 4. Pipeline status
if [ -f "$PROJECT_DIR/.pipeline/state.yaml" ]; then
  DONE=$("$PROJECT_DIR/.venv/bin/python" -c "
import yaml
state = yaml.safe_load(open('$PROJECT_DIR/.pipeline/state.yaml').read()) or {}
modules = state.get('modules', {})
done = sum(1 for m in modules.values() if m.get('phase') == 'done')
total = len(modules)
failed = sum(1 for m in modules.values() if m.get('errors'))
print(f'{done}/{total} done, {failed} with errors')
" 2>/dev/null)
  if [ -n "$DONE" ]; then
    INFO+=("Pipeline: $DONE")
  fi
fi

# 5. Open GH issues (top 5)
if command -v gh >/dev/null 2>&1; then
  ISSUES_LIST=$(gh issue list --state open --limit 5 --json number,title 2>/dev/null | jq -r '.[] | "  #\(.number): \(.title)"' 2>/dev/null)
  if [ -n "$ISSUES_LIST" ]; then
    ISSUE_COUNT=$(gh issue list --state open --json number 2>/dev/null | jq 'length' 2>/dev/null)
    INFO+=("$ISSUE_COUNT open issue(s):
$ISSUES_LIST")
  fi
fi

# 6. Check MEMORY.md size
MEMORY_FILE="$HOME/.claude/projects/-Users-krisztiankoos-projects-kubedojo/memory/MEMORY.md"
if [ -f "$MEMORY_FILE" ]; then
  MEMORY_LINES=$(wc -l < "$MEMORY_FILE" | tr -d ' ')
  if [ "$MEMORY_LINES" -gt 150 ]; then
    ISSUES+=("MEMORY.md is $MEMORY_LINES lines (limit: 200). Trim before it gets truncated.")
  fi
fi

# 7. Stale `astro dev` server check. Vite/Astro dev servers leak memory over
# long uptimes — a forgotten one reached ~5.4 GB after 2.5 days (s182). RSS
# under-reports it (mostly compressed), so flag by UPTIME: any astro dev whose
# elapsed time shows days (etime contains '-') is almost certainly stale.
# start-docs.sh now auto-stops after 12h; this catches servers started manually.
STALE_DEV=$(/bin/ps -axo pid,etime,command 2>/dev/null | grep "astro dev" | grep -v grep | awk '$2 ~ /-/ {print "      PID "$1" (up "$2")"}')
if [ -n "$STALE_DEV" ]; then
  ISSUES+=("STALE astro dev server(s) running 1+ day — Vite leaks memory over long uptimes (can reach multi-GB). Kill, then restart only if needed (\`npx astro preview\` for view-only doesn't leak):
$STALE_DEV")
fi

# ============================================================================
# COMPACT ORIENTATION PACKET
# ============================================================================
# ROOT CAUSE (2026-06-29, the bug the user hit on every restart): additionalContext
# MUST stay small — a few KB. The previous version inlined the FULL ~15KB
# curriculum-orchestrator SKILL.md body PLUS the FULL ~34KB cold-start dump → ~50KB.
# The harness flags any hook output that large as "Output too large", PERSISTS it
# to a file, and hands the model only a ~2KB PREVIEW that cuts off BEFORE the
# orientation. Net effect: the model woke up blind to the DO-NEXT and the user had
# to re-prompt the cold-start every single session.
#
# Parity reference: learn-ukrainian/.claude/hooks/session-setup.sh emits a ~1KB
# POINTER packet that lands directly in context and is reliably acted on. So here
# we do the same: a TIGHT packet with the orchestrator identity + discipline +
# the single DO-NEXT focus item + the handoff pointer. The full role (roster,
# dispatch commands) loads on demand via the curriculum-orchestrator Skill; the
# full briefing JSON via `bash scripts/cold-start.sh`.

# Run cold-start for its SIDE EFFECTS (services-up + read-only fetch + fresh
# briefing) but EXTRACT only a compact summary — never inline the whole dump.
# Outer timeout so a slow/down API can't hang session start; on failure the
# extractor falls back to a "run cold-start yourself" directive.
# When SESSION_EPIC / KUBEDOJO_ISSUE is set (./start-*.sh --epic N), pass the
# issue into cold-start so the epic bind is visible in the dump.
COLDSTART_BIN="$PROJECT_DIR/scripts/cold-start.sh"
COLDSTART_OUT=""
EPIC_NUM="${SESSION_EPIC:-${KUBEDOJO_ISSUE:-}}"
if [ -n "$EPIC_NUM" ]; then
  export KUBEDOJO_ISSUE="$EPIC_NUM"
  export SESSION_EPIC="$EPIC_NUM"
fi
if [ -f "$COLDSTART_BIN" ]; then
  COLDSTART_ARGS=()
  if [ -n "$EPIC_NUM" ]; then
    COLDSTART_ARGS=(--issue "$EPIC_NUM")
  fi
  if command -v timeout >/dev/null 2>&1; then
    COLDSTART_OUT=$(timeout 30 bash "$COLDSTART_BIN" "${COLDSTART_ARGS[@]}" 2>/dev/null || true)
  elif command -v gtimeout >/dev/null 2>&1; then
    COLDSTART_OUT=$(gtimeout 30 bash "$COLDSTART_BIN" "${COLDSTART_ARGS[@]}" 2>/dev/null || true)
  else
    COLDSTART_OUT=$(bash "$COLDSTART_BIN" "${COLDSTART_ARGS[@]}" 2>/dev/null || true)
  fi
fi

# Extract DO-NEXT (briefing.focus[0]) + latest-handoff pointer + workspace state
# from cold-start's labeled blocks. Prefer the venv python; fall back to system.
PYBIN="$PROJECT_DIR/.venv/bin/python"
[ -x "$PYBIN" ] || PYBIN="$(command -v python3 2>/dev/null)"
ORIENT_BODY=""
if [ -n "$COLDSTART_OUT" ] && [ -n "$PYBIN" ]; then
  # Pass the cold-start dump via env var, NOT a pipe: `python - <<'PY'` already
  # consumes stdin for the SCRIPT, so a piped stdin would leave sys.stdin.read()
  # empty (the focus item would silently never parse). Env var keeps them separate.
  ORIENT_BODY=$(COLDSTART_OUT="$COLDSTART_OUT" "$PYBIN" - <<'PY' 2>/dev/null || true
import os, re, json, sys
text = os.environ.get("COLDSTART_OUT", "")
blocks, cur, buf = {}, None, []
for line in text.splitlines():
    m = re.match(r'^--- kubedojo:(\S+) ---\s*$', line.strip())
    if m:
        if cur is not None:
            blocks[cur] = "\n".join(buf)
        cur, buf = m.group(1), []
    else:
        buf.append(line)
if cur is not None:
    blocks[cur] = "\n".join(buf)

def loadj(name):
    raw = (blocks.get(name, "") or "").strip()
    try:
        return json.loads(raw)
    except Exception:
        return None

brief = loadj("briefing")
sess = loadj("session")
focus = (brief.get("focus") if isinstance(brief, dict) else None) or []
do_next = (focus[0].strip() if focus and isinstance(focus[0], str) else "")[:2000]
latest = (sess.get("latest") if isinstance(sess, dict) else None) or {}
hpath = (latest.get("path", "") or "").strip()
htldr = (latest.get("tldr", "") or "").strip()[:500]
workspace = (blocks.get("workspace", "") or "").strip()[:400]
pending = (blocks.get("pending-decisions", "") or "").strip()[:200]

out = []
if do_next:
    out.append("DO NEXT (top focus item from the live briefing):\n" + do_next)
else:
    out.append("DO NEXT: queue may be empty — propose work or check blockers. "
               "Run `bash scripts/cold-start.sh` for the full briefing.")
if hpath:
    out.append("Latest handoff: " + hpath + (("\n  " + htldr) if htldr else ""))
if workspace:
    out.append("Workspace (git status --short):\n" + workspace)
if pending and pending.lower() not in ("(empty)", "readme.md"):
    out.append("Pending decisions: " + pending)
sys.stdout.write("\n\n".join(out))
PY
)
fi
if [ -z "$ORIENT_BODY" ]; then
  ORIENT_BODY="(cold-start produced no briefing — RUN IT YOURSELF NOW as your first action: bash scripts/cold-start.sh, then act on its DO-NEXT focus item.)"
fi

# =============================================================================
# LANE SELECTION — SESSION_HANDOFF_AGENT (exported by start-claude.sh from the
# selected --agent; see scripts/lib/handoff_identity.sh) routes the orientation
# identity + handoff slot. cold-start ran ABOVE for BOTH lanes, so the infra
# lane still orients via the API even on its FIRST session (no handoff file
# yet). SESSION_EPIC / KUBEDOJO_ISSUE (./start-*.sh --epic N) selects the
# epic-driver packet and OVERRIDES the default curriculum UK DO-NEXT.
# The DEFAULT (curriculum) lane keeps its exact original CONTEXT when no epic
# is bound. Additive — #2113 (learn-ukrainian parity) + thin --epic bind.
# =============================================================================
if [ -n "${EPIC_NUM:-}" ]; then
  EPIC_HANDOFF="$PROJECT_DIR/.agent/claude-epic-thread-handoff.md"
  if [ -f "$EPIC_HANDOFF" ]; then
    EPIC_LEAD="PREVIOUS-SESSION EPIC HANDOFF — read this FIRST if it matches epic #${EPIC_NUM}:
  Read: $EPIC_HANDOFF
(gitignored local thread state; never committed. Write the next handoff to this same path at session end.)"
  else
    EPIC_LEAD="No epic-lane handoff yet (.agent/claude-epic-thread-handoff.md absent). Orient via cold-start + drive-epic."
  fi
  CONTEXT="EPIC-DRIVER SESSION — auto-oriented by the SessionStart hook. You ARE driving GitHub epic #${EPIC_NUM} (SESSION_EPIC=${EPIC_NUM}). You are NOT the default curriculum UK-volume queue and NOT the infra lane unless this epic is infra.

Load-bearing discipline (do NOT violate):
  - Read and follow the drive-epic skill before acting (agents_extensions/shared/skills/drive-epic/SKILL.md).
  - Before any dispatch wave: CodexBar capacity (\`codexbar usage --provider both --no-color\` + cursor/antigravity as needed) → CAPACITY_CARD. Never habit-route Codex on pace deficit.
  - Drive via the fleet (\`dispatch_smart\` in worktrees). Do not solo-implement volume. Exact-head CF as a PR comment (not gh approve). Merge only when CI is green on the reviewed SHA.
  - Branch in .worktrees/ — NEVER branch/switch in the primary dir; never push direct to main.
  - Inventory BOTH remotes: kube-dojo/kube-dojo.github.io AND kube-dojo/kubedojo-labs.

$EPIC_LEAD

Live state from the API (situational — the curriculum DO-NEXT below is NOT your task list when it conflicts with epic #${EPIC_NUM}):
$ORIENT_BODY

AUTO-ORIENT — before responding to the user's first message: state that you are driving epic #${EPIC_NUM}, run CodexBar → CAPACITY_CARD if a wave is next, then proceed on that epic unless the user redirects you. Cold-start has ALREADY run with --issue ${EPIC_NUM}.

SESSION SETUP CHECK:"
elif [ "${SESSION_HANDOFF_AGENT:-}" = "claude-infra" ]; then
  INFRA_HANDOFF="$PROJECT_DIR/.agent/claude-infra-thread-handoff.md"
  if [ -f "$INFRA_HANDOFF" ]; then
    INFRA_LEAD="PREVIOUS-SESSION INFRA HANDOFF — read this FIRST, as your first action:
  Read: $INFRA_HANDOFF
(gitignored local thread state; never committed. Write the next handoff to this same path at session end.)"
  else
    INFRA_LEAD="FIRST INFRA SESSION — no infra handoff yet (.agent/claude-infra-thread-handoff.md absent). Orient via the API: this hook already ran cold-start (services-up + fresh briefing); for the full briefing run \`bash scripts/cold-start.sh\` or curl 127.0.0.1:8768/api/briefing/session?compact=1. Write your handoff to that path at session end."
  fi
  CONTEXT="INFRA-ORCHESTRATOR SESSION — auto-oriented by the SessionStart hook. You ARE the KubeDojo infra / tooling orchestrator (lane: claude-infra). You own the build/dev tooling, scripts/, .claude/hooks/, the local API (scripts/local_api.py), CI workflows, deploy.sh, and agent-runtime plumbing — NOT curriculum content. Hand curriculum work to the default lane (plain \`./start-claude.sh\`, no --agent).

Load-bearing discipline (do NOT violate):
  - Branch in .worktrees/ — NEVER branch/switch in the primary dir; never push direct to main.
  - PR + cross-family adversarial review before every merge.
  - Lint per edit, test per phase; \`npm run build\` must be 0 errors before push.

$INFRA_LEAD

Live state from the API (situational awareness — the curriculum queue below is NOT the infra lane's task list):
$ORIENT_BODY

AUTO-ORIENT — before responding to the user's first message: state what the infra lane is picking up (from the handoff above, or from the API briefing on a first session), then proceed unless the user redirects you.

SESSION SETUP CHECK:"
else
CONTEXT="ORCHESTRATOR SESSION — auto-oriented by the SessionStart hook. You ARE the KubeDojo curriculum orchestrator: you own the module queue, dispatch authors/reviewers, PR hygiene, and session handoffs. Standalone session = you ARE the main orchestrator; drive the queue, ask only on irreversible or ambiguous actions.

Load-bearing discipline (do NOT violate):
  - Branch in .worktrees/ — NEVER branch/switch in the primary dir; never push direct to main.
  - PR + cross-family adversarial review before every merge.
  - Dispatch authors/reviewers for content/code — orchestrate, don't inline-write modules.
Full role detail (agent roster, dispatch commands, review protocol) loads ON DEMAND via the curriculum-orchestrator Skill. Full live briefing JSON: \`bash scripts/cold-start.sh\` (or curl 127.0.0.1:8768/api/briefing/session?compact=1).

$ORIENT_BODY

AUTO-ORIENT — before responding to the user's first message (even if it seems unrelated, trivial, or empty): state the DO-NEXT action above, then proceed with it unless the user's message redirects you. Cold-start has ALREADY run — do NOT wait to be told to orient.

SESSION SETUP CHECK:"
fi
# --- end lane selection ---

if [ ${#ISSUES[@]} -gt 0 ]; then
  CONTEXT="$CONTEXT
ISSUES:"
  for issue in "${ISSUES[@]}"; do
    CONTEXT="$CONTEXT
  - $issue"
  done
fi

if [ ${#INFO[@]} -gt 0 ]; then
  CONTEXT="$CONTEXT
INFO:"
  for info in "${INFO[@]}"; do
    CONTEXT="$CONTEXT
  - $info"
  done
fi

# Emit via the current SessionStart hook schema (hookSpecificOutput.additionalContext).
# The legacy top-level {"additionalContext": ...} form is silently ignored by newer
# Claude Code builds — which is why an earlier version's reminder never reached the
# model and the user had to retype the orientation prompt each restart.
jq -n --arg msg "$CONTEXT" \
  '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":$msg}}'
exit 0
