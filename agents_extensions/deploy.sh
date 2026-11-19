#!/usr/bin/env bash
set -euo pipefail

project_root=$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if (( $# > 1 )) || [[ $# == 1 && $1 != --check && $1 != --help ]]; then
    printf 'Usage: %s [--check | --help]\n' "$0" >&2
    exit 2
fi

interpreter=${LEARN_UKRAINIAN_PYTHON:-}
if [[ $interpreter != /* || ! -f $interpreter || ! -x $interpreter ]]; then
    printf 'Configure LEARN_UKRAINIAN_PYTHON as an absolute executable with the pinned lu-machinery installed.\n' >&2
    exit 2
fi

exec "$interpreter" -I -m lu_machinery.agent_deploy --project-root "$project_root" "$@"
