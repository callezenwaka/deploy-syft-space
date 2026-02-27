"""Delete datasets and/or endpoints."""

import time

from client import SyftClient


def cmd_delete(client: SyftClient, args):
    delete_endpoints = args.endpoints or (not args.datasets and not args.endpoints)
    delete_datasets = args.datasets or (not args.datasets and not args.endpoints)

    print("=" * 60)
    print("DELETE RESOURCES")
    print("=" * 60)
    print(f"API: {client.base_url}")
    print(f"Dry run: {args.dry_run}")
    print(f"Delete endpoints: {delete_endpoints}")
    print(f"Delete datasets: {delete_datasets}")
    print()

    if not args.dry_run and not args.yes:
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            print("Aborted")
            return 0

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

    return 0
