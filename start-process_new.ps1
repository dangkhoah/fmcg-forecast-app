chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()

Write-Host "=== FMCG Sales Forecast App (Start-Process) ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔄 Starting services in the current console..." -ForegroundColor Yellow

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$pythonModel = Join-Path $root "model-service\.venv\Scripts\python.exe"
$pythonBackend = Join-Path $root "backend\.venv\Scripts\python.exe"

$modelArgs = @(
    '-X', 'utf8',
    '-m', 'uvicorn',
    'app.main:app',
    '--host', '0.0.0.0',
    '--port', '8001',
    '--reload',
    '--reload-dir', 'app',
    '--reload-exclude=__pycache__/*',
    '--log-config', 'logging.ini'
)

$backendArgs = @(
    '-X', 'utf8',
    '-m', 'uvicorn',
    'app.main:app',
    '--host', '0.0.0.0',
    '--port', '8000',
    '--reload',
    '--reload-dir', 'app',
    '--reload-exclude=uploads/*',
    '--log-config', 'logging.ini'
)

$modelOut = Join-Path $root "proc1-output.log"
$modelErr = Join-Path $root "proc1-error.log"
$backendOut = Join-Path $root "proc2-output.log"
$backendErr = Join-Path $root "proc2-error.log"

function Ensure-PortsFree {
    param(
        [int[]]$Ports
    )

    foreach ($Port in $Ports) {
        $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($listeners) {
            $pids = $listeners | Select-Object -ExpandProperty OwningProcess | Where-Object { $_ -and $_ -ne 0 } | Sort-Object -Unique
            foreach ($pid in $pids) {
                Write-Host "Port $Port is in use by PID $pid. Stopping process..." -ForegroundColor Yellow
                try {
                    Stop-Process -Id $pid -Force -ErrorAction Stop
                    Write-Host "Stopped PID $pid and freed port $Port." -ForegroundColor Green
                } catch {
                    Write-Host ("Unable to stop PID {0} for port {1}: {2}" -f $pid, $Port, $_) -ForegroundColor Red
                }
            }

            Start-Sleep -Milliseconds 200
            $remaining = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            if ($remaining) {
                Write-Host "Port $Port is still in use after stopping processes. Remaining listeners:" -ForegroundColor Red
                $remaining | ForEach-Object {
                    Write-Host "  PID=$($_.OwningProcess) State=$($_.State) LocalAddress=$($_.LocalAddress)" -ForegroundColor Red
                }
            }
        }
    }
}

Remove-Item -Path $modelOut, $modelErr, $backendOut, $backendErr -ErrorAction SilentlyContinue

# restart control
$shouldRestart = $false
$restartStateFile = Join-Path $env:TEMP "start-process-restart-state.json"
$maxRestarts = 5
$restartWindowSeconds = 600 # 10 minutes

Ensure-PortsFree -Ports 8001,8000

Write-Host "Starting Model Service (port 8001) as process \$proc1..." -ForegroundColor Green
Write-Host "Checking for existing background jobs (Model-Service/Backend/proc1/proc2)..." -ForegroundColor Magenta
$existingJobs = Get-Job -Name "Model-Service", "Backend", "proc1", "proc2" -ErrorAction SilentlyContinue
if ($existingJobs) {
    Write-Host "Found background jobs; streaming their output instead of starting new processes." -ForegroundColor Magenta
    try {
        $jobMissingSince = $null
        $missingGrace = 12
        while ($true) {
            $activeJobs = Get-Job -Name "Model-Service", "Backend", "proc1", "proc2" -ErrorAction SilentlyContinue
            if (-not $activeJobs) {
                if (-not $jobMissingSince) {
                    $jobMissingSince = Get-Date
                } elseif (((Get-Date) - $jobMissingSince).TotalSeconds -gt $missingGrace) {
                    Write-Host "No jobs found for $missingGrace seconds; stopping job-stream." -ForegroundColor Magenta
                    break
                }
                Start-Sleep -Milliseconds 200
                continue
            } else {
                $jobMissingSince = $null
            }

            foreach ($job in $activeJobs) {
                $results = Receive-Job -Job $job -Keep -ErrorAction SilentlyContinue 2>&1
                if ($null -ne $results) {
                    foreach ($line in $results) {
                        if ($null -ne $line) {
                            $color = if ($job.Name -in @('Model-Service','proc1')) { 'Yellow' } else { 'Cyan' }
                            $lineStr = [string]$line
                            if ($lineStr -match "^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - ") {
                                $formattedLine = $lineStr
                            } else {
                                $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
                                $formattedLine = "[$timestamp] [$($job.Name)] $lineStr"
                            }
                            Write-Host $formattedLine -ForegroundColor $color
                            $formattedLine | Out-File -FilePath $modelOut -Append -Encoding utf8
                        }
                    }
                }
            }
            Start-Sleep -Milliseconds 200
        }
    } finally {
        Write-Host "Finished streaming background jobs. Exiting." -ForegroundColor Magenta
    }
    return
} else {
    Write-Host "Starting Model Service (port 8001) as process \$proc1..." -ForegroundColor Green
    $proc1 = Start-Process -FilePath $pythonModel -ArgumentList $modelArgs -WorkingDirectory "$root\model-service" -NoNewWindow -RedirectStandardOutput $modelOut -RedirectStandardError $modelErr -PassThru
    Write-Host "Model Service started: PID=$($proc1.Id), Name=$($proc1.ProcessName)" -ForegroundColor Green

    Write-Host "Starting Backend Service (port 8000) as process \$proc2..." -ForegroundColor Green
    $proc2 = Start-Process -FilePath $pythonBackend -ArgumentList $backendArgs -WorkingDirectory "$root\backend" -NoNewWindow -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
    Write-Host "Backend Service started: PID=$($proc2.Id), Name=$($proc2.ProcessName)" -ForegroundColor Green
}

