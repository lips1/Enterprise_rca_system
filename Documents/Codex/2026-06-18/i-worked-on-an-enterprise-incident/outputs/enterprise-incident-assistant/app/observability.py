import time
from contextlib import contextmanager

from app.models import AgentObservation


class ObservabilityRecorder:
    def __init__(self) -> None:
        self.agent_observations: list[AgentObservation] = []

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return max(1, len(text.split()) * 4 // 3)

    @contextmanager
    def agent_span(self, agent_name: str, input_text: str = "", notes: str = ""):
        start = time.perf_counter()
        status = "success"
        output_text = ""
        try:
            box = {"output_text": ""}
            yield box
            output_text = box.get("output_text", "")
        except Exception:
            status = "failed"
            raise
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self.agent_observations.append(
                AgentObservation(
                    agent_name=agent_name,
                    latency_ms=latency_ms,
                    status=status,
                    input_tokens_estimate=self.estimate_tokens(input_text),
                    output_tokens_estimate=self.estimate_tokens(output_text) if output_text else 0,
                    notes=notes,
                )
            )

