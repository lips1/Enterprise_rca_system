from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.evaluation import run_eval_suite
from app.job_store import JobStore
from app.models import AsyncJobResponse, EvalSuiteResult, InvestigationRequest, InvestigationResponse, JobState
from app.orchestrator import IncidentOrchestrator

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Enterprise Incident Investigation Assistant",
    description="Azure OpenAI-style incident assistant with agents, tools, RBAC, validation, memory, and observability.",
    version="1.0.0",
)

orchestrator = IncidentOrchestrator()
job_store = JobStore()
last_responses: list[InvestigationResponse] = []

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def run_background_job(job_id: str) -> None:
    try:
        job_store.mark_running(job_id)
        state = job_store.get(job_id)
        result = orchestrator.investigate(state.request)
        result.observability["sync_or_async"] = "async"
        job_store.mark_complete(job_id, result)
        last_responses.append(result)
    except Exception as exc:
        job_store.mark_failed(job_id, str(exc))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def frontend() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/investigate", response_model=InvestigationResponse)
def investigate(request: InvestigationRequest) -> InvestigationResponse:
    try:
        response = orchestrator.investigate(request)
        last_responses.append(response)
        return response
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/investigate/async", response_model=AsyncJobResponse)
def investigate_async(request: InvestigationRequest, background_tasks: BackgroundTasks) -> AsyncJobResponse:
    state = job_store.create(request)
    background_tasks.add_task(run_background_job, state.job_id)
    return AsyncJobResponse(job_id=state.job_id, status=state.status, poll_url=f"/jobs/{state.job_id}")


@app.get("/jobs/{job_id}", response_model=JobState)
def get_job(job_id: str) -> JobState:
    try:
        return job_store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.get("/observability")
def observability() -> dict:
    if not last_responses:
        return {
            "message": "No investigations have run yet.",
            "request_count": 0,
            "average_latency_ms": 0,
            "average_token_estimate": 0,
            "tool_failure_rate": 0,
        }
    total = len(last_responses)
    avg_latency = sum(item.observability["total_latency_ms"] for item in last_responses) / total
    avg_tokens = sum(item.observability["estimated_total_tokens"] for item in last_responses) / total
    grounded_rate = sum(1 for item in last_responses if item.validation.is_grounded) / total
    return {
        "request_count": total,
        "average_latency_ms": round(avg_latency, 2),
        "average_token_estimate": round(avg_tokens, 2),
        "grounded_answer_rate": round(grounded_rate, 2),
        "last_selected_tools": last_responses[-1].observability["selected_tools"],
        "last_guardrails": [item.model_dump() for item in last_responses[-1].guardrails],
        "last_agent_evaluations": [item.model_dump() for item in last_responses[-1].agent_evaluations],
    }


@app.post("/eval/run", response_model=EvalSuiteResult)
def eval_run() -> EvalSuiteResult:
    return run_eval_suite(orchestrator)
