"""Deploy datasets and endpoints to Syft Space."""

import os
import json
import time
from pathlib import Path

from client import SyftClient
from utils import discover_datasets, detect_file_types, load_progress, save_progress, slugify
from commands.generate import (
    DESCRIPTION_FILENAME,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT_TEMPLATE,
    load_metadata,
    format_samples,
    generate_one,
)


def _resolve_description(dataset_dir: Path, name: str, descriptions: dict, generate_missing: bool, dry_run: bool) -> str:
    """Resolve description for a dataset.

    Priority: journal_description.md in dataset dir > --descriptions JSON > generate if missing > empty.
    """
    # 1. Check for journal_description.md in dataset directory
    md_path = dataset_dir / DESCRIPTION_FILENAME
    if md_path.exists():
        return md_path.read_text().strip()

    # 2. Check --descriptions JSON
    if name in descriptions:
        return descriptions[name]

    # 3. Generate if --generate-missing is set
    if generate_missing:
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            print("    No OPENROUTER_API_KEY set, cannot generate description")
            return ""

        items = load_metadata(dataset_dir)
        if not items:
            print("    No metadata to generate description from")
            return ""

        if dry_run:
            print(f"    [DRY RUN] Would generate {DESCRIPTION_FILENAME}")
            return "[would be generated]"

        samples_text = format_samples(items)
        print("    Generating description...", end=" ")
        description = generate_one(
            name, samples_text,
            DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT_TEMPLATE,
            "anthropic/claude-3.5-sonnet", api_key,
        )
        if description:
            md_path.write_text(description)
            print(f"wrote {DESCRIPTION_FILENAME} ({len(description)} chars)")
            return description
        else:
            print("failed")
            return ""

    return ""


def cmd_deploy(client: SyftClient, args):
    print("=" * 60)
    print("DEPLOY DATASETS")
    print("=" * 60)
    print(f"API: {client.base_url}")
    print(f"Source: {args.source_dir}")
    print(f"Dry run: {args.dry_run}")
    if args.generate_missing:
        print("Generate missing descriptions: enabled")
    print()

    if not args.dry_run:
        if not client.check_connection():
            print("Error: Cannot connect to API")
            return 1
        print("API connected\n")

    # Resolve file types
    if args.file_types:
        file_types = [t.strip() for t in args.file_types.split(",")]
    else:
        file_types = detect_file_types(args.source_dir)
        if file_types:
            print(f"Auto-detected file types: {', '.join(file_types)}")
        else:
            print("Warning: No file types detected, using ['.pdf', '.json']")
            file_types = [".pdf", ".json"]

    # Load descriptions JSON if provided (used as fallback)
    descriptions = {}
    if args.descriptions:
        with open(args.descriptions) as f:
            descriptions = json.load(f)
        print(f"Loaded {len(descriptions)} descriptions from JSON")

    # Load progress
    progress_file = Path(args.progress_file)
    progress = load_progress(progress_file) if args.resume else {"deployed": [], "updated": [], "failed": []}

    # Discover datasets
    datasets = discover_datasets(args.source_dir)
    print(f"Found {len(datasets)} datasets")

    if args.limit > 0:
        datasets = datasets[: args.limit]
        print(f"Limited to {args.limit}")
    print()

    success, skipped, failed = 0, 0, 0

    for i, name in enumerate(datasets, 1):
        display_name = name.replace("-", " ").title()
        print(f"[{i}/{len(datasets)}] {name}")

        if args.resume and name in progress["deployed"]:
            print("    Skipped (already deployed)")
            skipped += 1
            continue

        dataset_dir = args.source_dir / name

        # Resolve description
        description = _resolve_description(
            dataset_dir, name, descriptions, args.generate_missing, args.dry_run
        )
        if description:
            source = DESCRIPTION_FILENAME if (dataset_dir / DESCRIPTION_FILENAME).exists() else "JSON"
            print(f"    Description: {len(description)} chars (from {source})")

        # Build dataset payload
        dataset_name = slugify(args.name_template.format(name=name))
        container_path = f"{args.container_dir}/{name}"

        dataset_payload = {
            "name": dataset_name,
            "dtype": "local_file",
            "configuration": {
                "filePaths": [{"path": container_path, "description": name}],
                "ingestFileTypeOptions": file_types,
            },
            "summary": args.summary_template.format(name=display_name),
            "tags": args.tags,
        }

        if args.dry_run:
            print(f"    [DRY RUN] Would create dataset: {dataset_name}")
        else:
            ok, result = client.create_dataset(dataset_payload)
            if ok:
                print(f"    Dataset: {dataset_name}")
            else:
                print(f"    Dataset failed: {result}")
                progress["failed"].append(name)
                save_progress(progress_file, progress)
                failed += 1
                continue
            time.sleep(args.delay)

        dataset_id = None
        if not args.dry_run:
            dataset_id = result.get("id") if isinstance(result, dict) else None

        # Build endpoint payload
        endpoint_slug = slugify(args.slug_template.format(name=name))

        endpoint_payload = {
            "name": endpoint_slug,
            "slug": endpoint_slug,
            "description": description,
            "summary": args.summary_template.format(name=display_name),
            "response_type": args.response_type,
            "published": args.publish,
            "tags": args.tags,
        }

        if dataset_id:
            endpoint_payload["dataset_id"] = dataset_id

        if args.dry_run:
            print(f"    [DRY RUN] Would create endpoint: {endpoint_slug}")
            if args.publish:
                print(f"    [DRY RUN] Would publish to marketplace: {endpoint_slug}")
        else:
            ok, result = client.create_endpoint(endpoint_payload)
            if ok:
                print(f"    Endpoint: {endpoint_slug}")
            else:
                print(f"    Endpoint failed: {result}")
                progress["failed"].append(name)
                save_progress(progress_file, progress)
                failed += 1
                continue
            time.sleep(args.delay)

            # Actually publish to marketplace(s) if --publish was set
            if args.publish:
                pub_ok, pub_msg = client.publish_endpoint(endpoint_slug)
                if pub_ok:
                    print(f"    Published to marketplace")
                else:
                    print(f"    Publish to marketplace failed: {pub_msg}")
                time.sleep(args.delay)

        success += 1
        if not args.dry_run:
            progress["deployed"].append(name)
            save_progress(progress_file, progress)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Success:  {success}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")

    return 0 if failed == 0 else 1
