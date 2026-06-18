from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.vector_store import load_index
from app.local_rag import search_documents


def ensure_index():
    arr, meta = load_index()
    if arr is None:
        print('Index not found. Run: python -m app.ingest')
        return False
    print(f'Loaded index with {len(meta)} chunks, dim={arr.shape[1]}')
    return True


if __name__ == '__main__':
    ok = ensure_index()
    if not ok:
        sys.exit(1)
    q = input('Query: ')
    hits = search_documents('service', q, top=5)
    print('\nTop hits:')
    for i, h in enumerate(hits, start=1):
        print(f"{i}. score: {getattr(h, 'confidence', 'N/A')} ref: {h.raw_ref}\n{h.finding[:400]}\n---\n")
