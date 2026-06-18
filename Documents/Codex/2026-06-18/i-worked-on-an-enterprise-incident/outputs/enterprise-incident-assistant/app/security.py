ROLE_TOOL_ACCESS = {
    "L1_SUPPORT": {"search_documents", "save_checkpoint"},
    "SRE": {
        "search_documents",
        "query_postgres_logs",
        "query_vertica_metrics",
        "check_etl_job_status",
        "query_warehouse_events",
        "query_storage_array_metrics",
        "query_bundle_events",
        "get_change_events",
        "save_checkpoint",
    },
    "DBA": {
        "search_documents",
        "query_vertica_metrics",
        "query_warehouse_events",
        "query_storage_array_metrics",
        "query_bundle_events",
        "save_checkpoint",
    },
    "INCIDENT_COMMANDER": {
        "search_documents",
        "query_postgres_logs",
        "query_vertica_metrics",
        "check_etl_job_status",
        "query_warehouse_events",
        "query_storage_array_metrics",
        "query_bundle_events",
        "get_change_events",
        "save_checkpoint",
    },
}


def authorize_tool(role: str, tool_name: str) -> None:
    allowed_tools = ROLE_TOOL_ACCESS.get(role.upper(), set())
    if tool_name not in allowed_tools:
        raise PermissionError(f"Role {role} is not allowed to call tool {tool_name}")


def validate_time_window(start_time: str, end_time: str) -> None:
    if not start_time or not end_time:
        raise ValueError("start_time and end_time are required")


def mask_sensitive_text(value: str) -> str:
    blocked_tokens = ["password", "secret", "token", "apikey", "api_key"]
    sanitized = value
    for token in blocked_tokens:
        sanitized = sanitized.replace(token, "[MASKED]")
        sanitized = sanitized.replace(token.upper(), "[MASKED]")
    return sanitized
