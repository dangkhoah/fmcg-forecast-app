Write-Host "=== FMCG Sales Forecast App ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$LogFile = Join-Path $root "app_services.log"
Write-Host "Logging all output to: $LogFile" -ForegroundColor Yellow

# Start Model Service (port 8001)
$modelJob = Start-Job -Name "ModelService" -ScriptBlock {
    param($path)
    Set-Location $path
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
} -ArgumentList "$root\model-service"
Write-Host "[1/2] Model Service background job started (Port 8001)" -ForegroundColor Green

# Start Backend (port 8000)
$backendJob = Start-Job -Name "Backend" -ScriptBlock {
    param($path)
    Set-Location $path
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList "$root\backend"
Write-Host "[2/2] Backend API background job started (Port 8000)" -ForegroundColor Green

Write-Host ""
Write-Host "Frontend (separate terminal):" -ForegroundColor Yellow
Write-Host "  cd fmcg-forecast-app\frontend && npm start" -ForegroundColor White
Write-Host ""
Write-Host "Streaming logs to this terminal and $LogFile..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor White

try {
    # This blocks and streams output from both jobs into the console and the file
    Receive-Job -Job @($modelJob, $backendJob) -Wait | ForEach-Object {
        "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] $_"
    } | Tee-Object -FilePath $LogFile
}
finally {
    Write-Host "`nStopping services..." -ForegroundColor Red
    Stop-Job $modelJob, $backendJob
    Remove-Job $modelJob, $backendJob
    Write-Host "All jobs terminated."
}
