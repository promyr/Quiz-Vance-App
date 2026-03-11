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
    $artifactCandidates = if ($platform -eq "apk") {
        @(
            (Join-Path $workDir "build\apk\quiz-vance.apk"),
            (Join-Path $workDir "build\flutter\build\app\outputs\apk\release\app-release.apk"),
            (Join-Path $workDir "build\flutter\build\app\outputs\flutter-apk\app-release.apk")
        )
    }
    else {
        @(
            (Join-Path $workDir "build\aab\quiz-vance.aab"),
            (Join-Path $workDir "build\flutter\build\app\outputs\bundle\release\app-release.aab")
        )
    }

    $artifact = $artifactCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($artifact) {
        Write-Warning "Build returned non-zero, but artifact exists: $artifact"
        return
    }

    throw "Build failed for $platform"
}

function Resolve-BuildArtifact(
    [string]$platform,
    [string]$workDir
) {
    $candidates = if ($platform -eq "apk") {
        @(
            (Join-Path $workDir "build\apk\quiz-vance.apk"),
            (Join-Path $workDir "build\flutter\build\app\outputs\apk\release\app-release.apk"),
            (Join-Path $workDir "build\flutter\build\app\outputs\flutter-apk\app-release.apk")
        )
    }
    else {
        @(
            (Join-Path $workDir "build\aab\quiz-vance.aab"),
            (Join-Path $workDir "build\flutter\build\app\outputs\bundle\release\app-release.aab")
        )
    }

    return $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

function Write-BuildMetadata(
    [string]$artifactPath,
    [string]$platform,
    [string]$buildVersion,
    [string]$buildNumber
) {
    if (-not (Test-Path $artifactPath)) {
        return
    }

    $artifact = Get-Item $artifactPath
    $hash = (Get-FileHash $artifact.FullName -Algorithm SHA1).Hash
    $metadata = [ordered]@{
        platform = $platform
        artifact = $artifact.Name
        artifact_path = $artifact.FullName
        build_version = $buildVersion
        build_number = $buildNumber
        file_size = $artifact.Length
        last_write_time = $artifact.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        sha1 = $hash
        generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }
    $metadataPath = "$artifactPath.buildinfo.json"
    $metadata | ConvertTo-Json | Set-Content -Path $metadataPath -Encoding UTF8
    Set-Content -Path "$artifactPath.sha1" -Value $hash -Encoding ascii
    Write-Host "==> Metadados gravados em: $metadataPath"
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
    $resolvedApk = Resolve-BuildArtifact -platform "apk" -workDir $workDir
    if (-not $resolvedApk) {
        throw "Build finalizado sem localizar o artefato APK esperado."
    }
    Write-Host "==> APK gerado em: $resolvedApk"
}

if ($Target -in @("aab", "both")) {
    Invoke-FletBuild -platform "aab" -buildArgs $commonArgs -workDir $workDir
    $resolvedAab = Resolve-BuildArtifact -platform "aab" -workDir $workDir
    if (-not $resolvedAab) {
        throw "Build finalizado sem localizar o artefato AAB esperado."
    }
    Write-Host "==> AAB gerado em: $resolvedAab"
}

# Copiar artefatos do staging para o projeto raiz.
if ((-not $NoStaging) -and ($workDir -ne $projectRoot)) {
    if ($Target -in @("apk", "both")) {
        $srcApk = Resolve-BuildArtifact -platform "apk" -workDir $workDir
        if (-not $srcApk) {
            throw "Nao foi possivel localizar o APK no staging para copiar ao projeto raiz."
        }
        $dstDir = Join-Path $projectRoot "build\apk"
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
        $dstApkName = Split-Path -Leaf $srcApk
        $dstApk = Join-Path $dstDir $dstApkName
        Copy-Item $srcApk $dstApk -Force
        Write-Host "==> APK copiado para: $dstApk"
        Write-BuildMetadata -artifactPath $dstApk -platform "apk" -buildVersion $BuildVersion -buildNumber $resolvedBuildNumber
    }
    if ($Target -in @("aab", "both")) {
        $srcAab = Resolve-BuildArtifact -platform "aab" -workDir $workDir
        if (-not $srcAab) {
            throw "Nao foi possivel localizar o AAB no staging para copiar ao projeto raiz."
        }
        $dstDir = Join-Path $projectRoot "build\aab"
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
        $dstAabName = Split-Path -Leaf $srcAab
        $dstAab = Join-Path $dstDir $dstAabName
        Copy-Item $srcAab $dstAab -Force
        Write-Host "==> AAB copiado para: $dstAab"
        Write-BuildMetadata -artifactPath $dstAab -platform "aab" -buildVersion $BuildVersion -buildNumber $resolvedBuildNumber
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
