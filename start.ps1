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
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --log-config logging.ini
} -ArgumentList "$root\model-service"
Write-Host "[1/2] Model Service background job started (Port 8001)" -ForegroundColor Green

# Start Backend (port 8000)
$backendJob = Start-Job -Name "Backend" -ScriptBlock {
    param($path)
    Set-Location $path
    & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-config logging.ini
} -ArgumentList "$root\backend"
Write-Host "[2/2] Backend API background job started (Port 8000)" -ForegroundColor Green

Write-Host ""
Write-Host "Frontend (separate terminal):" -ForegroundColor Yellow
Write-Host "  cd frontend; npm start | Select-String -Pattern 'Compiled successfully','You can now view','Local:','On Your Network:' -NotMatch | Tee-Object -FilePath 'frontend_dev.log'" -ForegroundColor White
Write-Host "  cd frontend && `$env:BROWSER='none'; npm start | Select-String -Pattern 'Compiled successfully','You can now view','Local:','On Your Network:' -NotMatch | Tee-Object -FilePath 'frontend_dev.log'" -ForegroundColor White
Write-Host ""
Write-Host "Streaming logs to this terminal and $LogFile..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor White

try {
    # Initialize/Clear log file
    $null | Out-File -FilePath $LogFile -Encoding utf8

    $jobs = @($modelJob, $backendJob)
    while ($jobs | Where-Object { $_.State -eq 'Running' }) {
        foreach ($job in $jobs) {
            # Non-blocking receive of available log lines
            $results = Receive-Job -Job $job
            foreach ($line in $results) {
                if ($line) {
                    $color = if ($job.Name -eq "ModelService") { "Yellow" } else { "Cyan" }
                    $formattedLine = $line
                    
                    # Check if the line already starts with a timestamp (from Uvicorn's logging.ini)
                    if ($line -notmatch "^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ") {
                        $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                        $formattedLine = "[$timestamp] [$($job.Name)] $line"
                    } else {
                        $formattedLine = "[$($job.Name)] $line" # Just add the job name if Uvicorn already timestamped
                    }
                    
                    Write-Host $formattedLine -ForegroundColor $color
                    $formattedLine | Out-File -FilePath $LogFile -Append -Encoding utf8
                }
            }
        }
        Start-Sleep -Milliseconds 200
    }
}
finally {
    Write-Host "`nStopping services..." -ForegroundColor Red
    Stop-Job $modelJob, $backendJob
    Remove-Job $modelJob, $backendJob
    Write-Host "All jobs terminated."
}
