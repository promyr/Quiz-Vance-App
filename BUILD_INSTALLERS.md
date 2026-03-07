# Build de Instaladores (Android + Desktop)

Este projeto usa **Flet** para gerar binarios e pacotes instalaveis.

## 1) Pre-requisitos

- Python 3.13 (ou compativel com seu ambiente atual)
- Flutter SDK instalado e no `PATH`
- Java 17+ (Android toolchain)
- Android SDK + variaveis (`ANDROID_HOME` ou `ANDROID_SDK_ROOT`)
- Flet CLI:
  - `pip install --upgrade flet-cli`
- Para instalador Windows:
  - Inno Setup 6 instalado (`iscc` disponivel no `PATH`)
- Windows com **Developer Mode** habilitado (necessario para symlink durante `flutter/flet build`)

## 2) Dependencias Python

No diretorio raiz:

```powershell
pip install -r requirements.txt
pip install --upgrade flet-cli
```

## 3) Build Android

Script: `scripts/build_android.ps1`

### APK e AAB juntos

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 -Target both
```

### Apenas APK

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 -Target apk
```

### Apenas AAB

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 -Target aab
```

### Assinatura Android (release)

Defina antes de rodar:

```powershell
$env:ANDROID_SIGNING_KEY_STORE="C:\caminho\upload-keystore.jks"
$env:ANDROID_SIGNING_KEY_STORE_PASSWORD="senha_store"
$env:ANDROID_SIGNING_KEY_PASSWORD="senha_key"
$env:ANDROID_SIGNING_KEY_ALIAS="upload"   # opcional
```

## 4) Build Desktop Windows + Instalador

Script: `scripts/build_windows_installer.ps1`

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1 -Version 2.0.0
```

Saida esperada:

- Build do app: `build/windows/...`
- Instalador: `dist/Quiz-Vance-Setup-2.0.0.exe`

## 5) Variaveis de runtime importantes

- `BACKEND_URL`: URL do backend FastAPI (quando usar plano/billing remoto).
- `APP_BACKEND_SECRET`: segredo opcional para endpoints internos.

## 6) Dados locais no app instalado

O app agora salva dados em diretorio gravavel automaticamente:

- Desenvolvimento: usa `data/` e `logs/` da raiz quando gravaveis.
- App instalado: usa pasta de dados do usuario (ex.: `%APPDATA%\Quiz Vance` no Windows).

## 7) Troubleshooting rapido

- `flet build` falha por dependencias:
  - rode `flutter doctor` e corrija todos os itens criticos.
- `iscc` nao encontrado:
  - adicione o path do Inno Setup ao `PATH` (ou reinstale o Inno Setup).
- APK/AAB sem assinatura:
  - confira variaveis `ANDROID_SIGNING_*` antes de executar.
- Erro de symlink/plugins no build:
  - habilite Developer Mode no Windows (`start ms-settings:developers`) e ative "Modo de desenvolvedor".

## 8) Smoke Check pre-APK

Antes de empacotar para beta, rode:

```powershell
python .\scripts\smoke_go_live.py
```

Opcional (valida backend online):

```powershell
python .\scripts\smoke_go_live.py --online --backend-url "https://quiz-vance-backend.fly.dev"
python .\scripts\smoke_go_live.py --online --full --backend-url "https://quiz-vance-backend.fly.dev"
```

Observacao: o smoke online agora exige `GET /health/ready` por padrao.
Para backend legado sem esse endpoint, use temporariamente:

```powershell
python .\scripts\smoke_go_live.py --online --allow-missing-ready --backend-url "https://quiz-vance-backend.fly.dev"
```
