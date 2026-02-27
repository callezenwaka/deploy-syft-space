# Endpoint Name Fix Workflow

## ⚠️ Issue
167 out of 178 endpoints have spaces in their `name` field
- Current: `"Acta Numerica"` (with spaces)
- Should be: `"acta-numerica-oa"` (no spaces)

## ✅ Current Status
- **180 datasets deployed** ✓
- **178 endpoints deployed** ✓
- **167 endpoints need name fix** ⚠️
- **Need to**: Fix endpoint names by deleting and recreating

---

## 📋 Workflow

### Step 1: Review What Will Be Changed

```bash
cd /home/azureuser/deploy

# Check how many endpoints need fixing
curl -s http://localhost:8080/api/v1/endpoints/ \
  -H "Authorization: Bearer fancy_api_key_874658643543" | \
  python3 -c "import sys,json; eps=[e for e in json.load(sys.stdin) if ' ' in e.get('name','')]; print(f'Endpoints with spaces: {len(eps)}')"

# Preview first 5 changes
python3 -c "
import requests
API_URL = 'http://localhost:8080/api/v1'
API_KEY = 'fancy_api_key_874658643543'
headers = {'Authorization': f'Bearer {API_KEY}'}
r = requests.get(f'{API_URL}/endpoints/', headers=headers)
endpoints = [ep for ep in r.json() if ' ' in ep.get('name', '')][:5]
print('Examples of what will be changed:')
print('=' * 60)
for ep in endpoints:
    print(f\"Slug: {ep['slug']}\")
    print(f\"  Old: \\\"{ep['name']}\\\"\")
    print(f\"  New: \\\"{ep['slug']}\\\"\")
    print()
"
```

### Step 2: Test with Dry-Run

```bash
# Edit the script to enable dry-run mode
sed -i 's/DRY_RUN = False/DRY_RUN = True/' fix_endpoint_names.py

# Run dry-run to see what would happen
python3 fix_endpoint_names.py | head -50

# Review output, no actual changes made
```

### Step 3: Run the Fix

```bash
# Edit the script to disable dry-run mode
sed -i 's/DRY_RUN = True/DRY_RUN = False/' fix_endpoint_names.py

# Run in tmux for long-running process
tmux new -s fix-names
python3 fix_endpoint_names.py 2>&1 | tee fix_endpoint_names.log
# Ctrl+B, D to detach
```

**Time estimate**: ~10-15 mins for 167 endpoints

---

## 📊 Monitor Progress

```bash
# Attach to tmux session
tmux attach -t fix-names

# Watch the log file
tail -f fix_endpoint_names.log

# Check progress count
cat fix_endpoint_names_progress.json | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(f'Fixed: {len(d[\"fixed\"])}/{len(d[\"fixed\"])+len(d[\"failed\"])+len([x for x in d.values() if isinstance(x,list) and x])} endpoints')"

# Verify no spaces remain
curl -s http://localhost:8080/api/v1/endpoints/ \
  -H "Authorization: Bearer fancy_api_key_874658643543" | \
  python3 -c "import sys,json; eps=[e for e in json.load(sys.stdin) if ' ' in e.get('name','')]; print(f'Endpoints with spaces remaining: {len(eps)}')"
```

---

## ✅ Verification

After completion, verify the fix:

```bash
# Check all endpoints
curl -s http://localhost:8080/api/v1/endpoints/ \
  -H "Authorization: Bearer fancy_api_key_874658643543" | \
  python3 -c "
import sys, json
endpoints = json.load(sys.stdin)
with_spaces = [e for e in endpoints if ' ' in e.get('name', '')]
print(f'Total endpoints: {len(endpoints)}')
print(f'With spaces: {len(with_spaces)}')
print(f'Fixed: {len(endpoints) - len(with_spaces)}')
if with_spaces:
    print('\nRemaining issues:')
    for ep in with_spaces[:5]:
        print(f\"  - {ep['slug']}: {ep['name']}\")
"

# Check progress summary
cat fix_endpoint_names_progress.json | python3 -m json.tool
```

---

## 🔄 Resume After Interruption

The script automatically tracks progress. If interrupted:

```bash
# Just run again - it will skip already fixed endpoints
python3 fix_endpoint_names.py 2>&1 | tee -a fix_endpoint_names.log
```

---

## 🐛 Troubleshooting

### Check Failed Endpoints
```bash
cat fix_endpoint_names_progress.json | python3 -c \
  "import sys,json; print('\n'.join(json.load(sys.stdin).get('failed', [])))"
```

### Manually Fix One Endpoint
```bash
SLUG="acta-numerica-oa"
API_KEY="fancy_api_key_874658643543"

# Get current endpoint data
curl -s "http://localhost:8080/api/v1/endpoints/${SLUG}" \
  -H "Authorization: Bearer ${API_KEY}"

# Delete it
curl -X DELETE "http://localhost:8080/api/v1/endpoints/${SLUG}" \
  -H "Authorization: Bearer ${API_KEY}"

# Recreate with correct name (use data from above)
```

### Reset Progress
```bash
rm fix_endpoint_names_progress.json
python3 fix_endpoint_names.py
```

---
