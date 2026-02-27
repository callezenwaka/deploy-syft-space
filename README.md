# Cambridge Journal Deployment Manager

Consolidated CLI for deploying Cambridge journal datasets and endpoints to Syft Space.

## Prerequisites

- Syft Space running on `http://localhost:8080`
- API key configured (default: `fancy_api_key_874658643543`)
- Journal data at `/home/azureuser/datasets/cambridge_loader/`
- Journal descriptions in `journal_descriptions.json` (generated separately)

## Deployment Process

```bash
# 1. Generate descriptions (one-time, requires OPENROUTER_API_KEY)
python3 generate_descriptions.py

# 2. Delete existing resources (if redeploying)
python3 main.py delete --dry-run   # preview
python3 main.py delete --yes       # execute

# 3. Deploy datasets + endpoints
python3 main.py deploy --dry-run   # preview
python3 main.py deploy             # execute

# 4. Publish to marketplaces
python3 main.py publish --dry-run  # preview
python3 main.py publish            # execute
```

## Commands

| Command | Description |
|---------|-------------|
| `list` | List deployed datasets and endpoints |
| `deploy` | Create datasets and endpoints |
| `delete` | Delete datasets and/or endpoints |
| `publish` | Publish endpoints to marketplaces |
| `update` | Update endpoint descriptions |

## Usage Examples

### List Resources

```bash
python3 main.py list              # list all
python3 main.py list --datasets   # datasets only
python3 main.py list --endpoints  # endpoints only
```

### Deploy

```bash
python3 main.py deploy --dry-run          # preview
python3 main.py deploy --limit 5          # deploy first 5
python3 main.py deploy --resume           # resume interrupted deploy
python3 main.py deploy --delay 0.5        # custom delay between API calls
```

### Delete

```bash
python3 main.py delete --dry-run          # preview all deletions
python3 main.py delete --endpoints --dry-run  # preview endpoint deletions only
python3 main.py delete --datasets --dry-run   # preview dataset deletions only
python3 main.py delete --yes              # delete all (skip confirmation)
```

### Publish

```bash
python3 main.py publish --dry-run         # preview
python3 main.py publish --limit 10        # publish first 10
```

### Update Descriptions

```bash
python3 main.py update --dry-run          # preview
python3 main.py update --resume           # skip already updated
```

## Running with tmux

For long-running operations:

```bash
# Start a new tmux session
tmux new -s deploy

# Run the command
python3 main.py deploy 2>&1 | tee deploy.log

# Detach: Ctrl+B, then D

# Reattach later
tmux attach -t deploy

# List sessions
tmux ls

# Kill session when done
tmux kill-session -t deploy
```

## Files

| File | Description |
|------|-------------|
| `main.py` | Consolidated deployment CLI |
| `generate_descriptions.py` | Generate journal descriptions (standalone) |
| `journal_descriptions.json` | AI-generated journal descriptions |
| `progress.json` | Tracks deploy/update progress |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SYFT_API_URL` | `http://localhost:8080/api/v1` | Syft Space API URL |
| `SYFT_ADMIN_API_KEY` | `fancy_api_key_874658643543` | Admin API key |
| `OPENROUTER_API_KEY` | (required) | For generate_descriptions.py |

## Naming Convention

| Resource | Pattern | Example |
|----------|---------|---------|
| Dataset | `{journal}-journal-oa` | `acta-numerica-journal-oa` |
| Endpoint slug | `{journal}-oa` | `acta-numerica-oa` |
| Endpoint name | `{journal}-oa` | `acta-numerica-oa` |

## Troubleshooting

### Check API Connection

```bash
curl -s http://localhost:8080/health
curl -s -H "Authorization: Bearer fancy_api_key_874658643543" \
  http://localhost:8080/api/v1/datasets/types/
```

### Check Progress

```bash
cat progress.json | python3 -m json.tool
```

### Reset Progress

```bash
rm progress.json
```
