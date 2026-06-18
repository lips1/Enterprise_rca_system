<#
Windows helper script to free space, create a venv, and install core deps.
Run from project root in PowerShell as:
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
  .\scripts\setup_windows_env.ps1
#>

function Show-Drives {
    Write-Host "Available drives and free space (GB):"
    Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{Name='FreeGB';Expression={[math]::Round($_.Free/1GB,2)}}, @{Name='UsedGB';Expression={[math]::Round(($_.Used)/1GB,2)}} | Format-Table -AutoSize
}

function Purge-PipCache {
    Write-Host "Purging pip cache..."
    try {
        python -m pip cache purge 2>$null
    } catch {
        Write-Warning "pip cache purge failed: $_"
    }
}

function Clean-TempAndRecycle {
    Write-Host "Cleaning TEMP and emptying Recycle Bin (may require admin)..."
    try {
        Remove-Item -Path $env:TEMP\* -Recurse -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Warning "Failed to clear TEMP: $_"
    }
    try {
        Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Warning "Failed to clear Recycle Bin: $_"
    }
}

function Remove-BrokenVenv {
    if (Test-Path -Path ".venv") {
        Write-Host "Removing existing .venv folder..."
        try { Remove-Item -Recurse -Force .venv } catch { Write-Warning "Could not remove .venv: $_" }
    }
}

function Try-CreateVenv([string]$targetPath) {
    Write-Host "Attempting to create venv at: $targetPath"
    try {
        py -3 -m venv $targetPath 2>&1 | Write-Host
        if (Test-Path -Path (Join-Path $targetPath 'Scripts' 'Activate.ps1')) {
            Write-Host "Venv created at $targetPath"
            return $true
        } else {
            Write-Warning "Venv created but activation script not found at $targetPath\Scripts\Activate.ps1"
            return $false
        }
    } catch {
        Write-Warning "Failed to create venv at $targetPath: $_"
        return $false
    }
}

# Main
Write-Host "== Setup helper: free space, create venv, install core deps =="
Show-Drives
Purge-PipCache
Clean-TempAndRecycle
Remove-BrokenVenv

# Try create in current folder first
if (Try-CreateVenv '.venv') {
    $venvPath = '.venv'
} else {
    # try other drives with >5GB free
    $drives = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Free -gt 5GB }
    if ($drives.Count -gt 0) {
        $d = $drives[0].Name + ':'
        $alt = Join-Path $d 'envs' 'incident-assistant'
        New-Item -ItemType Directory -Path (Split-Path $alt) -Force | Out-Null
        if (Try-CreateVenv $alt) {
            $venvPath = $alt
        } else {
            Write-Error "Failed to create venv on alternative drive $d. Please free space and retry."
            exit 1
        }
    } else {
        Write-Error "No drive with >5GB free found. Please free space and retry."
        exit 1
    }
}

# Activate venv (PowerShell)
try {
    Write-Host "Activating venv: $venvPath"
    $activate = Join-Path $venvPath 'Scripts' 'Activate.ps1'
    if (Test-Path $activate) {
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
        . $activate
    } else {
        Write-Warning "Activation script not found: $activate"
    }
} catch {
    Write-Warning "Activation failed: $_"
}

# Upgrade pip and install core deps (no cache)
Write-Host "Upgrading pip and installing core dependencies (no-cache)..."
try {
    python -m pip install --upgrade pip setuptools wheel --no-cache-dir
    pip install --no-cache-dir fastapi uvicorn pydantic python-dotenv requests numpy joblib scipy scikit-learn
    Write-Host "Core dependencies installed. If you want sentence-transformers / rank-bm25 later, install separately."
} catch {
    Write-Warning "Package install failed: $_"
    Write-Host "If error was 'No space left on device', free disk space and rerun this script."
}

Write-Host "Setup script finished. To activate the venv later run:`n  . $venvPath\\Scripts\\Activate.ps1`"}