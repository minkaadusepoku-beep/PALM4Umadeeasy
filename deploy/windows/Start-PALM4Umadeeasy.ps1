<#
.SYNOPSIS
    One-click launcher for PALM4Umadeeasy on Windows.

.DESCRIPTION
    Brings up the FastAPI backend and the Next.js frontend in their own
    minimised console windows, waits for both to pass health checks, and
    opens the browser. Stop everything by closing the two console windows,
    or by running Stop-PALM4Umadeeasy.ps1.

    Safe to re-run: if the backend or frontend is already healthy on its
    expected port, that step is skipped.

.PARAMETER Mode
    dev       - uses 'next dev' (hot reload, fast startup, for interactive use)
    prod      - uses 'next build' then 'next start' (slower first launch, faster pages)
    Default: dev.

.PARAMETER NoBrowser
    Don't open the browser after startup. Useful when running headless.

.PARAMETER BackendPort
    Override the backend port. Default 8000.

.PARAMETER FrontendPort
    Override the frontend port. Default 3000.

.EXAMPLE
    .\Start-PALM4Umadeeasy.ps1
    .\Start-PALM4Umadeeasy.ps1 -Mode prod
    .\Start-PALM4Umadeeasy.ps1 -NoBrowser
#>

[CmdletBinding()]
param(
    [ValidateSet('dev', 'prod')]
    [string]$Mode = 'dev',
    [switch]$NoBrowser,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'

function Write-Step {
    param([string]$Message)
    Write-Host ">>> $Message" -ForegroundColor Cyan
}

function Test-Port {
    param([int]$Port)
    try {
        $socket = New-Object System.Net.Sockets.TcpClient
        $result = $socket.BeginConnect('127.0.0.1', $Port, $null, $null)
        $ok = $result.AsyncWaitHandle.WaitOne(200, $false)
        if ($ok) { $socket.EndConnect($result) | Out-Null }
        $socket.Close()
        return $ok
    } catch {
        return $false
    }
}

function Wait-ForHealth {
    param(
        [string]$Url,
        [string]$Name,
        [int]$TimeoutSeconds = 60
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    Write-Warning "$Name did not respond on $Url within $TimeoutSeconds s"
    return $false
}

# ------------------------------------------------------------------
# Preflight
# ------------------------------------------------------------------

Write-Step "PALM4Umadeeasy launcher (mode=$Mode)"
Write-Host "Repository : $RepoRoot"

if (-not (Test-Path $BackendDir) -or -not (Test-Path $FrontendDir)) {
    Write-Error "Cannot find backend/ or frontend/ under $RepoRoot"
    exit 1
}

# Python
try {
    $py = (Get-Command python -ErrorAction Stop).Source
    Write-Host "Python     : $py"
} catch {
    Write-Error "Python is not on PATH. Install Python 3.11+ and re-run."
    exit 1
}

# Node
try {
    $node = (Get-Command node -ErrorAction Stop).Source
    $nodeVersion = (& node --version).Trim()
    Write-Host "Node       : $node ($nodeVersion)"
} catch {
    Write-Error "Node.js is not on PATH. Install Node 20+ and re-run."
    exit 1
}

# Backend deps
if (-not (Test-Path (Join-Path $BackendDir 'palm4u.db'))) {
    Write-Host "Note       : palm4u.db not found - will be created on first backend start."
}

$frontendNodeModules = Join-Path $FrontendDir 'node_modules'
if (-not (Test-Path $frontendNodeModules)) {
    Write-Step "First run: installing frontend dependencies (npm ci)..."
    Push-Location $FrontendDir
    try {
        npm ci
    } finally {
        Pop-Location
    }
}

# ------------------------------------------------------------------
# Backend
# ------------------------------------------------------------------

$backendUrl = "http://127.0.0.1:$BackendPort"
$backendHealth = "$backendUrl/api/health"

# Literal double-quote - used below to wrap child process commands that
# contain spaces. Safer than backtick-escaping, which has surprising edge
# cases inside double-quoted strings with trailing variable expansions.
$q = [char]34

if (Test-Port -Port $BackendPort) {
    Write-Step "Backend already running on port $BackendPort (skipping start)"
} else {
    Write-Step "Starting backend on port $BackendPort..."
    $backendCmd = "cd $q$BackendDir$q; python -m uvicorn src.api.main:app --host 127.0.0.1 --port $BackendPort"
    Start-Process -FilePath 'powershell.exe' `
                  -ArgumentList @('-NoExit', '-Command', $backendCmd) `
                  -WindowStyle Minimized | Out-Null
    if (-not (Wait-ForHealth -Url $backendHealth -Name 'Backend' -TimeoutSeconds 60)) {
        Write-Error "Backend failed to become healthy."
        exit 1
    }
    Write-Host "Backend OK : $backendHealth" -ForegroundColor Green
}

# ------------------------------------------------------------------
# Frontend
# ------------------------------------------------------------------

$frontendUrl = "http://127.0.0.1:$FrontendPort"

if (Test-Port -Port $FrontendPort) {
    Write-Step "Frontend already running on port $FrontendPort (skipping start)"
} else {
    if ($Mode -eq 'prod') {
        Write-Step "Building frontend (next build)..."
        Push-Location $FrontendDir
        try {
            npm run build
        } finally {
            Pop-Location
        }
        $frontendStart = "npm run start -- -p $FrontendPort"
    } else {
        $frontendStart = "npm run dev -- -p $FrontendPort"
    }

    Write-Step "Starting frontend on port $FrontendPort ($Mode)..."
    $frontendCmd = "cd $q$FrontendDir$q; $frontendStart"
    Start-Process -FilePath 'powershell.exe' `
                  -ArgumentList @('-NoExit', '-Command', $frontendCmd) `
                  -WindowStyle Minimized | Out-Null
    if (-not (Wait-ForHealth -Url $frontendUrl -Name 'Frontend' -TimeoutSeconds 120)) {
        Write-Error "Frontend failed to become healthy. Check the minimised PowerShell window for errors."
        exit 1
    }
    Write-Host "Frontend OK: $frontendUrl" -ForegroundColor Green
}

# ------------------------------------------------------------------
# Open browser
# ------------------------------------------------------------------

if (-not $NoBrowser) {
    Write-Step "Opening $frontendUrl in your default browser..."
    Start-Process $frontendUrl
}

Write-Host ""
Write-Host "PALM4Umadeeasy is up." -ForegroundColor Green
Write-Host "  Frontend : $frontendUrl"
Write-Host "  Backend  : $backendUrl"
Write-Host "  Admin    : $frontendUrl/admin  (runner mode + worker config)"
Write-Host ""
Write-Host "To stop, close the two minimised PowerShell windows or run:"
Write-Host "  .\Stop-PALM4Umadeeasy.ps1"
