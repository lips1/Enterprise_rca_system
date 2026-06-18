import time
import uuid
import re
from typing import Callable, Optional

from app.azure_search import search_documents as azure_search_documents
from app.config import (
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_KEY,
    ETL_API_URL,
    POSTGRES_CONN,
    STORAGE_ARRAY_API_URL,
    VERTICA_CONN,
    WAREHOUSE_API_URL,
    BUNDLE_EVENTS_API_URL,
    CHANGE_EVENT_API_URL,
)
from app.data_loader import load_json
from app.models import Evidence, ToolObservation
from app.production_connectors import (
    check_etl_job_status_live,
    get_change_events_live,
    query_bundle_events_live,
    query_postgres_logs_live,
    query_storage_array_metrics_live,
    query_vertica_metrics_live,
    query_warehouse_events_live,
)
from app.local_rag import search_documents as local_search_documents
from app.security import authorize_tool, mask_sensitive_text, validate_time_window


class ToolGateway:
    def __init__(self) -> None:
        self.observations: list[ToolObservation] = []

    def reset(self) -> None:
        self.observations = []

    def _use_azure_search(self) -> bool:
        return bool(AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY)

    def _use_live_postgres(self) -> bool:
        return bool(POSTGRES_CONN)

    def _use_live_vertica(self) -> bool:
        return bool(VERTICA_CONN)

    def _use_live_etl(self) -> bool:
        return bool(ETL_API_URL)

    def _use_live_warehouse(self) -> bool:
        return bool(WAREHOUSE_API_URL)

    def _use_live_storage_array(self) -> bool:
        return bool(STORAGE_ARRAY_API_URL)

    def _use_live_bundle_events(self) -> bool:
        return bool(BUNDLE_EVENTS_API_URL)

    def _use_live_change_events(self) -> bool:
        return bool(CHANGE_EVENT_API_URL)

    def _run(self, role: str, tool_name: str, fn: Callable[[], list[Evidence]]) -> list[Evidence]:
        start = time.perf_counter()
        authorize_tool(role, tool_name)
        result = fn()
        latency_ms = int((time.perf_counter() - start) * 1000)
        self.observations.append(
            ToolObservation(
                tool_name=tool_name,
                allowed=True,
                latency_ms=latency_ms,
                row_count=len(result),
                notes="read-only tool executed through policy gateway",
            )
        )
        return result

    def search_documents(self, role: str, service_name: str, query: str) -> list[Evidence]:
        def action() -> list[Evidence]:
            # Prefer Azure Search when configured
            if self._use_azure_search():
                return azure_search_documents(service_name, query)

            # Next prefer a local vector index if available
            try:
                local_hits = local_search_documents(service_name, query)
                if local_hits:
                    return local_hits
            except Exception:
                pass

            # Fallback to simple JSON keyword search (demo mode)
            docs = load_json("documents.json")
            hits = []
            query_text = f"{service_name} {query}".lower()
            for item in docs:
                haystack = f"{item['title']} {item['content']} {item['service_name']}".lower()
                if service_name.lower() in haystack or any(term in haystack for term in query_text.split()):
                    hits.append(
                        Evidence(
                            source="rag_documents",
                            timestamp=item.get("created_at"),
                            finding=mask_sensitive_text(item["content"]),
                            confidence="medium",
                            raw_ref=f"doc://{item['doc_id']}",
                        )
                    )
            return hits[:5]

        return self._run(role, "search_documents", action)

    def query_postgres_logs(self, role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
        validate_time_window(start_time, end_time)

        def action() -> list[Evidence]:
            if self._use_live_postgres():
                return query_postgres_logs_live(role, service_name, start_time, end_time)

            rows = load_json("postgres_logs.json")
            matches = [
                row for row in rows
                if row["service_name"] == service_name and start_time <= row["timestamp"] <= end_time
            ]
            return [
                Evidence(
                    source="postgres_logs",
                    timestamp=row["timestamp"],
                    finding=mask_sensitive_text(row["message"]),
                    confidence="high" if row["level"] == "ERROR" else "medium",
                    raw_ref=f"postgres://logs/{row['log_id']}",
                )
                for row in matches[:20]
            ]

        return self._run(role, "query_postgres_logs", action)

    def query_vertica_metrics(self, role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
        validate_time_window(start_time, end_time)

        def action() -> list[Evidence]:
            if self._use_live_vertica():
                return query_vertica_metrics_live(role, service_name, start_time, end_time)

            rows = load_json("vertica_metrics.json")
            matches = [
                row for row in rows
                if row["service_name"] == service_name and start_time <= row["timestamp"] <= end_time
            ]
            return [
                Evidence(
                    source="vertica_metrics",
                    timestamp=row["timestamp"],
                    finding=(
                        f"active_sessions={row['active_sessions']}, "
                        f"max_sessions={row['max_sessions']}, "
                        f"p95_query_latency_ms={row['p95_query_latency_ms']}"
                    ),
                    confidence="high" if row["active_sessions"] >= row["max_sessions"] else "medium",
                    raw_ref=f"vertica://metrics/{row['metric_id']}",
                )
                for row in matches[:20]
            ]

        return self._run(role, "query_vertica_metrics", action)

    def check_etl_job_status(self, role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
        validate_time_window(start_time, end_time)

        def action() -> list[Evidence]:
            if self._use_live_etl():
                return check_etl_job_status_live(role, service_name, start_time, end_time)

            rows = load_json("etl_jobs.json")
            matches = [
                row for row in rows
                if row["service_name"] == service_name and start_time <= row["started_at"] <= end_time
            ]
            return [
                Evidence(
                    source="etl_job_status",
                    timestamp=row["started_at"],
                    finding=f"job={row['job_name']}, status={row['status']}, failure_reason={row['failure_reason']}",
                    confidence="high" if row["status"] == "FAILED" else "medium",
                    raw_ref=f"etl://jobs/{row['job_id']}",
                )
                for row in matches[:20]
            ]

        return self._run(role, "check_etl_job_status", action)

    def query_warehouse_events(self, role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
        validate_time_window(start_time, end_time)

        def action() -> list[Evidence]:
            if self._use_live_warehouse():
                return query_warehouse_events_live(role, service_name, start_time, end_time)

            rows = load_json("warehouse_events.json")
            matches = [
                row for row in rows
                if row["service_name"] == service_name and start_time <= row["timestamp"] <= end_time
            ]
            return [
                Evidence(
                    source="warehouse_events",
                    timestamp=row["timestamp"],
                    finding=row["event"],
                    confidence=row["confidence"],
                    raw_ref=f"warehouse://events/{row['event_id']}",
                )
                for row in matches[:20]
            ]

        return self._run(role, "query_warehouse_events", action)

    def query_storage_array_metrics(
        self, role: str, service_name: str, query: str, start_time: str, end_time: str
    ) -> list[Evidence]:
        validate_time_window(start_time, end_time)

        def action() -> list[Evidence]:
            if self._use_live_storage_array():
                return query_storage_array_metrics_live(role, service_name, query, start_time, end_time)

            rows = load_json("storage_array_metrics.json")
            array_id = _extract_array_id(query)
            matches = [
                row for row in rows
                if row["service_name"] == service_name
                and start_time <= row["timestamp"] <= end_time
                and (array_id is None or str(row["array_id"]) == array_id)
            ]
            return [
                Evidence(
                    source="storage_array_metrics",
                    timestamp=row["timestamp"],
                    finding=(
                        f"array_id={row['array_id']}, colo={row['colo']}, "
                        f"capacity_used_pct={row['capacity_used_pct']}, "
                        f"capacity_spike_pct={row['capacity_spike_pct']}, "
                        f"write_latency_ms={row['write_latency_ms']}"
                    ),
                    confidence="high" if row["capacity_spike_pct"] >= 70 else "medium",
                    raw_ref=f"array://metrics/{row['metric_id']}",
                )
                for row in matches[:20]
            ]

        return self._run(role, "query_storage_array_metrics", action)

    def query_bundle_events(
        self, role: str, service_name: str, query: str, start_time: str, end_time: str
    ) -> list[Evidence]:
        validate_time_window(start_time, end_time)

        def action() -> list[Evidence]:
            if self._use_live_bundle_events():
                return query_bundle_events_live(role, service_name, query, start_time, end_time)

            rows = load_json("bundle_events.json")
            array_id = _extract_array_id(query)
            matches = [
                row for row in rows
                if row["service_name"] == service_name
                and start_time <= row["timestamp"] <= end_time
                and (array_id is None or str(row["array_id"]) == array_id)
            ]
            return [
                Evidence(
                    source="bundle_events",
                    timestamp=row["timestamp"],
                    finding=(
                        f"array_id={row['array_id']}, colo={row['colo']}, "
                        f"bundle_id={row['bundle_id']}, status={row['status']}, "
                        f"message={row['message']}"
                    ),
                    confidence="high" if row["status"] in {"NOT_RECEIVED", "NOT_UPDATED"} else "medium",
                    raw_ref=f"bundle://events/{row['event_id']}",
                )
                for row in matches[:20]
            ]

        return self._run(role, "query_bundle_events", action)

    def get_change_events(self, role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
        validate_time_window(start_time, end_time)

        def action() -> list[Evidence]:
            if self._use_live_change_events():
                return get_change_events_live(role, service_name, start_time, end_time)

            rows = load_json("change_events.json")
            matches = [
                row for row in rows
                if row["service_name"] == service_name and start_time <= row["timestamp"] <= end_time
            ]
            return [
                Evidence(
                    source="change_events",
                    timestamp=row["timestamp"],
                    finding=row["description"],
                    confidence=row["confidence"],
                    raw_ref=f"change://events/{row['change_id']}",
                )
                for row in matches[:20]
            ]

        return self._run(role, "get_change_events", action)

    def save_checkpoint(self, role: str, incident_id: str, evidence: list[Evidence]) -> str:
        def action() -> list[Evidence]:
            return evidence

        self._run(role, "save_checkpoint", action)
        return f"cp-{incident_id}-{uuid.uuid4().hex[:8]}"


def _extract_array_id(query: str) -> Optional[str]:
    match = re.search(r"(?:array\s*(?:id)?\s*|array_id\s*=?\s*)(\d+)", query.lower())
    return match.group(1) if match else None
