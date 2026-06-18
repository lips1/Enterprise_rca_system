from app.models import Evidence, InvestigationRequest


class MemoryStore:
    def __init__(self) -> None:
        self.incident_memory: dict[str, list[dict]] = {}

    def append_turn(self, request: InvestigationRequest, evidence: list[Evidence], checkpoint_id: str) -> None:
        self.incident_memory.setdefault(request.incident_id, []).append(
            {
                "checkpoint_id": checkpoint_id,
                "query": request.query,
                "service_name": request.service_name,
                "evidence_count": len(evidence),
                "sources": sorted({item.source for item in evidence}),
            }
        )

    def get_incident_history(self, incident_id: str) -> list[dict]:
        return self.incident_memory.get(incident_id, [])

