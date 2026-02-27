"""Shared utilities: dataset discovery, file type detection, progress tracking."""

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def slugify(text: str, max_length: int = 63) -> str:
    """Convert text to a URL-safe slug only if it contains spaces or bad characters.

    Already-formatted slugs (kebab-case) pass through unchanged.
    Truncates to max_length at a word boundary (hyphen) to avoid cut-off words.
    """
    if re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", text):
        slug = text
    else:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        slug = text.strip("-")

    if len(slug) > max_length:
        # Preserve trailing suffix (e.g. "-oa", "-journal-oa") when truncating
        last_hyphen = slug.rfind("-")
        suffix = slug[last_hyphen:] if last_hyphen != -1 else ""
        trim_to = max_length - len(suffix)
        slug = slug[:trim_to].rsplit("-", 1)[0] + suffix
    return slug


def discover_datasets(source_dir: Path) -> list[str]:
    """Return sorted list of subdirectory names under source_dir.

    Every non-hidden subdirectory is treated as a dataset.
    """
    datasets = []
    for item in sorted(source_dir.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            datasets.append(item.name)
    return datasets


def detect_file_types(source_dir: Path, sample_limit: int = 100) -> list[str]:
    """Auto-detect file extensions present in the first dataset subdirectory.

    Scans up to sample_limit files to keep it fast on large directories.
    """
    datasets = discover_datasets(source_dir)
    if not datasets:
        return []

    first_dir = source_dir / datasets[0]
    extensions = set()
    for i, f in enumerate(first_dir.rglob("*")):
        if i >= sample_limit:
            break
        if f.is_file() and f.suffix:
            extensions.add(f.suffix.lower())
    return sorted(extensions)


def resolve_api_key(api_url: str) -> str:
    """Resolve the API key from the Docker container matching the api_url port.

    Inspects running Syft Space containers, finds the one whose published port
    matches the port in api_url, and returns its SYFT_ADMIN_API_KEY env var.
    """
    try:
        parsed = urlparse(api_url)
        target_port = str(parsed.port or 8080)

        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return ""

        for name in result.stdout.strip().splitlines():
            inspect = subprocess.run(
                ["docker", "inspect", name, "--format",
                 "{{range $p, $b := .NetworkSettings.Ports}}{{range $b}}{{.HostPort}} {{end}}{{end}}"],
                capture_output=True, text=True, timeout=5,
            )
            ports = inspect.stdout.strip().split()
            if target_port in ports:
                env_out = subprocess.run(
                    ["docker", "inspect", name, "--format",
                     "{{range .Config.Env}}{{println .}}{{end}}"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in env_out.stdout.splitlines():
                    if line.startswith("SYFT_ADMIN_API_KEY="):
                        return line.split("=", 1)[1]
        return ""
    except Exception:
        return ""


def load_progress(path: Path) -> dict:
    """Load progress from a JSON file."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"deployed": [], "updated": [], "failed": []}


def save_progress(path: Path, progress: dict):
    """Save progress to a JSON file."""
    with open(path, "w") as f:
        json.dump(progress, f, indent=2)
