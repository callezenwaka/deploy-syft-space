"""Update endpoint descriptions from a descriptions JSON file."""

import json
import time
from pathlib import Path

from client import SyftClient
from utils import load_progress, save_progress


def cmd_update(client: SyftClient, args):
    print("=" * 60)
    print("UPDATE ENDPOINT DESCRIPTIONS")
    print("=" * 60)
    print(f"API: {client.base_url}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Load descriptions
    try:
        with open(args.descriptions) as f:
            descriptions = json.load(f)
    except FileNotFoundError:
        print(f"Error: Descriptions file not found: {args.descriptions}")
        return 1
    print(f"Loaded {len(descriptions)} descriptions")

    # Load progress
    progress_file = Path(args.progress_file)
    progress = load_progress(progress_file) if args.resume else {"deployed": [], "updated": [], "failed": []}

    try:
        endpoints = client.list_endpoints()

        if args.limit > 0:
            endpoints = endpoints[: args.limit]

        print(f"Found {len(endpoints)} endpoints\n")

        success, skipped, failed, no_desc = 0, 0, 0, 0

        for i, ep in enumerate(endpoints, 1):
            slug = ep["slug"]
            print(f"[{i}/{len(endpoints)}] {slug}")

            if args.resume and slug in progress["updated"]:
                print("    Skipped (already updated)")
                skipped += 1
                continue

            # Look up description: try slug directly as the key
            if slug not in descriptions:
                print(f"    No description for: {slug}")
                no_desc += 1
                continue

            payload = {"description": descriptions[slug]}
            if args.summary_template:
                display_name = slug.replace("-", " ").title()
                payload["summary"] = args.summary_template.format(name=display_name)

            if args.dry_run:
                print(f"    [DRY RUN] Would update ({len(descriptions[slug])} chars)")
                success += 1
            else:
                ok, msg = client.update_endpoint(slug, payload)
                if ok:
                    print("    Updated")
                    progress["updated"].append(slug)
                    save_progress(progress_file, progress)
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
