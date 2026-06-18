from statistics import mean
from time import perf_counter

from app.models import AgentEvaluation, EvalSuiteResult, Evidence, InvestigationRequest, InvestigationResponse


class AgentEvaluator:
    def evaluate_planner(self, selected_tools: list[str]) -> AgentEvaluation:
        required = {"search_documents", "query_postgres_logs", "query_vertica_metrics"}
        missing = sorted(required.difference(selected_tools))
        score = 1.0 if not missing else 0.65
        return AgentEvaluation(
            agent_name="Planner Agent",
            score=score,
            passed=score >= 0.8,
            findings=["Selected critical tools."] if not missing else [f"Missing tools: {', '.join(missing)}"],
        )

    def evaluate_rag(self, evidence: list[Evidence]) -> AgentEvaluation:
        rag_hits = [item for item in evidence if item.source == "rag_documents"]
        score = min(1.0, len(rag_hits) / 2)
        return AgentEvaluation(
            agent_name="RAG Agent",
            score=score,
            passed=score >= 0.5,
            findings=[f"Retrieved {len(rag_hits)} relevant document chunks."],
        )

    def evaluate_operations(self, evidence: list[Evidence]) -> AgentEvaluation:
        sources = {item.source for item in evidence}
        expected = {"postgres_logs", "vertica_metrics", "etl_job_status"}
        score = len(expected.intersection(sources)) / len(expected)
        return AgentEvaluation(
            agent_name="Operations Data Agent",
            score=score,
            passed=score >= 0.67,
            findings=[f"Operational sources used: {', '.join(sorted(sources))}"],
        )

    def evaluate_validation(self, response: InvestigationResponse) -> AgentEvaluation:
        score = 1.0 if response.validation.is_grounded and response.validation.supported_claims else 0.4
        return AgentEvaluation(
            agent_name="Validation Agent",
            score=score,
            passed=score >= 0.8,
            findings=response.validation.supported_claims or ["No supported claims found."],
        )

    def evaluate_summary(self, response: InvestigationResponse) -> AgentEvaluation:
        has_timeline = len(response.timeline) > 0
        has_actions = len(response.recommended_actions) > 0
        has_root_cause = "Probable" in response.probable_root_cause
        score = sum([has_timeline, has_actions, has_root_cause]) / 3
        return AgentEvaluation(
            agent_name="Summary Agent",
            score=score,
            passed=score >= 0.8,
            findings=["Summary includes timeline, root cause, and recommended actions."],
        )


def run_eval_suite(orchestrator) -> EvalSuiteResult:
    cases = [
        InvestigationRequest(
            user_id="eval_sre",
            role="SRE",
            incident_id="EVAL-001",
            service_name="billing-etl",
            query="Why did the billing ETL fail last night?",
            start_time="2026-06-17T00:00:00",
            end_time="2026-06-17T06:00:00",
        ),
        InvestigationRequest(
            user_id="eval_ic",
            role="INCIDENT_COMMANDER",
            incident_id="EVAL-002",
            service_name="billing-etl",
            query="Investigate billing ETL timeout and check deployment changes",
            start_time="2026-06-17T00:00:00",
            end_time="2026-06-17T06:00:00",
        ),
    ]
    results = []
    for case in cases:
        start = perf_counter()
        response = orchestrator.investigate(case)
        latency_ms = int((perf_counter() - start) * 1000)
        eval_score = mean(item.score for item in response.agent_evaluations)
        passed = response.validation.is_grounded and eval_score >= 0.8
        results.append(
            {
                "incident_id": case.incident_id,
                "passed": passed,
                "grounded": response.validation.is_grounded,
                "eval_score": round(eval_score, 2),
                "latency_ms": latency_ms,
            }
        )
    return EvalSuiteResult(
        total_cases=len(results),
        passed_cases=sum(1 for item in results if item["passed"]),
        average_groundedness=mean(1.0 if item["grounded"] else 0.0 for item in results),
        average_latency_ms=mean(item["latency_ms"] for item in results),
        cases=results,
    )

