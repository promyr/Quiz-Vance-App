param(
    [ValidateSet("apk", "aab", "both")]
    [string]$Target = "both",
    [string]$OutputDir = "",
    [string]$BuildVersion = "2.0.0",
    [string]$BuildNumber = "",
    [switch]$NoStaging
)

$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:RICH_NO_COLOR = "1"

# Try to fix PATH if needed.
if (-not (Get-Command flet -ErrorAction SilentlyContinue)) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pyPath = (Get-Command python).Source
        $scriptsDir = Join-Path (Split-Path -Parent $pyPath) "Scripts"
        if (Test-Path $scriptsDir) {
            Write-Host "Adding Scripts to PATH: $scriptsDir"
            $env:Path = "$scriptsDir;$env:Path"
        }
    }
}

# Resolve flet executable.
$FletExe = "flet"
if (-not (Get-Command flet -ErrorAction SilentlyContinue)) {
    $knownPath = "C:\Users\Belchior\AppData\Local\Python\pythoncore-3.14-64\Scripts\flet.exe"
    if (Test-Path $knownPath) {
        Write-Host "Using flet at: $knownPath"
        $FletExe = $knownPath
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $pyPath = (Get-Command python).Source
        $scriptsDir = Join-Path (Split-Path -Parent $pyPath) "Scripts"
        $dynPath = Join-Path $scriptsDir "flet.exe"
        if (Test-Path $dynPath) {
            Write-Host "Using flet via python: $dynPath"
            $FletExe = $dynPath
        }
    }
}

if (-not (Get-Command $FletExe -ErrorAction SilentlyContinue) -and -not (Test-Path $FletExe)) {
    throw "Flet not found. Verify installation."
}

function Invoke-FletBuild(
    [string]$platform,
    [string[]]$buildArgs,
    [string]$workDir
) {
    Write-Host "==> $script:FletExe build $platform"
    & $script:FletExe build @buildArgs $platform "."
    if ($LASTEXITCODE -eq 0) {
        return
    }

    # Workaround for cases where Flet returns non-zero but artifact exists.
    $artifact = if ($platform -eq "apk") {
        Join-Path $workDir "build\flutter\build\app\outputs\flutter-apk\app-release.apk"
    }
    else {
        Join-Path $workDir "build\flutter\build\app\outputs\bundle\release\app-release.aab"
    }

    if (Test-Path $artifact) {
        Write-Warning "Build returned non-zero, but artifact exists: $artifact"
        return
    }

    throw "Build failed for $platform"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")
$workDir = $projectRoot
$stagingDir = $null

if (-not $NoStaging) {
    $stagingSuffix = (Get-Date).ToString("yyMMddHHmmss")
    $stagingDir = Join-Path $projectRoot ".android_pack_src_$stagingSuffix`_$PID"
    New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

    $excludeDirs = @(
        ".venv",
        "build",
        "dist",
        ".idea",
        ".agents",
        ".git",
        ".gradle-build-cache",
        ".gradle-fresh",
        ".gradle-local",
        ".gradle-local2",
        ".gradle-local3",
        "__pycache__",
        ".android_pack_src",
        ".android_pack_src*"
    )
    $excludeFiles = @(
        "build_log.txt",
        "build_log_final.txt",
        "test_review_view.db"
    )

    $roboArgs = @(
        "$projectRoot",
        "$stagingDir",
        "/E",
        "/NFL",
        "/NDL",
        "/NJH",
        "/NJS",
        "/NP",
        "/XD"
    ) + $excludeDirs + @("/XF") + $excludeFiles

    & robocopy @roboArgs | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -gt 7) {
        throw "Falha ao preparar staging de build (robocopy exit code: $rc)."
    }
    if (-not (Test-Path (Join-Path $stagingDir "main_v2.py"))) {
        throw "Staging invalido: main_v2.py nao encontrado."
    }

    Write-Host "==> Build em staging limpo: $stagingDir"
    $workDir = $stagingDir
}

Set-Location $workDir

# Isola cache do Gradle por build para evitar corrupcao em cache global do usuario.
$gradleUserHome = Join-Path $workDir ".gradle-build-cache"
New-Item -ItemType Directory -Path $gradleUserHome -Force | Out-Null
$env:GRADLE_USER_HOME = $gradleUserHome

