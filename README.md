# Quiz Vance App

Plataforma de estudo orientada por questoes, com IA aplicada, revisao espacada,
flashcards e simulados. O projeto adota stack final Android (cliente em Flet)
com backend de billing/entitlements em FastAPI integrado ao Mercado Pago.

## Visao Geral

- Cliente Android com experiencia focada em estudo e revisao.
- Motor de pratica com filtros avancados e fluxo de correcao.
- Revisao inteligente (SRS), caderno de erros e cards de reforco.
- Assinatura premium com reconciliacao automatica.
- Operacao pronta para beta pago com checks de saude e smoke tests.

## Rotas Principais do App

| Rota | Funcao |
|---|---|
| `/home` | Dashboard e atalhos principais |
| `/quiz` | Resolucao e correcao de questoes |
| `/revisao` | Revisao diaria, caderno de erros e marcadas |
| `/flashcards` | Estudo por cards (inclui fluxo continuo) |
| `/mais` | Configuracoes, suporte e atalhos |
| `/simulado` | Simulados com politica Free/Premium |

## Arquitetura

### Cliente (Flet)

- Ponto de entrada: `main_v2.py`
- Bootstrap de execucao: `run.py`
- UI e Design System: `ui/`
- Regras de negocio: `core/services/` e `services/`
- Persistencia local: `core/database_v2.py`
- Integracao com backend: `core/backend_client.py`
- Stack final de distribuicao: Android.

### Backend (FastAPI)

- Pasta: `backend/`
- App principal: `backend/app/main.py`
- Billing e webhooks Mercado Pago
- Entitlements premium e reconciliacao idempotente
- Deploy produtivo em Fly.io

## Estrutura do Repositorio

| Caminho | Descricao |
|---|---|
| `main_v2.py` | Aplicacao cliente (UI, navegacao e fluxos de estudo) |
| `run.py` | Inicializacao do app local |
| `core/` | Servicos, repositorios e infraestrutura do cliente |
| `services/` | Servicos complementares de dominio |
| `ui/` | Componentes visuais e views |
| `backend/` | API de billing, checkout e webhooks |
| `scripts/` | Build, smoke e automacoes operacionais |
| `docs/` | Documentacao legal e operacional |
| `tests/` | Testes automatizados |

## Requisitos

- Python 3.12+
- Pip atualizado
- Para build Android:
  - Flutter SDK
  - Java 17+
  - Android SDK
  - `flet-cli`

## Execucao Local do Cliente

```powershell
python run.py
```

Opcional (ambiente virtual):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Configuracao de Ambiente

Variaveis relevantes para execucao integrada:

- `BACKEND_URL`
- `APP_BACKEND_SECRET`
- `MP_WEBHOOK_TOKEN` (backend billing)
- `GEMINI_API_KEY`
- `OPENAI_API_KEY`

Exemplo (PowerShell):

```powershell
$env:BACKEND_URL="https://quiz-vance-backend.fly.dev"
$env:APP_BACKEND_SECRET="seu_segredo"
python run.py
```

## Build e Distribuicao

### Android (APK/AAB)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 -Target apk
```

Para detalhes de assinatura e AAB, consulte `BUILD_INSTALLERS.md`.

## Qualidade e Validacao

### Testes automatizados

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

### Smoke tecnico local

```powershell
python .\scripts\smoke_go_live.py
```

### Smoke online (producao)

```powershell
python .\scripts\smoke_go_live.py --online --backend-url "https://quiz-vance-backend.fly.dev"
python .\scripts\smoke_go_live.py --online --full --backend-url "https://quiz-vance-backend.fly.dev"
```

## Operacao e Beta

Documentos oficiais do ciclo beta:

- Checklist de go-live: `docs/GO_LIVE_CHECKLIST.md`
- Validacao manual: `docs/MANUAL_VALIDATION_BETA.md`
- Checklist de runtime UI: `docs/UI_RUNTIME_CHECKLIST.md`
- Runbook operacional: `docs/OPERATIONS_RUNBOOK.md`
- Billing backend: `backend/README.md`

## Seguranca e Confiabilidade

- Ativacao direta de plano bloqueada no backend.
- Webhook com idempotencia e reconciliacao segura.
- Check de saude `/health/ready` em producao.
- Tuning de runtime para reduzir delay e instabilidade no beta.

## Estado Atual

Projeto pronto para beta controlado, com fluxo de pagamento real validado,
conta premium ativada automaticamente e trilha de operacao documentada.
