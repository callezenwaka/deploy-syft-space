#!/usr/bin/env python3
"""
Syft Space Deploy
=================

Generic CLI for deploying datasets and endpoints to Syft Space.

Commands:
    python main.py list      List deployed datasets and endpoints
    python main.py deploy    Deploy datasets and endpoints
    python main.py delete    Delete datasets and/or endpoints
    python main.py publish   Publish endpoints to marketplaces
    python main.py update    Update endpoint descriptions
    python main.py generate  Generate AI descriptions for datasets
"""

import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from client import SyftClient
from commands import cmd_list, cmd_deploy, cmd_delete, cmd_publish, cmd_update, cmd_generate
from utils import resolve_api_key


def main():
    parser = argparse.ArgumentParser(
        description="Syft Space Deploy — generic dataset deployment CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "--api-url",
        default=os.getenv("SYFT_API_URL", "http://localhost:8080/api/v1"),
        help="Syft API URL [env: SYFT_API_URL]",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("SYFT_ADMIN_API_KEY", ""),
        help="Admin API key [env: SYFT_ADMIN_API_KEY]",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # -- list --
    p_list = subparsers.add_parser("list", help="List datasets and endpoints")
    p_list.add_argument("--datasets", action="store_true", help="List only datasets")
    p_list.add_argument("--endpoints", action="store_true", help="List only endpoints")

    # -- deploy --
    p_deploy = subparsers.add_parser("deploy", help="Deploy datasets and endpoints")
    p_deploy.add_argument("--source-dir", type=Path, required=True, help="Host path to dataset root directory")
    p_deploy.add_argument("--container-dir", type=str, required=True, help="Container path that maps to source-dir")
    p_deploy.add_argument("--name-template", default="{name}", help="Dataset name template (default: '{name}')")
    p_deploy.add_argument("--slug-template", default="{name}", help="Endpoint slug template (default: '{name}')")
    p_deploy.add_argument("--summary-template", default="{name}", help="Summary template (default: '{name}')")
    p_deploy.add_argument("--tags", default="", help="Comma-separated tags")
    p_deploy.add_argument("--file-types", default=None, help="Comma-separated file extensions (default: auto-detect)")
    p_deploy.add_argument("--descriptions", type=Path, default=None, help="Path to descriptions JSON file (fallback)")
    p_deploy.add_argument("--generate-missing", action="store_true", help="Generate journal_description.md via AI for datasets missing one")
    p_deploy.add_argument("--response-type", default="both", help="Endpoint response type (default: 'both')")
    p_deploy.add_argument("--publish", action="store_true", help="Mark endpoints as published immediately")
    p_deploy.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_deploy.add_argument("--limit", type=int, default=0, help="Limit to N datasets (0 = all)")
    p_deploy.add_argument("--resume", action="store_true", help="Skip already-deployed datasets")
    p_deploy.add_argument("--delay", type=float, default=0.5, help="Delay between API calls in seconds")
    p_deploy.add_argument("--progress-file", type=Path, default=Path("./progress.json"), help="Progress file path")

    # -- delete --
    p_delete = subparsers.add_parser("delete", help="Delete datasets and/or endpoints")
    p_delete.add_argument("--datasets", action="store_true", help="Delete only datasets")
    p_delete.add_argument("--endpoints", action="store_true", help="Delete only endpoints")
    p_delete.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p_delete.add_argument("--delay", type=float, default=0.3, help="Delay between API calls in seconds")

    # -- publish --
    p_publish = subparsers.add_parser("publish", help="Publish unpublished endpoints")
    p_publish.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_publish.add_argument("--limit", type=int, default=0, help="Limit to N endpoints (0 = all)")
    p_publish.add_argument("--delay", type=float, default=0.3, help="Delay between API calls in seconds")

    # -- update --
    p_update = subparsers.add_parser("update", help="Update endpoint descriptions")
    p_update.add_argument("--descriptions", type=Path, required=True, help="Path to descriptions JSON file")
    p_update.add_argument("--summary-template", default=None, help="Summary template for updated endpoints")
    p_update.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    p_update.add_argument("--limit", type=int, default=0, help="Limit to N endpoints (0 = all)")
    p_update.add_argument("--resume", action="store_true", help="Skip already-updated endpoints")
    p_update.add_argument("--delay", type=float, default=0.5, help="Delay between API calls in seconds")
    p_update.add_argument("--progress-file", type=Path, default=Path("./progress.json"), help="Progress file path")

    # -- generate --
    p_gen = subparsers.add_parser("generate", help="Generate AI descriptions for datasets")
    p_gen.add_argument("--source-dir", type=Path, required=True, help="Path to dataset root directory")
    p_gen.add_argument("--output", type=Path, default=Path("./descriptions.json"), help="Output JSON file")
    p_gen.add_argument("--system-prompt", default=None, help="Override system prompt text")
    p_gen.add_argument("--system-prompt-file", type=Path, default=None, help="Read system prompt from file")
    p_gen.add_argument("--user-prompt-template", default=None, help="User prompt template with {name} and {samples}")
    p_gen.add_argument("--metadata-field", default="title", help="JSON field for item title (default: 'title')")
    p_gen.add_argument("--abstract-field", default="abstract", help="JSON field for item abstract (default: 'abstract')")
    p_gen.add_argument("--sample-count", type=int, default=5, help="Items to sample per dataset (default: 5)")
    p_gen.add_argument("--model", default="anthropic/claude-3.5-sonnet", help="OpenRouter model ID")
    p_gen.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    p_gen.add_argument("--limit", type=int, default=0, help="Limit to N datasets (0 = all)")
    p_gen.add_argument("--resume", action="store_true", help="Skip already-generated descriptions")
    p_gen.add_argument("--delay", type=float, default=1.5, help="Delay between API calls in seconds")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Resolve API key: explicit flag > env var > Docker container auto-detect
    api_key = args.api_key
    if not api_key:
        api_key = resolve_api_key(args.api_url)
        if api_key:
            print(f"Auto-detected API key from Docker container\n")
        else:
            print("Warning: No API key provided. Set --api-key or SYFT_ADMIN_API_KEY.\n")

    client = SyftClient(args.api_url, api_key)

    commands = {
        "list": cmd_list,
        "deploy": cmd_deploy,
        "delete": cmd_delete,
        "publish": cmd_publish,
        "update": cmd_update,
        "generate": cmd_generate,
    }

    return commands[args.command](client, args)


if __name__ == "__main__":
    sys.exit(main())
