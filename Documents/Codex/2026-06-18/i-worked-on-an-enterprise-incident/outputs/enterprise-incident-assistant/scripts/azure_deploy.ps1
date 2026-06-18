<#
Automated Azure provisioning script (PowerShell).

What it does:
- Creates resource group `rg-incident` in `eastus`
- Creates ACR `incidentacr`
- Creates Key Vault `kv-incident`
- Creates a user-assigned managed identity `mi-incident`
- Creates a service principal scoped to the ACR with AcrPush role and prints the JSON for GitHub Actions

Usage:
  Open PowerShell, login with `az login`, then run:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
    .\azure_deploy.ps1

IMPORTANT: This script will output the service principal JSON. Save it and add to GitHub secret `AZURE_CREDENTIALS`.
#>

param(
    [string]$SubscriptionId = 'a5760e0c-7f48-4a8b-b9f3-f66b358df0b0',
    [string]$Location = 'eastus',
    [string]$ResourceGroup = 'rg-incident',
    [string]$AcrName = 'incidentacr',
    [string]$KeyVaultName = 'kv-incident',
    [string]$ManagedIdentityName = 'mi-incident'
)

Write-Host "Using subscription: $SubscriptionId"
az account set --subscription $SubscriptionId

Write-Host "Creating resource group $ResourceGroup in $Location..."
az group create --name $ResourceGroup --location $Location | Out-Null

Write-Host "Creating ACR $AcrName..."
az acr create --resource-group $ResourceGroup --name $AcrName --sku Standard --location $Location --admin-enabled false | Out-Null

$acrLogin = az acr show -g $ResourceGroup -n $AcrName --query loginServer -o tsv
Write-Host "ACR login server: $acrLogin"

Write-Host "Creating Key Vault $KeyVaultName..."
az keyvault create -g $ResourceGroup -n $KeyVaultName -l $Location | Out-Null

Write-Host "Creating user-assigned managed identity $ManagedIdentityName..."
az identity create -g $ResourceGroup -n $ManagedIdentityName | Out-Null

$miPrincipalId = az identity show -g $ResourceGroup -n $ManagedIdentityName --query principalId -o tsv
Write-Host "Managed Identity principalId: $miPrincipalId"

Write-Host "Creating service principal scoped to ACR with AcrPush role..."
$acrResourceId = az acr show -g $ResourceGroup -n $AcrName --query id -o tsv
$spJson = az ad sp create-for-rbac --name "gh-actions-acr-push" --scopes $acrResourceId --role acrpush --sdk-auth

Write-Host "Service principal JSON (copy this into GitHub secret AZURE_CREDENTIALS):"
Write-Host $spJson

Write-Host "Granting managed identity AcrPull on ACR..."
az role assignment create --assignee $miPrincipalId --scope $acrResourceId --role AcrPull | Out-Null

Write-Host "Granting managed identity access to Key Vault secrets..."
az keyvault set-policy -n $KeyVaultName --object-id $miPrincipalId --secret-permissions get list | Out-Null

Write-Host "Done. Next steps:" 
Write-Host "1) In GitHub repo, add secret AZURE_CREDENTIALS with the JSON printed above."
Write-Host "2) Add secret ACR_LOGIN_SERVER = $acrLogin"
Write-Host "3) Push to main to trigger .github/workflows/build-and-push-acr.yml"
Write-Host "4) After image exists in ACR, run the Azure Container Apps deployment commands (I can add a script for that too)."
