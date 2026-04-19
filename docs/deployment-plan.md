# MF FAQ Assistant - Deployment Strategy

This deployment architecture is specifically optimized for a zero-maintenance, low-cost (Free Tier) stack across three distinct infrastructure providers.

## 1. Data Ingestion layer (GitHub Actions)
The ingestion layer (Scraping, Chunking, Embedding) runs entirely within ephemeral Ubuntu runners on GitHub Actions to ensure scheduled automation safely without consuming main server compute.

* **Trigger**: Scheduled Cron (`45 3 * * *` corresponding to 9:15 AM IST daily) or Manual `workflow_dispatch`.
* **Execution**: Installs Playwright Chromium, triggers `scrape.py`, `chunk.py`, then `embed.py`.
* **Storage Artifact**: Once vectorization completes, it archives the local `data/chromadb/` sqlite chunks into an attached GitHub Actions Artifact named `chromadb-artifact` holding the data until the backend demands it.

## 2. API Backend Layer (Render)
The stateless FastAPI application acts as the middleware router processing the Query logic and hitting the Groq API. We host this on Render Web Services.

* **Provisioning**: A basic free-tier Python web service.
* **Environment**: Variables `GROQ_API_KEY`, `GITHUB_TOKEN`, and `GITHUB_REPO` are deployed in the Render environment settings.
* **Lifespan Hook (The Magic)**: When the Render container cold-boots or spins up from hibernation, the ASGI `lifespan` event runs `scripts/download_artifact.py`. This script securely authenticates with the GitHub API, locates the absolute newest `chromadb-artifact` `.zip` file, and downloads/extracts it directly into the ephemeral container's `data/chromadb/` directory.
* **Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

## 3. Frontend UI Layer (Vercel)
The customized, glassy React interface leverages Next.js and operates entirely detached from the backend logic.

* **Provisioning**: Deployed securely via Vercel Edge Networks. 
* **Environment**: Requires `NEXT_PUBLIC_API_URL` pointing straight to the `https://<YOUR-RENDER-APP>.onrender.com` domain.
* **CORS Safety**: While `api/main.py` is configured with `allow_origins=["*"]` locally, for production, it will be narrowed expressly to the generated Vercel domain.

## 4. Docker Containerization (Alternative Deployment)
Should you choose to skip Render/Vercel and host on a dedicated VPS (e.g. AWS EC2, DigitalOcean Droplet), you can containerize the backend API.

**Dockerfile Example:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .

# Install dependencies and Chromium for local Playwright tests if needed
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install-deps && \
    playwright install chromium

COPY . .

# Expose backend port
EXPOSE 8000

# Download artifact at container startup then launch the server
CMD ["sh", "-c", "python scripts/download_artifact.py && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
```
