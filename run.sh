#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<EOF
Usage: ./run.sh <command> [options]

Commands:
  deploy   <source-dir> <container-dir> [--port PORT] [--tags TAGS] [--name-tpl TPL] [--slug-tpl TPL] [--generate-missing] [--publish] [--dry-run]
  list     [--port PORT] [--datasets] [--endpoints]
  delete   [--port PORT] [--datasets] [--endpoints] [--yes] [--dry-run]
  publish  [--port PORT] [--dry-run]
  generate <source-dir> [--port PORT] [--dry-run]

Options:
  --port PORT       Syft Space port (default: 8080, auto-detects API key)
  --dry-run         Preview without making changes
  --limit N         Limit to N items

Examples:
  ./run.sh deploy /home/azureuser/datasets/cambridge_loader /root/datasets/cambridge_loader --port 8086 --tags "cambridge,rag,journal" --name-tpl "{name}-journal-oa" --slug-tpl "{name}-oa" --generate-missing --publish --dry-run
  ./run.sh list --port 8086
  ./run.sh delete --port 8086 --endpoints --dry-run
  ./run.sh generate /home/azureuser/datasets/cambridge_loader --dry-run
EOF
    exit 1
}

[[ $# -lt 1 ]] && usage

COMMAND="$1"; shift

# Defaults
PORT=8080
TAGS=""
NAME_TPL="{name}"
SLUG_TPL="{name}"
SUMMARY_TPL="{name}"
FILE_TYPES=""
GENERATE_MISSING=""
PUBLISH=""
DRY_RUN=""
LIMIT=""
RESUME=""
YES=""
DATASETS_FLAG=""
ENDPOINTS_FLAG=""
SOURCE_DIR=""
CONTAINER_DIR=""

# Parse positional args based on command
case "$COMMAND" in
    deploy)
        [[ $# -lt 2 ]] && { echo "Error: deploy requires <source-dir> <container-dir>"; usage; }
        SOURCE_DIR="$1"; shift
        CONTAINER_DIR="$1"; shift
        ;;
    generate)
        [[ $# -lt 1 ]] && { echo "Error: generate requires <source-dir>"; usage; }
        SOURCE_DIR="$1"; shift
        ;;
    list|delete|publish) ;;
    *) echo "Unknown command: $COMMAND"; usage ;;
esac

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)        PORT="$2"; shift 2 ;;
        --tags)        TAGS="$2"; shift 2 ;;
        --name-tpl)    NAME_TPL="$2"; shift 2 ;;
        --slug-tpl)    SLUG_TPL="$2"; shift 2 ;;
        --summary-tpl) SUMMARY_TPL="$2"; shift 2 ;;
        --file-types)  FILE_TYPES="$2"; shift 2 ;;
        --limit)       LIMIT="$2"; shift 2 ;;
        --generate-missing) GENERATE_MISSING=1; shift ;;
        --publish)     PUBLISH=1; shift ;;
        --dry-run)     DRY_RUN=1; shift ;;
        --resume)      RESUME=1; shift ;;
        --yes|-y)      YES=1; shift ;;
        --datasets)    DATASETS_FLAG=1; shift ;;
        --endpoints)   ENDPOINTS_FLAG=1; shift ;;
        *) echo "Unknown flag: $1"; usage ;;
    esac
done

API_URL="http://localhost:${PORT}/api/v1"

# Build python command
CMD=(python3 "${SCRIPT_DIR}/main.py" --api-url "$API_URL")

case "$COMMAND" in
    deploy)
        CMD+=( deploy --source-dir "$SOURCE_DIR" --container-dir "$CONTAINER_DIR" )
        [[ -n "$TAGS" ]]       && CMD+=( --tags "$TAGS" )
        [[ "$NAME_TPL" != "{name}" ]] && CMD+=( --name-template "$NAME_TPL" )
        [[ "$SLUG_TPL" != "{name}" ]] && CMD+=( --slug-template "$SLUG_TPL" )
        [[ "$SUMMARY_TPL" != "{name}" ]] && CMD+=( --summary-template "$SUMMARY_TPL" )
        [[ -n "$FILE_TYPES" ]] && CMD+=( --file-types "$FILE_TYPES" )
        [[ -n "$GENERATE_MISSING" ]] && CMD+=( --generate-missing )
        [[ -n "$PUBLISH" ]]    && CMD+=( --publish )
        [[ -n "$DRY_RUN" ]]    && CMD+=( --dry-run )
        [[ -n "$LIMIT" ]]      && CMD+=( --limit "$LIMIT" )
        [[ -n "$RESUME" ]]     && CMD+=( --resume )
        ;;
    list)
        CMD+=( list )
        [[ -n "$DATASETS_FLAG" ]]  && CMD+=( --datasets )
        [[ -n "$ENDPOINTS_FLAG" ]] && CMD+=( --endpoints )
        ;;
    delete)
        CMD+=( delete )
        [[ -n "$DATASETS_FLAG" ]]  && CMD+=( --datasets )
        [[ -n "$ENDPOINTS_FLAG" ]] && CMD+=( --endpoints )
        [[ -n "$DRY_RUN" ]] && CMD+=( --dry-run )
        [[ -n "$YES" ]]     && CMD+=( --yes )
        ;;
    publish)
        CMD+=( publish )
        [[ -n "$DRY_RUN" ]] && CMD+=( --dry-run )
        [[ -n "$LIMIT" ]]   && CMD+=( --limit "$LIMIT" )
        ;;
    generate)
        CMD+=( generate --source-dir "$SOURCE_DIR" )
        [[ -n "$DRY_RUN" ]] && CMD+=( --dry-run )
        [[ -n "$LIMIT" ]]   && CMD+=( --limit "$LIMIT" )
        [[ -n "$RESUME" ]]  && CMD+=( --resume )
        ;;
esac

echo "Running: ${CMD[*]}"
echo
exec "${CMD[@]}"
