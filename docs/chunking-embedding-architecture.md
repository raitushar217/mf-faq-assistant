# Chunking & Embedding Architecture — MF FAQ Assistant

**Last revised:** 2026-04-18  
**Scope:** Phases 4.1 (Chunking) · 4.2 (Embedding) · 4.3 (Vector Store)

---

## 1. Chunking Strategy — Fixed-Size Sliding Window

### Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `chunk_size` | 300 words | Large enough to hold a full FAQ answer with context; small enough for precise retrieval |
| `overlap` | 50 words | Prevents answer truncation at chunk boundaries; ensures continuity across adjacent chunks |
| `min_chunk` | 20 words | Discards boilerplate fragments (nav text, footers, single-line labels) that add noise |

### Algorithm

```
Input: plain-text content of one scraped file (data/raw/<slug>.txt)

words = content.split()
i = 0

while i < len(words):
    window = words[i : i + chunk_size]

    if len(window) < min_chunk:
        break                          # discard tail fragment

    chunk_text = " ".join(window)
    emit chunk_text with metadata
    i += (chunk_size - overlap)        # slide forward by (300 - 50) = 250 words
```

### Why sliding window over sentence splitting?

- Mutual fund pages mix tables, bullet lists, and prose — sentence boundaries are
  unreliable after HTML stripping.
- Fixed-size windows guarantee uniform context length fed to the embedding model,
  which is important for cosine similarity comparability across chunks.
- 50-word overlap ensures that answers spanning a chunk boundary are never cut off.

### Output per source file

```
data/chunks/<slug>_chunks.json

[
  {
    "text":        "...",
    "source_url":  "https://...",
    "filename":    "<slug>.txt",
    "chunk_index": 0,
    "scraped_at":  "2026-04-18T09:15:00+05:30"
  },
  ...
]
```

---

## 2. Chunk Metadata Structure

Each chunk carries five fields written to both the JSON file and ChromaDB metadata:

| Field | Type | Source | Purpose |
|-------|------|--------|---------|
| `text` | `str` | Sliding window | The actual text fed to the LLM as context |
| `source_url` | `str` | `scrape_manifest.json` (looked up by slug) | Shown to user as citation; appended to every answer |
| `filename` | `str` | `<slug>.txt` | Traceability — links chunk back to its raw file |
| `chunk_index` | `int` | Loop counter `i` | Ordering; used to reconstruct original sequence if needed |
| `scraped_at` | `str` | ISO 8601 timestamp from manifest | Data freshness indicator shown in `AnswerCard` |

### ChromaDB ID convention

```
id = f"{slug}_chunk{chunk_index}"
# e.g. "mutual-funds_hdfc-mid-cap-fund-direct-growth_chunk0"
```

IDs are deterministic — re-running embed.py with the same corpus produces the
same IDs, which is safe because the collection is always deleted and recreated.

---

## 3. Embedding Model

### Choice

| Property | Value |
|----------|-------|
| Model | `BAAI/bge-small-en-v1.5` |
| Library | `sentence-transformers` |
| Size on disk | ~33 MB |
| Output dimension | 384 |
| Normalization | `normalize_embeddings=True` |
| Load strategy | **Once at module level** — never per query |

> **This model is fixed for the entire project. Do not substitute.**  
> Upgrading to `bge-base-en-v1.5` (768-dim) requires a full re-embed and
> ChromaDB collection rebuild; update the architecture doc before changing.

### Module-level load pattern (`ingest/embedder/embed.py`)

```python
from sentence_transformers import SentenceTransformer

# Loaded once when the module is imported — not inside any function
MODEL = SentenceTransformer("BAAI/bge-small-en-v1.5")


def embed_chunks(chunks: list[dict]) -> list[list[float]]:
    texts = [c["text"] for c in chunks]
    return MODEL.encode(texts, normalize_embeddings=True).tolist()
```

The same pattern is used in `retrieval/retriever.py` so that both the ingest
pipeline and the query path use an identical vector space.

### Why normalize?

`normalize_embeddings=True` projects all vectors to the unit sphere.
ChromaDB's default distance metric (`l2`) on unit vectors is equivalent to
cosine similarity, which is the correct metric for semantic search.

---

## 4. Vector Store — Local ChromaDB Persist Pattern

> **ChromaDB is local only.**  
> No Chroma Cloud. No `trychroma.com`. No remote client.  
> Always use `chromadb.PersistentClient`.

### Persist directory

```
data/chromadb/       ← set by CHROMA_PERSIST_DIR in .env
```

### Delete-and-recreate pattern

