#!/usr/bin/env python3
"""
Generate detailed journal descriptions using OpenRouter API.

Reads article metadata from Cambridge journal JSON files and generates
comprehensive descriptions for each journal.
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

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DATASETS_PATH = Path("/home/azureuser/datasets/cambridge_loader")
OUTPUT_FILE = Path(__file__).parent / "journal_descriptions.json"

# Model to use (cheaper and faster options)
MODEL = "anthropic/claude-3.5-sonnet"  # or "openai/gpt-4o-mini" for cheaper

# =============================================================================
# Prompt Template
# =============================================================================

SYSTEM_PROMPT = """You are an expert academic librarian and research specialist who writes clear, authoritative descriptions of academic journals.

Your task is to generate a comprehensive description of a Cambridge University Press journal based on its name and sample article titles/abstracts.

Follow this exact structure:

1. Opening paragraph: Brief overview of what the journal is, its peer-review process, format, and role
2. Key characteristics section with bullet points covering: Scope, Format, Audience, Role
3. Typical topics section with a bulleted list of research areas covered
4. Editorial and history section (keep brief)

Write in a professional, encyclopedic tone. Be specific about research areas covered. Keep it factual and informative."""

def create_user_prompt(journal_name: str, articles: list) -> str:
    """Create the user prompt with journal context."""

    # Format article samples
    article_samples = []
    for i, article in enumerate(articles[:5], 1):  # Use first 5 articles
        article_samples.append(f"{i}. **{article['title']}**")
        if article.get('abstract'):
            abstract = article['abstract'][:300] + "..." if len(article['abstract']) > 300 else article['abstract']
            article_samples.append(f"   Abstract: {abstract}")

    articles_text = "\n".join(article_samples)

    return f"""Generate a comprehensive description for this Cambridge University Press journal:

**Journal Name:** {journal_name}

**Sample Articles:**
{articles_text}

Generate the description following the structure provided in the system prompt. The journal name is "{journal_name}". Make sure the description is detailed, specific to this journal's focus area, and follows academic publishing conventions."""

# =============================================================================
# Helper Functions
# =============================================================================

def load_journal_articles(journal_name: str) -> list:
    """Load article metadata from journal JSON file."""
    journal_dir = DATASETS_PATH / journal_name

    # Find the JSON file
    json_files = list(journal_dir.glob("*.json"))
    if not json_files:
        return []

    with open(json_files[0]) as f:
        articles = json.load(f)

    return articles if isinstance(articles, list) else [articles]


def generate_description(journal_name: str, articles: list, dry_run: bool = False) -> str:
    """Generate description using OpenRouter API."""

    if dry_run:
        return f"[DRY RUN] Would generate description for {journal_name}"

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable not set")

    user_prompt = create_user_prompt(journal_name, articles)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-org/syft-space-deploy",
        "X-Title": "Cambridge Journal Description Generator"
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            description = data["choices"][0]["message"]["content"]
            return description
        else:
            print(f"    ✗ API error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"    ✗ Request failed: {e}")
        return None


def load_progress() -> dict:
    """Load existing descriptions."""
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return {}


def save_progress(descriptions: dict):
    """Save descriptions to file."""
    with open(OUTPUT_FILE, "w") as f:
        json.dump(descriptions, f, indent=2)


def get_journal_directories() -> list[str]:
    """Get all journal directory names."""
    journals = []
    for item in sorted(DATASETS_PATH.iterdir()):
        if item.is_dir() and not item.name.startswith('.'):
            if any(item.glob("*.json")) or (item / "pdfs").exists():
                journals.append(item.name)
    return journals

# =============================================================================
# Main
# =============================================================================

def main():
    global MODEL

    parser = argparse.ArgumentParser(description="Generate journal descriptions using OpenRouter")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    parser.add_argument("--limit", type=int, default=0, help="Limit to N journals (0 = all)")
    parser.add_argument("--resume", action="store_true", help="Resume from existing descriptions")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between API calls (seconds)")
    parser.add_argument("--model", type=str, default=MODEL, help="OpenRouter model to use")
    args = parser.parse_args()

    MODEL = args.model

    print("=" * 60)
    print("Cambridge Journal Description Generator")
    print("=" * 60)
    print(f"Model: {MODEL}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Check API key
    if not args.dry_run and not OPENROUTER_API_KEY:
        print("✗ OPENROUTER_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export OPENROUTER_API_KEY='your-key-here'")
        return 1

    # Load progress
    descriptions = load_progress() if args.resume else {}

    # Get journals
    journals = get_journal_directories()
    print(f"Found {len(journals)} journals")

    if args.limit > 0:
        journals = journals[:args.limit]
        print(f"Limited to {args.limit}")
    print()

    # Generate descriptions
    print("Generating descriptions...")
    print("-" * 60)

    success = 0
    skipped = 0
    failed = 0

    for i, journal in enumerate(journals, 1):
        print(f"\n[{i}/{len(journals)}] {journal}")

        # Skip if already generated
        if args.resume and journal in descriptions:
            print("    ⏭ Already generated, skipping")
            skipped += 1
            continue

        # Load articles
        articles = load_journal_articles(journal)
        if not articles:
            print("    ⚠ No articles found, skipping")
            failed += 1
            continue

        print(f"    Found {len(articles)} articles")

        # Generate description
        description = generate_description(journal, articles, args.dry_run)

        if description:
            print(f"    ✓ Description generated ({len(description)} chars)")
            if not args.dry_run:
                descriptions[journal] = description
                save_progress(descriptions)
            success += 1
        else:
            print(f"    ✗ Failed to generate description")
            failed += 1

        # Delay
        if not args.dry_run and i < len(journals):
            time.sleep(args.delay)

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total:    {len(journals)}")
    print(f"Success:  {success}")
    print(f"Skipped:  {skipped}")
    print(f"Failed:   {failed}")

    if not args.dry_run:
        print(f"\nDescriptions saved to: {OUTPUT_FILE}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
