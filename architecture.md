# MF FAQ Assistant — RAG Architecture

**AMC:** HDFC Mutual Fund  
**Schemes:** HDFC Mid Cap · HDFC Equity · HDFC Focused · HDFC ELSS Tax Saver · HDFC Large Cap (all Direct Growth)  
**Approach:** Retrieval-Augmented Generation (RAG) · Facts-only · No investment advice  
**Last revised:** 2026-04-18

---

## Project Folder Structure

```
mf-faq/
├── docs/
│   ├── rag-architecture.md
│   ├── chunking-embedding-architecture.md
│   ├── edge-cases.md
│   └── deployment-plan.md
├── ingest/
│   ├── scraper/
│   │   └── scrape.py          ← Playwright (Groww) + requests (others)
│   ├── chunker/
│   │   └── chunk.py
│   └── embedder/
│       └── embed.py
├── retrieval/
│   └── retriever.py
├── llm/
│   └── generator.py           ← Groq API
├── classifier/
│   └── classifier.py          ← keyword-only, no LLM
├── api/
│   └── main.py                ← FastAPI, stateless multi-session
├── scripts/
│   └── download_artifact.py   ← pulls chromadb artifact from GitHub API
├── frontend/                  ← Next.js dark theme
│   └── test.html              ← basic HTML smoke-test page
├── .github/
│   └── workflows/
│       └── scheduler.yml      ← GitHub Actions daily 9:15 AM IST
├── data/
│   ├── raw/                   ← scraped .txt files
│   ├── chunks/                ← chunked .json files
│   ├── chromadb/              ← local ChromaDB persist dir
│   └── scrape_manifest.json   ← per-URL scrape status + timestamp
├── logs/
│   └── scheduler.log
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

---

## Source URLs — Full Corpus (20 URLs)

| # | URL | Scheme / Source | Page type | Scraper |
|---|-----|-----------------|-----------|---------|
| 1 | https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth | HDFC Mid Cap | Scheme page | Playwright |
| 2 | https://groww.in/mutual-funds/hdfc-equity-fund-direct-growth | HDFC Equity | Scheme page | Playwright |
| 3 | https://groww.in/mutual-funds/hdfc-focused-fund-direct-growth | HDFC Focused | Scheme page | Playwright |
| 4 | https://groww.in/mutual-funds/hdfc-elss-tax-saver-fund-direct-plan-growth | HDFC ELSS | Scheme page | Playwright |
| 5 | https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth | HDFC Large Cap | Scheme page | Playwright |
| 6 | https://groww.in/p/mutual-funds/capital-gains-statement | Groww | Capital gains guide | Playwright |
| 7 | https://groww.in/p/mutual-funds/how-to-invest-in-mutual-funds | Groww | How to invest | Playwright |
| 8 | https://www.hdfcfund.com/investor-services/service-request/download-account-statement | HDFC AMC | Statement download | requests |
| 9 | https://www.amfiindia.com/investor-corner/knowledge-center/sip.html | AMFI | SIP guide | requests |
| 10 | https://www.amfiindia.com/investor-corner/knowledge-center/elss.html | AMFI | ELSS guide | requests |
| 11 | https://www.amfiindia.com/investor-corner/knowledge-center/expense-ratio.html | AMFI | Expense ratio | requests |
| 12 | https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html | AMFI | Exit load | requests |
| 13 | https://www.amfiindia.com/investor-corner/knowledge-center/riskometer.html | AMFI | Riskometer | requests |
| 14 | https://www.amfiindia.com/investor-corner/knowledge-center/benchmark.html | AMFI | Benchmark | requests |
| 15 | https://www.amfiindia.com/investor-corner/knowledge-center/mutual-fund-factsheet.html | AMFI | Factsheet guide | requests |
| 16 | https://www.camsonline.com/Investors/Statements/ConsolidatedAccountStatement | CAMS | CAS download | requests |
| 17 | https://www.kfintech.com/investor-services/account-statement/ | KFintech | Statement | requests |
| 18 | https://mfcentral.com/statement | MF Central | Statement | requests |
| 19 | https://www.sebi.gov.in/legal/circulars/sep-2021/categorization-of-mutual-fund-schemes_52823.html | SEBI | Categorization | requests |
| 20 | https://www.sebi.gov.in/legal/circulars/oct-2020/product-labeling-in-mutual-fund-schemes_48101.html | SEBI | Product labeling | requests |

> **Rule:** Any URL under `groww.in` → Playwright. All others → requests.  
> No PDFs in this project.

---

## Embedding Model Decision

| Model | Size | Dim | Use when |
|-------|------|-----|----------|
| `BAAI/bge-small-en-v1.5` | 33 MB | 384 | ≤ 5 URLs / prototype |
| `BAAI/bge-base-en-v1.5` | 109 MB | 768 | 20 URLs / production |

**This project uses `BAAI/bge-small-en-v1.5` throughout.**  
Never substitute this model. Load once at module level, not per query.

---

## Phase Overview

| Phase | Name | Folder | Triggered by |
|-------|------|--------|--------------|
| 4.0 | Scheduler + Scraping | `ingest/scraper/` | GitHub Actions cron |
| 4.1 | Chunking | `ingest/chunker/` | Scheduler (after scrape) |
| 4.2 | Embedding | `ingest/embedder/` | Scheduler (after chunk) |
| 4.3 | Vector Store | `ingest/embedder/` | Scheduler (after embed) |
| 5 | Retrieval | `retrieval/` | User query |
| 6 | LLM Generation | `llm/` | After retrieval |
| 7 | Query Classifier | `classifier/` | Before retrieval |
| 8 | FastAPI Backend | `api/` | HTTP server |
| 9 | Next.js Frontend | `frontend/` | Vercel |

---

## Phase 4.0 — Scheduler + Scraping

### GitHub Actions Scheduler

```yaml
# .github/workflows/scheduler.yml
name: Daily Ingest
on:
  schedule:
    - cron: '45 3 * * *'    # 9:15 AM IST = 03:45 UTC
  workflow_dispatch:         # manual trigger for local testing
jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: playwright install chromium
      - name: Scrape
        run: python ingest/scraper/scrape.py
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
      - name: Chunk
        run: python ingest/chunker/chunk.py
      - name: Embed + store
        run: python ingest/embedder/embed.py
      - name: Upload ChromaDB artifact
        uses: actions/upload-artifact@v3
        with:
          name: chromadb-artifact
          path: data/chromadb/
          retention-days: 7
```

**Execution order (also used for local trigger):**
```
scrape.py → chunk.py → embed.py
```

All steps append to `logs/scheduler.log` with timestamps.

### Scraping Service (`ingest/scraper/scrape.py`)

```
For each URL in the corpus table above:
  If URL contains "groww.in":
    Use Playwright (headless Chromium)
    Wait for networkidle before extracting text
    page.inner_text("body")
  Else:
    Use requests (User-Agent: "MF-FAQ-Bot/1.0")
    Strip HTML tags with regex

Save plain text → data/raw/<slug>.txt
  where slug = URL path with "/" replaced by "_"

Log SKIP <url> status=<code> for non-200 responses
Sleep 1 second between requests (not needed for Playwright but keep for politeness)
Update data/scrape_manifest.json:
  { "url": str, "slug": str, "scraped_at": ISO8601, "status": "done"|"skip" }
