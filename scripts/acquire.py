#!/usr/bin/env python3
"""
Fetch the ICD-11 Foundation from the official WHO ICD API and write a consolidated JSON file.

Auth: WHO OAuth2 client credentials — set CLIENT_ID and CLIENT_SECRET in env/.env.
The token is valid for ~1 hour; this script re-authenticates automatically if it
expires mid-run.

The Foundation entity graph is traversed breadth-first from the root entity
(https://id.who.int/icd/entity). Every API response is cached to
tmp/cache/<encoded-uri>/response.json. If the run is interrupted, re-running
with an existing cache will resume without re-fetching already-cached nodes.

Usage:
    python scripts/acquire.py --output tmp/icd11foundation_raw.json
    python scripts/acquire.py --output tmp/icd11foundation_raw.json --release 2024-01
    python scripts/acquire.py --output tmp/icd11foundation_raw.json --no-cache
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

# ── Constants ──────────────────────────────────────────────────────────────────

TOKEN_ENDPOINT = "https://icdaccessmanagement.who.int/connect/token"
# Latest release: bare root. Specific release: append ?version=<release_id>
ENTITY_ROOT_LATEST = "https://id.who.int/icd/entity"
ENTITY_ROOT_VERSIONED = "https://id.who.int/icd/entity?version={release_id}"

ENV_FILE = Path(__file__).parent.parent / "env" / ".env"
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "tmp" / "cache"


# ── Auth ───────────────────────────────────────────────────────────────────────


def _get_token(client_id: str, client_secret: str) -> str:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "icdapi_access",
        "grant_type": "client_credentials",
    }
    r = requests.post(TOKEN_ENDPOINT, data=payload, verify=False, timeout=30)
    if not r.ok:
        detail = (r.text or "").strip()[:2000] or "(empty body)"
        raise RuntimeError(
            f"WHO token endpoint returned HTTP {r.status_code}: {detail}\n"
            "Verify CLIENT_ID and CLIENT_SECRET match the WHO ICD API client at "
            "https://icd.who.int/icdapi (no extra spaces or quotes; repository secrets "
            "must be named CLIENT_ID and CLIENT_SECRET)."
        )
    return r.json()["access_token"]


def _make_headers(token: str, language: str = "en") -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": language,
        "API-Version": "v2",
    }


# ── URI helpers ────────────────────────────────────────────────────────────────


def _to_https(uri: str) -> str:
    """WHO entity URIs use http:// but the API requires https://."""
    return uri.replace("http://id.who.int/", "https://id.who.int/", 1)


# ── Caching helpers ────────────────────────────────────────────────────────────


def _cache_path(uri: str, cache_dir: Path) -> Path:
    safe = quote(uri, safe="")[:200]
    return cache_dir / safe / "response.json"


def _fetch_node(uri: str, headers: dict, cache_dir: Path, use_cache: bool) -> dict:
    path = _cache_path(uri, cache_dir)
    if use_cache and path.exists():
        with open(path) as f:
            return json.load(f)
    r = requests.get(uri, headers=headers, verify=False, timeout=30)
    if r.status_code == 401:
        raise PermissionError("WHO API token expired")
    r.raise_for_status()
    data = r.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)
    return data


# ── BFS traversal ──────────────────────────────────────────────────────────────


def _traverse(
    root_uri: str,
    client_id: str,
    client_secret: str,
    cache_dir: Path,
    use_cache: bool,
    language: str,
) -> tuple[dict[str, dict], str]:
    """BFS traversal of ICD-11 Foundation entity graph.

    Returns ({uri: node_data}, release_id).
    """
    token = _get_token(client_id, client_secret)
    headers = _make_headers(token, language)
    token_fetched_at = time.time()

    results: dict[str, dict] = {}
    queue: list[str] = [root_uri]
    visited: set[str] = set()
    total = 0
    release_id = "unknown"

    print(f"Starting BFS from {root_uri}", file=sys.stderr)

    while queue:
        uri = queue.pop(0)
        if uri in visited:
            continue
        visited.add(uri)

        # Re-authenticate if token is near expiry (55 min threshold)
        if time.time() - token_fetched_at > 55 * 60:
            print("Refreshing WHO API token...", file=sys.stderr)
            token = _get_token(client_id, client_secret)
            headers = _make_headers(token, language)
            token_fetched_at = time.time()

        try:
            data = _fetch_node(uri, headers, cache_dir, use_cache)
        except PermissionError:
            print("Token expired mid-run — re-authenticating...", file=sys.stderr)
            token = _get_token(client_id, client_secret)
            headers = _make_headers(token, language)
            token_fetched_at = time.time()
            data = _fetch_node(uri, headers, cache_dir, use_cache)

        # Capture official release id from root response
        if uri == root_uri and "releaseId" in data:
            release_id = data["releaseId"]

        results[uri] = data
        total += 1
        if total % 500 == 0:
            print(f"  {total} nodes fetched...", file=sys.stderr)

        # Child URIs from the API use http://; convert to https:// for requests
        for child_uri in data.get("child", []):
            child_https = _to_https(child_uri)
            if child_https not in visited:
                queue.append(child_https)

    print(f"Traversal complete: {total} nodes | release: {release_id}", file=sys.stderr)
    return results, release_id


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Acquire ICD-11 Foundation from official WHO API → JSON"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--release",
        default="latest",
        help="Release id (e.g. '2024-01') or 'latest' (default)",
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Ignore cache and re-fetch all nodes"
    )
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    load_dotenv(ENV_FILE)
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Error: CLIENT_ID and CLIENT_SECRET must be set (e.g. env/.env locally, or "
            "GitHub Actions repository secrets CLIENT_ID / CLIENT_SECRET).",
            file=sys.stderr,
        )
        sys.exit(1)

    use_cache = not args.no_cache
    cache_dir = DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.release == "latest":
        root_uri = ENTITY_ROOT_LATEST
    else:
        root_uri = ENTITY_ROOT_VERSIONED.format(release_id=args.release)

    nodes, release_id = _traverse(
        root_uri=root_uri,
        client_id=client_id,
        client_secret=client_secret,
        cache_dir=cache_dir,
        use_cache=use_cache,
        language=args.language,
    )

    # Remove the root node itself — it is not a disease entity
    nodes.pop(root_uri, None)

    output = {
        "release_id": release_id,
        "entity_count": len(nodes),
        "entities": nodes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)
    print(f"Written: {args.output} ({len(nodes)} entities)", file=sys.stderr)


if __name__ == "__main__":
    main()
