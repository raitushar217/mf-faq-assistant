"""
Phase 5 — Retrieval Service
retrieval/retriever.py

Loads ChromaDB from data/chromadb, embed the query with BAAI/bge-small-en-v1.5,
and queries the mf_faq collection for top 3 results.
"""

import os
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Paths and configuration
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[1]
CHROMA_PATH = os.getenv("CHROMA_PERSIST_DIR", str(ROOT_DIR / "data" / "chromadb"))
COLLECTION_NAME = "mf_faq"

# Load the embedding model ONCE at module level
print("Loading embedding model BAAI/bge-small-en-v1.5 for retrieval...")
try:
    MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5")
    # Pre-ping ChromaDB on load to avoid cold start issues
    _client = chromadb.PersistentClient(path=CHROMA_PATH)
except Exception as e:
    print(f"Warning: Failed to initialize retrieval dependencies during module load: {e}")
    MODEL = None


def retrieve(query: str, n_results: int = 3) -> list[dict]:
    """
    Returns [{"text": str, "source_url": str, "score": float}]
    sorted by score descending.
    """
    if MODEL is None:
        return []

    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
    except Exception as e:
        print(f"Failed to connect to ChromaDB: {e}")
        return []

    existing_collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME not in existing_collections:
        print(f"Collection '{COLLECTION_NAME}' not found. Returning empty.")
        return []

    collection = client.get_collection(COLLECTION_NAME)

    try:
        query_embedding = MODEL.encode(query, normalize_embeddings=True).tolist()
    except Exception as e:
        print(f"Error encoding query: {e}")
        return []

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
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
        score = 1.0 - dist  # ChromaDB uses L2 distance; since normalized, L2 is proportional to cosine distance
        retrieved.append({
            "text": doc,
            "source_url": meta.get("source_url", ""),
            "score": score
        })
    
    # Sort by score descending (highest similarity first)
    retrieved.sort(key=lambda x: x["score"], reverse=True)
    return retrieved
