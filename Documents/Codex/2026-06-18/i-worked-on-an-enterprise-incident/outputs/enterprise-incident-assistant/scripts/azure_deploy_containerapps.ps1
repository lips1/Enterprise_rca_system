<#
Deploy container to Azure Container Apps using existing resources.

Prerequisites:
- Run `.	emplates\azure_deploy.ps1` (creates RG, ACR, Key Vault, managed identity, and service principal).
- GitHub Actions or local push must have pushed image to ACR with tag `latest`.

Usage:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
  .\scripts\azure_deploy_containerapps.ps1
#>

param(
    [string]$SubscriptionId = 'a5760e0c-7f48-4a8b-b9f3-f66b358df0b0',
    [string]$ResourceGroup = 'rg-incident',
    [string]$Location = 'eastus',
    [string]$EnvironmentName = 'env-incident',
    [string]$ContainerAppName = 'incident-app',
    [string]$AcrName = 'incidentacr',
    [string]$ImageTag = 'latest',
    [string]$ManagedIdentityName = 'mi-incident'
)

Write-Host "Setting subscription to $SubscriptionId"
az account set --subscription $SubscriptionId

Write-Host "Registering providers (if required)..."
az provider register --namespace Microsoft.Web | Out-Null
az provider register --namespace Microsoft.App | Out-Null

Write-Host "Creating Container Apps environment $EnvironmentName..."
az containerapp env create -g $ResourceGroup -n $EnvironmentName -l $Location | Out-Null

$acrLogin = az acr show -g $ResourceGroup -n $AcrName --query loginServer -o tsv
if (-not $acrLogin) {
    Write-Error "Could not determine ACR login server for $AcrName. Ensure ACR exists and is fully provisioned."
    exit 1
}

$image = "$acrLogin/incident-assistant:$ImageTag"
Write-Host "Deploying image $image to Container App $ContainerAppName"

# get managed identity resource id
$miResourceId = az identity show -g $ResourceGroup -n $ManagedIdentityName --query id -o tsv
if (-not $miResourceId) {
    Write-Error "Managed identity $ManagedIdentityName not found. Run azure_deploy.ps1 first."
    exit 1
}

az containerapp create \
  -g $ResourceGroup -n $ContainerAppName \
  --environment $EnvironmentName \
  --image $image \
  --ingress external --target-port 8000 \
  --assign-identity $miResourceId \
  --registry-server $acrLogin \
  --cpu 0.5 --memory 1.0 | Out-Null

$fqdn = az containerapp show -g $ResourceGroup -n $ContainerAppName --query properties.configuration.ingress.fqdn -o tsv
Write-Host "Container App deployed. FQDN: $fqdn"
Write-Host "Access the app: https://$fqdn/"
