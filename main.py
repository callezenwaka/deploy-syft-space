#!/usr/bin/env python3
"""
Cambridge Journal Deployment Manager
=====================================

Consolidated CLI for managing Cambridge journal datasets and endpoints on Syft Space.

Workflow:
    1. Run generate_descriptions.py first to create journal_descriptions.json
    2. python main.py deploy      # Create datasets + endpoints
    3. python main.py publish     # Publish endpoints to marketplaces

Commands:
    python main.py list [--datasets] [--endpoints]
    python main.py deploy [--dry-run] [--limit N] [--resume]
    python main.py delete [--datasets] [--endpoints] [--dry-run] [--yes]
    python main.py publish [--dry-run] [--limit N]
    python main.py update [--dry-run] [--limit N] [--resume]
"""

import os
import sys
import json
import argparse
import requests
import time
from pathlib import Path
from typing import Optional

# =============================================================================
# Configuration
# =============================================================================

API_URL = os.getenv("SYFT_API_URL", "http://localhost:8080/api/v1")
API_KEY = os.getenv("SYFT_ADMIN_API_KEY", "fancy_api_key_874658643543")

HOST_DATASETS_PATH = Path("/home/azureuser/datasets/cambridge_loader")
CONTAINER_DATASETS_PATH = "/root/datasets/cambridge_loader"

SCRIPT_DIR = Path(__file__).parent
DESCRIPTIONS_FILE = SCRIPT_DIR / "journal_descriptions.json"
PROGRESS_FILE = SCRIPT_DIR / "progress.json"

# =============================================================================
# API Client
# =============================================================================

class SyftClient:
    """Client for Syft Space API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def check_connection(self) -> bool:
        """Verify API connection."""
        try:
            r = requests.get(f"{self.base_url}/datasets/types/", headers=self._headers(), timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Datasets
    # -------------------------------------------------------------------------

    def list_datasets(self) -> list:
        """List all datasets."""
        r = requests.get(f"{self.base_url}/datasets/", headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_dataset(self, name: str) -> Optional[dict]:
        """Get a dataset by name."""
        r = requests.get(f"{self.base_url}/datasets/{name}", headers=self._headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
        return None

    def create_dataset(self, payload: dict) -> tuple[bool, dict | str]:
        """Create a dataset. Returns (success, data_or_error)."""
        r = requests.post(f"{self.base_url}/datasets/", headers=self._headers(), json=payload, timeout=30)
        if r.status_code == 201:
            return True, r.json()
        elif r.status_code == 409 or "already exists" in r.text.lower():
            existing = self.get_dataset(payload["name"])
            if existing:
                return True, existing
            return False, "Dataset exists but couldn't fetch"
        return False, f"{r.status_code}: {r.text[:200]}"

    def delete_dataset(self, name: str) -> tuple[bool, str]:
        """Delete a dataset."""
        r = requests.delete(f"{self.base_url}/datasets/{name}", headers=self._headers(), timeout=30)
        if r.status_code in [200, 204]:
            return True, "Deleted"
        elif r.status_code == 404:
            return True, "Not found"
        return False, f"{r.status_code}: {r.text[:200]}"

    # -------------------------------------------------------------------------
    # Endpoints
    # -------------------------------------------------------------------------

    def list_endpoints(self) -> list:
        """List all endpoints."""
        r = requests.get(f"{self.base_url}/endpoints/", headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def get_endpoint(self, slug: str) -> Optional[dict]:
        """Get an endpoint by slug."""
        r = requests.get(f"{self.base_url}/endpoints/{slug}", headers=self._headers(), timeout=10)
        if r.status_code == 200:
            return r.json()
        return None

    def create_endpoint(self, payload: dict) -> tuple[bool, dict | str]:
        """Create an endpoint. Returns (success, data_or_error)."""
        r = requests.post(f"{self.base_url}/endpoints/", headers=self._headers(), json=payload, timeout=30)
        if r.status_code == 201:
            return True, r.json()
        elif r.status_code == 409 or "already exists" in r.text.lower():
            return True, {"slug": payload["slug"], "exists": True}
        return False, f"{r.status_code}: {r.text[:200]}"

    def update_endpoint(self, slug: str, payload: dict) -> tuple[bool, str]:
        """Update an endpoint."""
        r = requests.patch(f"{self.base_url}/endpoints/{slug}", headers=self._headers(), json=payload, timeout=30)
        if r.status_code == 200:
            return True, "Updated"
        return False, f"{r.status_code}: {r.text[:200]}"

    def delete_endpoint(self, slug: str) -> tuple[bool, str]:
        """Delete an endpoint."""
        r = requests.delete(f"{self.base_url}/endpoints/{slug}", headers=self._headers(), timeout=30)
        if r.status_code in [200, 204]:
            return True, "Deleted"
        elif r.status_code == 404:
            return True, "Not found"
        return False, f"{r.status_code}: {r.text[:200]}"

    def publish_endpoint(self, slug: str) -> tuple[bool, str]:
        """Publish an endpoint."""
        r = requests.post(
            f"{self.base_url}/endpoints/{slug}/publish",
            headers=self._headers(),
            json={"publish_to_all_marketplaces": True},
            timeout=30
        )
        if r.status_code in [200, 201]:
            return True, "Published"
        return False, f"{r.status_code}: {r.text[:200]}"


# =============================================================================
# Progress Tracking
# =============================================================================

def load_progress() -> dict:
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"deployed": [], "updated": [], "failed": []}


def save_progress(progress: dict):
    """Save progress to file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def load_descriptions() -> dict:
    """Load journal descriptions from file."""
    if DESCRIPTIONS_FILE.exists():
        with open(DESCRIPTIONS_FILE) as f:
            return json.load(f)
    return {}


