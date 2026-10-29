<#
.SYNOPSIS
Starts the Intelligent Agent Desktop App

.DESCRIPTION
This script will activate the virtual environment (if it exists) and run the main entry point to start the AI Desktop Assistant UI.
#>

$env:PYTHONPATH = $PSScriptRoot

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "No local 'venv' found. Using global python..." -ForegroundColor Yellow
}

Write-Host "Starting the Artificial Intelligence Desktop Agent..." -ForegroundColor Cyan
python main.py
