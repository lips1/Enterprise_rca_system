# Incident Assistant — Local RAG demo

This repository contains a small RAG demo for incident investigation. Key files and folders:

- `app/` — application code (ingest, embeddings, vector store, API)
- `data/` — sample data used for local demos
- `scripts/azure_deploy.ps1` — creates RG, ACR, KeyVault, MI and prints SP JSON
- `.github/workflows/build-and-push-acr.yml` — GitHub Actions workflow to build and push container to ACR

Quick start (local):

1. Create and activate a Python virtualenv.
2. Install dependencies: `pip install -r requirements.txt`.
3. Build local index and run a sample query:
   `python -m app.ingest && python scripts/run_sample_query.py`
4. Run the API locally:
   `uvicorn app.main:app --reload --port 8000`

Deployment (Azure):

1. Run `.\scripts\azure_deploy.ps1` after `az login` to create Azure resources and print service principal JSON.
2. Add `AZURE_CREDENTIALS` and `ACR_LOGIN_SERVER` secrets to GitHub repository.
3. Push to `main` to trigger the build-and-push workflow.

See `scripts/` for helper scripts and `app/` for implementation details.
# Enterprise Incident Investigation Assistant

This is a VS Code-ready demo project for explaining a production-style GenAI incident investigation assistant.

The project simulates an enterprise hybrid setup:

- Azure hosts the GenAI application and orchestration layer.
- HPE on-prem / colo / HQ systems hold ETL logs, PostgreSQL logs, Vertica metrics, and warehouse signals.
- Azure OpenAI is used for reasoning and final summarization.
- Azure AI Search is represented by a local dummy RAG search over runbooks and RCA documents.
- MCP/tool gateway behavior is represented by controlled backend tools.

## Agents

This demo uses 5 clear agents:

| Agent | Purpose |
|---|---|
| Planner Agent | Understands the user query and decides which tools are needed |
| RAG Agent | Searches runbooks, SOPs, and RCA documents |
| Operations Data Agent | Calls PostgreSQL, Vertica, ETL, and warehouse tools |
| Validation Agent | Checks if the answer is supported by evidence |
| Summary Agent | Generates the final incident summary |

## Tools

This demo uses 9 tools:

| Tool | Purpose |
|---|---|
| `search_documents` | Searches dummy runbooks and RCA documents |
| `query_postgres_logs` | Searches dummy app and ETL logs |
| `query_vertica_metrics` | Searches dummy Vertica metrics |
| `check_etl_job_status` | Checks dummy ETL job status |
| `query_warehouse_events` | Searches dummy warehouse events |
| `query_storage_array_metrics` | Checks dummy HPE storage array capacity and latency |
| `query_bundle_events` | Checks dummy colo bundle receive/update events |
| `get_change_events` | Checks dummy deployment/config changes |
| `save_checkpoint` | Saves investigation state |

## Flow

```text
User query
  -> Auth and RBAC check
  -> Planner Agent
  -> Tool selection
  -> Tool Gateway policy checks
  -> RAG / PostgreSQL / Vertica / ETL / warehouse tools
  -> Evidence normalization
  -> Timeline and hypothesis creation
  -> Validation Agent
  -> Summary Agent
  -> Final grounded answer
```

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

API docs:

```text
http://127.0.0.1:8000/docs
```

Try this request in `POST /investigate`:

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

## Interview Explanation

When the user asks a question, the request first goes through authentication and RBAC. The Planner Agent identifies that this is an incident investigation for `billing-etl`, so it selects the RAG tool, PostgreSQL log tool, Vertica metrics tool, ETL status tool, warehouse event tool, and change event tool.

Before each tool runs, the tool gateway checks role permissions, time-window limits, row limits, and read-only access. The tools simulate private access to HPE on-prem systems. The results are normalized into evidence objects, merged into a timeline, and passed to the Validation Agent.

The Validation Agent checks whether the probable root cause is supported by multiple sources. The Summary Agent then generates a final response with timeline, evidence, probable root cause, confidence score, next actions, and observability metrics.

For production-level details, read:

```text
PRODUCTION_LEVEL_DESIGN.md
```

## Azure Deployment

For a real Azure deployment:

1. Create Azure OpenAI / Microsoft Foundry project.
2. Create Azure AI Search and index runbooks, RCA documents, SOPs, and incident reports.
3. Deploy this FastAPI app to Azure Container Apps, App Service, or AKS.
4. Put Azure API Management in front of the app.
5. Use Microsoft Entra ID for authentication.
6. Use Managed Identity from the app to Azure services.
7. Store secrets in Azure Key Vault.
8. Connect Azure to HPE colo/HQ through ExpressRoute or site-to-site VPN.
9. Deploy real MCP/tool gateway services inside the HPE network.
10. Replace dummy JSON tools with real read-only connectors for PostgreSQL, Vertica, ETL, and warehouse.
11. Configure the sample `.env` file to enable Azure AI Search and live on-prem connector endpoints.
12. Send logs, traces, latency, and tool metrics to Azure Monitor and Application Insights.
