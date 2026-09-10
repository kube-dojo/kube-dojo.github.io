#!/bin/bash
# Deploy agent extensions from source (agents_extensions/) to per-agent hidden
# dirs (.claude/, .codex/, ...). Source is the SSOT — edit there, never the
# deployed copy, or the next deploy reverts your edit.
#
# Usage: ./agents_extensions/deploy.sh [--quiet] [--check] [--target claude|codex|cursor|gemini|all]
#   --check   Report drift WITHOUT writing anything; exit 1 if anything is off.
#             Detects: (a) content drift (deployed != source), (b) executable-bit
#             drift on hooks/statusline (content matches but deployed lost +x),
#             (c) ORPHANS — a deployed commands/agents/skills file with no source
#             (left behind after a source deletion). Orphan detection is scoped to
#             those content types; the executable dirs (hooks/statusline) legitimately
#             carry direct-committed files with no source and are not orphan-checked.
#             Used by the extensions-sync CI gate.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_ROOT="$SCRIPT_DIR"

QUIET=false
CHECK=false
TARGET="all"
DRIFT_TOTAL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --quiet)
            QUIET=true
            shift
            ;;
        --check)
            CHECK=true
            shift
            ;;
        --target)
            TARGET="${2:-}"
            if [[ -z "$TARGET" ]]; then
                echo "Error: --target requires a value (claude|codex|cursor|gemini|all)" >&2
                exit 1
            fi
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--quiet] [--check] [--target claude|codex|cursor|gemini|all]" >&2
            exit 1
            ;;
    esac
done

log() {
    if [[ "$QUIET" == "false" ]]; then
        echo "$1" >&2
    fi
}

agent_hidden_dir() {
    case "$1" in
        claude) echo ".claude" ;;
        codex) echo ".codex" ;;
        cursor) echo ".cursor" ;;
        gemini) echo ".gemini" ;;
        *)
            echo "Error: unknown agent '$1'" >&2
            return 1
            ;;
    esac
}

