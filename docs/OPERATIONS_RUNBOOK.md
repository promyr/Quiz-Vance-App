# Quiz Vance - Operations Runbook (Beta)

Atualizado em: 2026-03-08

## 1) Ambiente de producao

- Backend: `https://quiz-vance-backend.fly.dev`
- App Fly: `quiz-vance-backend` (regiao `gru`)
- Runtime custo/escala:
  - `auto_stop_machines = stop`
  - `min_machines_running = 0`
  - `auto_start_machines = true`
  - `WEB_CONCURRENCY = 1`
  - limites HTTP: `soft_limit=20`, `hard_limit=40`

## 2) Checagem diaria (5 min)

1. Estado da aplicacao:
   - `flyctl status --app quiz-vance-backend`
   - confirmar app sem falha e maquina em `gru` (pode ficar `stopped` em ociosidade).
2. Saude HTTP:
   - `python scripts/smoke_go_live.py --online --backend-url https://quiz-vance-backend.fly.dev`
3. Fluxo funcional minimo:
   - executar `--full` pelo menos 1x por dia util ou sempre que houver mudanca em auth/plans/billing:
   - `python scripts/smoke_go_live.py --online --full --backend-url https://quiz-vance-backend.fly.dev`
4. Webhook MP:
   - painel Mercado Pago > Webhooks:
     - taxa de entrega >= 99%
     - ultimos eventos `payment.updated` com status `200`.
5. Sanity check de conta:
   - se houve atividade de pagamento, abrir uma conta premium de teste e validar estado/plano rapidamente.

## 3) Observabilidade e logs

- Ultimos logs:
  - `flyctl logs --app quiz-vance-backend --no-tail`
- Foco em erros:
  - `OOM`, `Worker failed to boot`, `db_down`, `timeout`, `HTTP 5xx`.

## 4) Resposta a incidente (delay/instabilidade)

1. Confirmar saude:
   - `python scripts/smoke_go_live.py --online --backend-url https://quiz-vance-backend.fly.dev`
2. Verificar maquina:
   - `flyctl machine list --app quiz-vance-backend`
   - `flyctl machine status <machine_id> --app quiz-vance-backend`
3. Verificar causa nos logs:
   - `flyctl logs --app quiz-vance-backend --no-tail`
4. Mitigacao rapida:
   - se a maquina estiver `stopped`, validar wake-up com request em `/health` e aguardar boot.
   - reiniciar maquina: `flyctl machine restart <machine_id> --app quiz-vance-backend`
   - se OOM persistir: reduzir carga de uso no app temporariamente e subir memoria da VM.
5. Pos-incidente:
   - registrar horario, causa, acao e resultado.

## 4.1) Rotina pre-release APK

Executar antes de compartilhar qualquer APK beta novo:

1. Suite automatizada:
   - `python -m unittest discover -s tests -p "test_*.py" -v`
2. Smoke local:
   - `python scripts/smoke_go_live.py`
3. Smoke online full:
   - `python scripts/smoke_go_live.py --online --full --backend-url https://quiz-vance-backend.fly.dev`
4. Build Android:
   - `powershell -ExecutionPolicy Bypass -File .\scripts\build_android.ps1 -Target apk`
5. Instalacao em device limpo:
   - instalar o APK mais recente e rodar a trilha curta do beta
   - login
   - home
   - questoes
   - revisao
   - flashcards
   - planos
   - settings / tema
6. Gate:
   - se houver `P0` ou `P1`, nao distribuir o APK
   - se houver apenas `P2` cosmetico, registrar e seguir com beta controlado

## 5) Billing e reconciliacao

- Quando cliente pagar e plano nao atualizar:
  1. Confirmar webhook no painel MP (evento entregue 200).
  2. Rodar reconciliacao por checkout:
     - `python backend/scripts/support_tools.py reconcile-checkout --checkout-id <checkout_id>`
  3. Validar snapshot:
     - `python backend/scripts/support_tools.py checkout-snapshot --checkout-id <checkout_id>`
  4. Confirmar webhook token:
     - URL no MP deve conter `?token=<MP_WEBHOOK_TOKEN>`.

## 6) Backup e retencao

- Banco:
  - executar backup diario (dump SQL) via `DATABASE_URL` em job agendado.
  - script pronto:
    - `python backend/scripts/backup_postgres.py --output-dir backend/backups --retention-days 7`
  - manter retencao minima de 7 dias.
- Evidencias de pagamento:
  - manter `payments`, `checkout_sessions` e `webhook_events` sem limpeza no beta.

## 7) SLA beta (pratico)

- Disponibilidade alvo backend: >= 99%.
- Tempo de resposta alvo `/health`: p50 < 300ms.
- Tempo de tratamento de incidente critico: ate 30 min.

## 7.1) Registro minimo de evidencias

Para cada rotina diaria, pre-release ou incidente, registrar:

- data/hora
- responsavel
- comandos executados
- resultado (`OK`, `FAIL`, `WARN`)
- acao tomada
- proximo passo

## 8) Rotacao de segredo interno (manual controlado)

1. Gerar novo segredo forte (min. 32 chars).
2. Atualizar backend Fly:
   - `flyctl secrets set APP_BACKEND_SECRET="<novo_valor>" --app quiz-vance-backend`
3. Atualizar app cliente com o mesmo valor em `APP_BACKEND_SECRET`.
4. Validar smoke:
   - `python scripts/smoke_go_live.py --online --full --backend-url https://quiz-vance-backend.fly.dev`
5. Confirmar login/plano no app sem erro `403 forbidden`.

## 9) Autenticacao de API (usuario)

- Endpoints de usuario exigem `Authorization: Bearer <token>` emitido em `/auth/login` e `/auth/register`.
- Evitar uso de `X-App-Secret` no cliente final; manter apenas para operacao interna.
