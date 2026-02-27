"""List datasets and/or endpoints."""

from client import SyftClient


def cmd_list(client: SyftClient, args):
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
