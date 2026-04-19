"""
Phase 7 — Query Classifier
classifier/classifier.py

Pure keyword/regex based query classifier and PII detector.
No LLM calls happen here.
"""

import re

# Architecture specified keywords for advice detection
ADVICE_KEYWORDS = [
    "should i", "should i buy", "should i sell", "is it good",
    "recommend", "better option", "worth investing", "which is best",
    "suggest", "should invest", "will it give", "returns will",
    "predict", "future performance", "portfolio", "compare returns"
]

PII_PATTERNS = {
    # [A-Z]{5}[0-9]{4}[A-Z]
    "pan": re.compile(r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b"),
    # \b\d{4}\s?\d{4}\s?\d{4}\b
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    # \b[6-9]\d{9}\b
    "phone": re.compile(r"\b[6-9]\d{9}\b"),
    # \S+@\S+\.\S+
    "email": re.compile(r"\S+@\S+\.\S+"),
    # \b\d{9,18}\b  (Account details roughly)
    "account": re.compile(r"\b\d{9,18}\b")
}

def is_pii(query: str) -> bool:
    """Check if the query contains any Personal Identifiable Information."""
    for pattern_name, pattern in PII_PATTERNS.items():
        if pattern.search(query):
            return True
    return False

def classify_query(query: str) -> str:
    """
    Classify the query based on keyword lists.
    Returns "advice" or "factual".
    """
    query_lower = query.lower()
    for kw in ADVICE_KEYWORDS:
        if kw in query_lower:
            return "advice"
    return "factual"
