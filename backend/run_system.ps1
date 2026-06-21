# Determine working directory dynamically
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrEmpty($ScriptDir)) {
    $ScriptDir = $PSScriptRoot
}
if ([string]::IsNullOrEmpty($ScriptDir)) {
    $ScriptDir = Get-Location
}

# 1. Start FastAPI YOLOv8 Backend
Write-Host "Starting YOLOv8 FastAPI Web Backend..." -ForegroundColor Green
Start-Process python -ArgumentList "app.py" -NoNewWindow -WorkingDirectory $ScriptDir

# 2. Wait for FastAPI to spin up
Write-Host "Waiting for backend to initialize on http://localhost:8000..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 3. Open frontend dashboard
Write-Host "Opening Frontend Dashboard..." -ForegroundColor Green
Start-Process "http://localhost:8000/"

Write-Host "System started successfully! Open browser console to verify A* routing execution times." -ForegroundColor Cyan