$lastProc1Id = $proc1.Id
$lastProc2Id = $proc2.Id

Write-Host ""
Write-Host "Services are running in the current console. Press Ctrl+C to stop." -ForegroundColor Cyan

function Read-NewLines {
    param(
        [string]$Path,
        [ref]$Position
    )

    if (-not (Test-Path $Path)) { return }
    $fsi = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $fsi.Seek($Position.Value, [System.IO.SeekOrigin]::Begin) | Out-Null
        $sr = New-Object System.IO.StreamReader($fsi, [System.Text.Encoding]::UTF8)
        while (-not $sr.EndOfStream) {
            $line = $sr.ReadLine()
            if ($line -ne $null) {
                Write-Output $line
            }
        }
        $Position.Value = $fsi.Position
    } finally {
        $sr.Close()
        $fsi.Close()
    }
}

function Write-ProcessLine {
    param(
        [string]$ProcessTag,
        [string]$Text,
        [string]$Color
    )
    Write-Host "[$ProcessTag] $Text" -ForegroundColor $Color
}

function Get-ServiceProcessByPort {
    param(
        [int]$Port
    )
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($conn) {
        return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    }
    return $null
}

function ReattachServiceProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$Port
    )
    if ($Process -and -not $Process.HasExited) {
        return $Process
    }
    return Get-ServiceProcessByPort -Port $Port
}

function IsServiceAlive {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$Port
    )
    if ($Process -and -not $Process.HasExited) {
        return $true
    }
    return (Get-ServiceProcessByPort -Port $Port) -ne $null
}

$proc1OutPosition = 0
$proc1ErrPosition = 0
$proc2OutPosition = 0
$proc2ErrPosition = 0
$proc1MissingSince = $null
$proc2MissingSince = $null
$missingGraceSeconds = 8

