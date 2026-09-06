<#
.SYNOPSIS
    Starts the bot together with a public HTTPS tunnel (ngrok).
    The tunnel exposes the local web server (port 8080) over HTTPS, its URL is
    captured and written into .env as the API backend (WEB_APP_URL), then the
    bot is launched. The frontend (Mini App) lives on GitHub Pages and reaches
    the backend via ?api=<tunnel>. On stop (Ctrl+C) both are killed.
#>

$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ProjectDir

$LocalPort = 8080
$EnvFile   = Join-Path $ProjectDir '.env'
$NgrokExe  = Join-Path $ProjectDir 'ngrok.exe'

# Frontend on GitHub Pages (static). Backend (API) = tunnel, injected via ?api=
$FrontendBase = 'https://threepleS.github.io/ai-app-frontend/'

function Update-EnvUrl {
    param([string]$Url)
    $key = 'WEB_APP_URL'
    $full = "$FrontendBase`?api=$Url"
    if (-not (Test-Path $EnvFile)) {
        "$([Environment]::NewLine)$key=$full" | Add-Content -Path $EnvFile -Encoding utf8
        return
    }
    $lines = Get-Content -Path $EnvFile -Encoding utf8
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^$key=") {
            $lines[$i] = "$key=$full"
            $found = $true
            break
        }
    }
    if (-not $found) { $lines += "$key=$full" }
    $tmp = "$EnvFile.tmp"
    $attempts = 0
    while ($true) {
        try {
            Set-Content -Path $tmp -Value $lines -Encoding utf8 -ErrorAction Stop
            Move-Item -Path $tmp -Destination $EnvFile -Force -ErrorAction Stop
            break
        } catch {
            $attempts++
            if ($attempts -ge 20) { throw }
            Start-Sleep -Milliseconds 250
        }
    }
}

# --- 1. Start ngrok tunnel ---
if (-not (Test-Path $NgrokExe)) { Write-Error "ngrok.exe not found in project root."; exit 1 }

$ngrokProc = Start-Process -FilePath $NgrokExe -ArgumentList @("http", $LocalPort, "--log=stdout") `
    -PassThru -NoNewWindow -RedirectStandardOutput "$ProjectDir\ngrok.out.log" -RedirectStandardError "$ProjectDir\ngrok.err.log"

Write-Host "[tunnel] Starting ngrok ..."

# ngrok exposes a local API; poll it for the public URL.
$url = $null
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2 -ErrorAction Stop
        $pub = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
        if ($pub) { $url = $pub.public_url; break }
    } catch { Start-Sleep -Milliseconds 500 }
    Start-Sleep -Milliseconds 500
}

if (-not $url) {
    Write-Error "[tunnel] Could not get ngrok public URL. Check ngrok.out.log / ngrok.err.log."
    if (-not $ngrokProc.HasExited) { $ngrokProc.Kill() }
    exit 1
}

Update-EnvUrl $url
Write-Host "[tunnel] Backend (API) tunnel: $url"
Write-Host "[tunnel] Mini App (GitHub Pages): $FrontendBase`?api=$url  (written to .env -> WEB_APP_URL)"

# --- 2. Start bot ---
$venvPy = Join-Path $ProjectDir 'venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { $venvPy = 'python' }

Write-Host "[bot] Starting bot..."
$botProc = Start-Process -FilePath $venvPy -ArgumentList 'main.py' -PassThru -NoNewWindow -WorkingDirectory $ProjectDir

try {
    $botProc.WaitForExit()
}
finally {
    if (-not $botProc.HasExited) { $botProc.Kill() }
    if (-not $ngrokProc.HasExited) { $ngrokProc.Kill() }
    Write-Host "[tunnel] Tunnel stopped."
}
