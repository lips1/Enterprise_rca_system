# Azure Upload and Deployment Steps

## 1. Open Project in VS Code

```bash
cd outputs/enterprise-incident-assistant
code .
```

## 2. Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 3. Test API

Open:

```text
http://127.0.0.1:8000/docs
```

Use `POST /investigate`.

## 4. Create Azure Resources

Create these resources:

- Resource Group
- Azure OpenAI / Microsoft Foundry project
- Azure AI Search
- Azure Container Apps or Azure App Service
- Azure Key Vault
- Azure API Management
- Application Insights
- Log Analytics Workspace
- Virtual Network
- Private endpoints
- ExpressRoute or site-to-site VPN to HPE colo/HQ

## 5. Containerize

Create a container image and push it to Azure Container Registry.

```bash
az acr build --registry <acr-name> --image incident-assistant:v1 .
```

## 6. Deploy to Azure Container Apps

```bash
az containerapp create ^
  --name incident-assistant ^
  --resource-group <resource-group> ^
  --environment <container-app-env> ^
  --image <acr-name>.azurecr.io/incident-assistant:v1 ^
  --target-port 8000 ^
  --ingress external
```

## 7. Production Changes

Replace dummy JSON files with real connectors and enable runtime configuration via environment variables:

- `query_postgres_logs` -> real PostgreSQL read-only connection in HPE using `POSTGRES_CONN`
- `query_vertica_metrics` -> real Vertica read-only connection in HPE using `VERTICA_CONN`
- `check_etl_job_status` -> real ETL scheduler API using `ETL_API_URL`
- `query_warehouse_events` -> real warehouse metadata table/API using `WAREHOUSE_API_URL`
- `query_storage_array_metrics` -> real storage array metrics API using `STORAGE_ARRAY_API_URL`
- `query_bundle_events` -> real bundle ingestion API using `BUNDLE_EVENTS_API_URL`
- `get_change_events` -> real change event API using `CHANGE_EVENT_API_URL`
- `search_documents` -> Azure AI Search SDK using `AZURE_SEARCH_ENDPOINT` and `AZURE_SEARCH_KEY`

Use the `.env.example` file as a starting point for Azure and on-prem runtime configuration.

## 8. Security Hardening

- Use Microsoft Entra ID authentication.
- Use Managed Identity.
- Store secrets in Key Vault.
- Disable public access where possible.
- Use private endpoints.
- Use ExpressRoute/VPN for HPE on-prem access.
- Keep SQL tools read-only.
- Add row limits and query timeout.
- Mask PII and secrets before model context.
- Audit every tool call.

## 9. Observability

Send these metrics to Application Insights:

- `total_latency_ms`
- `tool_latency_ms`
- `rag_search_latency`
- `postgres_query_latency`
- `vertica_query_latency`
- `tool_failure_rate`
- `validation_grounded`
- `evidence_count`
- `token_count`
- `cost_per_request`

