#!/usr/bin/env python3
"""
Update existing endpoint descriptions with detailed AI-generated content.

Reads descriptions from journal_descriptions.json and updates deployed endpoints.
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

DESCRIPTIONS_FILE = Path(__file__).parent / "journal_descriptions.json"
PROGRESS_FILE = Path(__file__).parent / "update_progress.json"

# =============================================================================
# Helper Functions
# =============================================================================

def api_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }


def load_descriptions() -> dict:
    """Load journal descriptions from file."""
    if not DESCRIPTIONS_FILE.exists():
        raise FileNotFoundError(f"Descriptions file not found: {DESCRIPTIONS_FILE}")
    with open(DESCRIPTIONS_FILE) as f:
        return json.load(f)


def load_progress() -> dict:
    """Load update progress."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"updated": [], "failed": [], "skipped": []}


def save_progress(progress: dict):
    """Save update progress."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def get_all_endpoints() -> list:
    """Fetch all deployed endpoints."""
    try:
        r = requests.get(f"{API_URL}/endpoints/", headers=api_headers(), timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"✗ Failed to fetch endpoints: {r.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error fetching endpoints: {e}")
        return []


def update_endpoint(slug: str, description: str, dry_run: bool = False) -> bool:
    """Update an endpoint's description."""

    journal_name = slug.replace("-oa", "")
    endpoint_name = journal_name.replace("-", " ").title()

    payload = {
        "description": description,
        "summary": f"Cambridge Core open access journal: {endpoint_name}"
    }

    if dry_run:
        print(f"    [DRY RUN] Would update: {slug}")
        print(f"              Description length: {len(description)} chars")
        return True

    try:
        r = requests.patch(
            f"{API_URL}/endpoints/{slug}",
            headers=api_headers(),
            json=payload,
            timeout=30
        )

        if r.status_code == 200:
            print(f"    ✓ Updated: {slug}")
            return True
        else:
            print(f"    ✗ Failed: {slug} - {r.status_code}")
            print(f"      Response: {r.text[:150]}")
            return False
    except Exception as e:
        print(f"    ✗ Error: {slug} - {e}")
        return False


def journal_name_from_slug(slug: str) -> str:
    """Extract journal name from endpoint slug."""
    return slug.replace("-oa", "")

# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Update endpoint descriptions from generated content")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--limit", type=int, default=0, help="Limit to N endpoints (0 = all)")
    parser.add_argument("--resume", action="store_true", help="Skip already updated endpoints")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    print("=" * 60)
    print("Update Endpoint Descriptions")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Load descriptions
    print("Loading journal descriptions...")
    try:
        descriptions = load_descriptions()
        print(f"✓ Loaded {len(descriptions)} descriptions")
    except FileNotFoundError as e:
        print(f"✗ {e}")
        print("\nRun generate_descriptions.py first to create descriptions.")
        return 1

    # Load progress
    progress = load_progress() if args.resume else {"updated": [], "failed": [], "skipped": []}

    # Fetch endpoints
    print("\nFetching deployed endpoints...")
    endpoints = get_all_endpoints()
    if not endpoints:
        print("✗ No endpoints found or failed to fetch")
        return 1

    print(f"✓ Found {len(endpoints)} endpoints")

    # Filter endpoints
    if args.limit > 0:
        endpoints = endpoints[:args.limit]
        print(f"Limited to {args.limit}")

    print()
    print("Starting updates...")
    print("-" * 60)

    success = 0
    skipped = 0
    failed = 0
    no_description = 0

    for i, endpoint in enumerate(endpoints, 1):
        slug = endpoint.get("slug")
        journal_name = journal_name_from_slug(slug)

        print(f"\n[{i}/{len(endpoints)}] {slug}")

        # Skip if already updated
        if args.resume and slug in progress["updated"]:
            print("    ⏭ Already updated, skipping")
            skipped += 1
            continue

        # Check if description exists
        if journal_name not in descriptions:
            print(f"    ⚠ No description found for journal: {journal_name}")
            no_description += 1
            progress["skipped"].append(slug)
            if not args.dry_run:
                save_progress(progress)
            continue

        # Update endpoint
        description = descriptions[journal_name]
        if update_endpoint(slug, description, args.dry_run):
            success += 1
            if not args.dry_run:
                progress["updated"].append(slug)
                save_progress(progress)
        else:
            failed += 1
            if not args.dry_run:
                progress["failed"].append(slug)
                save_progress(progress)

        # Delay
        if not args.dry_run and i < len(endpoints):
            time.sleep(args.delay)

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total endpoints:       {len(endpoints)}")
    print(f"Updated:               {success}")
    print(f"Skipped (already done): {skipped}")
    print(f"Skipped (no desc):     {no_description}")
    print(f"Failed:                {failed}")

    if not args.dry_run:
        print(f"\nProgress saved to: {PROGRESS_FILE}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
