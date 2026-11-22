#!/usr/bin/env bash
# services.sh — Start/stop/restart project services
#
# Usage:
#   ./services.sh start              # Start all services
#   ./services.sh start dev api      # Start specific service
#   ./services.sh stop               # Stop all services
#   ./services.sh restart            # Restart all
#   ./services.sh status             # Show what's running
#   ./services.sh logs dev           # Tail logs for a service
#
# Services: dev, api, feedback

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$PROJECT_ROOT/logs"
PIDS_DIR="$PROJECT_ROOT/.pids"
VENV_BIN="$PROJECT_ROOT/.venv/bin"

mkdir -p "$LOGS_DIR" "$PIDS_DIR"

# Service definitions
declare -A SVC_CMD SVC_PORT SVC_LOG SVC_DESC

ASTRO_BIN="./node_modules/.bin/astro"
SVC_CMD[dev]="$ASTRO_BIN dev --port 4333"
SVC_PORT[dev]=4333
SVC_LOG[dev]="$LOGS_DIR/dev.log"
SVC_DESC[dev]="Astro Dev Server (hot reload)"

SVC_CMD[api]="$VENV_BIN/python3 scripts/local_api.py --host 0.0.0.0 --port 8768"
SVC_PORT[api]=8768
SVC_LOG[api]="$LOGS_DIR/api.log"
SVC_DESC[api]="Deterministic Local API"

SVC_CMD[feedback]="$VENV_BIN/python3 scripts/issue_watch.py loop 248 --interval-seconds 1800"
SVC_PORT[feedback]="-"
SVC_LOG[feedback]="$LOGS_DIR/feedback.log"
SVC_DESC[feedback]="GitHub Issue Feedback Watcher (#248)"

ALL_SERVICES="dev api feedback"

_pid_file() { echo "$PIDS_DIR/$1.pid"; }

_is_numeric_port() {
    [[ "$1" =~ ^[0-9]+$ ]]
}

_port_pid() {
    local port="$1"
    if ! _is_numeric_port "$port"; then
        return 1
    fi

    local pid
    pid=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n1 || true)
    if [[ -n "$pid" ]]; then
        echo "$pid"
        return 0
    fi
    return 1
}

_is_running() {
    local name="$1"
    local pidfile
    pidfile="$(_pid_file "$name")"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$pidfile"
    fi

    local port
    port="${SVC_PORT[$name]}"
    if _is_numeric_port "$port"; then
        local port_pid
        port_pid=$(_port_pid "$port" || true)
        if [[ -n "$port_pid" ]] && kill -0 "$port_pid" 2>/dev/null; then
            echo "$port_pid" > "$pidfile"
            return 0
        fi
    fi
    return 1
}

_start_service() {
    local name="$1"
    if _is_running "$name"; then
        echo "  $name is already running (PID $(cat "$(_pid_file "$name")"))"
        return 0
    fi

    cd "$PROJECT_ROOT"
    if [[ "$name" == "dev" && ( ! -f "$ASTRO_BIN" || ! -x "$ASTRO_BIN" ) ]]; then
        echo "  Astro executable missing or unusable at $ASTRO_BIN. Run npm ci from the project root." >&2
        return 1
    fi

    echo "  Starting $name — ${SVC_DESC[$name]}..."
    # shellcheck disable=SC2086
    nohup ${SVC_CMD[$name]} >> "${SVC_LOG[$name]}" 2>&1 &
    local pid=$!

    sleep 1
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "  $name failed to start; check ${SVC_LOG[$name]}"
        rm -f "$(_pid_file "$name")"
        return 1
    fi

    echo "$pid" > "$(_pid_file "$name")"
    echo "  $name started (PID $pid, port ${SVC_PORT[$name]}, log ${SVC_LOG[$name]})"
}

