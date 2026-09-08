param(
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-NativeCommand {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE."
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "The Windows application and installer must be built on Windows."
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvRoot = Join-Path $ProjectRoot ".venv-windows"
$Python = Join-Path $VenvRoot "Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Invoke-NativeCommand -FilePath "py" -ArgumentList @("-3.12", "-m", "venv", $VenvRoot)
}

Invoke-NativeCommand -FilePath $Python -ArgumentList @("-m", "pip", "install", "--upgrade", "pip")
Invoke-NativeCommand -FilePath $Python -ArgumentList @(
    "-m", "pip", "install", "-r", (Join-Path $ProjectRoot "requirements-desktop.txt"),
    "nuitka==4.1.1", "ordered-set", "zstandard"
)
Invoke-NativeCommand -FilePath $Python -ArgumentList @((Join-Path $ProjectRoot "scripts\make_windows_icon.py"))

if (-not $Version) {
    $ProjectText = Get-Content (Join-Path $ProjectRoot "pyproject.toml") -Raw
    $Match = [regex]::Match($ProjectText, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $Match.Success) {
        throw "Could not read the application version from pyproject.toml."
    }
    $Version = $Match.Groups[1].Value
}

$StageRoot = Join-Path $env:TEMP ("waraq-windows-build-" + [guid]::NewGuid().ToString("N"))
$StageDist = Join-Path $StageRoot "dist"
$AppOutput = Join-Path $ProjectRoot "dist\windows\app"
$InstallerOutput = Join-Path $ProjectRoot "dist\windows\installer"

try {
    New-Item -ItemType Directory -Path $StageRoot | Out-Null
    Copy-Item (Join-Path $ProjectRoot "run_desktop.py") $StageRoot
    Copy-Item (Join-Path $ProjectRoot "Warraq.pyproject") $StageRoot
    Copy-Item (Join-Path $ProjectRoot "waraq") $StageRoot -Recurse

    $Template = Get-Content (Join-Path $ProjectRoot "packaging\windows\pysidedeploy.spec.in") -Raw
    $Config = $Template.Replace("@PYTHON_PATH@", $Python)
    $ConfigPath = Join-Path $StageRoot "pysidedeploy.spec"
    [System.IO.File]::WriteAllText($ConfigPath, $Config, [System.Text.UTF8Encoding]::new($false))

    Push-Location $StageRoot
    try {
        Invoke-NativeCommand -FilePath (Join-Path $VenvRoot "Scripts\pyside6-deploy.exe") -ArgumentList @(
            "-c", "pysidedeploy.spec", "--force"
        )
    }
    finally {
        Pop-Location
    }

    $Executable = Get-ChildItem $StageDist -Filter "Warraq.exe" -File -Recurse | Select-Object -First 1
    if (-not $Executable) {
        throw "pyside6-deploy did not produce Warraq.exe."
    }

    if (Test-Path $AppOutput) {
        Remove-Item $AppOutput -Recurse -Force
    }
    New-Item -ItemType Directory -Path $AppOutput | Out-Null
    Copy-Item (Join-Path $Executable.Directory.FullName "*") $AppOutput -Recurse

    $IsccCandidates = @(
        (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }
    $Iscc = $IsccCandidates | Select-Object -First 1

    if (-not $Iscc) {
        Write-Warning "Warraq.exe was built, but Inno Setup was not found. Install Inno Setup and run this script again to create the Setup wizard."
        Write-Host "Application directory: $AppOutput"
        exit 0
    }

    New-Item -ItemType Directory -Path $InstallerOutput -Force | Out-Null
    Invoke-NativeCommand -FilePath $Iscc -ArgumentList @(
        "/DAppVersion=$Version",
        "/DSourceDir=$AppOutput",
        "/DOutputDir=$InstallerOutput",
        (Join-Path $ProjectRoot "packaging\windows\Warraq.iss")
    )
    Write-Host "Windows installer: $(Join-Path $InstallerOutput ("Warraq-Setup-$Version.exe"))"
}
finally {
    if (Test-Path $StageRoot) {
        Remove-Item $StageRoot -Recurse -Force
    }
}
