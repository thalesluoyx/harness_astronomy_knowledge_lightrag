# keepalive_services.ps1
# 24/7 Watchdog Supervisor for Astronomy LightRAG Knowledge Graph Pipeline
# Ensures orchestrator, dashboard, and Cloudflare tunnel are always alive.

$ErrorActionPreference = "Continue"
$projectRoot = "C:\Work\openclaw_projects\bilingual_project\harness_astronomy_knowledge_lightrag"
$pythonExe = "C:\Users\33991\miniconda3\envs\MinerU\python.exe"

function Ensure-PowerSettings {
    powercfg /change standby-timeout-ac 0 | Out-Null
    powercfg /change hibernate-timeout-ac 0 | Out-Null
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 | Out-Null
    powercfg /change monitor-timeout-ac 15 | Out-Null
    powercfg /setactive SCHEME_CURRENT | Out-Null
}

function Check-And-Start-Services {
    Ensure-PowerSettings

    # 1. Check Orchestrator
    $orchProc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*orchestrator.py*" }
    if (-not $orchProc) {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [WATCHDOG] Orchestrator is down! Starting..." -ForegroundColor Yellow
        Start-Process -FilePath $pythonExe -ArgumentList "src/astronomy_lightrag/harness/orchestrator.py" -WorkingDirectory $projectRoot -WindowStyle Hidden
    } else {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [WATCHDOG] Orchestrator is running (PID: $($orchProc.ProcessId))" -ForegroundColor Green
    }

    # 2. Check Dashboard Server
    $dashProc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*dashboard/server.py*" }
    if (-not $dashProc) {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [WATCHDOG] Dashboard is down! Starting..." -ForegroundColor Yellow
        Start-Process -FilePath $pythonExe -ArgumentList "dashboard/server.py" -WorkingDirectory $projectRoot -WindowStyle Hidden
    } else {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [WATCHDOG] Dashboard is running (PID: $($dashProc.ProcessId))" -ForegroundColor Green
    }

    # 3. Check Cloudflare Tunnel
    $cfProc = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*cloudflared*7789*" }
    if (-not $cfProc) {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [WATCHDOG] Cloudflared tunnel is down! Starting..." -ForegroundColor Yellow
        Start-Process -FilePath "cloudflared" -ArgumentList "tunnel --url http://127.0.0.1:7789" -WorkingDirectory $projectRoot -WindowStyle Hidden
    } else {
        Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [WATCHDOG] Cloudflared tunnel is running (PID: $($cfProc.ProcessId))" -ForegroundColor Green
    }
}

Check-And-Start-Services
