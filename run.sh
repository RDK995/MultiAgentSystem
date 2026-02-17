#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

usage() {
  cat <<'USAGE'
Usage:
  ./run.sh [mode] [args...]

Modes:
  local   Run local dry-run entrypoint (default)
  adk     Run ADK web with uk_resell_adk.app:root_agent

Examples:
  ./run.sh
  ./run.sh local --json
  ./run.sh adk
USAGE
}

mode="local"
if [[ $# -gt 0 ]]; then
  case "$1" in
    local|adk)
      mode="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
  esac
fi

if [[ "$mode" == "local" ]]; then
  python -m uk_resell_adk.main "$@"
  exit 0
fi

if ! command -v adk >/dev/null 2>&1; then
  echo "Error: adk CLI not found. Install/configure ADK CLI first." >&2
  exit 1
fi

adk web uk_resell_adk.app:root_agent "$@"
