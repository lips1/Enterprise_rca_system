from __future__ import annotations

import os
from typing import List

import numpy as np
from app.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:  # pragma: no cover
    TfidfVectorizer = None
    
try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional
    SentenceTransformer = None


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts. Prefer Azure OpenAI embeddings when configured, else fall back to TF-IDF dense vectors.

    Returns a list of embedding vectors (lists of floats).
    """
    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY and AZURE_OPENAI_DEPLOYMENT:
        if requests is None:
            raise RuntimeError("requests package is required for Azure OpenAI embeddings")
        url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/embeddings?api-version={AZURE_OPENAI_API_VERSION or '2024-10-21'}"
        headers = {"api-key": AZURE_OPENAI_KEY, "Content-Type": "application/json"}
        payload = {"input": texts}
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        embeddings = [item["embedding"] for item in data.get("data", [])]
        return embeddings

    # Local semantic embeddings: prefer sentence-transformers if installed
    if SentenceTransformer is not None:
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embs = model.encode(texts, show_progress_bar=False)
        # ensure nested lists
        return [emb.tolist() for emb in embs]

    # Fallback: TF-IDF dense vectors
    if TfidfVectorizer is None:
        raise RuntimeError("Install sentence-transformers or scikit-learn for local embeddings")
    vec = TfidfVectorizer(max_features=16384)
    X = vec.fit_transform(texts)
    return [row.tolist() for row in X.toarray()]
