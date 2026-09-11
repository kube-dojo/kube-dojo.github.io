#!/bin/bash
# KubeDojo - Codex Wrapper
# Default: starts Codex in the repository's primary main checkout.
# Optional: pass --worktree (or set CODEX_TARGET=worktree) to use a dedicated
# git worktree when Codex needs isolated git state.

set -e

# Ensure common local bin paths are available
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
hash -r 2>/dev/null || true

# Get the checkout containing this script, then resolve the repository's
# primary main checkout so the launcher behaves consistently from any worktree.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
CODEX_TARGET="${CODEX_TARGET:-main}"
CODEX_ARGS=()
CODEX_FLAGS=(--dangerously-bypass-approvals-and-sandbox)

if [ "${CODEX_ENABLE_MULTI_AGENT:-1}" != "0" ]; then
    CODEX_FLAGS+=(--enable multi_agent)
fi

while [ "$#" -gt 0 ]; do
    case "$1" in
        --help-wrapper)
            cat <<'EOF'
Usage: ./start-codex.sh [--main|--worktree] [--epic N] [codex args...]

KubeDojo Codex launcher:
  - runs Codex in the primary main checkout by default
  - use --worktree to run in .worktrees/codex-interactive instead
  - --epic N  bind drive-epic (SESSION_EPIC + KUBEDOJO_ISSUE); CodexBar + fleet
  - always adds --dangerously-bypass-approvals-and-sandbox
  - enables Codex multi-agent support by default
  - set CODEX_ENABLE_MULTI_AGENT=0 to disable multi-agent support
  - forwards all other arguments to codex unchanged
EOF
            exit 0
            ;;
        --main)
            CODEX_TARGET="main"
            shift
            ;;
        --worktree)
            CODEX_TARGET="worktree"
            shift
            ;;
        --epic)
            if [ "$#" -lt 2 ]; then
                echo "Error: --epic requires a positive integer" >&2
                exit 2
            fi
            CODEX_EPIC="$2"
            shift 2
            ;;
        --epic=*)
            CODEX_EPIC="${1#--epic=}"
            shift
            ;;
        *)
            CODEX_ARGS+=("$1")
            shift
            ;;
    esac
done

if [ -n "${CODEX_EPIC:-}" ]; then
    # shellcheck source=scripts/lib/epic_driver_bind.sh
    source "$SCRIPT_DIR/scripts/lib/epic_driver_bind.sh"
    epic_export_env "$CODEX_EPIC" || exit $?
    echo "Epic driver → SESSION_EPIC=$SESSION_EPIC (drive-epic + CodexBar + fleet)"
    CODEX_ARGS+=("$(epic_driver_prompt "$CODEX_EPIC")")
fi

case "$CODEX_TARGET" in
    main|worktree)
        ;;
    *)
        echo "Error: CODEX_TARGET must be 'main' or 'worktree' (got '$CODEX_TARGET')"
        exit 1
        ;;
esac

echo "Starting Codex in KubeDojo project..."
echo "Launcher checkout: $SCRIPT_DIR"

echo "Preflight check..."
MISSING_TOOLS=""
for tool in git gh codex; do
    if ! command -v "$tool" &> /dev/null; then
        MISSING_TOOLS="$MISSING_TOOLS $tool"
    fi
done

if [ -n "$MISSING_TOOLS" ]; then
    echo "Error: Required tools not found:$MISSING_TOOLS"
    exit 1
fi

if git -C "$SCRIPT_DIR" rev-parse --git-dir > /dev/null 2>&1; then
    MAIN_WORKTREE_DIR=$(
        git -C "$SCRIPT_DIR" worktree list --porcelain | awk '
            $1 == "worktree" { path = $2 }
            $1 == "branch" && $2 == "refs/heads/main" { print path; exit }
        '
    )
    if [ -n "$MAIN_WORKTREE_DIR" ]; then
        PROJECT_DIR="$MAIN_WORKTREE_DIR"
    fi
fi

WORKTREE_DIR="$PROJECT_DIR/.worktrees/codex-interactive"

echo "Project root: $PROJECT_DIR"
echo "Target checkout: $CODEX_TARGET"

cd "$PROJECT_DIR"

if git rev-parse --git-dir > /dev/null 2>&1; then
    CURRENT_BRANCH=$(git branch --show-current)
    echo "Primary checkout branch: $CURRENT_BRANCH"
fi

TARGET_DIR="$PROJECT_DIR"

if [ "$CODEX_TARGET" = "worktree" ]; then
    # ── Worktree setup ──────────────────────────────────────────────
    # Creates a linked worktree at .worktrees/codex-interactive/ that
    # shares the same git objects but has its OWN index file. This means
    # Codex can run git status/add/commit freely without creating
    # .git/index.lock races with other agents in the main checkout.
    if [ ! -d "$WORKTREE_DIR" ]; then
        echo "Creating Codex worktree at $WORKTREE_DIR..."
        git worktree add "$WORKTREE_DIR" HEAD --detach
        echo "Worktree created."
    else
        echo "Codex worktree exists at $WORKTREE_DIR"
        cd "$WORKTREE_DIR"
        git checkout --detach origin/main 2>/dev/null || git checkout --detach HEAD
        cd "$PROJECT_DIR"
        echo "Worktree updated to latest."
    fi

    # Symlink .venv into the worktree so Codex has the same Python env
    if [ ! -e "$WORKTREE_DIR/.venv" ]; then
        ln -s "$PROJECT_DIR/.venv" "$WORKTREE_DIR/.venv"
        echo "Symlinked .venv into worktree"
    fi

    # Symlink node_modules so npm/astro build works
    if [ -d "$PROJECT_DIR/node_modules" ] && [ ! -e "$WORKTREE_DIR/node_modules" ]; then
        ln -s "$PROJECT_DIR/node_modules" "$WORKTREE_DIR/node_modules"
        echo "Symlinked node_modules into worktree"
    fi

    # Symlink .pipeline/ so workers share state db and budgets
    if [ ! -e "$WORKTREE_DIR/.pipeline" ]; then
        ln -s "$PROJECT_DIR/.pipeline" "$WORKTREE_DIR/.pipeline"
        echo "Symlinked .pipeline/ into worktree"
    fi

    TARGET_DIR="$WORKTREE_DIR"
fi

echo ""
echo "KUBEDOJO - Cloud Native Curriculum"
echo ""
if [ "$CODEX_TARGET" = "worktree" ]; then
    echo "   Codex runs in worktree: $WORKTREE_DIR"
    echo "   This isolates git operations from the main checkout."
    echo "   Any commits Codex makes stay in the worktree until you merge them."
    echo ""
    echo "   To pull latest from main into the worktree:"
    echo "       cd $WORKTREE_DIR && git checkout --detach origin/main"
    echo ""
    echo "   To clean up the worktree when done:"
    echo "       git worktree remove $WORKTREE_DIR"
else
    echo "   Codex runs in the main checkout: $PROJECT_DIR"
    echo "   Use this when Codex needs to continue work directly in main."
    echo "   Git operations here are not isolated from other agents."
fi
echo ""
echo "   Handoff doc: .pipeline/codex-handoff.md"
echo "   First command: cat .pipeline/codex-handoff.md"
if [ "${CODEX_ENABLE_MULTI_AGENT:-1}" != "0" ]; then
    echo "   Multi-agent: enabled"
else
    echo "   Multi-agent: disabled"
fi
echo ""

echo "Launching Codex in $CODEX_TARGET checkout..."
export CODEX_SESSION=1
codex "${CODEX_FLAGS[@]}" -C "$TARGET_DIR" "${CODEX_ARGS[@]}"
