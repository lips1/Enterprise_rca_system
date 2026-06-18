# Interview Flow Explanation

## Short Project Introduction

I built an Enterprise Incident Investigation Assistant using Azure OpenAI. The goal was to help SRE and support teams investigate production incidents faster.

Our operational data was not fully in Azure. ETL systems, warehouse data, PostgreSQL logs, and Vertica metrics were hosted on HPE on-prem infrastructure across colo and HQ data centers. Azure hosted the GenAI application, orchestration layer, Azure OpenAI, and document search.

The model did not directly connect to production databases. Instead, the backend exposed secure read-only tools. The orchestrator decided which tool to call, collected evidence, validated it, and then used Azure OpenAI to generate the final investigation summary.

## How Many Agents?

The project has 5 agents.

| Agent | Responsibility |
|---|---|
| 1. Planner Agent | Understands user query and decides required tools |
| 2. RAG Agent | Searches runbooks, RCA documents, and SOPs |
| 3. Operations Data Agent | Calls PostgreSQL, Vertica, ETL, warehouse, and change tools |
| 4. Validation Agent | Checks if final claims are supported by evidence |
| 5. Summary Agent | Creates final timeline, root cause, confidence, and actions |

## How Many Tools?

The project has 9 tools.

| Tool | Source | Purpose |
|---|---|---|
| `search_documents` | Azure AI Search in real project | Runbook, RCA, SOP retrieval |
| `query_postgres_logs` | PostgreSQL on HPE | App and ETL log search |
| `query_vertica_metrics` | Vertica on HPE | Metrics, active sessions, latency |
| `check_etl_job_status` | ETL scheduler on HPE | Batch job status and failure reason |
| `query_warehouse_events` | HQ warehouse/on-prem | Warehouse events and load signals |
| `query_storage_array_metrics` | HPE storage arrays | Capacity spike and array latency |
| `query_bundle_events` | HPE colo ingestion | Bundle received / not received / not updated events |
| `get_change_events` | Change system | Deployment/config changes |
| `save_checkpoint` | Memory/checkpoint store | Save investigation progress |

## Full Runtime Flow

Example user query:

```text
Why did the billing ETL fail last night?
```

### Step 1: User Sends Query

The request comes from web app, Teams bot, or incident portal.

```json
{
  "user_id": "sre_user_01",
  "role": "SRE",
  "incident_id": "INC12345",
  "service_name": "billing-etl",
  "query": "Why did the billing ETL fail last night?",
  "start_time": "2026-06-17T00:00:00",
  "end_time": "2026-06-17T06:00:00"
}
```

### Step 2: RBAC and Security Check

Before any tool runs, the tool gateway checks the user's role.

Example:

| Role | Allowed |
|---|---|
| L1 Support | Documents only |
| SRE | Documents, logs, metrics, ETL, warehouse |
| DBA | Documents, Vertica, warehouse |
| Incident Commander | All investigation tools |

If a user is not allowed to see PostgreSQL logs, `query_postgres_logs` is blocked.

### Step 3: Planner Agent Selects Tools

The Planner Agent reads the query and selects tools.

For `Why did billing ETL fail last night?`, it selects:

```text
search_documents
check_etl_job_status
query_postgres_logs
query_vertica_metrics
query_warehouse_events
get_change_events
save_checkpoint
```

### Step 4: Tool Gateway Executes Read-Only Tools

Each tool call goes through policy checks:

```text
RBAC check
read-only check
time-window check
row-limit check
timeout check
sensitive data masking
audit logging
```

In the real project, this gateway connects privately to HPE on-prem systems through ExpressRoute or VPN.

```text
Azure Orchestrator
  -> Private network
  -> HPE MCP/Tool Gateway
  -> PostgreSQL / Vertica / ETL / warehouse
```

### Step 5: Tools Return Evidence

PostgreSQL logs may return:

```text
01:42 - Billing ETL failed during warehouse load step: connection timeout.
```

