"""Download latest chromadb artifact from GitHub Actions into local data/chromadb."""

from __future__ import annotations

import io
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import requests

ARTIFACT_NAME = "chromadb-artifact"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

ROOT_DIR = Path(__file__).resolve().parents[1]
CHROMA_PATH = Path(os.getenv("CHROMA_PERSIST_DIR", str(ROOT_DIR / "data" / "chromadb"))).resolve()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()


def _github_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }


def _list_artifacts() -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/artifacts"
    params = {"per_page": 100}
    response = requests.get(url, headers=_github_headers(), params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    return payload.get("artifacts", [])


def _find_latest_artifact_download_url() -> str:
    artifacts = _list_artifacts()
    matches = [
        artifact
        for artifact in artifacts
        if artifact.get("name") == ARTIFACT_NAME and not artifact.get("expired", False)
    ]
    if not matches:
        return ""

    matches.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return str(matches[0].get("archive_download_url", ""))


def _safe_extract_zip(zip_bytes: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for member in archive.infolist():
            member_path = (destination / member.filename).resolve()
            if destination not in member_path.parents and member_path != destination:
                raise RuntimeError(f"Unsafe zip entry detected: {member.filename}")
        archive.extractall(destination)


def _replace_chroma_dir_with_zip(download_url: str) -> None:
    response = requests.get(download_url, headers=_github_headers(), timeout=60)
    response.raise_for_status()

    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)

    _safe_extract_zip(response.content, CHROMA_PATH)


def run() -> int:
    print("=== download_artifact.py ===")

    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("Missing GITHUB_TOKEN or GITHUB_REPO. Skipping artifact download.")
        return 0

    print(f"Fetching latest '{ARTIFACT_NAME}' for repo: {GITHUB_REPO}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            download_url = _find_latest_artifact_download_url()
            if not download_url:
                print(f"No artifact named '{ARTIFACT_NAME}' found.")
                return 0

            _replace_chroma_dir_with_zip(download_url)
            print(f"Artifact extracted to: {CHROMA_PATH}")
            return 0
        except (requests.RequestException, zipfile.BadZipFile, RuntimeError) as err:
            print(f"Attempt {attempt}/{MAX_RETRIES} failed: {err}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS)
            else:
                print("Artifact download failed after retries.")
                return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(run())
