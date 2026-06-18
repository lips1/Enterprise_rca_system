from __future__ import annotations

from typing import Any

from app.config import AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, AZURE_SEARCH_KEY
from app.models import Evidence

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
except ImportError:  # pragma: no cover
    SearchClient = None  # type: ignore
    AzureKeyCredential = None  # type: ignore


def search_documents(service_name: str, query: str, top: int = 5) -> list[Evidence]:
    if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_KEY:
        raise RuntimeError(
            "Azure AI Search is not configured. Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY."
        )
    if SearchClient is None or AzureKeyCredential is None:
        raise RuntimeError(
            "Missing azure-search-documents package. Install it to use Azure AI Search."
        )

    client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY),
    )

    search_query = f"{service_name} {query}".strip()
    results = client.search(search_query, top=top)

    hits: list[Evidence] = []
    for doc in results:
        content = doc.get("content") or doc.get("text") or ""
        hits.append(
            Evidence(
                source="rag_documents",
                timestamp=doc.get("created_at"),
                finding=content,
                confidence="medium",
                raw_ref=f"azure-search://{doc.get('id', 'unknown')}",
            )
        )
        if len(hits) >= top:
            break

    return hits
