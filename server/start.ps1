<#
  Turn on Textprint's narration host: starts the proxy + the named tunnel together.
  Run setup_tunnel.ps1 once first. Ctrl+C stops everything.

  Usage:
    .\start.ps1                        # uses gemma4:26b (or $env:TEXTPRINT_MODEL)
    .\start.ps1 -Model qwen2.5:14b -Token my-secret
#>
param(
  [string]$Name  = "textprint",
  [int]$Port     = 8100,
  [string]$Model = $env:TEXTPRINT_MODEL,
  [string]$Token = $env:TEXTPRINT_TOKEN
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if (-not $Model) { $Model = "gemma4:26b" }

function Find-Cloudflared {
  $c = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $candidates = @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
                  "$env:ProgramFiles\cloudflared\cloudflared.exe")
  foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
  throw "cloudflared not found. Install:  winget install Cloudflare.cloudflared"
}
$cf = Find-Cloudflared

# is Ollama up?
try { Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 4 | Out-Null }
catch { Write-Warning "Ollama isn't responding on :11434 -- start it with 'ollama serve' (reads won't work until then)." }

$env:TEXTPRINT_MODEL = $Model
if ($Token) { $env:TEXTPRINT_TOKEN = $Token }
$tokState = if ($Token) { "on" } else { "off" }

Write-Host "starting narration proxy on 127.0.0.1:$Port  (model $Model, token $tokState)" -ForegroundColor Cyan
$pyArgs = @("-m", "uvicorn", "proxy:app", "--host", "127.0.0.1", "--port", "$Port")
$proxy = Start-Process -FilePath "python" -ArgumentList $pyArgs -WorkingDirectory $here -PassThru -NoNewWindow

Start-Sleep -Seconds 2
if ($proxy.HasExited) { throw "proxy failed to start -- run 'pip install -r requirements.txt' in server\ first." }

$hn = ""
if (Test-Path "$here\.tunnel_hostname") { $hn = (Get-Content "$here\.tunnel_hostname" -Raw).Trim() }
if ($hn) { Write-Host "public URL:  https://$hn   (paste into the site)" -ForegroundColor Green }

Write-Host "starting tunnel '$Name'...  (Ctrl+C to stop everything)" -ForegroundColor Cyan
Write-Host ""
try {
  & $cf tunnel run $Name
} finally {
  Write-Host ""
  Write-Host "stopping proxy..." -ForegroundColor Cyan
  if ($proxy -and -not $proxy.HasExited) { Stop-Process -Id $proxy.Id -Force }
}