# Echo number of files copied (stdout); logs go through log().
deploy_skills() {
    local source_subdir="$1"
    local target_subdir="$2"
    local changed=0

    [[ -d "$source_subdir" ]] || { echo 0; return 0; }
    [[ "$CHECK" == "true" ]] || mkdir -p "$target_subdir"

    for skill_dir in "$source_subdir"/*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name=$(basename "$skill_dir")
        local source_file="$skill_dir/SKILL.md"
        local target_skill_dir="$target_subdir/$skill_name"
        local target_file="$target_skill_dir/SKILL.md"

        if [[ -f "$source_file" ]]; then
            if [[ "$CHECK" == "false" ]]; then
                mkdir -p "$target_skill_dir"
            fi
            if [[ ! -f "$target_file" ]] || ! cmp -s "$source_file" "$target_file"; then
                if [[ "$CHECK" == "true" ]]; then
                    log "   ✗ DRIFT skills/$skill_name/SKILL.md"
                else
                    cp "$source_file" "$target_file"
                    log "   📄 skills/$skill_name/SKILL.md"
                fi
                changed=$((changed + 1))
            fi
            # Companion files (reference.md, dual-repo.md, …) stay next to SKILL.md
            # so relative links in the skill body resolve after deploy.
            local extra extra_base target_extra
            for extra in "$skill_dir"*; do
                [[ -f "$extra" ]] || continue
                extra_base=$(basename "$extra")
                [[ "$extra_base" == "SKILL.md" ]] && continue
                target_extra="$target_skill_dir/$extra_base"
                if [[ ! -f "$target_extra" ]] || ! cmp -s "$extra" "$target_extra"; then
                    if [[ "$CHECK" == "true" ]]; then
                        log "   ✗ DRIFT skills/$skill_name/$extra_base"
                    else
                        mkdir -p "$target_skill_dir"
                        cp "$extra" "$target_extra"
                        log "   📄 skills/$skill_name/$extra_base"
                    fi
                    changed=$((changed + 1))
                fi
            done
        fi
    done
    echo "$changed"
}

# Deploy flat *.md (commands) or *.sh (hooks/statusline). Echo change count.
deploy_flat() {
    local source_subdir="$1"
    local target_subdir="$2"
    local label="$3"
    local pattern="$4"
    local executable="$5"
    local changed=0

    [[ -d "$source_subdir" ]] || { echo 0; return 0; }
    [[ "$CHECK" == "true" ]] || mkdir -p "$target_subdir"

    for file in "$source_subdir"/$pattern; do
        [[ -f "$file" ]] || continue
        local filename
        filename=$(basename "$file")
        local target_file="$target_subdir/$filename"

        if [[ ! -f "$target_file" ]] || ! cmp -s "$file" "$target_file"; then
            if [[ "$CHECK" == "true" ]]; then
                log "   ✗ DRIFT $label/$filename"
            else
                cp "$file" "$target_file"
                if [[ "$executable" == "yes" ]]; then
                    chmod +x "$target_file"
                fi
                log "   📄 $label/$filename"
            fi
            changed=$((changed + 1))
        elif [[ "$executable" == "yes" ]] && [[ ! -x "$target_file" ]]; then
            # Content matches but the deployed copy lost its executable bit — a
            # hook/statusline that isn't +x silently won't run. Detect (check) or
            # fix (deploy). Caught codex review of #2115.
            if [[ "$CHECK" == "true" ]]; then
                log "   ✗ DRIFT (exec bit) $label/$filename"
            else
                chmod +x "$target_file"
                log "   🔧 chmod +x $label/$filename"
            fi
            changed=$((changed + 1))
        fi
    done
    echo "$changed"
}

# CHECK-mode only: report DEPLOYED files that have NO source (orphaned when a
# source skill/command/agent is deleted but its deployed copy lingers — the next
# deploy is additive and won't remove it). Echoes the orphan count.
#
# Scoped to CONTENT types (commands/agents/skills): the executable dirs (hooks,
# statusline) legitimately carry direct-committed operational files with no
# source (e.g. .claude/hooks/block-*.sh), so flagging deployed-only files there
# would be a false positive. Caught by codex review of #2115.
check_orphans_flat() {
    local target_subdir="$1" pattern="$2" label="$3"; shift 3
    local source_dirs=("$@")
    local orphans=0
    [[ -d "$target_subdir" ]] || { echo 0; return 0; }
    for dep in "$target_subdir"/$pattern; do
        [[ -f "$dep" ]] || continue
        local base found=no sd
        base=$(basename "$dep")
        for sd in "${source_dirs[@]}"; do [[ -f "$sd/$base" ]] && { found=yes; break; }; done
        if [[ "$found" == "no" ]]; then
            log "   ✗ ORPHAN (no source) $label/$base"
            orphans=$((orphans + 1))
        fi
    done
    echo "$orphans"
}

check_orphans_skills() {
    local target_subdir="$1"; shift
    local source_dirs=("$@")  # each is a .../skills dir holding <name>/SKILL.md
    local orphans=0
    [[ -d "$target_subdir" ]] || { echo 0; return 0; }
    for dep in "$target_subdir"/*/; do
        [[ -d "$dep" ]] || continue
        local base found=no sd
        base=$(basename "$dep")
        for sd in "${source_dirs[@]}"; do [[ -f "$sd/$base/SKILL.md" ]] && { found=yes; break; }; done
        if [[ "$found" == "no" ]]; then
            log "   ✗ ORPHAN (no source) skills/$base"
            orphans=$((orphans + 1))
        fi
    done
    echo "$orphans"
}

