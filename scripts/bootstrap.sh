#!/usr/bin/env bash
# One-command development setup. Safe to run repeatedly.
set -euo pipefail

cd "$(dirname "$0")/.."

log() { printf '==> %s\n' "$*"; }
die() { printf 'bootstrap: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || die "docker is required"
docker compose version >/dev/null 2>&1 || die "docker compose is required"
command -v uv >/dev/null || die "uv is required (https://docs.astral.sh/uv/)"

log "installing portalctl and its test dependencies"
(cd portalctl && uv sync)

if [ ! -f config/portal.yml ]; then
  log "creating config/portal.yml from the example (edit it before docker compose up)"
  cp config/portal.yml.example config/portal.yml
fi

log "running the portalctl tests"
(cd portalctl && uv run pytest -q)

log "bootstrap complete"
