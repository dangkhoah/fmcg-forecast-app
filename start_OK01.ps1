Write-Host "=== FMCG Sales Forecast App ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start Model Service (port 8001)
$modelJob = Start-Job -ScriptBlock {
    Set-Location $using:root\model-service
    .\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
}
Write-Host "[1/2] Model Service starting on http://localhost:8001" -ForegroundColor Green

# Start Backend (port 8000)
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:root\backend
    .\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}
Write-Host "[2/2] Backend API starting on http://localhost:8000" -ForegroundColor Green

Write-Host ""
Write-Host "Frontend (separate terminal):" -ForegroundColor Yellow
Write-Host "  cd fmcg-forecast-app\frontend && npm start" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to stop all services..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Stop-Job $modelJob
Stop-Job $backendJob
Remove-Job $modelJob
Remove-Job $backendJob
Write-Host "Services stopped." -ForegroundColor Red
