"""
Phase 5 — Retrieval Service
retrieval/retriever.py

Loads ChromaDB from data/chromadb, embed the query with BAAI/bge-small-en-v1.5,
and queries the mf_faq collection for top 3 results.
"""

import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# ---------------------------------------------------------------------------
# Paths and configuration
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
CHROMA_PATH = os.getenv("CHROMA_PERSIST_DIR", str(ROOT_DIR / "data" / "chromadb"))
COLLECTION_NAME = "mf_faq"

# Using the same DefaultEmbeddingFunction as used during ingest.
# This runs via ONNX and does not require torch/sentence-transformers.
EMBEDDING_FUNCTION = embedding_functions.DefaultEmbeddingFunction()

def retrieve(query: str, n_results: int = 3) -> list[dict]:
    """
    Returns [{"text": str, "source_url": str, "score": float}]
    sorted by score descending.
    """
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
    except Exception as e:
        print(f"Failed to connect to ChromaDB: {e}")
        return []

    existing_collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME not in existing_collections:
        print(f"Collection '{COLLECTION_NAME}' not found. Returning empty.")
        return []

    # Load collection with the corresponding embedding function
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=EMBEDDING_FUNCTION
    )

    try:
        # Chroma handles embedding internally when query_texts is used
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        print(f"Failed to query collection: {e}")
        return []

    if not results or not results["documents"] or not results["documents"][0]:
        return []

    # Unpack the first (and only) query result
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    retrieved = []
    for doc, meta, dist in zip(docs, metas, dists):
        # ChromaDB uses L2 distance; since normalized, L2 is proportional to cosine distance
        score = 1.0 - dist
        retrieved.append({
            "text": doc,
            "source_url": meta.get("source_url", ""),
            "score": score
        })
    
    # Sort by score descending (highest similarity first)
    retrieved.sort(key=lambda x: x["score"], reverse=True)
    return retrieved
