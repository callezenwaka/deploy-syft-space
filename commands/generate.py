"""Generate dataset descriptions using AI (OpenRouter API)."""

import os
import json
import time
from pathlib import Path

import requests

from utils import discover_datasets

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_SYSTEM_PROMPT = """You are an expert who writes clear, authoritative descriptions of datasets.

Your task is to generate a comprehensive description of a dataset based on its name and sample content metadata.

Follow this structure:

1. Opening paragraph: Brief overview of what this dataset contains and its purpose
2. Key characteristics with bullet points: Scope, Format, Audience, Use cases
3. Typical content areas covered (bulleted list)
4. Additional context (if inferrable from the content)

Write in a professional, informative tone. Be specific about the content areas covered."""

DEFAULT_USER_PROMPT_TEMPLATE = """Generate a comprehensive description for this dataset:

**Dataset Name:** {name}

**Sample Content:**
{samples}

Generate the description following the structure provided. The dataset is named "{name}". Make the description detailed and specific to this dataset's content area."""


DESCRIPTION_FILENAME = "journal_description.md"


def load_metadata(dataset_dir: Path) -> list[dict]:
    """Load metadata from the first JSON file found in a dataset directory."""
    json_files = list(dataset_dir.glob("*.json"))
    if not json_files:
        return []
    with open(json_files[0]) as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def format_samples(
    items: list[dict], title_field: str = "title", abstract_field: str = "abstract", count: int = 5
) -> str:
    """Format metadata items into sample text for the prompt."""
    samples = []
    for i, item in enumerate(items[:count], 1):
        title = item.get(title_field, "Untitled")
        samples.append(f"{i}. **{title}**")
        abstract = item.get(abstract_field, "")
        if abstract:
            truncated = abstract[:300] + "..." if len(abstract) > 300 else abstract
            samples.append(f"   Abstract: {truncated}")
    return "\n".join(samples)


def generate_one(
    name: str,
    samples_text: str,
    system_prompt: str,
    user_prompt_template: str,
    model: str,
    api_key: str,
) -> str | None:
    """Call OpenRouter API to generate a single description."""
    user_prompt = user_prompt_template.format(name=name, samples=samples_text)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/syft-space-deploy",
        "X-Title": "Dataset Description Generator",
    }

    try:
        response = requests.post(
            OPENROUTER_URL, headers=headers, json=payload, timeout=60
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"    API error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"    Request failed: {e}")
        return None


def cmd_generate(client, args):
    """Generate AI descriptions for datasets."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")

    # Resolve system prompt
    system_prompt = DEFAULT_SYSTEM_PROMPT
    if args.system_prompt:
        system_prompt = args.system_prompt
    elif args.system_prompt_file:
        with open(args.system_prompt_file) as f:
            system_prompt = f.read()

    user_prompt_template = args.user_prompt_template or DEFAULT_USER_PROMPT_TEMPLATE

    print("=" * 60)
    print("GENERATE DESCRIPTIONS")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Source: {args.source_dir}")
    print(f"Output: {args.output}")
    print(f"Dry run: {args.dry_run}")
    print()

    if not args.dry_run and not api_key:
        print("Error: OPENROUTER_API_KEY environment variable not set")
        print("  export OPENROUTER_API_KEY='your-key-here'")
        return 1

    # Load existing descriptions if resuming
    output_path = Path(args.output)
    descriptions = {}
    if args.resume and output_path.exists():
        with open(output_path) as f:
            descriptions = json.load(f)

    # Discover datasets
    datasets = discover_datasets(args.source_dir)
    print(f"Found {len(datasets)} datasets")

    if args.limit > 0:
        datasets = datasets[: args.limit]
        print(f"Limited to {args.limit}")
    print()

    success, skipped, failed = 0, 0, 0

    for i, name in enumerate(datasets, 1):
        print(f"[{i}/{len(datasets)}] {name}")

        if args.resume and name in descriptions:
            print("    Already generated, skipping")
            skipped += 1
            continue

        # Load and format metadata samples
        dataset_dir = args.source_dir / name
        items = load_metadata(dataset_dir)
        if not items:
            print("    No metadata found, skipping")
            failed += 1
            continue

        print(f"    Found {len(items)} items")
        samples_text = format_samples(
            items, args.metadata_field, args.abstract_field, args.sample_count
        )

        if args.dry_run:
            print(f"    [DRY RUN] Would generate description")
            success += 1
            continue

        description = generate_one(
            name, samples_text, system_prompt, user_prompt_template, args.model, api_key
        )

        if description:
            print(f"    Generated ({len(description)} chars)")
            descriptions[name] = description
            with open(output_path, "w") as f:
                json.dump(descriptions, f, indent=2)
            # Also write journal_description.md into dataset directory
            md_path = dataset_dir / DESCRIPTION_FILENAME
            with open(md_path, "w") as f:
                f.write(description)
            print(f"    Wrote {DESCRIPTION_FILENAME}")
            success += 1
        else:
            print("    Failed to generate")
            failed += 1

        if i < len(datasets):
            time.sleep(args.delay)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Success:  {success}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")

    if not args.dry_run:
        print(f"\nDescriptions saved to: {output_path}")

    return 0 if failed == 0 else 1