Vertica metrics may return:

```text
01:40 - active_sessions=100, max_sessions=100, p95_query_latency_ms=8900
```

ETL status may return:

```text
billing-nightly-load failed due to repeated warehouse connection timeout errors.
```

RAG may return:

```text
Previous RCA says billing ETL can fail when warehouse active sessions reach maximum.
```

### Step 6: Evidence Is Normalized

The system converts all tool outputs into a common evidence format:

```json
{
  "source": "postgres_logs",
  "timestamp": "2026-06-17T01:42:00",
  "finding": "Billing ETL failed during warehouse load step: connection timeout.",
  "confidence": "high",
  "raw_ref": "postgres://logs/pg-1002"
}
```

### Step 7: Merge and Timeline Creation

The Summary Agent builds a timeline:

```text
01:35 - Vertica query latency increased
01:40 - Vertica active sessions reached max limit
01:42 - Billing ETL failed with connection timeout
01:45 - Retry attempt failed
02:10 - Warehouse sessions normalized
```

### Step 8: Validation Agent Checks Correctness

The Validation Agent checks:

```text
Is the failure time supported by logs?
Is the database saturation supported by metrics?
Is the root-cause hypothesis supported by more than one source?
Is there conflicting change/deployment evidence?
Are unsupported claims removed?
```

Example:

| Claim | Evidence | Result |
|---|---|---|
| ETL failed at 01:42 | PostgreSQL logs | Supported |
| Warehouse sessions were maxed | Vertica metrics | Supported |
| Connection/session exhaustion caused failure | Logs + metrics + RCA | Probable |
| Deployment caused failure | No evidence | Not included |

### Step 9: Azure OpenAI Generates Final Summary

Only filtered evidence is passed to Azure OpenAI.

The model receives:

```text
user query
incident metadata
retrieved runbook/RCA evidence
PostgreSQL log summary
Vertica metric summary
ETL job status
warehouse events
validation result
```

Final response contains:

```text
incident summary
timeline
probable root cause
confidence
evidence
recommended actions
```

## Security Explanation

Important interview line:

The model never directly accessed PostgreSQL, Vertica, or warehouse systems. All access happened through secure backend tools. Those tools were read-only, RBAC-controlled, masked sensitive fields, enforced row limits and timeouts, and logged every call for audit.

Security controls:

```text
Microsoft Entra ID authentication
role-based access control
managed identity
Azure Key Vault
private endpoint / VPN / ExpressRoute
read-only DB users
SQL validation
row limits
query timeout
PII and secret masking
audit logs
```

## Observability Explanation

We measured the complete request path.

Metrics:

```text
total_request_latency
planner_latency
rag_search_latency
postgres_query_latency
vertica_query_latency
etl_tool_latency
warehouse_tool_latency
openai_generation_latency
validation_latency
tool_failure_rate
timeout_count
evidence_count
grounded_answer_score
token_count
cost_per_request
```

In production, these are sent to:

```text
Azure Monitor
Application Insights
Log Analytics
OpenTelemetry traces
```

## Latency Explanation

To reduce latency:

```text
Run independent tools in parallel
Use time filters
Use row limits
Cache common runbook/RCA search results
Use small model for planning
Use stronger model only for final RCA summary
Stream final response
Run deep RCA as background async job
```

## Final Interview Answer

You can say:

I used 5 agents and 7 tools. The Planner Agent first understood the user query and selected the required tools. For an ETL failure, it selected document search, ETL status, PostgreSQL logs, Vertica metrics, warehouse events, and change events. Every tool call went through a secure tool gateway with RBAC, read-only access, row limits, timeouts, masking, and audit logging. The tools retrieved filtered evidence from HPE on-prem systems through private connectivity. The evidence was normalized, merged into a timeline, and validated. Only after validation did Azure OpenAI generate the final summary with probable root cause, confidence, evidence, and next actions.
