from __future__ import annotations

import json
from pathlib import Path
from typing import List

import joblib
import numpy as np
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity

from app.models import Evidence
from app.vector_store import load_index, search, search_bm25


def search_documents(service_name: str, query: str, top: int = 5) -> List[Evidence]:
    arr, meta = load_index()
    if arr is None:
        return []

    # Try embedding-based search first (import locally to avoid cycles)
    results = []
    try:
        from app.embeddings import embed_texts

        q_emb = embed_texts([query])[0]
        results = search(q_emb, top_k=top)
    except Exception:
        results = []

    # If embedding search failed or returned nothing, try BM25 (if available)
    if not results:
        try:
            results = search_bm25(query, top_k=top)
            # Hybrid rerank: compute embedding similarity for the BM25 hits if embeddings available
            try:
                from app.embeddings import embed_texts

                # gather chunk_texts for hits
                chunk_texts = [m.get("chunk_text") or "" for (_, _, m) in results]
                q_emb = embed_texts([query])[0]
                chunk_embs = embed_texts(chunk_texts)
                # compute cosine similarities
                import numpy as _np
                from numpy.linalg import norm as _norm

                qv = _np.array(q_emb, dtype=float)
                ces = _np.array(chunk_embs, dtype=float)
                dots = ces @ qv
                norms = _norm(ces, axis=1) * (_norm(qv) + 1e-12)
                emb_scores = dots / norms
                # combine BM25 score and embedding score (simple average after normalization)
                bm_scores = _np.array([s for (_, s, _) in results], dtype=float)
                if bm_scores.max() - bm_scores.min() > 1e-6:
                    bm_norm = (bm_scores - bm_scores.min()) / (bm_scores.max() - bm_scores.min())
                else:
                    bm_norm = bm_scores
                if emb_scores.max() - emb_scores.min() > 1e-6:
                    emb_norm = (emb_scores - emb_scores.min()) / (emb_scores.max() - emb_scores.min())
                else:
                    emb_norm = emb_scores
                combined = 0.5 * bm_norm + 0.5 * emb_norm
                order = list(_np.argsort(combined)[::-1])
                results = [results[i] for i in order]
            except Exception:
                pass
        except Exception:
            results = []

    hits: List[Evidence] = []
    for idx, score, m in results:
        chunk_text = m.get("chunk_text") or f"Document {m.get('doc_id')} - {m.get('title')}"
        hits.append(
            Evidence(
                source="rag_documents",
                timestamp=m.get("created_at"),
                finding=chunk_text,
                confidence="medium",
                raw_ref=f"local-rag://{m.get('chunk_id')}",
            )
        )
    return hits
