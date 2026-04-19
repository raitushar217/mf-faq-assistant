# MF FAQ Assistant - HDFC Mutual Funds

A Retrieval-Augmented Generation (RAG) assistant designed to answer factual questions about HDFC Mutual Fund schemes exclusively using official public pages. 

## Scope
- **AMC**: HDFC Mutual Fund
- **Schemes**:
  1. HDFC Mid Cap Direct Growth
  2. HDFC Equity Direct Growth
  3. HDFC Focused Direct Growth
  4. HDFC ELSS Tax Saver Direct Growth
  5. HDFC Large Cap Direct Growth

## Setup Steps

### 1. Requirements
Ensure you are using Python 3.11+ and Node.js 18+.

### 2. Backend Setup
```bash
# For local ingestion (heavy dependencies like torch)
pip install -r requirements-ingest.txt

# For running only the backend (lean dependencies for Render)
pip install -r requirements.txt

playwright install chromium

# Create the .env file with your API Keys (see .env.example)
# GROQ_API_KEY=your_key

# Run the ingestion pipeline locally to scrape data and build vectors
python scripts/trigger_local.py

# Start the FastAPI Server
uvicorn api.main:app --port 8000
```

### 3. Frontend Setup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to interact with the FAQ bot.

## Known Limitations
- **DOM Dependencies**: Scraping Groww uses broad `page.inner_text("body")` which resists CSS changes but risks losing texts if immense DOM hydration delays occur.
- **Lexical Limitations**: Hardcoded keyword interceptors (e.g. blocking "should I buy") will intercept both actual investment advice questions AND benign semantic inquiries like "What does AMFI say about how I *should invest*?".
- **Data Latency**: Data is frozen at the moment of the Github Action trigger (cron 9:15 AM). Live intraday NAV fluctuations are not mirrored.
- **Model**: `BAAI/bge-small-en-v1.5` is highly constrained and accuracy across the spread of a 20-URL corpus may face collision edge cases.
