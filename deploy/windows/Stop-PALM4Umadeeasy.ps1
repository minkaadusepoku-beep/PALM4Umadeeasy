<#
.SYNOPSIS
    Stops the PALM4Umadeeasy backend and frontend started by
    Start-PALM4Umadeeasy.ps1.

.DESCRIPTION
    Finds the processes listening on the backend and frontend ports and
    stops them (together with the minimised PowerShell host windows that
    Start-PALM4Umadeeasy.ps1 spawned). Safe to run when nothing is up -
    it will just report which ports were already free.

.PARAMETER BackendPort
    Backend port to stop. Default 8000.

.PARAMETER FrontendPort
    Frontend port to stop. Default 3000.

.PARAMETER Force
    Don't ask for confirmation before killing processes.

.EXAMPLE
    .\Stop-PALM4Umadeeasy.ps1
    .\Stop-PALM4Umadeeasy.ps1 -Force
    .\Stop-PALM4Umadeeasy.ps1 -BackendPort 8001 -FrontendPort 3001
#>

[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host ">>> $Message" -ForegroundColor Cyan
}

function Get-PortListenerPids {
    param([int]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        return @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
    } catch {
        return @()
    }
}

function Stop-PidTree {
    param(
        [int]$ProcessId,
        [string]$Label
    )
    try {
        $proc = Get-Process -Id $ProcessId -ErrorAction Stop
    } catch {
        return
    }

    $name = $proc.ProcessName
    Write-Host "  - $Label pid $ProcessId ($name)"

    # Kill children too - npm/uvicorn spawn worker processes, and the minimised
    # powershell host owns the dev server.
    try {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction Stop
        foreach ($child in $children) {
            Stop-PidTree -ProcessId $child.ProcessId -Label "    child"
        }
    } catch { }

    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    } catch {
        Write-Warning "    failed to stop pid $ProcessId : $($_.Exception.Message)"
    }
}

Write-Step "Stopping PALM4Umadeeasy"

$targets = @(
    @{ Port = $BackendPort;  Label = 'Backend'  },
    @{ Port = $FrontendPort; Label = 'Frontend' }
)

$anyStopped = $false

foreach ($t in $targets) {
    $listenerPids = Get-PortListenerPids -Port $t.Port
    if ($listenerPids.Count -eq 0) {
        Write-Host "$($t.Label.PadRight(8)) : nothing listening on port $($t.Port)"
        continue
    }

    if (-not $Force) {
        $answer = Read-Host "Stop $($t.Label) on port $($t.Port) (pids: $($listenerPids -join ', '))? [y/N]"
        if ($answer -notmatch '^[Yy]') {
            Write-Host "  skipped"
            continue
        }
    }

    Write-Step "Stopping $($t.Label) on port $($t.Port)"
    foreach ($listenerPid in $listenerPids) {
        Stop-PidTree -ProcessId $listenerPid -Label $t.Label
    }
    $anyStopped = $true
}

if ($anyStopped) {
    Write-Host ""
    Write-Host "PALM4Umadeeasy stopped." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Nothing was running on those ports." -ForegroundColor Yellow
}
