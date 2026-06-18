# Production-Level Design

## What This Project Contains Now

This is not only documentation. It now has:

- FastAPI backend
- Browser frontend dashboard
- Sync investigation API
- Async investigation API with polling
- 5 agents
- 9 tools
- Guardrail engine
- RBAC tool gateway
- Memory/checkpoint store
- Agent-level evaluation
- Token estimation
- Observability metrics
- Dummy enterprise incident data
- Dockerfile
- Azure deployment guide

## Frontend

The frontend is available at:

```text
http://127.0.0.1:8000/
```

It shows:

- Incident query form
- Sync and async run buttons
- Final summary
- Root cause
- Recommended actions
- Evidence timeline
- Agent latency and token estimates
- Tool call latency and row counts
- Guardrail pass/fail status
- Per-agent evaluation score

## Sync vs Async

### Sync Flow

Use sync when investigation is small and expected to finish quickly.

```text
POST /investigate
```

Good for:

- Simple runbook search
- One service
- Small time window
- Few tool calls

### Async Flow

Use async when investigation may take longer.

```text
POST /investigate/async
GET /jobs/{job_id}
```

Good for:

- Deep RCA
- Multiple systems
- Wider time windows
- Slow on-prem tools
- Long SQL/log queries
- More expensive model calls

Production async architecture:

```text
API
  -> Service Bus / Queue
  -> Worker pool
  -> Tool calls
  -> Memory/checkpoint store
  -> User polls or receives notification
```

For Azure production, use:

- Azure Service Bus
- Azure Container Apps jobs
- AKS workers
- Durable Functions
- Cosmos DB / PostgreSQL for job state

## Guardrails

Guardrails run at two points.

### 1. Request Guardrails

Before planning and tool calling:

- Prompt injection check
- Dangerous action check
- Time-window required check
- Role/tool authorization

### 2. Evidence Guardrails

Before final answer generation:

- Sensitive output check
- Grounding evidence check
- Secret masking
- Unsupported claim prevention

Interview line:

The model did not get unrestricted access. Guardrails checked the user request, tool permissions, retrieved evidence, and final answer context before Azure OpenAI generated the summary.

## RBAC

Role access is defined in `app/security.py`.

Example:

| Role | Access |
|---|---|
| L1_SUPPORT | Documents and checkpoints only |
| SRE | Logs, metrics, ETL, warehouse, documents |
| DBA | Vertica and warehouse diagnostics |
| INCIDENT_COMMANDER | Full incident investigation |

Every tool call goes through:

```text
authorize_tool(role, tool_name)
```

## Memory and Checkpointing

Memory stores:

- Incident ID
- Query
- Evidence count
- Evidence sources
- Checkpoint ID

In production, replace local memory with:

- Cosmos DB
- Azure Database for PostgreSQL
- Redis Enterprise
- Foundry memory if using Foundry Agent Service

Memory is used for:

- Resuming investigations
- Handoff between engineers
- Avoiding repeated work
- Audit/replay
- Long-running async RCA

## Token Management

This demo estimates tokens for every agent span.

Tracked fields:

```text
estimated_input_tokens
estimated_output_tokens
estimated_total_tokens
```

Production token strategy:

- Keep raw logs out of model context
- Summarize tool results before model call
- Pass only top evidence
- Use small model for planning/classification
- Use stronger model for final RCA
- Apply max context budget per incident
- Drop duplicate evidence
- Use citations instead of full raw payload

Example budget:

| Step | Model | Budget |
|---|---|---|
| Planning | Small model | 500-1,000 tokens |
| Tool result compression | Small model or code summarizer | 2,000 tokens |
| Final RCA | Strong model | 4,000-8,000 tokens |

## Observability

The project tracks:

- Total request latency
- Tool latency
- Agent latency
- Estimated token usage
- Evidence count
- Grounded answer status
- Selected tools
- Guardrail decisions
- Agent evaluation scores

Endpoints:

```text
GET /observability
```

Production tools:

- Azure Monitor
- Application Insights
- Log Analytics
- OpenTelemetry
- Distributed tracing with trace ID per incident

Trace shape:

```text
incident_id
request_id
user_id
planner_span
rag_span
tool_call_spans
validation_span
summary_span
model_request_id
checkpoint_id
```

## Latency Measurement

Latency is measured at:

- API level
- Agent level
- Tool level
- End-to-end request level

Production latency targets:

| Flow | Target |
|---|---|
| Simple document Q&A | 2-5 sec |
| Single service incident | 8-20 sec |
| Multi-source RCA | 30-90 sec |
| Deep async investigation | 2-5 min |

Latency reduction:

- Run independent tools in parallel
- Use async jobs for long RCA
- Add row limits and time filters
- Cache runbook/RCA retrieval
- Cache previous incident summaries
- Use query summaries instead of raw logs
- Circuit-break slow on-prem tools
- Use model routing

## Scaling

Production scale pattern:

```text
Frontend
  -> API Management
  -> FastAPI Orchestrator on Container Apps / AKS
  -> Service Bus for async jobs
  -> Worker pool
  -> MCP/tool gateway near HPE data
  -> PostgreSQL / Vertica / ETL / warehouse
```

Scale each layer independently:

- API scales on HTTP requests
- Workers scale on queue depth
- Tool gateway scales inside HPE network
- Azure AI Search scales on replicas/partitions
- Azure OpenAI scales by deployment quota and regional capacity

## Agent Evaluation

Each agent gets its own evaluation.

| Agent | Evaluation |
|---|---|
| Planner Agent | Did it select required tools? |
| RAG Agent | Did it retrieve relevant docs? |
| Operations Data Agent | Did it collect logs, metrics, and ETL evidence? |
| Validation Agent | Did it verify claims against evidence? |
| Summary Agent | Did it produce timeline, root cause, and actions? |

Endpoint:

```text
POST /eval/run
```

Production eval should include:

- Golden incident scenarios
- Expected evidence sources
- Expected root cause
- Retrieval precision/recall
- Tool correctness
- Groundedness
- Hallucination checks
- Human SRE review score

## Upload to Azure

Use the existing `Dockerfile`.

High-level:

```text
az acr build --registry <acr-name> --image incident-assistant:v1 .
az containerapp create --name incident-assistant ...
```

Real production replacements:

- Local document search -> Azure AI Search
- JSON PostgreSQL logs -> HPE PostgreSQL connector
- JSON Vertica metrics -> HPE Vertica connector
- In-memory jobs -> Azure Service Bus + Cosmos DB/PostgreSQL
- In-memory metrics -> App Insights/OpenTelemetry
- Local frontend -> Azure App Service/Static Web Apps or same FastAPI container
