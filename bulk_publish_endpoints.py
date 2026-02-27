#!/usr/bin/env python3
"""
Bulk Publish Endpoints
======================
Publishes all unpublished endpoints to all marketplaces.
"""

import os
import requests
import time
from pathlib import Path

# =============================================================================
# Configuration
# =============================================================================

API_URL = os.getenv("SYFT_API_URL", "http://localhost:8080/api/v1")
API_KEY = os.getenv("SYFT_ADMIN_API_KEY", "fancy_api_key_874658643543")

DRY_RUN = False  # Set to True to test without publishing

# =============================================================================
# API Helpers
# =============================================================================

def api_headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

def fetch_endpoints():
    """Fetch all endpoints."""
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

def publish_endpoint(slug: str) -> bool:
    """Publish an endpoint to all marketplaces."""
    if DRY_RUN:
        print(f"    [DRY RUN] Would publish: {slug}")
        return True

    try:
        r = requests.post(
            f"{API_URL}/endpoints/{slug}/publish",
            headers=api_headers(),
            json={"publish_to_all_marketplaces": True},
            timeout=30
        )
        if r.status_code in [200, 201]:
            return True
        else:
            print(f"    ✗ Publish failed ({r.status_code}): {r.text[:200]}")
            return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False

# =============================================================================
# Main Process
# =============================================================================

def main():
    print("=" * 60)
    print("Bulk Publish Endpoints")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {DRY_RUN}")
    print()

    # Fetch all endpoints
    print("Fetching endpoints...")
    endpoints = fetch_endpoints()
    print(f"✓ Found {len(endpoints)} total endpoints")

    # Filter unpublished
    unpublished = [ep for ep in endpoints if not ep.get("published", False)]
    print(f"✓ Found {len(unpublished)} unpublished endpoints")
    print()

    if not unpublished:
        print("✓ All endpoints are already published!")
        return

    print(f"Publishing {len(unpublished)} endpoints...")
    print("-" * 60)
    print()

    # Publish each endpoint
    published_count = 0
    failed_count = 0

    for idx, endpoint in enumerate(unpublished, 1):
        slug = endpoint["slug"]
        name = endpoint.get("name", slug)

        print(f"[{idx}/{len(unpublished)}] {slug}")

        if publish_endpoint(slug):
            published_count += 1
            print(f"    ✓ Published")
        else:
            failed_count += 1
            print(f"    ✗ Failed")

        print()

        # Brief pause between publishes
        if not DRY_RUN and idx < len(unpublished):
            time.sleep(0.3)

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Published:     {published_count}")
    print(f"Failed:        {failed_count}")
    print(f"Already published: {len(endpoints) - len(unpublished)}")
    print(f"Total:         {len(endpoints)}")

if __name__ == "__main__":
    main()
