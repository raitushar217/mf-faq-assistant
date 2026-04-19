"""
Phase 8 — FastAPI Backend
api/main.py

Stateless multi-session design.
Lifecycle hook triggers ChromaDB artifact download.
"""

import os
import sys
from contextlib import asynccontextmanager

# Add root project dir to path so absolute imports work regardless of cwd.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from classifier.classifier import is_pii, classify_query
from retrieval.retriever import retrieve
from llm.generator import generate_answer
from scripts.download_artifact import run as download_artifact

class ChatRequest(BaseModel):
    session_id: str
    query: str

class ChatResponse(BaseModel):
    answer: str
    source_url: str
    session_id: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Note: On Render, ChromaDB artifacts are downloaded in the startCommand 
    # BEFORE the server process starts to avoid file locks.
    print("FastAPI server starting up...")
    yield
    # Cleanup if necessary

app = FastAPI(lifespan=lifespan)

# CORS config: allow all in dev, restrict to vercel in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*", "GET", "POST", "OPTIONS"],
    allow_headers=["*", "Authorization", "Content-Type", "Accept"],
)

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    query = request.query.strip()
    session_id = request.session_id
    
    # 1. PII detection
    if is_pii(query):
        return ChatResponse(
            answer="I cannot process queries containing numbers that look like personal information (PAN, Aadhaar, account or phone numbers) for privacy reasons. Please rephrase your question without them.",
            source_url="",
            session_id=session_id
        )

    # 2. Classifier (factual vs advice)
    intent = classify_query(query)
    if intent == "advice":
        return ChatResponse(
            answer="I cannot provide investment advice or recommendations. However, you can find educational resources to aid your decision making here:",
            source_url="https://www.amfiindia.com/investor-corner/knowledge-center",
            session_id=session_id
        )

    # 3. Retrieval
    retrieved_chunks = retrieve(query, n_results=3)
    if not retrieved_chunks:
        return ChatResponse(
            answer="I don't have that information. Please check: https://www.hdfcfund.com",
            source_url="",
            session_id=session_id
        )

    # 4. Generator
    response_data = generate_answer(query, retrieved_chunks)
    
    return ChatResponse(
        answer=response_data["answer"],
        source_url=response_data["source_url"],
        session_id=session_id
    )

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok"}
