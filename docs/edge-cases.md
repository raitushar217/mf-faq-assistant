# MF FAQ Assistant — Extracted Edge Cases & Limitations

This document centralizes all known edge cases, system limitations, and failure fallbacks extracted from the core architecture.

## 1. Data Ingestion & Scraping (`ingest/scraper/scrape.py`)
- **Non-200 HTTP Responses**: Expected frequently from SEBI and AMFI URLs (e.g., 403 Forbidden or 404 Not Found) due to strict bot-protection or decaying public links. The scraper successfully catches these, logs `SKIP <url> status=<code>`, and gracefully continues building the `scrape_manifest.json` without crashing.
- **Dynamic DOM Layouts**: Groww pages load content via React hydration. Playwright uses a blunt `page.inner_text("body")` to extract raw text safely. While this resists CSS class changes, extreme structural DOM changes post-hydration might still drop critical texts.
- **Static Daily Delta**: Corpus remains static between daily pipeline executions (9:15 AM IST). Intraday market fluctuations, live NAV changes, or breaking news are inherently excluded until the next cron cycle.
- **PDF Exclusion**: The pipeline deliberately skips PDF extraction (e.g., raw fact sheets).

## 2. Chunking & Embedding (`ingest/chunker/`, `ingest/embedder/`)
- **Sub-minimum Chunk Discarding**: Slicing logic is configured with `min_chunk=20 words`. Trailing ends of textual documents that are shorter than 20 words are silently discarded, potentially dropping ultra-short trailing disclaimers.
- **Vector Accuracy Cap**: We are utilizing `BAAI/bge-small-en-v1.5` globally due to memory and artifact size constraints. It is heavily optimized for a smaller corpus (≤ 5 URLs). Query relevance against the full spread of 20 URLs might experience degraded precision compared to `bge-base-en-v1.5`.

## 3. Storage & Retrieval (`retrieval/retriever.py`)
- **Missing or Stale ChromaDB Artifact**: If the GitHub Actions pipeline fails to build the `chromadb-artifact`, the Render `lifespan` hook (`download_artifact.py`) handles the 404 gracefully. It attempts a 3x retry-backoff, and on total failure, the backend boots up anyway using the last known local DB, preventing a total outage.
- **Empty Collections**: If the `mf_faq` collection is ever wiped, `retriever.py` catches the missing collection gracefully and returns `[]` empty results to the LLM, triggering the standard "I don't have that information" response rather than throwing a Server 500 error.

## 4. Query Classification & Security (`classifier/classifier.py`)
- **PII Blocking**: Hardcoded RegEx patterns intercept PAN, Aadhaar, 10-digit Phone Numbers, Emails, and general Account structures. These queries are halted instantly before hitting the database or Groq.
  - *Edge case*: A valid factual question containing an arbitrary 10-digit number (e.g., a massive monetary figure) will trip the false-positive phone number detector and be blocked.
- **Advice Keyword Interception**: Matches terms like "should I buy" or "predict". It hard-blocks the query and diverts the user to an AMFI educational vault.
  - *Edge case*: A user asking "What does AMFI say about how I *should invest*?" will be incorrectly blocked from retrieving actual semantic RAG data due to the keyword trigger.

## 5. LLM Generation & Output (`llm/generator.py`)
- **Deprecation / Model Dropouts**: API providers (like Groq) occasionally decommission models unexpectedly (e.g. `llama3-8b-8192` transitioning to `llama-3.1-8b-instant`). The `try/except` block wraps these HTTP 400s and gracefully outputs `"Service unavailable. Please try again."`
- **Rate Limiting**: Groq Free Tier enforces a strict ~30 requests/minute limit. Traffic spikes will result in internal 429 warnings and trigger the same graceful "Service unavailable" LLM fallback.
- **Stateless Constraints**: The backend does absolutely zero session memory caching. Contextual followup questions (e.g., User: "What is HDFC Mid Cap?", User: "Who manages *it*?") will fail on the second query because "it" will lack semantic context for the ChromaDB vector search.

## 6. Deployment & Dev-Ops
- **Render Cold Starts**: Because the backend runs on a free tier and relies heavily on downloading a heavy SQLite database `.zip` upon startup, the very first user who wakes the system up will experience a ~30 second loading latency while `scripts/download_artifact.py` completes.
