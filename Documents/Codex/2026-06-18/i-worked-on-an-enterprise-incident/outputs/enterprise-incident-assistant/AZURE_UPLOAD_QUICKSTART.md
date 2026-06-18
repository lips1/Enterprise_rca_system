# Azure Upload Quickstart

This project is easiest to upload as a Docker container to **Azure Container Apps**.

## 1. Login

```powershell
az login
az account set --subscription "<your-subscription-id>"
```

## 2. Set Variables

Use globally unique names for ACR and Container App.

```powershell
$RG="rg-incident-ai-demo"
$LOC="eastus"
$ACR="incidentaidemoacr001"
$ENV="incident-ai-env"
$APP="incident-ai-assistant"
$IMAGE="incident-assistant:v1"
```

## 3. Create Resource Group

```powershell
az group create --name $RG --location $LOC
```

## 4. Create Azure Container Registry

```powershell
az acr create `
  --resource-group $RG `
  --name $ACR `
  --sku Basic `
  --admin-enabled true
```

## 5. Build and Push Image

Run this from the project root, where the `Dockerfile` exists.

```powershell
az acr build `
  --registry $ACR `
  --image $IMAGE `
  .
```

## 6. Create Container Apps Environment

```powershell
az containerapp env create `
  --name $ENV `
  --resource-group $RG `
  --location $LOC
```

## 7. Deploy Container App

```powershell
az containerapp create `
  --name $APP `
  --resource-group $RG `
  --environment $ENV `
  --image "$ACR.azurecr.io/$IMAGE" `
  --target-port 8000 `
  --ingress external `
  --registry-server "$ACR.azurecr.io" `
  --query properties.configuration.ingress.fqdn
```

The command returns a URL like:

```text
incident-ai-assistant.<random-region>.azurecontainerapps.io
```

Open:

```text
https://<returned-url>/
```

API docs:

```text
https://<returned-url>/docs
```

## 8. Update Existing Deployment

After code changes:

```powershell
az acr build --registry $ACR --image $IMAGE .

az containerapp update `
  --name $APP `
  --resource-group $RG `
  --image "$ACR.azurecr.io/$IMAGE"
```

## 9. Production Settings

For a real enterprise deployment, add these next:

```powershell
az containerapp update `
  --name $APP `
  --resource-group $RG `
  --min-replicas 1 `
  --max-replicas 5 `
  --cpu 1.0 `
  --memory 2.0Gi
```

Then configure:

- Microsoft Entra ID authentication
- Azure API Management in front of the app
- Azure Key Vault for secrets
- Managed Identity
- Application Insights / Log Analytics
- Private networking to HPE colo/HQ
- Real MCP/tool gateway for PostgreSQL, Vertica, ETL, storage array, and bundle events

## 10. Delete Demo Resources

Only run this when you want to remove the Azure demo.

```powershell
az group delete --name $RG
```

