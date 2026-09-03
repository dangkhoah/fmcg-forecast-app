chcp 65001 | Out-Null
Write-Host "=== FMCG Sales Forecast App (Jobs Stream) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔄 Starting services as background jobs..." -ForegroundColor Yellow

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$LogFile = Join-Path $root "app_services.log"
Write-Host "Logging all output to: $LogFile" -ForegroundColor Yellow

# Start Model Service (port 8001)
$modelJob = Start-Job -Name "proc1" -ScriptBlock {
    param($path)
    chcp 65001 | Out-Null
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    $OutputEncoding = [System.Text.UTF8Encoding]::new()

    Set-Location $path
    & ".\.venv\Scripts\python.exe" -X utf8 -u -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --reload-dir app --reload-exclude="__pycache__/*" --log-config logging.ini 2>&1
} -ArgumentList "$root\model-service"
Write-Host "[1/2] Model Service job started (proc1)" -ForegroundColor Green

# Start Backend (port 8000)
$backendJob = Start-Job -Name "proc2" -ScriptBlock {
    param($path)
    chcp 65001 | Out-Null
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    $OutputEncoding = [System.Text.UTF8Encoding]::new()

    Set-Location $path
    & ".\.venv\Scripts\python.exe" -X utf8 -u -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-exclude="uploads/*" --log-config logging.ini 2>&1
} -ArgumentList "$root\backend"
Write-Host "[2/2] Backend Service job started (proc2)" -ForegroundColor Green

Write-Host ""
Write-Host "Streaming job output to this terminal. Press Ctrl+C to stop." -ForegroundColor Cyan

try {
    while ($true) {
        $activeJobs = Get-Job -Name "proc1", "proc2" -ErrorAction SilentlyContinue
        if (-not $activeJobs) { break }

        $anyJobHasMoreData = $false
        foreach ($job in $activeJobs) {
            $results = Receive-Job -Job $job -Keep -ErrorAction SilentlyContinue 2>&1
            if ($null -ne $results) {
                foreach ($line in $results) {
                    if ($null -ne $line) {
                        $color = if ($job.Name -eq "proc1") { "Yellow" } else { "Cyan" }
                        $lineStr = [string]$line
                        if ($lineStr -match "^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ") {
                            $formattedLine = $lineStr
                        } else {
                            $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                            $formattedLine = "[$timestamp] [$($job.Name)] $lineStr"
                        }
                        Write-Host $formattedLine -ForegroundColor $color
                        $formattedLine | Out-File -FilePath $LogFile -Append -Encoding utf8
                        $anyJobHasMoreData = $true
                    }
                }
            }
        }

        # Break loop if no jobs are running and no more data is available from any job
        $runningJobs = $activeJobs | Where-Object { $_.State -match 'Running|Scheduled|Blocked' }
        if (-not $runningJobs -and -not $anyJobHasMoreData) { break }

        Start-Sleep -Milliseconds 200
    }
}
finally {
    Write-Host "`nStopping services..." -ForegroundColor Red
    Stop-Job $modelJob, $backendJob -ErrorAction SilentlyContinue
    Remove-Job $modelJob, $backendJob -ErrorAction SilentlyContinue
    Get-Job -Name "proc1", "proc2" -ErrorAction SilentlyContinue | Stop-Job -Force -ErrorAction SilentlyContinue
    Get-Job -Name "proc1", "proc2" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
    Write-Host "All services stopped. Exiting." -ForegroundColor Red
}
