from __future__ import annotations

from typing import List

from app.config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


def generate_summary(incident_id: str, service_name: str, evidence_texts: List[str]) -> str:
    prompt = (
        "You are an incident investigation summarization assistant. "
        "Given the following evidence snippets, produce a concise summary, probable root cause, and recommended next actions.\n\n"
    )
    prompt += "\n\n".join(evidence_texts[:10])

    if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY and AZURE_OPENAI_DEPLOYMENT:
        if requests is None:
            raise RuntimeError("requests is required for Azure OpenAI calls")
        url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION or '2024-10-21'}"
        headers = {"api-key": AZURE_OPENAI_KEY, "Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful incident summarizer."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 512,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        # Response structure: choices[0].message.content
        content = data.get("choices", [])[0].get("message", {}).get("content", "")
        return content

    # Fallback: simple deterministic summarization
    summary = f"Investigation {incident_id} for {service_name}: found {len(evidence_texts)} evidence items."
    summary += " Top evidence:\n"
    for i, e in enumerate(evidence_texts[:5], start=1):
        summary += f"{i}. {e[:300]}\n"
    summary += "\nRecommended actions: review timeline, check ETL status, check DB sessions, follow runbook."
    return summary
