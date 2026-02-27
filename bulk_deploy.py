#!/usr/bin/env python3
"""
Bulk deploy Cambridge journal datasets to Syft Space.

Usage:
    python bulk_deploy.py --dry-run          # Preview changes
    python bulk_deploy.py --limit 5          # Deploy first 5 journals
    python bulk_deploy.py                    # Deploy all journals
    python bulk_deploy.py --resume           # Resume from progress file
"""

import os
import json
import requests
import argparse
from pathlib import Path
import time

# =============================================================================
# Configuration
# =============================================================================

API_URL = os.getenv("SYFT_API_URL", "http://localhost:8080/api/v1")
API_KEY = os.getenv("SYFT_ADMIN_API_KEY", "fancy_api_key_874658643543")

HOST_DATASETS_PATH = Path("/home/azureuser/datasets/cambridge_loader")
CONTAINER_DATASETS_PATH = "/root/datasets/cambridge_loader"

PROGRESS_FILE = Path(__file__).parent / "deploy_progress.json"
DESCRIPTIONS_FILE = Path(__file__).parent / "journal_descriptions.json"

# =============================================================================
# Journal Descriptions
# =============================================================================

def load_descriptions() -> dict:
    """Load journal descriptions from file."""
    if DESCRIPTIONS_FILE.exists():
        with open(DESCRIPTIONS_FILE) as f:
            return json.load(f)
    return {}

# =============================================================================
# Progress Tracking
# =============================================================================

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": [], "failed": [], "in_progress": None}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

# =============================================================================
# Journal Discovery
# =============================================================================

def get_journal_directories() -> list[str]:
    """Return sorted list of journal directory names."""
    journals = []
    for item in sorted(HOST_DATASETS_PATH.iterdir()):
        if item.is_dir() and not item.name.startswith('.'):
            # Must have content (json or pdfs)
            if any(item.glob("*.json")) or (item / "pdfs").exists():
                journals.append(item.name)
    return journals

# =============================================================================
# API Helpers
# =============================================================================

def api_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }


def check_api():
    """Verify API connection."""
    try:
        r = requests.get(f"{API_URL}/datasets/types/", headers=api_headers(), timeout=10)
        return r.status_code == 200
    except:
        return False

# =============================================================================
# Dataset Creation
# =============================================================================

def create_dataset(journal_name: str, dry_run: bool = False) -> dict | None:
    """Create a dataset for a journal. Returns dataset dict or None on failure."""

    dataset_name = f"{journal_name}-journal-oa"
    container_path = f"{CONTAINER_DATASETS_PATH}/{journal_name}"

    # Infer tags from journal name
    tags = ["cambridge", "open-access", "journal"]
    if "law" in journal_name or "legal" in journal_name:
        tags.append("law")
    if "medical" in journal_name or "health" in journal_name or "psych" in journal_name:
        tags.append("health")
    if "economic" in journal_name or "finance" in journal_name:
        tags.append("economics")
    if "politic" in journal_name or "government" in journal_name:
        tags.append("politics")

    payload = {
        "name": dataset_name,
        "dtype": "local_file",
        "configuration": {
            "filePaths": [
                {"path": container_path, "description": f"Cambridge Core - {journal_name}"}
            ],
            "ingestFileTypeOptions": [".pdf", ".json"]
        },
        "summary": f"Open access articles from Cambridge Core: {journal_name}",
        "tags": ",".join(tags)
    }

    if dry_run:
        print(f"    [DRY RUN] Would create dataset: {dataset_name}")
        print(f"              Path: {container_path}")
        return {"id": "dry-run-id", "name": dataset_name}

    try:
        r = requests.post(f"{API_URL}/datasets/", headers=api_headers(), json=payload, timeout=30)

        if r.status_code == 201:
            data = r.json()
            print(f"    ✓ Dataset created: {dataset_name}")
            return data
        elif r.status_code == 409 or "already exists" in r.text.lower():
            print(f"    ⚠ Dataset exists: {dataset_name}")
            # Try to fetch existing
            r2 = requests.get(f"{API_URL}/datasets/{dataset_name}", headers=api_headers(), timeout=10)
            if r2.status_code == 200:
                return r2.json()
            return None
        else:
            print(f"    ✗ Dataset failed: {r.status_code} - {r.text[:100]}")
            return None
    except Exception as e:
        print(f"    ✗ Dataset error: {e}")
        return None

