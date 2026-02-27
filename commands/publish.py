"""Publish unpublished endpoints to marketplaces."""

import time

from client import SyftClient


def _needs_publish(ep):
    """Check if endpoint needs publishing (not synced to any marketplace)."""
    if not ep.get("published"):
        return True
    if not ep.get("published_to"):
        return True
    return False


def cmd_publish(client: SyftClient, args):
    print("=" * 60)
    print("PUBLISH ENDPOINTS")
    print("=" * 60)
    print(f"API: {client.base_url}")
    print(f"Dry run: {args.dry_run}")
    print()

    try:
        endpoints = client.list_endpoints()
        unpublished = [ep for ep in endpoints if _needs_publish(ep)]

        if args.limit > 0:
            unpublished = unpublished[: args.limit]

        print(f"Found {len(unpublished)} unpublished endpoints\n")

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