_stop_service() {
    local name="$1"
    local pidfile
    pidfile="$(_pid_file "$name")"

    if ! _is_running "$name"; then
        echo "  $name is not running"
        rm -f "$pidfile"
        return 0
    fi

    local pid
    pid=$(cat "$pidfile")
    echo "  Stopping $name (PID $pid)..."
    kill "$pid" 2>/dev/null || true

    # Wait up to 5 seconds for graceful shutdown
    for _ in $(seq 1 10); do
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 0.5
    done

    # Force kill if still running
    if kill -0 "$pid" 2>/dev/null; then
        echo "  Force killing $name..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$pidfile"

    # Dev server: clear Astro content cache on stop
    if [[ "$name" == "dev" ]]; then
        local cache_file="$PROJECT_ROOT/.astro/data-store.json"
        if [[ -f "$cache_file" ]]; then
            rm -f "$cache_file"
            echo "  Cleared Astro content cache"
        fi
        local vite_cache_dir="$PROJECT_ROOT/node_modules/.vite"
        if [[ -d "$vite_cache_dir" ]]; then
            rm -rf "$vite_cache_dir"
            echo "  Cleared Vite cache"
        fi
    fi

    echo "  $name stopped"
}

_status() {
    printf "%-12s %-8s %-8s %s\n" "SERVICE" "STATUS" "PID" "PORT"
    printf "%-12s %-8s %-8s %s\n" "-------" "------" "---" "----"
    for name in $ALL_SERVICES; do
        if _is_running "$name"; then
            local pid
            pid=$(cat "$(_pid_file "$name")")
            printf "%-12s \033[32m%-8s\033[0m %-8s %s\n" "$name" "running" "$pid" "${SVC_PORT[$name]}"
        else
            printf "%-12s \033[31m%-8s\033[0m %-8s %s\n" "$name" "stopped" "-" "${SVC_PORT[$name]}"
        fi
    done
}

_logs() {
    local name="$1"
    if [[ -z "${SVC_LOG[$name]+x}" ]]; then
        echo "Unknown service: $name"
        exit 1
    fi
    if [[ ! -f "${SVC_LOG[$name]}" ]]; then
        echo "No log file yet for $name"
        exit 0
    fi
    tail -f "${SVC_LOG[$name]}"
}

# Parse arguments
action="${1:-help}"
shift || true
services="${*:-$ALL_SERVICES}"

case "$action" in
    start)
        echo "Starting services..."
        for svc in $services; do
            if [[ -z "${SVC_CMD[$svc]+x}" ]]; then
                echo "  Unknown service: $svc (available: $ALL_SERVICES)"
                continue
            fi
            _start_service "$svc"
        done
        echo ""
        _status
        ;;
    stop)
        echo "Stopping services..."
        for svc in $services; do
            if [[ -z "${SVC_CMD[$svc]+x}" ]]; then
                echo "  Unknown service: $svc"
                continue
            fi
            _stop_service "$svc"
        done
        echo ""
        _status
        ;;
    restart)
        echo "Restarting services..."
        for svc in $services; do
            if [[ -z "${SVC_CMD[$svc]+x}" ]]; then
                echo "  Unknown service: $svc"
                continue
            fi
            _stop_service "$svc"
            _start_service "$svc"
        done
        echo ""
        _status
        ;;
    status)
        _status
        ;;
    logs)
        if [[ -z "${1:-}" ]]; then
            echo "Usage: $0 logs <service>"
            exit 1
        fi
        _logs "$1"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs} [service ...]"
        echo ""
        echo "Services:"
        for name in $ALL_SERVICES; do
            printf "  %-12s %s (port %s)\n" "$name" "${SVC_DESC[$name]}" "${SVC_PORT[$name]}"
        done
        echo ""
        echo "Examples:"
        echo "  $0 start              # Start dev server and local API"
        echo "  $0 start api          # Start only the local API"
        echo "  $0 stop               # Stop all services"
        echo "  $0 restart api        # Restart the local API"
        echo "  $0 status             # Show status"
        echo "  $0 logs dev           # Tail dev server logs"
        ;;
esac
