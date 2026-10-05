#!/usr/bin/env bash

# Run model-heavy corpus maintenance without a second copy of the API's warmed models.
# The EXIT trap restarts the API after success, failure, or an interrupt.
set -u

action=${1:-}
version=${2:-}
source_id=${3:-}

case "$action" in
  test)
    maintenance_command=(docker compose run --rm --no-deps -e MOCK_MODE=1 backend pytest -p no:cacheprovider)
    ;;
  ingest)
    maintenance_command=(docker compose run --rm --no-deps backend python -m app.ingest.cli)
    ;;
  resume-ingest)
    if [[ -z "$version" ]]; then
      printf 'Usage: make resume-ingest V=<staged-version-label>\n' >&2
      exit 2
    fi
    maintenance_command=(docker compose run --rm --no-deps backend python -m app.ingest.cli --resume-version-label "$version")
    if [[ -n "$source_id" ]]; then
      IFS=',' read -r -a source_ids <<< "$source_id"
      for requested_source in "${source_ids[@]}"; do
        [[ -n "$requested_source" ]] && maintenance_command+=(--source "$requested_source")
      done
    fi
    ;;
  promote)
    if [[ -z "$version" ]]; then
      printf 'Usage: make promote V=<staged-version-label>\n' >&2
      exit 2
    fi
    maintenance_command=(docker compose run --rm --no-deps backend python -m app.ingest.versions promote --label "$version")
    ;;
  *)
    printf 'Usage: bash scripts/run-maintenance.sh {test|ingest|resume-ingest <version>|promote <version>}\n' >&2
    exit 2
    ;;
esac

docker compose stop backend || exit $?

restore_backend() {
  local status=$?
  trap - EXIT INT TERM
  docker compose up -d backend
  local restart_status=$?
  if (( status != 0 )); then
    exit "$status"
  fi
  exit "$restart_status"
}

trap 'exit 130' INT
trap 'exit 143' TERM
trap restore_backend EXIT

"${maintenance_command[@]}"
