<#
  One-time setup for a NAMED Cloudflare tunnel giving Textprint a stable public URL.

  Prereqs (yours to do -- they need your browser / Cloudflare account):
    * a domain managed by Cloudflare (free plan is fine)
    * cloudflared installed  (winget install Cloudflare.cloudflared)

  Usage:
    .\setup_tunnel.ps1 -Hostname textprint.yourdomain.com
    # then run it anytime with:  .\start.ps1
#>
param(
  [Parameter(Mandatory=$true)][string]$Hostname,
  [string]$Name = "textprint",
  [int]$Port = 8100
)
$ErrorActionPreference = "Stop"

function Find-Cloudflared {
  $c = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $candidates = @("${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
                  "$env:ProgramFiles\cloudflared\cloudflared.exe")
  foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
  throw "cloudflared not found. Install it:  winget install Cloudflare.cloudflared"
}

$cf = Find-Cloudflared
Write-Host "cloudflared: $cf"
$cfgDir = "$env:USERPROFILE\.cloudflared"
if (-not (Test-Path $cfgDir)) { New-Item -ItemType Directory -Path $cfgDir | Out-Null }

# 1. authenticate (opens a browser; pick the domain you want to use)
if (-not (Test-Path "$cfgDir\cert.pem")) {
  Write-Host ""
  Write-Host ">> Authorizing with Cloudflare. A browser will open -- log in and pick your domain." -ForegroundColor Cyan
  & $cf tunnel login
  if (-not (Test-Path "$cfgDir\cert.pem")) { throw "login did not complete (no cert.pem)." }
}

# 2. create the tunnel if it doesn't exist yet
$tunnels = & $cf tunnel list --output json | ConvertFrom-Json
$t = $tunnels | Where-Object { $_.name -eq $Name } | Select-Object -First 1
if (-not $t) {
  Write-Host ">> Creating tunnel '$Name'..." -ForegroundColor Cyan
  & $cf tunnel create $Name
  $tunnels = & $cf tunnel list --output json | ConvertFrom-Json
  $t = $tunnels | Where-Object { $_.name -eq $Name } | Select-Object -First 1
}
$uuid = $t.id
Write-Host "tunnel '$Name' = $uuid"
$creds = "$cfgDir\$uuid.json"

# 3. write config.yml (route the hostname to the local proxy)
$lines = @(
  "tunnel: $uuid",
  "credentials-file: $creds",
  "ingress:",
  "  - hostname: $Hostname",
  "    service: http://127.0.0.1:$Port",
  "  - service: http_status:404"
)
Set-Content -Path "$cfgDir\config.yml" -Value $lines -Encoding utf8
Write-Host "wrote $cfgDir\config.yml"

# 4. point the DNS name at the tunnel
Write-Host ">> Routing $Hostname -> tunnel..." -ForegroundColor Cyan
& $cf tunnel route dns $Name $Hostname

# 5. remember the hostname for start.ps1's summary
Set-Content -Path "$PSScriptRoot\.tunnel_hostname" -Value $Hostname -Encoding ascii

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Turn it on anytime with:   .\start.ps1"
Write-Host "Public URL:                https://$Hostname"
Write-Host "Paste that URL into the site's 'Ollama proxy URL' box."
