param(
    [string]$InstallerPath = ".tools\python-3.12.10-amd64.exe",
    [string]$TargetDir = ".tools\python-3.12.10"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$Installer = Resolve-Path -LiteralPath $InstallerPath
$Target = Join-Path $Root $TargetDir

Write-Host "Installing local Python 3.12.10..."
Write-Host "Installer: $Installer"
Write-Host "Target:    $Target"
Write-Host "PATH and file associations will not be modified."

Start-Process -FilePath $Installer.Path -ArgumentList @(
    "/quiet",
    "InstallAllUsers=0",
    "TargetDir=$Target",
    "PrependPath=0",
    "Include_launcher=0",
    "InstallLauncherAllUsers=0",
    "AssociateFiles=0",
    "Shortcuts=0",
    "Include_test=0",
    "Include_pip=1"
) -Wait -NoNewWindow

$Python = Join-Path $Target "python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Local Python install did not create expected file: $Python"
}

& $Python --version
