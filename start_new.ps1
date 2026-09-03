[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

Write-Host "=== FMCG Sales Forecast App ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔄 Starting services..." -ForegroundColor Yellow

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Install/update dependencies inside virtual environments
<# Write-Host "📦 Checking and updating virtual environment dependencies..." -ForegroundColor Yellow
& "$root\backend\.venv\Scripts\pip.exe" install -q -r "$root\backend\requirements.txt" -r "$root\backend\requirements-dev.txt"
& "$root\model-service\.venv\Scripts\pip.exe" install -q -r "$root\model-service\requirements.txt" -r "$root\model-service\requirements-dev.txt"
Write-Host "✅ Dependencies verified." -ForegroundColor Green #>

$LogFile = Join-Path $root "app_services.log"
Write-Host "Logging all output to: $LogFile" -ForegroundColor Yellow

# Start Model Service (port 8001)
$modelJob = Start-Job -Name "Model-Service" -ScriptBlock {
	
    param($path)
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    $OutputEncoding = [System.Text.UTF8Encoding]::new()
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
    
    Set-Location $path
    & .\.venv\Scripts\python.exe -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --reload-dir app --reload-exclude=__pycache__/* --log-config logging.ini 2>&1 | ForEach-Object { $_ }
} -ArgumentList "$root\model-service"
Write-Host "[1/2] Model Service background job started (Port 8001)" -ForegroundColor Green

# Start Backend (port 8000)
$backendJob = Start-Job -Name "Backend" -ScriptBlock {
    param($path)
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
    $OutputEncoding = [System.Text.UTF8Encoding]::new()
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
    Set-Location $path
    & .\.venv\Scripts\python.exe -X utf8 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app --reload-exclude=uploads/* --log-config logging.ini 2>&1 | ForEach-Object { $_ }
} -ArgumentList "$root\backend"
Write-Host "[2/2] Backend API background job started (Port 8000)" -ForegroundColor Green

Write-Host ""
Write-Host "Frontend (separate terminal):" -ForegroundColor Yellow
Write-Host "  cd frontend && npm start" -ForegroundColor White
Write-Host ""
Write-Host "Streaming logs to this terminal and $LogFile..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor White

try {
    # Initialize/Clear log file
    # $null | Out-File -FilePath $LogFile -Encoding utf8

    Write-Host "--- Log Stream Active ---" -ForegroundColor Gray

    while ($true) {
        $activeJobs = Get-Job -Name "Model-Service", "Backend" -ErrorAction SilentlyContinue
        if (-not $activeJobs) { break } # All jobs are gone

        $anyJobHasMoreData = $false
        foreach ($job in $activeJobs) {
            $results = Receive-Job -Job $job -ErrorAction SilentlyContinue 2>&1 | ForEach-Object {
                if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { [string]$_ }
            }
            if ($null -ne $results) {
                $anyJobHasMoreData = $true
                foreach ($line in $results) {
                    if ($null -ne $line) {
                        $color = if ($job.Name -eq "Model-Service") { "Yellow" } else { "Cyan" }

                        $lineStr = [string]$line
                        $utf8Bytes = [System.Text.Encoding]::UTF8.GetBytes($lineStr)
                        $utf8Line = [System.Text.Encoding]::UTF8.GetString($utf8Bytes)
                        
                        # Check if the line already starts with a timestamp (from Uvicorn's logging.ini)
                        if ($utf8Line -match "^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ") {
                            $formattedLine = $utf8Line # Use as is if already formatted
                        } else {
                            $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                            $formattedLine = "[$timestamp] [$($job.Name)] $utf8Line" # Add timestamp and job name
                        }
                        
                        Write-Host $formattedLine -ForegroundColor $color
                        # $formattedLine | Out-File -FilePath $LogFile -Append -Encoding utf8
                    }
                }
            }
        }

        # Break loop if no jobs are running and no more data is available from any job
        $runningJobs = $activeJobs | Where-Object { $_.State -match 'Running|Scheduled|Blocked' }
        if (-not $runningJobs -and -not $anyJobHasMoreData) { break }

        Start-Sleep -Milliseconds 250 # Wait a bit before checking again
    }
}
finally {
    Write-Host "`nStopping services..." -ForegroundColor Red
    # Stop-Job $modelJob, $backendJob
    # Remove-Job $modelJob, $backendJob
    # Get-Job -Name "Model-Service", "Backend" -ErrorAction SilentlyContinue | Stop-Job -Force -ErrorAction SilentlyContinue
    # Get-Job -Name "Model-Service", "Backend" -ErrorAction SilentlyContinue | Remove-Job -Force -ErrorAction SilentlyContinue
    Stop-Process -Name python -Force
    Write-Host "All services stopped. Exiting." -ForegroundColor Red
}