$resolvedBuildNumber = $BuildNumber
if (-not $resolvedBuildNumber) {
    # Android versionCode must be <= 2100000000.
    $resolvedBuildNumber = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds().ToString()
}

$commonArgs = @(
    "--project", "quiz-vance",
    "--product", "Quiz Vance",
    "--org", "br.quizvance",
    "--bundle-id", "br.quizvance.app",
    "--build-version", $BuildVersion,
    "--build-number", $resolvedBuildNumber,
    "--no-rich-output",
    "--clear-cache"
)

if ($OutputDir) {
    $commonArgs += @("--output", $OutputDir)
}

# Excluir artefatos e pastas de desenvolvimento do pacote final.
$excludePaths = @(
    ".venv",
    "build",
    "dist",
    ".idea",
    ".agents",
    ".git",
    ".gradle-build-cache",
    ".gradle-fresh",
    ".gradle-local",
    ".gradle-local2",
    ".gradle-local3",
    "__pycache__",
    "test_review_view.db",
    "build_log.txt",
    "build_log_final.txt"
)
foreach ($exclude in $excludePaths) {
    $commonArgs += @("--exclude", $exclude)
}

# Optional release signing for Play Store.
$keystore = $env:ANDROID_SIGNING_KEY_STORE
$storePwd = $env:ANDROID_SIGNING_KEY_STORE_PASSWORD
$keyPwd = $env:ANDROID_SIGNING_KEY_PASSWORD
$keyAlias = $env:ANDROID_SIGNING_KEY_ALIAS
if ($keystore -and $storePwd -and $keyPwd) {
    $commonArgs += @("--android-signing-key-store", $keystore)
    $commonArgs += @("--android-signing-key-store-password", $storePwd)
    $commonArgs += @("--android-signing-key-password", $keyPwd)
    if ($keyAlias) {
        $commonArgs += @("--android-signing-key-alias", $keyAlias)
    }
    Write-Host "==> Android signing enabled."
}
else {
    Write-Host "==> Android signing not configured. Generating local/debug-signed build."
}

$commonArgs += @("--yes")

if ($Target -in @("apk", "both")) {
    Invoke-FletBuild -platform "apk" -buildArgs $commonArgs -workDir $workDir
}

if ($Target -in @("aab", "both")) {
    Invoke-FletBuild -platform "aab" -buildArgs $commonArgs -workDir $workDir
}

# Copiar artefatos do staging para o projeto raiz.
if ((-not $NoStaging) -and ($workDir -ne $projectRoot)) {
    if ($Target -in @("apk", "both")) {
        $srcApk = Join-Path $workDir "build\apk\app-release.apk"
        if (Test-Path $srcApk) {
            $dstDir = Join-Path $projectRoot "build\apk"
            New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
            Copy-Item $srcApk (Join-Path $dstDir "app-release.apk") -Force
            $srcSha1 = "$srcApk.sha1"
            if (Test-Path $srcSha1) {
                Copy-Item $srcSha1 (Join-Path $dstDir "app-release.apk.sha1") -Force
            }
        }
    }
    if ($Target -in @("aab", "both")) {
        $srcAab = Join-Path $workDir "build\aab\app-release.aab"
        if (Test-Path $srcAab) {
            $dstDir = Join-Path $projectRoot "build\aab"
            New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
            Copy-Item $srcAab (Join-Path $dstDir "app-release.aab") -Force
        }
    }
}

Write-Host "Build Android concluido. version=$BuildVersion build=$resolvedBuildNumber"

# Limpeza best-effort do staging (pode falhar se algum processo ainda estiver segurando arquivos).
if ($stagingDir -and (Test-Path $stagingDir)) {
    try {
        cmd /c "rmdir /s /q `"$stagingDir`"" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Nao foi possivel remover staging totalmente: $stagingDir"
        }
    }
    catch {
        Write-Warning "Nao foi possivel remover staging: $stagingDir"
    }
    # Evita retornar erro quando somente a limpeza best-effort falha.
    $global:LASTEXITCODE = 0
}
