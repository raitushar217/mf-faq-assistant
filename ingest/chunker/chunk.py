"""
Phase 4.1 — Chunking Service
ingest/chunker/chunk.py

Strategy:
  - Fixed-size sliding window over plain text
  - chunk_size = 300 words
  - overlap = 50 words
  - min_chunk = 20 words

Input: data/raw/*.txt
Output: data/chunks/<slug>_chunks.json
"""

import json
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
CHUNKS_DIR = ROOT_DIR / "data" / "chunks"
MANIFEST_PATH = ROOT_DIR / "data" / "scrape_manifest.json"

CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 100
OVERLAP = 20
MIN_CHUNK = 10
STRIDE = CHUNK_SIZE - OVERLAP

def _clean_text(text: str) -> str:
    """Remove UI noise like single-digit lines and excessive whitespace."""
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are just numbers (0-9) or very short navigational noise
        if stripped.isdigit() and len(stripped) < 3:
            continue
        if stripped in ["+", "-", "%", ".", "Stocks", "F&O", "Mutual Funds", "More", "Search Groww....", "Ctrl+K"]:
            continue
        if stripped:
            cleaned_lines.append(stripped)
    return " ".join(cleaned_lines)

from datetime import datetime, timezone

def _log(message: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    line = f"[{now_iso}] {message}"
    print(line)
    with open(LOGS_DIR / "scheduler.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")

def _load_manifest_dict() -> dict[str, dict]:
    """Load manifest into a dict keyed by slug for easy lookup."""
    if not MANIFEST_PATH.exists():
        return {}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return {entry["slug"]: entry for entry in manifest if "slug" in entry}

def chunk_file(filepath: Path, manifest_data: dict) -> list[dict]:
    """Chunk a single raw text file into a list of chunk metadata dicts."""
    slug = filepath.stem
    file_info = manifest_data.get(slug, {})
    
    source_url = file_info.get("url", "unknown")
    scraped_at = file_info.get("scraped_at", "unknown")
    
    # Try to extract a clean fund name from the slug for context injection
    fund_name = slug.replace("mutual-funds_", "").replace("-", " ").title()
    
    raw_text = filepath.read_text(encoding="utf-8")
    cleaned_text = _clean_text(raw_text)
    words = cleaned_text.split()
    
    chunks = []
    i = 0
    chunk_index = 0
    
    while i < len(words):
        window = words[i : i + CHUNK_SIZE]
        
        if len(window) < MIN_CHUNK:
            break
            
        # Context Injection: Prepend the fund name to each chunk's text
        # This helps the retriever match queries that use the fund name.
        chunk_text = f"[{fund_name}] " + " ".join(window)
        
        chunks.append({
            "text": chunk_text,
            "source_url": source_url,
            "filename": filepath.name,
            "chunk_index": chunk_index,
            "scraped_at": scraped_at
        })
        
        i += STRIDE
        chunk_index += 1
        
    return chunks

def run():
    _log("=== chunk.py START (Refined Chunking) ===")
    
    if not RAW_DIR.exists():
        _log(f"Directory not found: {RAW_DIR}")
        return
        
    manifest_data = _load_manifest_dict()
    
    total_files = 0
    total_chunks = 0
    
    for filepath in RAW_DIR.glob("*.txt"):
        chunks = chunk_file(filepath, manifest_data)
        if not chunks:
            continue
            
        out_path = CHUNKS_DIR / f"{filepath.stem}_chunks.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
            
        total_files += 1
        total_chunks += len(chunks)
        _log(f"  -> Created {len(chunks)} chunks for {filepath.name}")
        
    _log(f"=== chunk.py DONE — Chunked {total_chunks} chunks from {total_files} files ===")

if __name__ == "__main__":
    run()
