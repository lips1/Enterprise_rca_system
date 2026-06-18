from __future__ import annotations

import os
from typing import Any, Callable

from app.config import (
    BUNDLE_EVENTS_API_URL,
    CHANGE_EVENT_API_URL,
    ETL_API_URL,
    POSTGRES_CONN,
    STORAGE_ARRAY_API_URL,
    VERTICA_CONN,
    WAREHOUSE_API_URL,
)
from app.models import Evidence
from app.data_loader import load_json

try:
    import psycopg2  # type: ignore
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore


def _load_demo_rows(filename: str, service_name: str, start_time: str, end_time: str, time_field: str) -> list[dict[str, Any]]:
    rows = load_json(filename)
    return [
        row
        for row in rows
        if row["service_name"] == service_name and start_time <= row[time_field] <= end_time
    ]


def query_postgres_logs_live(role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
    if not POSTGRES_CONN:
        raise RuntimeError("POSTGRES_CONN is not set for live PostgreSQL access.")
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for live PostgreSQL access.")

    with psycopg2.connect(POSTGRES_CONN, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT log_id, timestamp, level, message FROM logs WHERE service_name = %s AND timestamp BETWEEN %s AND %s ORDER BY timestamp LIMIT 100",
                (service_name, start_time, end_time),
            )
            rows = cursor.fetchall()

    return [
        Evidence(
            source="postgres_logs",
            timestamp=row[1],
            finding=str(row[3]),
            confidence="high" if row[2] == "ERROR" else "medium",
            raw_ref=f"postgres://logs/{row[0]}",
        )
        for row in rows
    ]


def query_vertica_metrics_live(role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
    if not VERTICA_CONN:
        raise RuntimeError("VERTICA_CONN is not set for live Vertica access.")
    raise RuntimeError("Live Vertica connector is not implemented. Use the JSON fallback or add a Vertica client implementation.")


def check_etl_job_status_live(role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
    if not ETL_API_URL:
        raise RuntimeError("ETL_API_URL is not set for live ETL job status access.")
    if requests is None:
        raise RuntimeError("requests is required for live ETL API access.")

    response = requests.get(
        f"{ETL_API_URL}?service_name={service_name}&start_time={start_time}&end_time={end_time}",
        timeout=10,
    )
    response.raise_for_status()

    jobs = response.json()
    return [
        Evidence(
            source="etl_job_status",
            timestamp=job.get("started_at"),
            finding=f"job={job.get('job_name')}, status={job.get('status')}, failure_reason={job.get('failure_reason')}",
            confidence="high" if job.get("status") == "FAILED" else "medium",
            raw_ref=f"etl://jobs/{job.get('job_id')}",
        )
        for job in jobs
    ]


def query_warehouse_events_live(role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
    if not WAREHOUSE_API_URL:
        raise RuntimeError("WAREHOUSE_API_URL is not set for live warehouse event access.")
    if requests is None:
        raise RuntimeError("requests is required for live warehouse API access.")

    response = requests.get(
        f"{WAREHOUSE_API_URL}?service_name={service_name}&start_time={start_time}&end_time={end_time}",
        timeout=10,
    )
    response.raise_for_status()

    events = response.json()
    return [
        Evidence(
            source="warehouse_events",
            timestamp=event.get("timestamp"),
            finding=event.get("event", ""),
            confidence=event.get("confidence", "medium"),
            raw_ref=f"warehouse://events/{event.get('event_id')}",
        )
        for event in events
    ]


def query_storage_array_metrics_live(role: str, service_name: str, query: str, start_time: str, end_time: str) -> list[Evidence]:
    if not STORAGE_ARRAY_API_URL:
        raise RuntimeError("STORAGE_ARRAY_API_URL is not set for live storage array access.")
    if requests is None:
        raise RuntimeError("requests is required for live storage array API access.")

    response = requests.get(
        f"{STORAGE_ARRAY_API_URL}?service_name={service_name}&start_time={start_time}&end_time={end_time}&query={query}",
        timeout=10,
    )
    response.raise_for_status()

    metrics = response.json()
    return [
        Evidence(
            source="storage_array_metrics",
            timestamp=metric.get("timestamp"),
            finding=(
                f"array_id={metric.get('array_id')}, colo={metric.get('colo')}, "
                f"capacity_used_pct={metric.get('capacity_used_pct')}, "
                f"capacity_spike_pct={metric.get('capacity_spike_pct')}, "
                f"write_latency_ms={metric.get('write_latency_ms')}"
            ),
            confidence="high" if metric.get("capacity_spike_pct", 0) >= 70 else "medium",
            raw_ref=f"array://metrics/{metric.get('metric_id')}",
        )
        for metric in metrics
    ]


def query_bundle_events_live(role: str, service_name: str, query: str, start_time: str, end_time: str) -> list[Evidence]:
    if not BUNDLE_EVENTS_API_URL:
        raise RuntimeError("BUNDLE_EVENTS_API_URL is not set for live bundle event access.")
    if requests is None:
        raise RuntimeError("requests is required for live bundle event API access.")

    response = requests.get(
        f"{BUNDLE_EVENTS_API_URL}?service_name={service_name}&start_time={start_time}&end_time={end_time}&query={query}",
        timeout=10,
    )
    response.raise_for_status()

    events = response.json()
    return [
        Evidence(
            source="bundle_events",
            timestamp=event.get("timestamp"),
            finding=(
                f"array_id={event.get('array_id')}, colo={event.get('colo')}, "
                f"bundle_id={event.get('bundle_id')}, status={event.get('status')}, "
                f"message={event.get('message')}"
            ),
            confidence="high" if event.get("status") in {"NOT_RECEIVED", "NOT_UPDATED"} else "medium",
            raw_ref=f"bundle://events/{event.get('event_id')}",
        )
        for event in events
    ]


def get_change_events_live(role: str, service_name: str, start_time: str, end_time: str) -> list[Evidence]:
    if not CHANGE_EVENT_API_URL:
        raise RuntimeError("CHANGE_EVENT_API_URL is not set for live change event access.")
    if requests is None:
        raise RuntimeError("requests is required for live change event API access.")

    response = requests.get(
        f"{CHANGE_EVENT_API_URL}?service_name={service_name}&start_time={start_time}&end_time={end_time}",
        timeout=10,
    )
    response.raise_for_status()

    events = response.json()
    return [
        Evidence(
            source="change_events",
            timestamp=event.get("timestamp"),
            finding=event.get("description", ""),
            confidence=event.get("confidence", "medium"),
            raw_ref=f"change://events/{event.get('change_id')}",
        )
        for event in events
    ]