try {
    while ($true) {
        $proc1 = ReattachServiceProcess -Process $proc1 -Port 8001
        if ($proc1 -and -not $proc1.HasExited) {
            $proc1MissingSince = $null
        } elseif (-not $proc1MissingSince) {
            $proc1MissingSince = Get-Date
        }

        $proc2 = ReattachServiceProcess -Process $proc2 -Port 8000
        if ($proc2 -and -not $proc2.HasExited) {
            $proc2MissingSince = $null
        } elseif (-not $proc2MissingSince) {
            $proc2MissingSince = Get-Date
        }

        $proc1Down = $false
        if ($proc1MissingSince) {
            $proc1Down = ((Get-Date) - $proc1MissingSince).TotalSeconds -gt $missingGraceSeconds
        }

        $proc2Down = $false
        if ($proc2MissingSince) {
            $proc2Down = ((Get-Date) - $proc2MissingSince).TotalSeconds -gt $missingGraceSeconds
        }

        if ($proc1Down -and $proc2Down) {
            $shouldRestart = $true
            break
        }

        if ($proc1 -and -not $proc1.HasExited -and $lastProc1Id -ne $proc1.Id) {
            Write-ProcessLine -ProcessTag 'proc1' -Text "Reattached to reloaded PID $($proc1.Id)" -Color Yellow
            $lastProc1Id = $proc1.Id
        }

        if ($proc2 -and -not $proc2.HasExited -and $lastProc2Id -ne $proc2.Id) {
            Write-ProcessLine -ProcessTag 'proc2' -Text "Reattached to reloaded PID $($proc2.Id)" -Color Cyan
            $lastProc2Id = $proc2.Id
        }

        foreach ($line in Read-NewLines -Path $modelOut -Position ([ref]$proc1OutPosition)) {
            Write-ProcessLine -ProcessTag 'proc1' -Text $line -Color Yellow
        }
        foreach ($line in Read-NewLines -Path $modelErr -Position ([ref]$proc1ErrPosition)) {
            Write-ProcessLine -ProcessTag 'proc1' -Text $line -Color DarkYellow
        }

        foreach ($line in Read-NewLines -Path $backendOut -Position ([ref]$proc2OutPosition)) {
            Write-ProcessLine -ProcessTag 'proc2' -Text $line -Color Cyan
        }
        foreach ($line in Read-NewLines -Path $backendErr -Position ([ref]$proc2ErrPosition)) {
            Write-ProcessLine -ProcessTag 'proc2' -Text $line -Color DarkCyan
        }

        Start-Sleep -Milliseconds 200
    }
    # flush any remaining lines after processes exit
    foreach ($line in Read-NewLines -Path $modelOut -Position ([ref]$proc1OutPosition)) {
        Write-ProcessLine -ProcessTag 'proc1' -Text $line -Color Yellow
    }
    foreach ($line in Read-NewLines -Path $modelErr -Position ([ref]$proc1ErrPosition)) {
        Write-ProcessLine -ProcessTag 'proc1' -Text $line -Color DarkYellow
    }
    foreach ($line in Read-NewLines -Path $backendOut -Position ([ref]$proc2OutPosition)) {
        Write-ProcessLine -ProcessTag 'proc2' -Text $line -Color Cyan
    }
    foreach ($line in Read-NewLines -Path $backendErr -Position ([ref]$proc2ErrPosition)) {
        Write-ProcessLine -ProcessTag 'proc2' -Text $line -Color DarkCyan
    }
    } finally {
    Write-Host "`nStopping services..." -ForegroundColor Red
    if ($proc1 -and -not $proc1.HasExited) {
        Stop-Process -Id $proc1.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Model Service process $($proc1.Id)." -ForegroundColor Red
    }
    if ($proc2 -and -not $proc2.HasExited) {
        Stop-Process -Id $proc2.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Backend Service process $($proc2.Id)." -ForegroundColor Red
    }
    Write-Host "All services stopped. Exiting." -ForegroundColor Red

    # Immediately relaunch this script in a new PowerShell process and exit current one
    try {
        $scriptPath = $MyInvocation.MyCommand.Path
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$scriptPath`"" -WorkingDirectory $PSScriptRoot -NoNewWindow | Out-Null
        Write-Host "Relaunched $scriptPath in a new process. Exiting current instance." -ForegroundColor Green
        exit
    } catch {
        Write-Host "Failed to relaunch script: $_" -ForegroundColor Yellow
    }

    # Decide whether to restart this script
    function Read-RestartState {
        param([string]$path)
        if (-not (Test-Path $path)) { return $null }
        try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null }
    }

    function Write-RestartState {
        param([string]$path, $obj)
        $json = $obj | ConvertTo-Json -Depth 3
        $json | Out-File -FilePath $path -Encoding utf8 -Force
    }

    $doRestart = $false
    if ($shouldRestart) {
        $state = Read-RestartState -path $restartStateFile
        $now = Get-Date
        if (-not $state) {
            $state = @{ count = 0; first = $now }
        }
        # reset window if expired
        if (((Get-Date) - [DateTime]$state.first).TotalSeconds -gt $restartWindowSeconds) {
            $state.count = 0
            $state.first = $now
        }
        $state.count = $state.count + 1
        Write-RestartState -path $restartStateFile -obj $state

        if ($state.count -le $maxRestarts) {
            $doRestart = $true
        } else {
            Write-Host "Restart limit reached ($($state.count)) within window; not restarting." -ForegroundColor Yellow
        }
    }

    if ($doRestart) {
        Write-Host "Relaunching script in background..." -ForegroundColor Green
        $scriptPath = $MyInvocation.MyCommand.Path
        Write-Host "Relaunching script in same console..." -ForegroundColor Green
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$scriptPath`"" -WorkingDirectory $PSScriptRoot -NoNewWindow | Out-Null
        Write-Host "Started new instance of $scriptPath in same console. Exiting current process." -ForegroundColor Green
    }
}
