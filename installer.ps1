# Tuneshine Windows Desktop Companion Installer
$ErrorActionPreference = "Stop"

$AppName = "TuneshineWindows"
$DisplayName = "Tuneshine Windows"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$SourceDir = $PSScriptRoot

# Locate built executable or source directory
$SourceExe = Join-Path $SourceDir "dist\TuneshineWindows.exe"
if (-not (Test-Path $SourceExe)) {
    $SourceExe = Join-Path $SourceDir "TuneshineWindows.exe"
}

if (-not (Test-Path $SourceExe)) {
    Write-Host "Error: TuneshineWindows.exe not found! Please run build_exe.py first." -ForegroundColor Red
    exit 1
}

Write-Host "Installing $DisplayName..." -ForegroundColor Cyan

# 1. Stop running instance if any
Get-Process -Name "TuneshineWindows" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

# 2. Create installation directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# 3. Copy files
$TargetExe = Join-Path $InstallDir "TuneshineWindows.exe"
Copy-Item -Path $SourceExe -Destination $TargetExe -Force

$SourceIcon = Join-Path $SourceDir "icon.ico"
if (Test-Path $SourceIcon) {
    Copy-Item -Path $SourceIcon -Destination (Join-Path $InstallDir "icon.ico") -Force
}

# 4. Create Start Menu Shortcut
$StartMenuDir = [Environment]::GetFolderPath('Programs')
$WshShell = New-Object -ComObject WScript.Shell
$StartShortcut = $WshShell.CreateShortcut((Join-Path $StartMenuDir "$DisplayName.lnk"))
$StartShortcut.TargetPath = $TargetExe
$StartShortcut.WorkingDirectory = $InstallDir
$StartShortcut.IconLocation = (Join-Path $InstallDir "icon.ico")
$StartShortcut.Description = "Tuneshine Desktop Media Companion"
$StartShortcut.Save()

# 5. Create Desktop Shortcut
$DesktopDir = [Environment]::GetFolderPath('Desktop')
$DesktopShortcut = $WshShell.CreateShortcut((Join-Path $DesktopDir "$DisplayName.lnk"))
$DesktopShortcut.TargetPath = $TargetExe
$DesktopShortcut.WorkingDirectory = $InstallDir
$DesktopShortcut.IconLocation = (Join-Path $InstallDir "icon.ico")
$DesktopShortcut.Description = "Tuneshine Desktop Media Companion"
$DesktopShortcut.Save()

# 6. Register Windows Autostart
$RegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $RegPath -Name $AppName -Value "`"$TargetExe`""

Write-Host "`nInstallation successful!" -ForegroundColor Green
Write-Host "- Installed to: $InstallDir"
Write-Host "- Start Menu & Desktop shortcuts created"
Write-Host "- Windows Startup enabled"

# 7. Launch application
Write-Host "`nLaunching $DisplayName..." -ForegroundColor Cyan
Start-Process -FilePath $TargetExe

Write-Host "Done!" -ForegroundColor Green