# =============================================================================
# Journal Discovery
# =============================================================================

def get_journal_directories() -> list[str]:
    """Return sorted list of journal directory names."""
    journals = []
    for item in sorted(HOST_DATASETS_PATH.iterdir()):
        if item.is_dir() and not item.name.startswith('.'):
            if any(item.glob("*.json")) or (item / "pdfs").exists():
                journals.append(item.name)
    return journals


def infer_tags(journal_name: str) -> list[str]:
    """Infer tags from journal name."""
    tags = ["cambridge", "open-access", "journal"]
    name_lower = journal_name.lower()
    if "law" in name_lower or "legal" in name_lower:
        tags.append("law")
    if "medical" in name_lower or "health" in name_lower or "psych" in name_lower:
        tags.append("health")
    if "economic" in name_lower or "finance" in name_lower:
        tags.append("economics")
    if "politic" in name_lower or "government" in name_lower:
        tags.append("politics")
    return tags


# =============================================================================
# Commands
# =============================================================================

def cmd_list(args):
    """List datasets and/or endpoints."""
    client = SyftClient(API_URL, API_KEY)

    show_datasets = args.datasets or (not args.datasets and not args.endpoints)
    show_endpoints = args.endpoints or (not args.datasets and not args.endpoints)

    if show_datasets:
        print("=" * 60)
        print("DATASETS")
        print("=" * 60)
        try:
            datasets = client.list_datasets()
            print(f"Total: {len(datasets)}\n")
            for ds in datasets:
                print(f"  - {ds['name']}")
        except Exception as e:
            print(f"Error: {e}")

    if show_endpoints:
        print("\n" + "=" * 60)
        print("ENDPOINTS")
        print("=" * 60)
        try:
            endpoints = client.list_endpoints()
            published = sum(1 for ep in endpoints if ep.get("published"))
            print(f"Total: {len(endpoints)} ({published} published)\n")
            for ep in endpoints:
                status = "published" if ep.get("published") else "unpublished"
                print(f"  - {ep['slug']} ({status})")
        except Exception as e:
            print(f"Error: {e}")


