param(
    [string]$Version = "2.0.0",
    [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Comando '$name' nao encontrado. Instale e tente novamente."
    }
}

Assert-Command "flet"
Assert-Command "iscc"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $rootDir

$buildArgs = @(
    "--project", "quiz-vance",
    "--product", "Quiz Vance",
    "--org", "br.quizvance",
    "--bundle-id", "br.quizvance.app",
    "--build-version", $Version,
    "--build-number", "1",
    "--no-rich-output",
    "--clear-cache",
    "--yes"
)

Write-Host "==> Gerando binario Windows com Flet..."
& flet build @buildArgs windows "."

$appSourceDir = $null
$appExeName = "quiz-vance.exe"

if ($LASTEXITCODE -ne 0) {
    Write-Host "==> Build Flet retornou erro. Tentando fallback com runner Release..."
    $fallbackRunnerDir = Join-Path $rootDir "build/flutter/build/windows/x64/runner/Release"
    $fallbackExe = Join-Path $fallbackRunnerDir $appExeName
    if (-not (Test-Path $fallbackExe)) {
        throw "Falha no build Windows e fallback indisponivel (quizvance.exe nao encontrado)."
    }

    # Alguns ambientes falham ao copiar essa DLL no passo INSTALL. Garante no bundle final.
    $runtimeDll = "C:\Windows\System32\vcruntime140_1.dll"
    if ((Test-Path $runtimeDll) -and (-not (Test-Path (Join-Path $fallbackRunnerDir "vcruntime140_1.dll")))) {
        Copy-Item $runtimeDll (Join-Path $fallbackRunnerDir "vcruntime140_1.dll") -Force
    }
    $appSourceDir = $fallbackRunnerDir
}

if (-not $appSourceDir) {
    $windowsBuildDir = Join-Path $rootDir "build/windows"
    if (-not (Test-Path $windowsBuildDir)) {
        throw "Diretorio de build Windows nao encontrado: $windowsBuildDir"
    }

    $exeCandidates = Get-ChildItem -Path $windowsBuildDir -Recurse -Filter *.exe |
        Where-Object { $_.Name -notmatch "(?i)setup|unins|uninstall" }

    if (-not $exeCandidates) {
        throw "Nenhum executavel encontrado apos o build."
    }

$primaryExe = $exeCandidates |
    Where-Object { $_.Name -match "(?i)^quiz-vance\.exe$" } |
        Select-Object -First 1

    if (-not $primaryExe) {
        $primaryExe = $exeCandidates | Sort-Object Length -Descending | Select-Object -First 1
    }

    $appSourceDir = $primaryExe.Directory.FullName
    $appExeName = $primaryExe.Name
}

$distDir = if ($OutputDir) { $OutputDir } else { Join-Path $rootDir "dist" }
New-Item -Path $distDir -ItemType Directory -Force | Out-Null

$safeAppSourceDir = $appSourceDir.Replace('"', '""')
$safeDistDir = $distDir.Replace('"', '""')

$issPath = Join-Path $env:TEMP "quizvance_installer.iss"
$issContent = @"
[Setup]
AppId={{3AFD4588-17E7-4B89-BD2D-73E04B4D4A4F}
AppName=Quiz Vance
AppVersion=$Version
AppPublisher=Quiz Vance
DefaultDirName={autopf}\Quiz Vance
DefaultGroupName=Quiz Vance
DisableProgramGroupPage=yes
OutputDir=$safeDistDir
OutputBaseFilename=Quiz-Vance-Setup-$Version
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "$safeAppSourceDir\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Quiz Vance"; Filename: "{app}\$appExeName"
Name: "{autodesktop}\Quiz Vance"; Filename: "{app}\$appExeName"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos adicionais:"

[Run]
Filename: "{app}\$appExeName"; Description: "Executar Quiz Vance"; Flags: nowait postinstall skipifsilent
"@

Set-Content -Path $issPath -Value $issContent -Encoding UTF8

Write-Host "==> Gerando instalador com Inno Setup..."
& iscc $issPath
if ($LASTEXITCODE -ne 0) {
    throw "Falha na geracao do instalador via Inno Setup"
}

Write-Host "Instalador gerado em: $distDir"
