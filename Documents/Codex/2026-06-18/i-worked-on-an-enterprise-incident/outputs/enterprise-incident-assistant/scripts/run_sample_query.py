from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.vector_store import load_index
from app.ingest import build_local_index
from app.local_rag import search_documents


def main():
    arr, meta = load_index()
    if arr is None:
        print('Index not found — building local index...')
        build_local_index()
    else:
        print(f'Loaded index with {len(meta)} chunks.')

    query = 'Why did the billing ETL fail last night?'
    print(f'Running sample query: {query}')
    hits = search_documents('billing-etl', query, top=5)
    out = []
    for h in hits:
        out.append({
            'source': h.source,
            'timestamp': h.timestamp,
            'finding': h.finding,
            'raw_ref': h.raw_ref,
        })
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
