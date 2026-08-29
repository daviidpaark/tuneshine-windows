# Tuneshine Windows Desktop Companion Uninstaller
$ErrorActionPreference = "SilentlyContinue"

$AppName = "TuneshineWindows"
$DisplayName = "Tuneshine Windows"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName

Write-Host "Uninstalling $DisplayName..." -ForegroundColor Yellow

# 1. Stop running process
Get-Process -Name $AppName | Stop-Process -Force
Start-Sleep -Milliseconds 500

# 2. Remove shortcuts
$StartMenuDir = [Environment]::GetFolderPath('Programs')
$DesktopDir = [Environment]::GetFolderPath('Desktop')
Remove-Item -Path (Join-Path $StartMenuDir "$DisplayName.lnk") -Force
Remove-Item -Path (Join-Path $DesktopDir "$DisplayName.lnk") -Force

# 3. Remove Registry Startup
$RegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Remove-ItemProperty -Path $RegPath -Name $AppName -ErrorAction SilentlyContinue

# 4. Remove installation files
if (Test-Path $InstallDir) {
    Remove-Item -Path $InstallDir -Recurse -Force
}

Write-Host "Uninstallation complete. Tuneshine Windows has been removed." -ForegroundColor Green
