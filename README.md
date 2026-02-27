# Syft Space Deploy

Generic CLI for deploying datasets and endpoints to Syft Space. Auto-discovers datasets from a directory (each subdirectory = one dataset) and creates corresponding Syft datasets + RAG endpoints.

## Prerequisites

- Syft Space running in Docker
- Python 3.10+ with `requests` and `python-dotenv`
- Copy `.env.example` to `.env` and set your keys

## Quick Start

```bash
# Deploy Cambridge journals (dry-run first)
./run.sh deploy /home/azureuser/datasets/cambridge_loader /root/datasets/cambridge_loader \
  --port 8086 \
  --tags "cambridge,rag,journal" \
  --name-tpl "{name}-journal-oa" \
  --slug-tpl "{name}-oa" \
  --generate-missing \
  --publish \
  --dry-run

# Remove --dry-run to execute
```

## run.sh (Recommended)

Wrapper script that simplifies `main.py` usage.

```bash
# Deploy
./run.sh deploy <source-dir> <container-dir> [--port PORT] [--tags TAGS] \
  [--name-tpl TPL] [--slug-tpl TPL] [--generate-missing] [--publish] [--dry-run] [--limit N]

# List
./run.sh list [--port PORT] [--datasets] [--endpoints]

# Delete
./run.sh delete [--port PORT] [--datasets] [--endpoints] [--yes] [--dry-run]

# Publish unpublished endpoints
./run.sh publish [--port PORT] [--dry-run]

# Generate AI descriptions
./run.sh generate <source-dir> [--port PORT] [--dry-run] [--limit N]
```

`--port` defaults to 8080. The API key is auto-detected from the Docker container on that port.

## Commands

| Command    | Description                          |
|------------|--------------------------------------|
| `deploy`   | Deploy datasets and endpoints        |
| `list`     | List deployed datasets and endpoints |
| `delete`   | Delete datasets and/or endpoints     |
| `publish`  | Publish endpoints to marketplaces    |
| `update`   | Update endpoint descriptions         |
| `generate` | Generate AI descriptions via OpenRouter |

## Deploy Details

Each subdirectory under `--source-dir` becomes one dataset + one endpoint.

**`--publish` flag:** When set, each endpoint is published to the SyftHub marketplace immediately after creation. This calls the `/endpoints/{slug}/publish` API, which syncs the endpoint metadata to the configured marketplace (default: `https://syfthub.openmined.org`).

**Description resolution order:**
1. `journal_description.md` in the dataset directory (if exists)
2. `--descriptions` JSON file (fallback)
3. AI-generated via OpenRouter (when `--generate-missing` is set)

**Slug handling:**
- Slugs are auto-sanitized (lowercased, spaces to hyphens)
- Truncated to 63 chars at word boundaries, preserving the trailing suffix (e.g. `-oa`)
- The 63-char limit matches the SyftHub marketplace constraint

**File types** are auto-detected from the first dataset directory if `--file-types` is not specified.

## Publish Details

The `publish` command syncs endpoints to the configured SyftHub marketplace. An endpoint is considered unpublished if:
- Its `published` flag is `false`, **or**
- Its `published_to` list is empty (locally marked published but never synced to a marketplace)

This ensures endpoints that were created with `--publish` on older versions (which only set the local flag without syncing) are picked up and published correctly.

```bash
# Dry-run to see what would be published
./run.sh publish --port 8086 --dry-run

# Publish all unsynced endpoints
./run.sh publish --port 8086

# Publish a limited batch
./run.sh publish --port 8086 --limit 10
```

## Running Containers

| Container | Port | API Key |
|-----------|------|---------|
| space-openmined-data | 8080 | `docker inspect space-openmined-data` |
| space-cambridge-press | 8086 | `docker inspect space-cambridge-press` |
| space-unknown | 8088 | `docker inspect space-unknown` |
| space-nature-oa | 8095 | `docker inspect space-nature-oa` |
| space-openmined-models | 8098 | `docker inspect space-openmined-models` |

Access the frontend: `http://<host>:<port>/frontend/`

## Environment Variables

Set in `.env` (auto-loaded via python-dotenv):

| Variable             | Default                              | Description       |
|----------------------|--------------------------------------|-------------------|
| `SYFT_API_URL`       | `http://localhost:8080/api/v1`       | Syft Space API URL |
| `SYFT_ADMIN_API_KEY` | (auto-detected from Docker)          | Admin API key     |
| `OPENROUTER_API_KEY` | (required for `generate`)            | OpenRouter API key |
| `OPENROUTER_MODEL`   | `anthropic/claude-3.5-sonnet`        | Model for description generation |

## Project Structure

```
deploy-syft-space/
├── run.sh               # Bash wrapper for main.py
├── main.py              # CLI entry point (argparse + dispatch)
├── client.py            # SyftClient API wrapper
├── utils.py             # Dataset discovery, slugify, file type detection, progress tracking
├── commands/
│   ├── __init__.py
│   ├── list.py          # list command
│   ├── deploy.py        # deploy command
│   ├── delete.py        # delete command
│   ├── publish.py       # publish command
│   ├── update.py        # update command
│   └── generate.py      # generate command (AI descriptions)
├── .env                 # Environment variables (not committed)
└── README.md
```