def cmd_deploy(args):
    """Deploy journals as datasets and endpoints."""
    client = SyftClient(API_URL, API_KEY)

    print("=" * 60)
    print("DEPLOY JOURNALS")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Check API
    if not args.dry_run:
        if not client.check_connection():
            print("Error: Cannot connect to API")
            return 1
        print("API connected\n")

    # Load resources
    progress = load_progress() if args.resume else {"deployed": [], "updated": [], "failed": []}
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
    success, skipped, failed = 0, 0, 0

    for i, journal in enumerate(journals, 1):
        print(f"[{i}/{len(journals)}] {journal}")

        # Skip if already deployed
        if args.resume and journal in progress["deployed"]:
            print("    Skipped (already deployed)")
            skipped += 1
            continue

        # Build dataset payload
        dataset_name = f"{journal}-journal-oa"
        dataset_payload = {
            "name": dataset_name,
            "dtype": "local_file",
            "configuration": {
                "filePaths": [{"path": f"{CONTAINER_DATASETS_PATH}/{journal}", "description": f"Cambridge Core - {journal}"}],
                "ingestFileTypeOptions": [".pdf", ".json"]
            },
            "summary": f"Open access articles from Cambridge Core: {journal}",
            "tags": ",".join(infer_tags(journal))
        }

        if args.dry_run:
            print(f"    [DRY RUN] Would create dataset: {dataset_name}")
        else:
            ok, result = client.create_dataset(dataset_payload)
            if ok:
                print(f"    Dataset: {dataset_name}")
            else:
                print(f"    Dataset failed: {result}")
                progress["failed"].append(journal)
                save_progress(progress)
                failed += 1
                continue

            dataset_id = result.get("id") if isinstance(result, dict) else None
            time.sleep(args.delay)

        # Build endpoint payload
        endpoint_slug = f"{journal}-oa"
        endpoint_name = endpoint_slug  # Use slug as name (no spaces)
        description = descriptions.get(journal, f"Query endpoint for {journal} - Cambridge Core open access articles")

        endpoint_payload = {
            "name": endpoint_name,
            "slug": endpoint_slug,
            "description": description,
            "summary": f"Cambridge Core open access journal: {journal.replace('-', ' ').title()}",
            "response_type": "both",
            "published": True,  # Mark as published (not Draft)
            "tags": "cambridge,rag,journal"
        }

        if not args.dry_run and dataset_id:
            endpoint_payload["dataset_id"] = dataset_id

        if args.dry_run:
            print(f"    [DRY RUN] Would create endpoint: {endpoint_slug}")
        else:
            ok, result = client.create_endpoint(endpoint_payload)
            if ok:
                print(f"    Endpoint: {endpoint_slug}")
            else:
                print(f"    Endpoint failed: {result}")
                progress["failed"].append(journal)
                save_progress(progress)
                failed += 1
                continue

            time.sleep(args.delay)

        success += 1
        if not args.dry_run:
            progress["deployed"].append(journal)
            save_progress(progress)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Success:  {success}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")

    return 0 if failed == 0 else 1


def cmd_delete(args):
    """Delete datasets and/or endpoints."""
    client = SyftClient(API_URL, API_KEY)

    delete_endpoints = args.endpoints or (not args.datasets and not args.endpoints)
    delete_datasets = args.datasets or (not args.datasets and not args.endpoints)

    print("=" * 60)
    print("DELETE RESOURCES")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {args.dry_run}")
    print(f"Delete endpoints: {delete_endpoints}")
    print(f"Delete datasets: {delete_datasets}")
    print()

    if not args.dry_run and not args.yes:
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            print("Aborted")
            return 0

    # Delete endpoints first (they depend on datasets)
    if delete_endpoints:
        print("\nDeleting endpoints...")
        print("-" * 40)
        try:
            endpoints = client.list_endpoints()
            for i, ep in enumerate(endpoints, 1):
                slug = ep["slug"]
                if args.dry_run:
                    print(f"  [{i}/{len(endpoints)}] [DRY RUN] Would delete: {slug}")
                else:
                    ok, msg = client.delete_endpoint(slug)
                    status = "Deleted" if ok else f"Failed: {msg}"
                    print(f"  [{i}/{len(endpoints)}] {slug}: {status}")
                    time.sleep(args.delay)
            print(f"\nEndpoints: {len(endpoints)} processed")
        except Exception as e:
            print(f"Error listing endpoints: {e}")

    # Delete datasets
    if delete_datasets:
        print("\nDeleting datasets...")
        print("-" * 40)
        try:
            datasets = client.list_datasets()
            for i, ds in enumerate(datasets, 1):
                name = ds["name"]
                if args.dry_run:
                    print(f"  [{i}/{len(datasets)}] [DRY RUN] Would delete: {name}")
                else:
                    ok, msg = client.delete_dataset(name)
                    status = "Deleted" if ok else f"Failed: {msg}"
                    print(f"  [{i}/{len(datasets)}] {name}: {status}")
                    time.sleep(args.delay)
            print(f"\nDatasets: {len(datasets)} processed")
        except Exception as e:
            print(f"Error listing datasets: {e}")

    # Clear progress file
    if not args.dry_run:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
            print("\nProgress file cleared")

    return 0