Every embed run starts with a clean collection to prevent stale chunks from
previous scrapes accumulating in the store.

```python
import chromadb
import os

CHROMA_PATH = os.getenv("CHROMA_PERSIST_DIR", "data/chromadb")
COLLECTION_NAME = "mf_faq"

client = chromadb.PersistentClient(path=CHROMA_PATH)

# Always wipe and rebuild — no partial updates
existing = [c.name for c in client.list_collections()]
if COLLECTION_NAME in existing:
    client.delete_collection(COLLECTION_NAME)

collection = client.create_collection(COLLECTION_NAME)

collection.add(
    ids=ids,            # list[str]  e.g. ["slug_chunk0", "slug_chunk1", ...]
    documents=docs,     # list[str]  raw chunk text
    embeddings=embeddings,  # list[list[float]]  dim=384
    metadatas=metadatas     # list[dict]  {source_url, filename, chunk_index, scraped_at}
)

print(f"Embedded {len(ids)} chunks into ChromaDB")
```

### Why delete and recreate?

- Upsert + selective delete risks leaving orphaned chunks if a URL is removed
  from the corpus or a slug changes.
- Full rebuild takes <60 seconds for 20 URLs and is triggered only once per day
  by the GitHub Actions scheduler — cost is negligible.
- Guarantees the vector store always matches the current day's scrape exactly.

---

## 5. GitHub Actions Artifact → Render Backend Flow

### Overview

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions (daily 9:15 AM IST / 03:45 UTC)         │
│                                                         │
│  scrape.py → chunk.py → embed.py                        │
│                    │                                    │
│                    └── data/chromadb/  (PersistentClient│
│                            │           writes here)     │
│                            ▼                            │
│        actions/upload-artifact@v3                       │
│        name: chromadb-artifact                          │
│        retention-days: 7                                │
└─────────────────────────────────────────────────────────┘
                            │  ZIP archive stored by GitHub
                            ▼
┌─────────────────────────────────────────────────────────┐
│  Render Backend (startup lifespan event)                │
│                                                         │
│  scripts/download_artifact.py                           │
│    1. GET /repos/{GITHUB_REPO}/actions/artifacts        │
│       Authorization: token {GITHUB_TOKEN}  (from .env)  │
│    2. Find latest artifact named "chromadb-artifact"    │
│    3. GET artifact download_url → ZIP stream            │
│    4. Unzip → data/chromadb/                            │
│    5. Print "ChromaDB loaded: N documents"              │
│                                                         │
│  uvicorn api.main:app  → begins serving /chat           │
└─────────────────────────────────────────────────────────┘
```

### Why not push chromadb/ to the Git repo?

- Binary SQLite files in ChromaDB change on every embed run (binary blobs +
  WAL files). Committing them bloats the repo history permanently.
- GitHub Actions artifacts are purpose-built for ephemeral build outputs,
  with automatic expiry (7 days here) and no repo pollution.
- The download-at-startup pattern means Render always gets the most recent
  artifact without any manual deploy step.

### Failure handling in `download_artifact.py`

| Scenario | Behaviour |
|----------|-----------|
| No artifact found (first deploy before any Action has run) | Print warning; backend starts with empty ChromaDB; `/chat` returns "no context" fallback |
| GitHub API rate limit / network error | Retry 3× with 5 s backoff; exit with code 1 if all retries fail (Render marks deploy as failed) |
| Artifact older than 7 days (expired) | Same as "not found" |

### Environment variables required

```
GITHUB_TOKEN=<your_github_pat>     # stored in Render env vars / GitHub Secrets
GITHUB_REPO=raitushar217/mf-faq-assistant
CHROMA_PERSIST_DIR=./data/chromadb
```

> **Never hardcode the token value in any source file.**  
> Use `.env` locally (gitignored) and Render/GitHub Secrets in CI/CD.

---

## 6. End-to-End Data Flow Summary

```
data/raw/<slug>.txt
        │
        │  chunk.py  (300w / 50w overlap / min 20w)
        ▼
data/chunks/<slug>_chunks.json
        │
        │  embed.py  (BAAI/bge-small-en-v1.5, dim=384, normalized)
        ▼
data/chromadb/          ← PersistentClient, collection "mf_faq"
        │
        │  upload-artifact (GitHub Actions)
        ▼
GitHub artifact store   (retention 7 days)
        │
        │  download_artifact.py  (Render startup)
        ▼
data/chromadb/  on Render instance
        │
        │  retriever.py  (query time)
        ▼
Top-3 chunks by cosine similarity  →  generator.py  →  /chat response
```
