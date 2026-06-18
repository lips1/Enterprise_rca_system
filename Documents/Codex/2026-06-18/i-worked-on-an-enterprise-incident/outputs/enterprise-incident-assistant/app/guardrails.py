from app.models import Evidence, GuardrailDecision, InvestigationRequest


class GuardrailEngine:
    blocked_terms = ["drop table", "delete from", "truncate", "password", "api key", "secret"]

    def check_request(self, request: InvestigationRequest) -> list[GuardrailDecision]:
        text = request.query.lower()
        decisions = [
            GuardrailDecision(
                name="prompt_injection_check",
                passed=not any(term in text for term in ["ignore previous", "bypass", "reveal system prompt"]),
                severity="high",
                message="Detects attempts to override system or security instructions.",
            ),
            GuardrailDecision(
                name="dangerous_action_check",
                passed=not any(term in text for term in self.blocked_terms),
                severity="critical",
                message="Blocks destructive commands, secrets, and unsafe data requests.",
            ),
            GuardrailDecision(
                name="time_window_required",
                passed=bool(request.start_time and request.end_time),
                severity="medium",
                message="Requires bounded time window to control latency and blast radius.",
            ),
        ]
        return decisions

    def check_evidence(self, evidence: list[Evidence]) -> list[GuardrailDecision]:
        text = " ".join(item.finding.lower() for item in evidence)
        return [
            GuardrailDecision(
                name="sensitive_output_check",
                passed=not any(term in text for term in self.blocked_terms),
                severity="high",
                message="Ensures sensitive values are not included in model context or final output.",
            ),
            GuardrailDecision(
                name="grounding_evidence_check",
                passed=len(evidence) > 0,
                severity="high",
                message="Requires evidence before generating incident conclusions.",
            ),
        ]

    @staticmethod
    def enforce(decisions: list[GuardrailDecision]) -> None:
        failed = [item for item in decisions if not item.passed and item.severity in {"high", "critical"}]
        if failed:
            names = ", ".join(item.name for item in failed)
            raise PermissionError(f"Guardrail blocked request: {names}")

