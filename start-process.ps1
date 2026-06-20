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

Remove-Item -Path $modelOut, $modelErr, $backendOut, $backendErr -ErrorAction SilentlyContinue

Write-Host "Starting Model Service (port 8001) as process \$proc1..." -ForegroundColor Green
$proc1 = Start-Process -FilePath $pythonModel -ArgumentList $modelArgs -WorkingDirectory "$root\model-service" -NoNewWindow -RedirectStandardOutput $modelOut -RedirectStandardError $modelErr -PassThru
Write-Host "Model Service started: PID=$($proc1.Id), Name=$($proc1.ProcessName)" -ForegroundColor Green

Write-Host "Starting Backend Service (port 8000) as process \$proc2..." -ForegroundColor Green
$proc2 = Start-Process -FilePath $pythonBackend -ArgumentList $backendArgs -WorkingDirectory "$root\backend" -NoNewWindow -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
Write-Host "Backend Service started: PID=$($proc2.Id), Name=$($proc2.ProcessName)" -ForegroundColor Green

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

$proc1OutPosition = 0
$proc1ErrPosition = 0
$proc2OutPosition = 0
$proc2ErrPosition = 0

try {
    while ($true) {
        if ($proc1 -and $proc1.HasExited -and $proc2 -and $proc2.HasExited) {
            break
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
}
