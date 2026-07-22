<#
  Serve the Textprint narration proxy to your phone over Tailscale: private to
  your tailnet, HTTPS, no Cloudflare tunnel. Use this when Ollama is bound to
  0.0.0.0 and your devices are on Tailscale.

  ONE-TIME: enable Tailscale Serve for your tailnet (a one-click toggle in your
  Tailscale account). If it is not enabled, this script prints the exact link.

  Then, on your PHONE (Tailscale app connected to the same tailnet): open the
  Textprint site and set "Ollama proxy URL" to the https URL this prints.

  Usage:  .\start_tailscale.ps1  [-Model gemma4:26b] [-Port 8100] [-Token secret]
#>
param([int]$Port = 8100, [string]$Model = $env:TEXTPRINT_MODEL, [string]$Token = $env:TEXTPRINT_TOKEN)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if (-not $Model) { $Model = "gemma4:26b" }

function Find-TS {
  $c = Get-Command tailscale -ErrorAction SilentlyContinue; if ($c) { return $c.Source }
  $p = "$env:ProgramFiles\Tailscale\tailscale.exe"; if (Test-Path $p) { return $p }
  throw "tailscale not found. Install Tailscale first."
}
$ts = Find-TS
$dns = ((& $ts status --json | ConvertFrom-Json).Self.DNSName).TrimEnd('.')
if (-not $dns) { throw "Could not read your tailnet name. Is Tailscale running and logged in?" }

# Ollama check
try { Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 4 | Out-Null }
catch { Write-Warning "Ollama is not answering on :11434. Start it (reads will not work until then)." }

# start the proxy if it is not already up
$env:TEXTPRINT_MODEL = $Model
if ($Token) { $env:TEXTPRINT_TOKEN = $Token }
$up = $false
try { if ((Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 3).ok) { $up = $true } } catch {}
if (-not $up) {
  Write-Host "starting proxy on 127.0.0.1:$Port (model $Model)..." -ForegroundColor Cyan
  Start-Process python -ArgumentList @("-m","uvicorn","proxy:app","--host","127.0.0.1","--port","$Port") -WorkingDirectory $here -WindowStyle Hidden
  Start-Sleep 2
} else {
  Write-Host "proxy already running on :$Port" -ForegroundColor Cyan
}

# expose over Tailscale Serve (HTTPS), with a timeout so a not-yet-enabled tailnet
# does not hang the script
Write-Host "exposing proxy over Tailscale Serve..." -ForegroundColor Cyan
$job = Start-Job { param($tsPath, $p) & $tsPath serve --bg $p 2>&1 } -ArgumentList $ts, $Port
if (Wait-Job $job -Timeout 25) { $out = Receive-Job $job } else { Stop-Job $job; $out = "TIMEOUT" }
Remove-Job $job -Force
$outText = ($out | Out-String)

if ($outText -match "not enabled" -or $outText -match "TIMEOUT") {
  Write-Host ""
  Write-Warning "Tailscale Serve is not enabled on your tailnet yet."
  $link = ($out | Select-String "https://login.tailscale.com").Matches.Value
  if ($link) {
    Write-Host "Enable it here (one click), then re-run this script:" -ForegroundColor Yellow
    Write-Host "    $link" -ForegroundColor Yellow
  } else {
    Write-Host "Enable Tailscale Serve in your Tailscale admin console, then re-run." -ForegroundColor Yellow
  }
  exit 1
}

Write-Host ""
Write-Host "Textprint proxy is live on your tailnet:" -ForegroundColor Green
Write-Host "    https://$dns" -ForegroundColor Green
Write-Host ""
Write-Host "On your phone (Tailscale app connected), open the Textprint site and set the"
Write-Host "'Ollama proxy URL' to:  https://$dns"
Write-Host ""
& $ts serve status
