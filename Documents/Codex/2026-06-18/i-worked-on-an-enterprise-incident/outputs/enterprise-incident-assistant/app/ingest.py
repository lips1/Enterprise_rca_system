"""
Simple local ingest pipeline:
- Reads `data/documents.json`
- Splits documents into chunks
- Fits a `TfidfVectorizer` over chunks and saves vectors and metadata
- Outputs files under `data/local_rag/` with `vectors.npz`, `meta.json`, and `vectorizer.joblib`

Usage:
    python -m app.ingest
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import List

import joblib
import numpy as np
from app.embeddings import embed_texts
from app.vector_store import save_index

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOCAL_RAG_DIR = DATA_DIR / "local_rag"
LOCAL_RAG_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _split_sentences(text: str):
    import re

    # split on sentence-ending punctuation followed by whitespace
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Chunk text into coherent passages.

    Strategy:
    1. Split by paragraph (double newlines). Prefer paragraph-sized chunks.
    2. If a paragraph is too large, split by sentences and pack sentences into chunks up to `size` characters.
    3. Fallback to sliding window character chunks with overlap.
    """
    if not text:
        return []

    # Normalize newlines
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks: List[str] = []

    for para in paragraphs:
        if len(para) <= size:
            chunks.append(para)
            continue

        # split into sentences and pack
        sentences = _split_sentences(para)
        cur = []
        cur_len = 0
        for s in sentences:
            if cur_len + len(s) + 1 <= size:
                cur.append(s)
                cur_len += len(s) + 1
            else:
                if cur:
                    chunks.append(' '.join(cur).strip())
                # if single sentence longer than size, fallback to sliding window on sentence
                if len(s) > size:
                    start = 0
                    while start < len(s):
                        end = min(start + size, len(s))
                        chunks.append(s[start:end].strip())
                        if end == len(s):
                            break
                        start = end - overlap
                    cur = []
                    cur_len = 0
                else:
                    cur = [s]
                    cur_len = len(s) + 1
        if cur:
            chunks.append(' '.join(cur).strip())

    # If still no chunks for weird inputs, fallback to sliding window over full text
    if not chunks:
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunk = text[start:end]
            chunks.append(chunk.strip())
            if end == len(text):
                break
            start = end - overlap

    return chunks


def build_local_index(documents_path: str | Path = "data/documents.json") -> None:
    path = BASE_DIR / documents_path
    with path.open("r", encoding="utf-8") as fh:
        docs = json.load(fh)

    chunks = []
    meta = []
    for doc in docs:
        doc_id = doc.get("doc_id")
        title = doc.get("title", "")
        content = doc.get("content", "")
        created_at = doc.get("created_at")
        doc_chunks = _chunk_text(content)
        for idx, chunk in enumerate(doc_chunks):
            chunk_id = f"{doc_id}::chunk_{idx}"
            chunks.append(chunk)
            meta.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "title": title,
                "created_at": created_at,
            })

    if not chunks:
        print("No chunks created from documents.json")
        return

    # Generate embeddings for chunks (Azure OpenAI if configured, else TF-IDF fallback)
    embeddings = embed_texts(chunks)

    # Include chunk text in meta for retrieval output
    for i, m in enumerate(meta):
        m["chunk_text"] = chunks[i]

    save_index(embeddings, meta)

    print(f"Built local RAG index: {len(chunks)} chunks saved to {LOCAL_RAG_DIR}")


if __name__ == "__main__":
    build_local_index()
