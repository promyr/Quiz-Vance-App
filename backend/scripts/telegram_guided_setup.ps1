param(
    [string]$BackendPublicUrl = "",
    [string]$BotToken = "",
    [string]$WebhookSecret = "",
    [string]$CommunityInviteUrl = "",
    [string]$DownloadUrl = "",
    [string]$SupportUrl = "",
    [string]$SalesUrl = "",
    [string]$ChatId = "",
    [switch]$SkipWebhook,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Read-IfEmpty {
    param(
        [string]$Value,
        [string]$Prompt,
        [switch]$Required
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        $Value = Read-Host $Prompt
    }
    if ($Required -and [string]::IsNullOrWhiteSpace($Value)) {
        throw "Campo obrigatorio nao informado: $Prompt"
    }
    if ($null -eq $Value) {
        return ""
    }
    return ([string]$Value).Trim()
}

function Ensure-Secret {
    param([string]$Value)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=")
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = (Resolve-Path (Join-Path $scriptDir "..")).Path
$repoRoot = (Resolve-Path (Join-Path $backendDir "..")).Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$telegramSetupScript = Join-Path $backendDir "scripts\telegram_setup.py"

if (-not (Test-Path $venvPython)) {
    throw "Nao encontrei $venvPython"
}
if (-not (Test-Path $telegramSetupScript)) {
    throw "Nao encontrei $telegramSetupScript"
}

$BackendPublicUrl = Read-IfEmpty $BackendPublicUrl "URL publica do backend (ex: https://seu-backend.fly.dev)" -Required
$BotToken = Read-IfEmpty $BotToken "Token do bot do Telegram" -Required
$WebhookSecret = Ensure-Secret $WebhookSecret
$CommunityInviteUrl = Read-IfEmpty $CommunityInviteUrl "Link do grupo Telegram" -Required
$DownloadUrl = Read-IfEmpty $DownloadUrl "Link do APK" -Required
$SupportUrl = Read-IfEmpty $SupportUrl "Link do suporte (pode repetir o grupo se quiser)" 
$SalesUrl = Read-IfEmpty $SalesUrl "Link do comercial (opcional)"
$ChatId = Read-IfEmpty $ChatId "Chat ID do supergrupo/forum (ex: -1001234567890)" -Required

$env:TELEGRAM_BOT_TOKEN = $BotToken
$env:TELEGRAM_WEBHOOK_SECRET = $WebhookSecret
$env:TELEGRAM_COMMUNITY_INVITE_URL = $CommunityInviteUrl
$env:TELEGRAM_DOWNLOAD_URL = $DownloadUrl
$env:TELEGRAM_SUPPORT_URL = $SupportUrl
$env:TELEGRAM_SALES_URL = $SalesUrl

Write-Host ""
Write-Host "Resumo da configuracao" -ForegroundColor Cyan
Write-Host "Backend: $BackendPublicUrl"
Write-Host "Grupo:   $CommunityInviteUrl"
Write-Host "APK:     $DownloadUrl"
Write-Host "Chat ID: $ChatId"
Write-Host "Secret:  $WebhookSecret"
Write-Host ""

$commands = @()
$commands += ". '$venvPython' '$telegramSetupScript' blueprint"
$commands += ". '$venvPython' '$telegramSetupScript' provision --chat-id $ChatId"
if (-not $SkipWebhook) {
    $commands += ". '$venvPython' '$telegramSetupScript' set-webhook --public-base-url $BackendPublicUrl"
}

if ($DryRun) {
    Write-Host "Dry run ativado. Estes sao os comandos que eu executaria:" -ForegroundColor Yellow
    $commands | ForEach-Object { Write-Host $_ }
    exit 0
}

Push-Location $repoRoot
try {
    & $venvPython $telegramSetupScript blueprint
    & $venvPython $telegramSetupScript provision --chat-id $ChatId
    if (-not $SkipWebhook) {
        & $venvPython $telegramSetupScript set-webhook --public-base-url $BackendPublicUrl
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Configuracao concluida." -ForegroundColor Green
Write-Host "Se quiser persistir essas variaveis no Fly, rode fly secrets set com os mesmos valores."