deploy_agent() {
    local agent="$1"
    local hidden
    hidden=$(agent_hidden_dir "$agent") || return 1

    local agent_dir="$SOURCE_ROOT/$agent"
    local shared_dir="$SOURCE_ROOT/shared"
    local target_dir="$PROJECT_ROOT/$hidden"

    log "🔧 Deploying $agent extensions..."
    log "   Source: $SOURCE_ROOT (shared + $agent/)"
    log "   Target: $target_dir"

    local n
    local commands_changed=0
    local skills_changed=0
    local agents_changed=0
    local hooks_changed=0
    local statusline_changed=0

    n=$(deploy_flat "$shared_dir/commands" "$target_dir/commands" "commands" "*.md" "no")
    commands_changed=$((commands_changed + n))
    n=$(deploy_flat "$agent_dir/commands" "$target_dir/commands" "commands" "*.md" "no")
    commands_changed=$((commands_changed + n))

    n=$(deploy_skills "$shared_dir/skills" "$target_dir/skills")
    skills_changed=$((skills_changed + n))
    n=$(deploy_skills "$agent_dir/skills" "$target_dir/skills")
    skills_changed=$((skills_changed + n))

    # Agent definitions (flat *.md). Selected via `claude --agent <name>`, where
    # <name> is the `name:` frontmatter field (not the filename). shared/ first,
    # then per-agent.
    n=$(deploy_flat "$shared_dir/agents" "$target_dir/agents" "agents" "*.md" "no")
    agents_changed=$((agents_changed + n))
    n=$(deploy_flat "$agent_dir/agents" "$target_dir/agents" "agents" "*.md" "no")
    agents_changed=$((agents_changed + n))

    n=$(deploy_flat "$agent_dir/hooks" "$target_dir/hooks" "hooks" "*.sh" "yes")
    hooks_changed=$((hooks_changed + n))

    n=$(deploy_flat "$agent_dir/statusline" "$target_dir/statusline" "statusline" "*.sh" "yes")
    statusline_changed=$((statusline_changed + n))

    # Orphan detection (CHECK mode only) for the fully-source-managed content
    # types — catches a deployed copy left behind after its source was deleted.
    if [[ "$CHECK" == "true" ]]; then
        n=$(check_orphans_flat "$target_dir/commands" "*.md" "commands" "$shared_dir/commands" "$agent_dir/commands")
        commands_changed=$((commands_changed + n))
        n=$(check_orphans_flat "$target_dir/agents" "*.md" "agents" "$shared_dir/agents" "$agent_dir/agents")
        agents_changed=$((agents_changed + n))
        n=$(check_orphans_skills "$target_dir/skills" "$shared_dir/skills" "$agent_dir/skills")
        skills_changed=$((skills_changed + n))
    fi

    local total_changed=$((commands_changed + skills_changed + agents_changed + hooks_changed + statusline_changed))
    DRIFT_TOTAL=$((DRIFT_TOTAL + total_changed))
    if [[ "$CHECK" == "true" ]]; then
        if [[ $total_changed -gt 0 ]]; then
            log "⚠️  $total_changed file(s) drifted for '$agent' (deployed != source)"
        else
            log "✅ '$agent' extensions in sync"
        fi
    elif [[ $total_changed -gt 0 ]]; then
        log "✅ Deployed $total_changed extension(s)"
    else
        log "✅ Extensions up to date"
    fi
}

case "$TARGET" in
    all)
        for agent in claude codex cursor gemini; do
            deploy_agent "$agent"
        done
        ;;
    claude|codex|cursor|gemini)
        deploy_agent "$TARGET"
        ;;
    *)
        echo "Error: invalid --target '$TARGET' (use claude|codex|cursor|gemini|all)" >&2
        exit 1
        ;;
esac

# --check gate: drift means a deployed copy diverged from its source (edit the
# SOURCE under agents_extensions/, then redeploy). Exit non-zero so CI fails.
if [[ "$CHECK" == "true" ]]; then
    if [[ $DRIFT_TOTAL -gt 0 ]]; then
        log "❌ deploy --check: $DRIFT_TOTAL file(s) drifted (deployed != source). Fix: edit the source under agents_extensions/, then run 'bash agents_extensions/deploy.sh' and commit the synced deployed copy."
        exit 1
    fi
    log "✅ deploy --check: all extensions in sync with source"
fi
exit 0
