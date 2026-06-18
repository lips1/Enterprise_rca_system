from app.models import Evidence, InvestigationRequest, ValidationResult
from app.tools import ToolGateway


class PlannerAgent:
    def plan(self, request: InvestigationRequest) -> list[str]:
        query = request.query.lower()
        tools = ["search_documents", "save_checkpoint"]
        if any(term in query for term in ["etl", "job", "batch", "failed", "failure"]):
            tools.append("check_etl_job_status")
        if any(term in query for term in ["log", "error", "failed", "timeout", "etl"]):
            tools.append("query_postgres_logs")
        if any(term in query for term in ["metric", "latency", "warehouse", "vertica", "timeout", "etl"]):
            tools.append("query_vertica_metrics")
            tools.append("query_warehouse_events")
        if any(term in query for term in ["array", "capacity", "spike", "storage", "70"]):
            tools.append("query_storage_array_metrics")
        if any(term in query for term in ["bundle", "colo", "received", "receive", "update", "updated"]):
            tools.append("query_bundle_events")
        if any(term in query for term in ["change", "deploy", "release", "config", "why"]):
            tools.append("get_change_events")
        return list(dict.fromkeys(tools))


class RagAgent:
    def run(self, gateway: ToolGateway, request: InvestigationRequest) -> list[Evidence]:
        return gateway.search_documents(request.role, request.service_name, request.query)


class OperationsDataAgent:
    def run(self, gateway: ToolGateway, request: InvestigationRequest, selected_tools: list[str]) -> list[Evidence]:
        evidence: list[Evidence] = []
        if "check_etl_job_status" in selected_tools:
            evidence += gateway.check_etl_job_status(
                request.role, request.service_name, request.start_time, request.end_time
            )
        if "query_postgres_logs" in selected_tools:
            evidence += gateway.query_postgres_logs(
                request.role, request.service_name, request.start_time, request.end_time
            )
        if "query_vertica_metrics" in selected_tools:
            evidence += gateway.query_vertica_metrics(
                request.role, request.service_name, request.start_time, request.end_time
            )
        if "query_warehouse_events" in selected_tools:
            evidence += gateway.query_warehouse_events(
                request.role, request.service_name, request.start_time, request.end_time
            )
        if "query_storage_array_metrics" in selected_tools:
            evidence += gateway.query_storage_array_metrics(
                request.role, request.service_name, request.query, request.start_time, request.end_time
            )
        if "query_bundle_events" in selected_tools:
            evidence += gateway.query_bundle_events(
                request.role, request.service_name, request.query, request.start_time, request.end_time
            )
        if "get_change_events" in selected_tools:
            evidence += gateway.get_change_events(
                request.role, request.service_name, request.start_time, request.end_time
            )
        return evidence


class ValidationAgent:
    def validate(self, evidence: list[Evidence]) -> ValidationResult:
        sources = {item.source for item in evidence}
        findings = " ".join(item.finding.lower() for item in evidence)
        supported_claims = []
        unsupported_claims = []

        if "connection timeout" in findings or "active_sessions" in findings:
            supported_claims.append("Warehouse connection/session exhaustion is supported by logs or metrics.")
        else:
            unsupported_claims.append("No direct evidence of connection/session exhaustion was found.")

        if "etl_job_status" in sources and "postgres_logs" in sources:
            supported_claims.append("ETL failure is supported by job status and PostgreSQL logs.")

        if "storage_array_metrics" in sources and "capacity_spike_pct=70" in findings:
            supported_claims.append("Array capacity spike is supported by storage array metrics.")

        if "bundle_events" in sources and ("not_received" in findings or "not_updated" in findings):
            supported_claims.append("Bundle/update issue is supported by colo bundle events.")

        is_grounded = len(supported_claims) > 0 and len(sources) >= 2
        confidence = "high" if is_grounded and len(sources) >= 4 else "medium" if is_grounded else "low"

        return ValidationResult(
            is_grounded=is_grounded,
            confidence=confidence,
            supported_claims=supported_claims,
            unsupported_claims=unsupported_claims,
        )


class SummaryAgent:
    def summarize(
        self,
        request: InvestigationRequest,
        evidence: list[Evidence],
        validation: ValidationResult,
    ) -> tuple[str, str, list[str], list[str]]:
        timeline = [
            f"{item.timestamp} - {item.finding}"
            for item in sorted(evidence, key=lambda item: item.timestamp or "")
            if item.timestamp
        ]

        findings = " ".join(item.finding.lower() for item in evidence)
        if "capacity_spike_pct=70" in findings and "not_received" in findings:
            root_cause = "Probable array 201 capacity spike caused the ETL update bundle to miss colo ingestion."
        elif "capacity_spike_pct=70" in findings and "failed" in findings:
            root_cause = "Probable storage array capacity spike contributed to the ETL failure."
        elif "active_sessions" in findings and "connection timeout" in findings:
            root_cause = "Probable warehouse connection/session exhaustion caused the billing ETL failure."
        elif "failed" in findings:
            root_cause = "Probable ETL execution failure was detected, but the exact root cause needs more evidence."
        else:
            root_cause = "No strong root cause was found from the available evidence."

        # Use LLM summarization if available
        try:
            from app.llm import generate_summary

            evidence_texts = [item.finding for item in evidence]
            llm_out = generate_summary(request.incident_id, request.service_name, evidence_texts)
            summary = llm_out
        except Exception:
            summary = (
                f"Incident {request.incident_id} for {request.service_name} was investigated using "
                "runbook/RCA retrieval, ETL status, PostgreSQL logs, Vertica metrics, warehouse events, "
                "storage array metrics, bundle events, and change events. "
                f"Validation confidence is {validation.confidence}."
            )

        actions = [
            "Check current Vertica active sessions and long-running queries.",
            "Confirm whether ETL retry succeeded after warehouse sessions normalized.",
            "Review connection pool and max session thresholds for billing ETL.",
            "Attach this evidence timeline to the incident ticket for RCA review.",
            "If array 201 is involved, verify colo bundle receipt and rerun the missed bundle after capacity stabilizes.",
        ]

        return summary, root_cause, timeline, actions
