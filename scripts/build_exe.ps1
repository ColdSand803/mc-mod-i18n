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

function Convert-PngToIco {
    param(
        [Parameter(Mandatory)]
        [string]$PngPath,
        [Parameter(Mandatory)]
        [string]$IcoPath
    )

    if (-not (Test-Path -LiteralPath $PngPath)) {
        throw "Application icon source was not found: $PngPath"
    }

    Add-Type -AssemblyName System.Drawing
    if ($null -eq ("NativeMethods" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class NativeMethods {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool DestroyIcon(IntPtr handle);
}
"@
    }

    $iconDir = Split-Path -Parent $IcoPath
    if (-not (Test-Path -LiteralPath $iconDir)) {
        New-Item -ItemType Directory -Path $iconDir | Out-Null
    }

    $sourceImage = [System.Drawing.Image]::FromFile($PngPath)
    try {
        $size = 256
        $resized = New-Object System.Drawing.Bitmap $size, $size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($resized)
            try {
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

                $sourceSize = [Math]::Min($sourceImage.Width, $sourceImage.Height)
                $sourceX = [int](($sourceImage.Width - $sourceSize) / 2)
                $sourceY = [int](($sourceImage.Height - $sourceSize) / 2)
                $sourceRect = New-Object System.Drawing.Rectangle $sourceX, $sourceY, $sourceSize, $sourceSize
                $targetRect = New-Object System.Drawing.Rectangle 0, 0, $size, $size
                $graphics.DrawImage($sourceImage, $targetRect, $sourceRect, [System.Drawing.GraphicsUnit]::Pixel)
            }
            finally {
                $graphics.Dispose()
            }

            $iconHandle = $resized.GetHicon()
            try {
                $icon = [System.Drawing.Icon]::FromHandle($iconHandle)
                try {
                    $stream = [System.IO.File]::Open($IcoPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
                    try {
                        $icon.Save($stream)
                    }
                    finally {
                        $stream.Dispose()
                    }
                }
                finally {
                    $icon.Dispose()
                }
            }
            finally {
                [NativeMethods]::DestroyIcon($iconHandle) | Out-Null
            }
        }
        finally {
            $resized.Dispose()
        }
    }
    finally {
        $sourceImage.Dispose()
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

$BrandingConfig = Join-Path $Root "logo\branding.json"
$BrandLogo = "cat"
if (Test-Path -LiteralPath $BrandingConfig) {
    try {
        $branding = Get-Content -LiteralPath $BrandingConfig -Raw | ConvertFrom-Json
        if ($branding.brand_logo -in @("cat", "grass", "sign")) {
            $BrandLogo = $branding.brand_logo
        }
    }
    catch {
        Write-Warning "Could not read branding config, falling back to cat logo: $($_.Exception.Message)"
    }
}
$BrandLogoSources = @{
    cat = "logo\png\co1dsand_logo_cat.png"
    grass = "logo\png\minecraft.png"
    sign = "logo\png\co1dsand_logo_sign.png"
}
$IconSource = Join-Path $Root $BrandLogoSources[$BrandLogo]
$ExeIcon = Join-Path $Root "logo\app.ico"
Convert-PngToIco -PngPath $IconSource -IcoPath $ExeIcon
Write-Host "Using exe icon: $ExeIcon ($BrandLogo)"

Invoke-Python -Arguments @("-m", "PyInstaller", ".\mc-mod-i18n.spec", "--noconfirm")

$Exe = Join-Path $Root "dist\mc-mod-i18n\mc-mod-i18n.exe"
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "Build finished but exe was not found: $Exe"
}

Write-Host "Built: $Exe"