```

---

## Phase 4.1 — Chunking (`ingest/chunker/chunk.py`)

```
Input:  data/raw/*.txt
Output: data/chunks/<slug>_chunks.json

Strategy: fixed-size sliding window
  chunk_size   = 300 words
  overlap      = 50 words
  min_chunk    = 20 words  (discard smaller)

Each chunk dict:
  {
    "text":        str,
    "source_url":  str,   ← looked up from scrape_manifest.json by slug
    "filename":    str,
    "chunk_index": int,
    "scraped_at":  str
  }

Print "Chunked N chunks from M files" on completion.
```

---

## Phase 4.2 — Embedding (`ingest/embedder/embed.py`)

```
Input:  data/chunks/*.json
Model:  BAAI/bge-small-en-v1.5
        sentence_transformers.SentenceTransformer
        normalize_embeddings=True
        Load ONCE at module level

Output: embedding vectors (dim=384) attached to each chunk in memory
        then immediately written to ChromaDB in Phase 4.3
```

---

## Phase 4.3 — Vector Store (Local ChromaDB)

> **ChromaDB is local only. No Chroma Cloud. No trychroma.com.**  
> The built `data/chromadb/` directory is uploaded as a GitHub Actions artifact
> and downloaded by the Render backend at startup.

```python
# Pattern used in embed.py (phases 4.2 + 4.3 are one script)
import chromadb

client = chromadb.PersistentClient(path="data/chromadb")

# Always delete and recreate — no stale data
if "mf_faq" in [c.name for c in client.list_collections()]:
    client.delete_collection("mf_faq")
collection = client.create_collection("mf_faq")

collection.add(
    ids=ids,                # "{slug}_chunk{i}"
    documents=docs,         # chunk text strings
    embeddings=embeddings,  # bge-small vectors
    metadatas=metadatas     # chunk metadata dicts
)

print(f"Embedded {len(ids)} chunks into ChromaDB")
```

---

## Phase 5 — Retrieval (`retrieval/retriever.py`)

```python
def retrieve(query: str, n_results: int = 3) -> list[dict]:
    """
    Returns [{"text": str, "source_url": str, "score": float}]
    sorted by score descending.
    """
    # 1. Load ChromaDB from data/chromadb, collection mf_faq
    # 2. Embed query with bge-small (module-level cache)
    # 3. collection.query(n_results=3, include=["documents","metadatas","distances"])
    # 4. score = 1 - distance
    # 5. Return sorted list
    # 6. On empty collection or any error: return []
```

---

## Phase 6 — LLM Generation (`llm/generator.py`)

**Provider: Groq**  
**Model: `llama3-8b-8192`**  
**Key: `GROQ_API_KEY` from `.env`**

```
SYSTEM_PROMPT (use verbatim):
"You are a mutual fund FAQ assistant. Answer ONLY factual questions about
HDFC mutual fund schemes using the provided context chunks.

Rules:
- Answer in 1–3 sentences maximum.
- End every answer with: Source: <url>  (use source_url from context)
- If context does not contain the answer, say exactly:
  'I don't have that information. Please check: https://www.hdfcfund.com'
- Never give investment advice, return predictions, or recommendations.
- Do not make up any facts. Use only the provided context."

Call parameters: model="llama3-8b-8192", max_tokens=200, temperature=0
On any API error: return "Service unavailable. Please try again."
```

---

## Phase 7 — Query Classifier (`classifier/classifier.py`)

**Pure keyword/regex. No LLM call.**

```python
ADVICE_KEYWORDS = [
    "should i", "should i buy", "should i sell", "is it good",
    "recommend", "better option", "worth investing", "which is best",
    "suggest", "should invest", "will it give", "returns will",
    "predict", "future performance", "portfolio", "compare returns"
]

def classify_query(query: str) -> str:
    # Returns "factual" or "advice"

def is_pii(query: str) -> bool:
    # PAN:      [A-Z]{5}[0-9]{4}[A-Z]
    # Aadhaar:  \b\d{4}\s?\d{4}\s?\d{4}\b
    # Phone:    \b[6-9]\d{9}\b
    # Email:    \S+@\S+\.\S+
    # Account:  \b\d{9,18}\b
```

**Decision tree on every incoming query:**
```
is_pii?
  True  → block, return PII error message
  False → classify_query
            "advice"  → polite refusal + link to
                        https://www.amfiindia.com/investor-corner/knowledge-center
            "factual" → retrieve → generate → respond
```

---

## Phase 8 — FastAPI Backend (`api/main.py`)

### Endpoints

```
POST /chat
  Body:     { "session_id": str, "query": str }
  Response: { "answer": str, "source_url": str, "session_id": str }

GET /health
  Response: { "status": "ok" }
```

### Multi-session design

- Each `session_id` is fully isolated — no shared memory between sessions
- No conversation history stored (stateless per query)
- `session_id` used only for logging, never for state lookup
- FastAPI async handlers — no global mutable state
- CORS: allow all origins in dev; restrict to Vercel domain in production

### Startup (lifespan event)

```python
# At startup, call scripts/download_artifact.py to pull
# latest chromadb-artifact from GitHub Actions into data/chromadb/
# before the first query is served
```

---

## Phase 9 — Next.js Frontend (`frontend/`)

Dark theme. All API calls use `process.env.NEXT_PUBLIC_API_URL` as base URL.
Never hardcode `localhost`. Add `NEXT_PUBLIC_API_URL` to `frontend/.env.local.example`.

### Components

| Component | Purpose |
|-----------|---------|
| `WelcomeBanner` | Title + disclaimer pill |
| `ExampleQuestions` | 3 clickable chips that pre-fill the input |
| `ChatThread` | Message bubbles, one per session |
| `AnswerCard` | Answer text + source link + last updated date |
| `RefusalCard` | Polite refusal message + educational link |
| `NewSessionButton` | Creates a new isolated chat thread |
| `DisclaimerFooter` | Persistent facts-only notice at bottom |

### Example questions shown on load

1. "What is the expense ratio of HDFC ELSS Tax Saver Fund?"
2. "What is the minimum SIP for HDFC Mid Cap Fund?"
3. "How do I download my capital gains statement?"

### Disclaimer text (use verbatim in UI)

> "Facts only. No investment advice. Data sourced from public AMC/AMFI/SEBI pages.
> Consult a SEBI-registered investment advisor before making any financial decisions."

### Basic HTML test page

`frontend/test.html` — a plain HTML form that POSTs to `NEXT_PUBLIC_API_URL/chat`
and displays the raw JSON response. Used for smoke-testing the backend without
running Next.js.

---

## Environment Variables

### `.env` (backend)

```
GROQ_API_KEY=
CHROMA_PERSIST_DIR=./data/chromadb
GITHUB_TOKEN=
GITHUB_REPO=raitushar217/mf-faq-assistant
```

### `frontend/.env.local`

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### `.env.example` (committed to repo)

```
GROQ_API_KEY=your_groq_key_here
CHROMA_PERSIST_DIR=./data/chromadb
GITHUB_TOKEN=your_github_pat_here
GITHUB_REPO=raitushar217/mf-faq-assistant
NEXT_PUBLIC_API_URL=https://your-render-url.onrender.com
```

---

## GitHub Artifact → Render Flow

```
GitHub Actions (daily 9:15 AM IST)
  └── runs scrape → chunk → embed
  └── uploads data/chromadb/ as artifact "chromadb-artifact"

Render backend (startup lifespan)
  └── scripts/download_artifact.py
        1. GET /repos/{GITHUB_REPO}/actions/artifacts  (auth: GITHUB_TOKEN)
        2. Find most recent artifact named "chromadb-artifact"
        3. Download zip → unzip to data/chromadb/
        4. Print "ChromaDB loaded: N documents"
  └── uvicorn api.main:app starts serving queries
```

`scripts/download_artifact.py` must be implemented before the deploy prompts.

---

## Deployment Plan

| Layer | Platform | Notes |
|-------|----------|-------|
| Scheduler / Ingest | GitHub Actions | Cron 9:15 AM IST; artifact = `data/chromadb/` |
| Backend | Render (FastAPI + uvicorn) | Downloads artifact at startup; `PORT=8000` |
| Frontend | Vercel (Next.js) | `NEXT_PUBLIC_API_URL` → Render service URL |
| Container (optional) | Docker | Single image wrapping backend + artifact download |

### Render startup command

```bash
python scripts/download_artifact.py && uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && playwright install chromium
COPY . .
CMD ["sh", "-c", "python scripts/download_artifact.py && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
```

---

## requirements.txt

```
requests==2.31.0
playwright==1.44.0
chromadb==0.4.22
sentence-transformers==2.6.1
groq==0.9.0
fastapi==0.111.0
uvicorn==0.30.0
python-dotenv==1.0.1
```

---

## Known Limitations

- Groww pages may change their React component structure — Playwright selector
  `page.inner_text("body")` is intentionally broad to resist layout changes
- bge-small-en-v1.5 is optimised for ≤5 URLs; accuracy may drop on edge queries
  with the full 20-URL corpus — upgrade to bge-base for production
- Stateless design means follow-up questions must be self-contained
- Groq free tier: ~30 req/min — add exponential backoff retry for production
- Render cold start adds ~30s on first query after the artifact download
- Corpus is static between daily runs; intraday NAV changes not reflected
- No PDF ingestion in this version
