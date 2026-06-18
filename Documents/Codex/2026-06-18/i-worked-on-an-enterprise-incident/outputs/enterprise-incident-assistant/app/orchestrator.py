import time

from app.agents import OperationsDataAgent, PlannerAgent, RagAgent, SummaryAgent, ValidationAgent
from app.evaluation import AgentEvaluator
from app.guardrails import GuardrailEngine
from app.memory import MemoryStore
from app.models import InvestigationRequest, InvestigationResponse
from app.observability import ObservabilityRecorder
from app.tools import ToolGateway


class IncidentOrchestrator:
    def __init__(self) -> None:
        self.planner = PlannerAgent()
        self.rag_agent = RagAgent()
        self.ops_agent = OperationsDataAgent()
        self.validation_agent = ValidationAgent()
        self.summary_agent = SummaryAgent()
        self.guardrails = GuardrailEngine()
        self.memory = MemoryStore()
        self.evaluator = AgentEvaluator()

    def investigate(self, request: InvestigationRequest) -> InvestigationResponse:
        start = time.perf_counter()
        gateway = ToolGateway()
        recorder = ObservabilityRecorder()

        guardrail_decisions = self.guardrails.check_request(request)
        self.guardrails.enforce(guardrail_decisions)

        evidence = []
        with recorder.agent_span("Planner Agent", request.query, "Intent classification and tool selection") as span:
            selected_tools = self.planner.plan(request)
            span["output_text"] = " ".join(selected_tools)

        if "search_documents" in selected_tools:
            with recorder.agent_span("RAG Agent", request.query, "Hybrid RAG retrieval over runbooks and RCA docs") as span:
                rag_evidence = self.rag_agent.run(gateway, request)
                evidence += rag_evidence
                span["output_text"] = " ".join(item.finding for item in rag_evidence)

        with recorder.agent_span(
            "Operations Data Agent",
            " ".join(selected_tools),
            "Read-only tool calls to HPE on-prem operational sources",
        ) as span:
            ops_evidence = self.ops_agent.run(gateway, request, selected_tools)
            evidence += ops_evidence
            span["output_text"] = " ".join(item.finding for item in ops_evidence)

        guardrail_decisions += self.guardrails.check_evidence(evidence)
        self.guardrails.enforce(guardrail_decisions)

        with recorder.agent_span("Validation Agent", " ".join(item.finding for item in evidence), "Grounding and evidence checks") as span:
            validation = self.validation_agent.validate(evidence)
            span["output_text"] = " ".join(validation.supported_claims + validation.unsupported_claims)

        with recorder.agent_span("Summary Agent", " ".join(item.finding for item in evidence), "Final RCA summary generation") as span:
            summary, root_cause, timeline, actions = self.summary_agent.summarize(request, evidence, validation)
            span["output_text"] = f"{summary} {root_cause} {' '.join(actions)}"

        checkpoint_id = gateway.save_checkpoint(request.role, request.incident_id, evidence)
        self.memory.append_turn(request, evidence, checkpoint_id)

        total_latency_ms = int((time.perf_counter() - start) * 1000)
        tool_latency_ms = sum(item.latency_ms for item in gateway.observations)
        total_input_tokens = sum(item.input_tokens_estimate for item in recorder.agent_observations)
        total_output_tokens = sum(item.output_tokens_estimate for item in recorder.agent_observations)

        response = InvestigationResponse(
            incident_id=request.incident_id,
            service_name=request.service_name,
            summary=summary,
            probable_root_cause=root_cause,
            timeline=timeline,
            evidence=evidence,
            validation=validation,
            recommended_actions=actions,
            checkpoint_id=checkpoint_id,
            observability={
                "total_latency_ms": total_latency_ms,
                "tool_latency_ms": tool_latency_ms,
                "agent_count": 5,
                "tool_count": 9,
                "selected_tools": selected_tools,
                "evidence_count": len(evidence),
                "grounded": validation.is_grounded,
                "estimated_input_tokens": total_input_tokens,
                "estimated_output_tokens": total_output_tokens,
                "estimated_total_tokens": total_input_tokens + total_output_tokens,
                "memory_turns_for_incident": len(self.memory.get_incident_history(request.incident_id)),
                "sync_or_async": "sync",
                "scale_pattern": "For production, execute independent tools concurrently and run deep RCA via async jobs.",
            },
            guardrails=guardrail_decisions,
            agent_observations=recorder.agent_observations,
            agent_evaluations=[],
            tool_observations=gateway.observations,
        )

        response.agent_evaluations = [
            self.evaluator.evaluate_planner(selected_tools),
            self.evaluator.evaluate_rag(evidence),
            self.evaluator.evaluate_operations(evidence),
            self.evaluator.evaluate_validation(response),
            self.evaluator.evaluate_summary(response),
        ]
        return response