# =============================================================================
# Endpoint Creation
# =============================================================================

def create_endpoint(dataset: dict, journal_name: str, descriptions: dict, dry_run: bool = False) -> dict | None:
    """Create and publish an endpoint for a dataset."""

    endpoint_slug = f"{journal_name}-oa"
    endpoint_name = journal_name.replace("-", " ").title()
    dataset_id = dataset.get("id")

    # Use detailed description if available, otherwise fallback
    if journal_name in descriptions:
        description = descriptions[journal_name]
        summary = f"Cambridge Core open access journal: {endpoint_name}"
    else:
        description = f"Query endpoint for {endpoint_name} - Cambridge Core open access articles"
        summary = f"RAG endpoint for {endpoint_name}"

    payload = {
        "name": endpoint_name,
        "slug": endpoint_slug,
        "description": description,
        "summary": summary,
        "dataset_id": dataset_id,
        "response_type": "both",
        "published": True,
        "tags": "cambridge,rag,journal"
    }

    if dry_run:
        print(f"    [DRY RUN] Would create endpoint: {endpoint_slug} (published)")
        return {"id": "dry-run-id", "slug": endpoint_slug}

    try:
        r = requests.post(f"{API_URL}/endpoints/", headers=api_headers(), json=payload, timeout=30)

        if r.status_code == 201:
            data = r.json()
            print(f"    ✓ Endpoint created: {endpoint_slug} (published)")
            return data
        elif r.status_code == 409 or "already exists" in r.text.lower():
            print(f"    ⚠ Endpoint exists: {endpoint_slug}")
            return {"slug": endpoint_slug, "exists": True}
        else:
            print(f"    ✗ Endpoint failed: {r.status_code} - {r.text[:100]}")
            return None
    except Exception as e:
        print(f"    ✗ Endpoint error: {e}")
        return None

# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Bulk deploy Cambridge journals to Syft Space")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--limit", type=int, default=0, help="Limit to N journals (0 = all)")
    parser.add_argument("--resume", action="store_true", help="Resume from progress file")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    print("=" * 60)
    print("Cambridge Journal Bulk Deployment")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Check API
    if not args.dry_run:
        print("Checking API connection...")
        if not check_api():
            print("✗ Cannot connect to API")
            return 1
        print("✓ API connected")
        print()

    # Load progress
    progress = load_progress() if args.resume else {"completed": [], "failed": [], "in_progress": None}

    # Load descriptions
    descriptions = load_descriptions()
    print(f"Loaded {len(descriptions)} journal descriptions")

    # Get journals
    journals = get_journal_directories()
    print(f"Found {len(journals)} journals")

    if args.limit > 0:
        journals = journals[:args.limit]
        print(f"Limited to {args.limit}")
    print()

    # Deploy
    print("Starting deployment...")
    print("-" * 60)

    success = 0
    skipped = 0
    failed = 0

    for i, journal in enumerate(journals, 1):
        print(f"\n[{i}/{len(journals)}] {journal}")

        # Skip if already completed
        if args.resume and journal in progress["completed"]:
            print("    ⏭ Already completed, skipping")
            skipped += 1
            continue

        # Mark in progress
        progress["in_progress"] = journal
        if not args.dry_run:
            save_progress(progress)

        # Create dataset
        dataset = create_dataset(journal, args.dry_run)

        if not dataset:
            failed += 1
            if not args.dry_run:
                progress["failed"].append(journal)
                progress["in_progress"] = None
                save_progress(progress)
            continue

        # Delay
        if not args.dry_run:
            time.sleep(args.delay)

        # Create endpoint
        endpoint = create_endpoint(dataset, journal, descriptions, args.dry_run)

        if not endpoint:
            failed += 1
            if not args.dry_run:
                progress["failed"].append(journal)
                progress["in_progress"] = None
                save_progress(progress)
            continue

        # Mark completed
        success += 1
        if not args.dry_run:
            progress["completed"].append(journal)
            progress["in_progress"] = None
            save_progress(progress)

        # Delay before next
        if not args.dry_run and i < len(journals):
            time.sleep(args.delay)

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total:    {len(journals)}")
    print(f"Success:  {success}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")

    if not args.dry_run:
        print(f"\nProgress saved to: {PROGRESS_FILE}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
