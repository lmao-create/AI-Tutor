# ============================================================
#  CodeTutor AI - one-command Windows startup
#  Usage:  .\start.ps1                (dev mode: Vite + API)
#          .\start.ps1 -Prod          (build + single server on 8123)
#          .\start.ps1 -RunTests      (run the pytest suite, then exit)
# ============================================================
param(
    [switch]$Prod,
    [switch]$RunTests
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$apiPort = 8123
$webPort = 5173

function Write-Step($msg) {
    Write-Host "`n==> $msg" -ForegroundColor Cyan
}

# ------------------------------------------------------------
# 0. Tests only?
# ------------------------------------------------------------
if ($RunTests) {
    $py = "$root\backend\.venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        Write-Step "No virtualenv found - creating one..."
        python -m venv "$root\backend\.venv"
        & "$root\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
        & "$root\backend\.venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements-dev.txt"
    }
    & $py -m pytest $root\backend
    exit $LASTEXITCODE
}

# ------------------------------------------------------------
# 1. Backend: virtualenv + dependencies
# ------------------------------------------------------------
Write-Step "Checking Python backend..."
$py = "$root\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    python -m venv "$root\backend\.venv"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not create a virtualenv. Is Python 3.10+ installed?" -ForegroundColor Red
        exit 1
    }
    Write-Step "Installing backend dependencies (one time)..."
    & "$root\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
    & "$root\backend\.venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements.txt"
}

# ------------------------------------------------------------
# 2. Frontend: npm dependencies
# ------------------------------------------------------------
Write-Step "Checking frontend dependencies..."
if (-not (Test-Path "$root\frontend\node_modules")) {
    npm install --prefix "$root\frontend"
    # npm may block esbuild's postinstall (new npm security policy); the
    # binary ships as an optional dependency and must be linked manually.
    $esbuildInstall = "$root\frontend\node_modules\esbuild\install.js"
    if (Test-Path $esbuildInstall) {
        node $esbuildInstall
    }
}

# ------------------------------------------------------------
# 3. Start the backend
# ------------------------------------------------------------
Write-Step "Starting the API server on http://127.0.0.1:$apiPort ..."
$env:CODETUTOR_DATA_DIR = "$root\data"
$api = Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$apiPort" `
    -WorkingDirectory "$root\backend" -PassThru

$ready = $false
foreach ($i in 1..20) {
    Start-Sleep -Milliseconds 700
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$apiPort/api/health" -TimeoutSec 3
        if ($health.status -eq "ok") { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    Write-Host "The API server did not become ready. Check the logs above." -ForegroundColor Red
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id -Force }
    exit 1
}
Write-Host "   API ready (seed: 10 courses / 22 Python lessons / 34 exercises)." -ForegroundColor Green

# ------------------------------------------------------------
# 4. Production mode: build once and serve everything from the API
# ------------------------------------------------------------
if ($Prod) {
    Write-Step "Building the frontend (one time, takes ~20s)..."
    npm run build --prefix "$root\frontend"
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Start-Process "http://127.0.0.1:$apiPort/"
    Write-Host "`nCodeTutor AI is running at  http://127.0.0.1:$apiPort/" -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop the server."
    try { Wait-Process -Id $api.Id } finally {
        if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force }
    }
    exit 0
}

# ------------------------------------------------------------
# 5. Dev mode: Vite dev server alongside the API
# ------------------------------------------------------------
Write-Step "Starting the frontend dev server on http://localhost:$webPort ..."
$web = Start-Process -FilePath "npm" -ArgumentList "run", "dev" `
    -WorkingDirectory "$root\frontend" -PassThru

Start-Sleep -Seconds 4
Start-Process "http://localhost:$webPort/"

Write-Host "`nCodeTutor AI is running:" -ForegroundColor Green
Write-Host "   App:        http://localhost:$webPort/"
Write-Host "   API docs:   http://127.0.0.1:$apiPort/api/docs"
Write-Host "   Data dir:   $env:CODETUTOR_DATA_DIR (delete it to fully reset)"
Write-Host "`nClose this window (or Ctrl+C) to stop both servers."

try {
    Wait-Process -Id $web.Id
} finally {
    if (-not $web.HasExited) {
        Stop-Process -Id $web.Id -Force
        # npm run dev spawns a node child; stop the tree
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$($web.Id)" |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    if (-not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
}
