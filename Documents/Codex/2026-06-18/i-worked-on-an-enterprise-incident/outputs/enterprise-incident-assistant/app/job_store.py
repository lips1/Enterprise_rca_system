import uuid

from app.models import InvestigationRequest, InvestigationResponse, JobState


class JobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, JobState] = {}

    def create(self, request: InvestigationRequest) -> JobState:
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        state = JobState(job_id=job_id, status="queued", request=request)
        self.jobs[job_id] = state
        return state

    def mark_running(self, job_id: str) -> None:
        self.jobs[job_id].status = "running"

    def mark_complete(self, job_id: str, result: InvestigationResponse) -> None:
        self.jobs[job_id].status = "complete"
        self.jobs[job_id].result = result

    def mark_failed(self, job_id: str, error: str) -> None:
        self.jobs[job_id].status = "failed"
        self.jobs[job_id].error = error

    def get(self, job_id: str) -> JobState:
        return self.jobs[job_id]

