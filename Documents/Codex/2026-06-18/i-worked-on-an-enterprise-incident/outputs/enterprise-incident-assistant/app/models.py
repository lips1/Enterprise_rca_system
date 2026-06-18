from pydantic import BaseModel, Field
from typing import Optional


class InvestigationRequest(BaseModel):
    user_id: str
    role: str = Field(examples=["SRE", "L1_SUPPORT", "DBA", "INCIDENT_COMMANDER"])
    incident_id: str
    service_name: str
    query: str
    start_time: str
    end_time: str


class Evidence(BaseModel):
    source: str
    timestamp: Optional[str] = None
    finding: str
    confidence: str
    raw_ref: str


class ToolObservation(BaseModel):
    tool_name: str
    allowed: bool
    latency_ms: int
    row_count: int
    notes: str


class AgentObservation(BaseModel):
    agent_name: str
    latency_ms: int
    status: str
    input_tokens_estimate: int = 0
    output_tokens_estimate: int = 0
    notes: str


class GuardrailDecision(BaseModel):
    name: str
    passed: bool
    severity: str
    message: str


class AgentEvaluation(BaseModel):
    agent_name: str
    score: float
    passed: bool
    findings: list[str]


class ValidationResult(BaseModel):
    is_grounded: bool
    confidence: str
    supported_claims: list[str]
    unsupported_claims: list[str]


class InvestigationResponse(BaseModel):
    incident_id: str
    service_name: str
    summary: str
    probable_root_cause: str
    timeline: list[str]
    evidence: list[Evidence]
    validation: ValidationResult
    recommended_actions: list[str]
    checkpoint_id: str
    observability: dict
    guardrails: list[GuardrailDecision]
    agent_observations: list[AgentObservation]
    agent_evaluations: list[AgentEvaluation]
    tool_observations: list[ToolObservation]


class AsyncJobResponse(BaseModel):
    job_id: str
    status: str
    poll_url: str


class JobState(BaseModel):
    job_id: str
    status: str
    request: InvestigationRequest
    result: Optional[InvestigationResponse] = None
    error: Optional[str] = None


class EvalSuiteResult(BaseModel):
    total_cases: int
    passed_cases: int
    average_groundedness: float
    average_latency_ms: float
    cases: list[dict]
