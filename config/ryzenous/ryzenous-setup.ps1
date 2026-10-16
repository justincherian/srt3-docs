# SRT3 observability - Ryzenous (Windows). Run in an ADMIN PowerShell:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME\Downloads\srt3-observability\ryzenous-setup.ps1"
# Installs two small exporters as Windows services. Both are only reachable from Hellcat (192.168.8.220).
#   windows_exporter     :9182  CPU, RAM, disks, NICs, uptime
#   nvidia_gpu_exporter  :9835  RTX 3070 utilization, VRAM, temp, power, clocks, per-process VRAM
$ErrorActionPreference = 'Stop'
$Prom = '192.168.8.220'
function Ok($m){ Write-Host "[ok] $m" -ForegroundColor Green }

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Run this from an Administrator PowerShell (right-click PowerShell > Run as administrator).'
}

# 1. windows_exporter (official Prometheus community MSI, latest release)
$rel = Invoke-RestMethod 'https://api.github.com/repos/prometheus-community/windows_exporter/releases/latest'
$msi = $rel.assets | Where-Object name -like '*amd64.msi' | Select-Object -First 1
$msiPath = Join-Path $env:TEMP $msi.name
Invoke-WebRequest $msi.browser_download_url -OutFile $msiPath
# Only the collectors the dashboards use (the default 'service' collector is slow WMI work every scrape).
$p = Start-Process msiexec.exe -Wait -PassThru -ArgumentList "/i `"$msiPath`" /qn ENABLED_COLLECTORS=cpu,memory,logical_disk,physical_disk,net,os,system,time"
if ($p.ExitCode -notin 0,3010) { throw "windows_exporter MSI failed with exit code $($p.ExitCode)" }
Ok "windows_exporter $($rel.tag_name) installed"

# 2. nvidia_gpu_exporter (machine-wide winget install, then its own service registration)
winget install --scope machine -e --id utkuozdemir.nvidia_gpu_exporter --silent --accept-source-agreements --accept-package-agreements | Out-Null
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$exe = (Get-Command nvidia_gpu_exporter -ErrorAction SilentlyContinue).Source
if (-not $exe) { $exe = (Get-ChildItem "$env:ProgramFiles\WinGet" -Recurse -Filter nvidia_gpu_exporter.exe -ErrorAction SilentlyContinue | Select-Object -First 1).FullName }
if (-not $exe) { throw 'nvidia_gpu_exporter.exe not found after winget install' }
if (-not (Get-Service nvidia_gpu_exporter -ErrorAction SilentlyContinue)) { & $exe install | Out-Null }
Start-Service nvidia_gpu_exporter
Ok "nvidia_gpu_exporter running ($exe)"

# 3. Firewall: allow only Hellcat to scrape. Works on Public or Private network profiles.
foreach ($r in @(@{n='SRT3 windows_exporter';p=9182}, @{n='SRT3 nvidia_gpu_exporter';p=9835})) {
  Get-NetFirewallRule -DisplayName $r.n -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  New-NetFirewallRule -DisplayName $r.n -Direction Inbound -Action Allow -Protocol TCP -LocalPort $r.p -RemoteAddress $Prom -Profile Any | Out-Null
}
Ok "firewall: 9182 and 9835 open to $Prom only"

# 4. Self-test
Start-Sleep 3
foreach ($port in 9182, 9835) {
  $n = ((Invoke-WebRequest "http://localhost:$port/metrics" -UseBasicParsing).Content -split "`n").Count
  Ok "localhost:$port/metrics -> $n lines"
}
Write-Host "`nDone. Hellcat will start scraping within 15 seconds." -ForegroundColor Cyan
