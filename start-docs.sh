#!/bin/bash
# KubeDojo - Documentation Server (Starlight/Astro)
# Starts Astro dev server on port 4321

set -e

# Get script directory (project root)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting KubeDojo Documentation Server..."
echo "Project: $PROJECT_DIR"

# Change to project directory
cd "$PROJECT_DIR"

# Port to use
PORT=4333
LOG_FILE="/tmp/astro-kubedojo.log"

# Leak guard: astro dev (Vite) leaks memory over long uptimes — a forgotten
# server reached ~5.4 GB after 2.5 days (s182). The dev server is meant to be
# ephemeral, so auto-stop it after MAX_HOURS; it can never balloon again.
# Override: KUBEDOJO_DEV_MAX_HOURS=24 bash start-docs.sh  (0 = no auto-stop).
MAX_HOURS="${KUBEDOJO_DEV_MAX_HOURS:-12}"

# Check if port is in use
if lsof -ti:$PORT > /dev/null 2>&1; then
    echo "Port $PORT is already in use"
    echo "   Killing existing process..."
    lsof -ti:$PORT | xargs kill -9
    sleep 1
    echo "Cleaned up port $PORT"
fi

# Check if project-local Astro binary exists (not just a partial node_modules/)
if [ ! -x "node_modules/.bin/astro" ]; then
    echo "Installing dependencies..."
    npm ci
    if [ ! -x "node_modules/.bin/astro" ]; then
        echo "Error: node_modules/.bin/astro is missing or not executable after npm ci" >&2
        exit 1
    fi
    echo "Dependencies installed"
else
    echo "Dependencies found"
fi

# Start Astro dev server using the locked project-local binary (never npx)
echo "Starting Astro dev server on http://localhost:$PORT"
nohup ./node_modules/.bin/astro dev --port "$PORT" > "$LOG_FILE" 2>&1 &
DEV_PID=$!
sleep 3

# Check if it started successfully
if /bin/ps -p $DEV_PID > /dev/null 2>&1; then
    echo "Astro dev server running (PID: $DEV_PID)"
    echo "   Documentation: http://localhost:$PORT"
    echo "   Logs: $LOG_FILE"

    # Leak-guard watchdog: stop the dev server after MAX_HOURS so a forgotten
    # session can't balloon. PID-reuse-safe — only kills if the PID is still
    # THIS astro dev (re-checks the command before killing). Detached so the
    # launcher can exit. Set KUBEDOJO_DEV_MAX_HOURS=0 to disable.
    if [ "$MAX_HOURS" -gt 0 ] 2>/dev/null; then
        (
            sleep "$((MAX_HOURS * 3600))"
            if /bin/ps -p "$DEV_PID" -o command= 2>/dev/null | grep -q "astro dev"; then
                kill "$DEV_PID" 2>/dev/null
                echo "[start-docs] leak-guard: auto-stopped astro dev (PID $DEV_PID) after ${MAX_HOURS}h" >> "$LOG_FILE"
            fi
        ) >/dev/null 2>&1 &
        disown 2>/dev/null || true
        echo "   Leak guard: auto-stops after ${MAX_HOURS}h (override KUBEDOJO_DEV_MAX_HOURS; 0=off)"
    fi
    echo ""
    echo "To stop: kill $DEV_PID"
    echo "Or: lsof -ti:$PORT | xargs kill"
else
    echo "Astro dev server failed to start"
    echo "   Check logs: $LOG_FILE"
    exit 1
fi
