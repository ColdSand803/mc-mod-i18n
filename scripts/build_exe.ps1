param(
    [switch]$Clean,
    [switch]$InstallPyInstaller,
    [switch]$InstallDesktopDeps
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$RepoPython = Join-Path $Root ".tools\python-3.12.10\python.exe"
if (Test-Path -LiteralPath $RepoPython) {
    $Python = (Resolve-Path -LiteralPath $RepoPython).Path
}
else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python was not found. Install Python 3.10-3.12 or place it at .tools\python-3.12.10\python.exe."
    }
    $Python = $pythonCommand.Source
}

function Invoke-Python {
    param(
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed ($LASTEXITCODE): $Python $($Arguments -join ' ')"
    }
}

Write-Host "Using Python: $Python"

if ($InstallPyInstaller) {
    Invoke-Python -Arguments @("-m", "pip", "install", "--upgrade", "pyinstaller")
}

if ($InstallDesktopDeps) {
    Invoke-Python -Arguments @("-m", "pip", "install", ".[desktop]")
}

$webviewCheck = & $Python -c "import webview" 2>&1
if ($LASTEXITCODE -ne 0) {
    $detail = ($webviewCheck | Out-String).Trim()
    $pipDesktopHint = "`"$Python`" -m pip install `".[desktop]`""
    throw "pywebview is missing from $Python. Run .\scripts\build_exe.ps1 -InstallDesktopDeps -Clean or $pipDesktopHint and rebuild.`n$detail"
}

& $Python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not available in $Python. Run .\scripts\build_exe.ps1 -InstallPyInstaller -Clean or `"$Python`" -m pip install --upgrade pyinstaller."
}

if ($Clean) {
    $buildDir = Join-Path $Root "build"
    $distDir = Join-Path $Root "dist"
    foreach ($path in @($buildDir, $distDir)) {
        if (Test-Path -LiteralPath $path) {
            $resolved = Resolve-Path -LiteralPath $path
            if ($resolved.Path -notlike (Join-Path $Root "*")) {
                throw "Refusing to remove path outside project: $resolved"
            }
            try {
                Remove-Item -LiteralPath $resolved.Path -Recurse -Force
            }
            catch {
                $detail = $_.Exception.Message
                throw "Failed to clean build artifact path: $($resolved.Path)`nClose any running mc-mod-i18n.exe, Python, or Explorer window using files under dist/build, then retry.`n$detail"
            }
        }
    }
}

Invoke-Python -Arguments @("-m", "PyInstaller", ".\mc-mod-i18n.spec", "--noconfirm")

$Exe = Join-Path $Root "dist\mc-mod-i18n\mc-mod-i18n.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "Build finished but exe was not found: $Exe"
}

Write-Host "Built: $Exe"