def cmd_publish(args):
    """Publish unpublished endpoints."""
    client = SyftClient(API_URL, API_KEY)

    print("=" * 60)
    print("PUBLISH ENDPOINTS")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {args.dry_run}")
    print()

    try:
        endpoints = client.list_endpoints()
        unpublished = [ep for ep in endpoints if not ep.get("published")]

        if args.limit > 0:
            unpublished = unpublished[:args.limit]

        print(f"Found {len(unpublished)} unpublished endpoints")
        print()

        if not unpublished:
            print("Nothing to publish")
            return 0

        success, failed = 0, 0
        for i, ep in enumerate(unpublished, 1):
            slug = ep["slug"]
            if args.dry_run:
                print(f"  [{i}/{len(unpublished)}] [DRY RUN] Would publish: {slug}")
                success += 1
            else:
                ok, msg = client.publish_endpoint(slug)
                if ok:
                    print(f"  [{i}/{len(unpublished)}] {slug}: Published")
                    success += 1
                else:
                    print(f"  [{i}/{len(unpublished)}] {slug}: Failed - {msg}")
                    failed += 1
                time.sleep(args.delay)

        print(f"\nPublished: {success}, Failed: {failed}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def cmd_update(args):
    """Update endpoint descriptions from journal_descriptions.json."""
    client = SyftClient(API_URL, API_KEY)

    print("=" * 60)
    print("UPDATE ENDPOINT DESCRIPTIONS")
    print("=" * 60)
    print(f"API: {API_URL}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Load descriptions
    descriptions = load_descriptions()
    if not descriptions:
        print("Error: No descriptions found. Run generate_descriptions.py first.")
        return 1
    print(f"Loaded {len(descriptions)} descriptions")

    # Load progress
    progress = load_progress() if args.resume else {"deployed": [], "updated": [], "failed": []}

    try:
        endpoints = client.list_endpoints()

        if args.limit > 0:
            endpoints = endpoints[:args.limit]

        print(f"Found {len(endpoints)} endpoints\n")

        success, skipped, failed, no_desc = 0, 0, 0, 0

        for i, ep in enumerate(endpoints, 1):
            slug = ep["slug"]
            journal = slug.replace("-oa", "")

            print(f"[{i}/{len(endpoints)}] {slug}")

            if args.resume and slug in progress["updated"]:
                print("    Skipped (already updated)")
                skipped += 1
                continue

            if journal not in descriptions:
                print(f"    No description for: {journal}")
                no_desc += 1
                continue

            payload = {
                "description": descriptions[journal],
                "summary": f"Cambridge Core open access journal: {journal.replace('-', ' ').title()}"
            }

            if args.dry_run:
                print(f"    [DRY RUN] Would update ({len(descriptions[journal])} chars)")
                success += 1
            else:
                ok, msg = client.update_endpoint(slug, payload)
                if ok:
                    print(f"    Updated")
                    progress["updated"].append(slug)
                    save_progress(progress)
                    success += 1
                else:
                    print(f"    Failed: {msg}")
                    failed += 1
                time.sleep(args.delay)

        print(f"\nUpdated: {success}, Skipped: {skipped}, No description: {no_desc}, Failed: {failed}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Cambridge Journal Deployment Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  list      List deployed datasets and endpoints
  deploy    Deploy journals as datasets and endpoints
  delete    Delete datasets and/or endpoints
  publish   Publish unpublished endpoints
  update    Update endpoint descriptions

Examples:
  python main.py list
  python main.py deploy --dry-run
  python main.py deploy --limit 5
  python main.py delete --endpoints --dry-run
  python main.py delete --yes
  python main.py publish --dry-run
  python main.py update --dry-run
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    p_list = subparsers.add_parser("list", help="List datasets and endpoints")
    p_list.add_argument("--datasets", action="store_true", help="List only datasets")
    p_list.add_argument("--endpoints", action="store_true", help="List only endpoints")

    # deploy
    p_deploy = subparsers.add_parser("deploy", help="Deploy journals")
    p_deploy.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_deploy.add_argument("--limit", type=int, default=0, help="Limit to N journals")
    p_deploy.add_argument("--resume", action="store_true", help="Skip already deployed journals")
    p_deploy.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (seconds)")

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete resources")
    p_delete.add_argument("--datasets", action="store_true", help="Delete only datasets")
    p_delete.add_argument("--endpoints", action="store_true", help="Delete only endpoints")
    p_delete.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p_delete.add_argument("--delay", type=float, default=0.3, help="Delay between API calls (seconds)")

    # publish
    p_publish = subparsers.add_parser("publish", help="Publish endpoints")
    p_publish.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_publish.add_argument("--limit", type=int, default=0, help="Limit to N endpoints")
    p_publish.add_argument("--delay", type=float, default=0.3, help="Delay between API calls (seconds)")

    # update
    p_update = subparsers.add_parser("update", help="Update endpoint descriptions")
    p_update.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_update.add_argument("--limit", type=int, default=0, help="Limit to N endpoints")
    p_update.add_argument("--resume", action="store_true", help="Skip already updated endpoints")
    p_update.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (seconds)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "list": cmd_list,
        "deploy": cmd_deploy,
        "delete": cmd_delete,
        "publish": cmd_publish,
        "update": cmd_update,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
