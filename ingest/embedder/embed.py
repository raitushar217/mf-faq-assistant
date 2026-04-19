"""
Phase 4.2 & 4.3 — Embedding & Vector Store Service
ingest/embedder/embed.py

Model: BAAI/bge-small-en-v1.5
Vector Store: Local ChromaDB (PersistentClient)

Input: data/chunks/*.json
Output: data/chromadb/
"""

import json
import os
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Paths and configuration
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
CHUNKS_DIR = ROOT_DIR / "data" / "chunks"

# Use Chroma persist path from env, fallback to data/chromadb
CHROMA_PATH = os.getenv("CHROMA_PERSIST_DIR", str(ROOT_DIR / "data" / "chromadb"))
COLLECTION_NAME = "mf_faq"

from datetime import datetime, timezone
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def _log(message: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    line = f"[{now_iso}] {message}"
    print(line)
    with open(LOGS_DIR / "scheduler.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")

# Load the embedding model ONCE at module level
_log("Loading embedding model BAAI/bge-small-en-v1.5...")
MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5")


def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Embed a list of text strings into 384-dim normalized vectors."""
    # normalize_embeddings=True projects vectors to unit sphere for cosine similarity via L2
    return MODEL.encode(texts, normalize_embeddings=True).tolist()


def run() -> None:
    _log("=== embed.py START ===")

    if not CHUNKS_DIR.exists():
        _log(f"Directory not found: {CHUNKS_DIR}")
        return

    # 1. Gather all chunks
    all_chunks = []
    for filepath in CHUNKS_DIR.glob("*_chunks.json"):
        with open(filepath, "r", encoding="utf-8") as f:
            file_chunks = json.load(f)
            # The dictionary needs to track the slug to form the ID
            slug = filepath.name.replace("_chunks.json", "")
            for c in file_chunks:
                c["_slug"] = slug  # temporary key for ID generation
            all_chunks.extend(file_chunks)

    if not all_chunks:
        _log("No chunks found to embed.")
        return

    _log(f"Loaded {len(all_chunks)} total chunks from JSON files.")

    # 2. Extract texts and generate embeddings
    texts = [c["text"] for c in all_chunks]
    _log(f"Embedding {len(texts)} chunks...")
    embeddings = embed_chunks(texts)

    # 3. Format data for ChromaDB
    ids = []
    documents = []
    metadatas = []

    for chunk, emb in zip(all_chunks, embeddings):
        chunk_id = f"{chunk['_slug']}_chunk{chunk['chunk_index']}"
        ids.append(chunk_id)
        documents.append(chunk["text"])

        # Metadatas cannot contain complex objects, but ours are simple strings/ints
        metadata = {
            "source_url": chunk["source_url"],
            "filename": chunk["filename"],
            "chunk_index": chunk["chunk_index"],
            "scraped_at": chunk["scraped_at"]
        }
        metadatas.append(metadata)

    # 4. Initialize Local ChromaDB
    _log(f"Connecting to Local ChromaDB at {CHROMA_PATH}...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Always delete and recreate to prevent stale chunks
    existing_collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing_collections:
        _log(f"Deleting existing collection '{COLLECTION_NAME}'...")
        client.delete_collection(COLLECTION_NAME)

    _log(f"Creating new collection '{COLLECTION_NAME}'...")
    collection = client.create_collection(COLLECTION_NAME)

    # Note: Chroma recommends batching if there are >41666 items (sqlite limit).
    # Since we have ~20 URLs, chunks will be < 500, so adding in one batch is completely safe.
    _log(f"Adding {len(ids)} embedded chunks to ChromaDB...")
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    _log(f"=== embed.py DONE — Embedded {len(ids)} chunks total ===")

if __name__ == "__main__":
    run()
