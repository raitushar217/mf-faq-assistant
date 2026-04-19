"""
Phase 6 — LLM Generation
llm/generator.py

Uses Groq API (llama3-8b-8192) to generate an answer based ONLY on retrieved chunks.
"""

import os
from groq import Groq

SYSTEM_PROMPT = """You are a mutual fund FAQ assistant. Answer ONLY factual questions about
HDFC mutual fund schemes using the provided context chunks.

Rules:
- Answer in 1–3 sentences maximum.
- End every answer exactly with this phrasing: "Last updated from sources: <url>" (use source_url from context)
- If context does not contain the answer, say exactly:
  'I don't have that information. Please check: https://www.hdfcfund.com'
- Never give investment advice, return predictions, or recommendations.
- Do not make up any facts. Use only the provided context."""

def generate_answer(query: str, context_chunks: list[dict]) -> dict:
    """
    Generates an answer using the provided context.
    Returns: {"answer": str, "source_url": str}
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"answer": "Service unavailable. API key missing.", "source_url": ""}

    client = Groq(api_key=api_key)

    if not context_chunks:
        return {"answer": "I don't have that information. Please check: https://www.hdfcfund.com", "source_url": ""}

    # Build context string
    context_text = "\n\n".join([f"Context (Source: {c['source_url']}):\n{c['text']}" for c in context_chunks])
    
    # We will pick the top source_url to return along with the result, 
    # though the LLM is instructed to embed it in the response as well.
    top_source_url = context_chunks[0]["source_url"]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context_text}\n\nQuestion: {query}"}
    ]

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=200,
            temperature=0,
        )
        answer = completion.choices[0].message.content.strip()
        return {"answer": answer, "source_url": top_source_url}
    except Exception as e:
        print(f"Groq API Error: {e}")
        return {"answer": "Service unavailable. Please try again.", "source_url": ""}
