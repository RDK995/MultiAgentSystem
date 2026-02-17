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

_truthy() {
  local raw="${1:-}"
  local raw_lc
  raw_lc="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$raw_lc" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

if _truthy "${ENABLE_LANGFUSE_TRACING:-true}" \
  && [[ -n "${LANGFUSE_PUBLIC_KEY:-}" ]] \
  && [[ -n "${LANGFUSE_SECRET_KEY:-}" ]]; then
  export LANGFUSE_USER_ID="${LANGFUSE_USER_ID:-${USER:-unknown-user}}"
  export LANGFUSE_SESSION_ID="${LANGFUSE_SESSION_ID:-uk-resell-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
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
