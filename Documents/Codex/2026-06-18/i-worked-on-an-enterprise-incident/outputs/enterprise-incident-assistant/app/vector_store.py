from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
from numpy.linalg import norm

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover
    BM25Okapi = None

try:
    import faiss
except Exception:  # pragma: no cover
    faiss = None

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_RAG_DIR = BASE_DIR / "data" / "local_rag"
LOCAL_RAG_DIR.mkdir(parents=True, exist_ok=True)

VECTORS_PATH = LOCAL_RAG_DIR / "vectors.npy"
META_PATH = LOCAL_RAG_DIR / "meta.json"
FAISS_INDEX_PATH = LOCAL_RAG_DIR / "faiss.index"


def save_index(embeddings: List[List[float]], meta: List[dict]) -> None:
    arr = np.array(embeddings, dtype="float32")
    np.save(VECTORS_PATH, arr)
    with META_PATH.open("w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    # build FAISS index for faster nearest-neighbor search if available
    if faiss is not None and arr.size:
        dim = arr.shape[1]
        index = faiss.IndexFlatIP(dim)
        # normalize vectors for cosine similarity via inner product
        faiss.normalize_L2(arr)
        index.add(arr)
        faiss.write_index(index, str(FAISS_INDEX_PATH))


def load_index():
    if not VECTORS_PATH.exists() or not META_PATH.exists():
        return None, None
    arr = np.load(VECTORS_PATH)
    with META_PATH.open("r", encoding="utf-8") as fh:
        meta = json.load(fh)
    return arr, meta


def search(query_embedding: List[float], top_k: int = 5) -> List[Tuple[int, float, dict]]:
    arr, meta = load_index()
    if arr is None:
        return []
    q = np.array(query_embedding, dtype="float32")
    # use FAISS index if available
    if faiss is not None and FAISS_INDEX_PATH.exists():
        index = faiss.read_index(str(FAISS_INDEX_PATH))
        q_norm = q.reshape(1, -1)
        faiss.normalize_L2(q_norm)
        D, I = index.search(q_norm, top_k)
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            results.append((int(idx), float(score), meta[int(idx)]))
        return results

    # brute-force cosine similarity fallback
    q = q.astype(float)
    dots = arr @ q
    norms = norm(arr, axis=1) * (norm(q) + 1e-12)
    scores = dots / norms
    idx = list(np.argsort(scores)[::-1][:top_k])
    results = [(int(i), float(scores[i]), meta[int(i)]) for i in idx]
    return results


def _tokenize(text: str):
    # simple whitespace tokenizer; keep it lightweight and deterministic
    return [t.lower() for t in text.split() if t.strip()]


def search_bm25(query: str, top_k: int = 5) -> List[Tuple[int, float, dict]]:
    """BM25 search over stored chunks. Requires `rank_bm25` package.

    Returns a list of tuples (index, score, meta).
    """
    if BM25Okapi is None:
        raise RuntimeError("Install rank_bm25 to use BM25 retrieval (pip install rank_bm25)")
    _, meta = load_index()
    if not meta:
        return []
    # expect each meta item to contain a 'chunk_text' field
    docs = [m.get("chunk_text") or m.get("text") or "" for m in meta]
    tokenized = [ _tokenize(d) for d in docs ]
    bm25 = BM25Okapi(tokenized)
    qtok = _tokenize(query)
    scores = bm25.get_scores(qtok)
    idxs = list(np.argsort(scores)[::-1][:top_k])
    results = [(int(i), float(scores[i]), meta[i]) for i in idxs]
    return results
