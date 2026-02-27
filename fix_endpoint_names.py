#!/usr/bin/env python3
"""
Fix Endpoint Names - Remove Spaces
===================================
Deletes endpoints with spaces in their names and recreates them with proper names.
"""

import os
import json
import requests
import time
from pathlib import Path
from typing import Dict, List, Optional

# =============================================================================
# Configuration
# =============================================================================

API_URL = os.getenv("SYFT_API_URL", "http://localhost:8080/api/v1")
API_KEY = os.getenv("SYFT_ADMIN_API_KEY", "fancy_api_key_874658643543")

PROGRESS_FILE = Path("fix_endpoint_names_progress.json")
DRY_RUN = False  # Set to True to test without making changes

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
# Progress Tracking
# =============================================================================

def load_progress() -> dict:
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        "fixed": [],
        "failed": [],
        "skipped": [],
        "in_progress": None
    }

def save_progress(progress: dict):
    """Save progress to file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

# =============================================================================
# Endpoint Operations
# =============================================================================

def fetch_endpoints_with_spaces() -> List[dict]:
    """Fetch all endpoints that have spaces in their name."""
    try:
        r = requests.get(f"{API_URL}/endpoints/", headers=api_headers(), timeout=30)
        if r.status_code == 200:
            all_endpoints = r.json()
            # Filter endpoints with spaces in name
            endpoints_with_spaces = [ep for ep in all_endpoints if " " in ep.get("name", "")]
            return endpoints_with_spaces
        else:
            print(f"✗ Failed to fetch endpoints: {r.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error fetching endpoints: {e}")
        return []

def generate_proper_name(slug: str) -> str:
    """Generate a proper name from slug (without spaces)."""
    # Remove the -oa suffix if present
    base_name = slug.replace("-oa", "")
    # Keep it as a slug format (no spaces, just hyphens)
    # Or we could title case without spaces:
    # return base_name.replace("-", "").title()
    # But let's just keep it simple and use the slug as the name
    return slug

def delete_endpoint(endpoint_id: str, slug: str) -> bool:
    """Delete an endpoint."""
    if DRY_RUN:
        print(f"    [DRY RUN] Would delete endpoint: {slug}")
        return True

    try:
        r = requests.delete(
            f"{API_URL}/endpoints/{slug}",
            headers=api_headers(),
            timeout=30
        )
        if r.status_code == 204 or r.status_code == 200:
            return True
        else:
            print(f"    ✗ Delete failed ({r.status_code}): {r.text[:200]}")
            return False
    except Exception as e:
        print(f"    ✗ Delete error: {e}")
        return False

def create_endpoint(endpoint_data: dict) -> bool:
    """Recreate endpoint with proper name."""
    slug = endpoint_data["slug"]
    new_name = generate_proper_name(slug)

    payload = {
        "name": new_name,
        "slug": slug,
        "description": endpoint_data.get("description", ""),
        "summary": endpoint_data.get("summary", ""),
        "dataset_id": endpoint_data["dataset"]["id"],
        "response_type": endpoint_data.get("response_type", "both"),
        "tags": endpoint_data.get("tags", ""),
        "model": endpoint_data.get("model")
    }

    if DRY_RUN:
        print(f"    [DRY RUN] Would create endpoint: {slug}")
        print(f"              New name: {new_name}")
        return True

    try:
        # Create endpoint
        r = requests.post(
            f"{API_URL}/endpoints/",
            headers=api_headers(),
            json=payload,
            timeout=30
        )

        if r.status_code == 201:
            # Publish if the original was published
            if endpoint_data.get("published", False):
                time.sleep(0.5)  # Brief pause before publishing
                publish_r = requests.post(
                    f"{API_URL}/endpoints/{slug}/publish",
                    headers=api_headers(),
                    json={"publish_to_all_marketplaces": True},
                    timeout=30
                )
                if publish_r.status_code not in [200, 201]:
                    print(f"    ⚠ Created but publish failed: {publish_r.status_code}")
                    if publish_r.status_code != 200:
                        print(f"      Error: {publish_r.text[:200]}")
            return True
        else:
            print(f"    ✗ Create failed ({r.status_code}): {r.text[:200]}")
            return False
    except Exception as e:
        print(f"    ✗ Create error: {e}")
        return False

def fix_endpoint(endpoint: dict, progress: dict) -> bool:
    """Fix a single endpoint (delete and recreate)."""
    slug = endpoint["slug"]
    old_name = endpoint["name"]
    endpoint_id = endpoint["id"]

    # Check if already fixed
    if slug in progress["fixed"]:
        print(f"    ⊙ Already fixed: {slug}")
        return True

    print(f"    Old name: '{old_name}'")
    print(f"    New name: '{generate_proper_name(slug)}'")

    # Step 1: Delete
    print(f"    Deleting...", end=" ")
    if not delete_endpoint(endpoint_id, slug):
        return False
    print("✓")

    # Step 2: Wait briefly
    if not DRY_RUN:
        time.sleep(1)

    # Step 3: Recreate
    print(f"    Recreating...", end=" ")
    if not create_endpoint(endpoint):
        print("✗")
        return False
    print("✓")

    return True

# =============================================================================
# Main Process
# =============================================================================

def main():
    print("=" * 60)
    print("Fix Endpoint Names - Remove Spaces")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {DRY_RUN}")
    print()

    # Check API connection
    if not check_api():
        print("✗ Cannot connect to API")
        return

    # Load progress
    progress = load_progress()
    print(f"Progress: {len(progress['fixed'])} fixed, {len(progress['failed'])} failed")
    print()

    # Fetch endpoints with spaces
    print("Fetching endpoints with spaces in names...")
    endpoints = fetch_endpoints_with_spaces()
    print(f"✓ Found {len(endpoints)} endpoints to fix")
    print()

    # Filter out already fixed
    endpoints_to_fix = [
        ep for ep in endpoints
        if ep["slug"] not in progress["fixed"]
    ]

    if not endpoints_to_fix:
        print("✓ All endpoints already fixed!")
        return

    print(f"Starting fixes ({len(endpoints_to_fix)} remaining)...")
    print("-" * 60)
    print()

    # Process each endpoint
    for idx, endpoint in enumerate(endpoints_to_fix, 1):
        slug = endpoint["slug"]

        print(f"[{idx}/{len(endpoints_to_fix)}] {slug}")

        # Update progress
        progress["in_progress"] = slug
        save_progress(progress)

        # Fix endpoint
        try:
            success = fix_endpoint(endpoint, progress)

            if success:
                progress["fixed"].append(slug)
                print(f"    ✓ Fixed: {slug}")
            else:
                progress["failed"].append(slug)
                print(f"    ✗ Failed: {slug}")
        except Exception as e:
            print(f"    ✗ Error: {e}")
            progress["failed"].append(slug)

        # Save progress
        progress["in_progress"] = None
        save_progress(progress)
        print()

        # Brief pause between endpoints
        if not DRY_RUN and idx < len(endpoints_to_fix):
            time.sleep(0.5)

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Fixed:   {len(progress['fixed'])}")
    print(f"Failed:  {len(progress['failed'])}")
    print(f"Skipped: {len(progress['skipped'])}")
    print()

    if progress["failed"]:
        print("Failed endpoints:")
        for slug in progress["failed"]:
            print(f"  - {slug}")

    print()
    print(f"Progress saved to: {PROGRESS_FILE}")

if __name__ == "__main__":
    main()
