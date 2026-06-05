# run_system.ps1 - Startup launcher for Bengaluru Gridlock Solver 2.0
Write-Host "=== Bengaluru Smart Traffic Gridlock Solver 2.0 Launcher ===" -ForegroundColor Cyan

# 1. Start FastAPI YOLOv8 Backend
Write-Host "Starting YOLOv8 FastAPI Web Backend..." -ForegroundColor Green
Start-Process python -ArgumentList "app.py" -NoNewWindow -WorkingDirectory "C:\Users\ashok\.gemini\antigravity\scratch\gridlock-solver"

# 2. Wait for FastAPI to spin up
Write-Host "Waiting for backend to initialize on http://localhost:8000..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 3. Open frontend dashboard
Write-Host "Opening Frontend Dashboard..." -ForegroundColor Green
Start-Process "C:\Users\ashok\.gemini\antigravity\scratch\gridlock-solver\index.html"

Write-Host "System started successfully! Open browser console to verify A* routing execution times." -ForegroundColor Cyan
