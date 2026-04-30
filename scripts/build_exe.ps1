param(
    [switch]$Clean,
    [switch]$InstallPyInstaller
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

if ($InstallPyInstaller) {
    python -m pip install --upgrade pyinstaller
}

python -m PyInstaller --version | Out-Null

if ($Clean) {
    $buildDir = Join-Path $Root "build"
    $distDir = Join-Path $Root "dist"
    foreach ($path in @($buildDir, $distDir)) {
        if (Test-Path -LiteralPath $path) {
            $resolved = Resolve-Path -LiteralPath $path
            if ($resolved.Path -notlike (Join-Path $Root "*")) {
                throw "Refusing to remove path outside project: $resolved"
            }
            Remove-Item -LiteralPath $resolved.Path -Recurse -Force
        }
    }
}

python -m PyInstaller .\mc-mod-i18n.spec --noconfirm

$Exe = Join-Path $Root "dist\mc-mod-i18n\mc-mod-i18n.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "Build finished but exe was not found: $Exe"
}

Write-Host "Built: $Exe"
