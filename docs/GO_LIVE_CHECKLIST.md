# Go-live Checklist (Quiz Vance)

Atualizado em: 2026-02-27

## Atualizacoes tecnicas automaticas (2026-02-27)
- [x] Backend deployado no Fly com tuning de custo:
  - `auto_stop_machines = stop`
  - `min_machines_running = 0`
  - `auto_start_machines = true`
  - `WEB_CONCURRENCY = 1`
  - VM escalada para `512MB`
  - limites de concorrencia HTTP configurados
- [x] Health check nativo Fly em `/health/ready` (1/1 passing).
- [x] Endpoint `/health/ready` publicado e validado em producao.
- [x] Smoke online estrito (`/health` + `/health/ready`) validado.
- [x] Smoke online full (auth/plans/checkout/usage) validado em producao.

## 1) Pagamento real validado
- [x] Compra real completa em producao (manual no Mercado Pago).
- [x] Webhook recebido em `/billing/webhook/mercadopago`.
- [x] `payments` gravado e plano atualizado automaticamente.

## 2) Preco final e plano
- [x] Plano unico mensal em codigo (`premium_30`).
- [x] Preco definido em `backend/app/services.py` (`999` centavos).

## 3) Credenciais de producao
- [x] Secrets de producao presentes no Fly (`MP_ACCESS_TOKEN`, `APP_BACKEND_SECRET`).
- [x] Confirmar `APP_BACKEND_SECRET` forte (>=32 chars) no Fly.
- [x] Definir `MP_WEBHOOK_TOKEN` forte no Fly.
- [x] Rotacionar tokens expostos anteriormente.

## 4) Webhook de producao
- [x] URL do webhook configurada no painel MP:
  - `https://quiz-vance-backend.fly.dev/billing/webhook/mercadopago`
- [ ] Atualizar URL com token:
  - `https://quiz-vance-backend.fly.dev/billing/webhook/mercadopago?token=<MP_WEBHOOK_TOKEN>`
- [x] Teste com notificacao real em producao.

## 5) Estado de conta e UX de planos
- [x] Validade formatada (`dd/mm/aaaa hh:mm`).
- [x] Reconciliacao de checkout robusta e idempotente.
- [x] Fluxo mensal unico na UI.
- [ ] Validacao em 2 dispositivos com a mesma conta (manual).

## 6) Saude tecnica minima
- [x] Script de smoke pre-release: `scripts/smoke_go_live.py`.
- [x] Compilacao/validacao automatizada local.
- [ ] Smoke funcional manual no app (login/quiz/flashcards/simulado/plano/biblioteca).
  - guia: `MANUAL_VALIDATION_BETA.md`
- [ ] APK beta instalado em dispositivo limpo.

## 7) Politica comercial e legal
- [x] Estrutura legal criada em `docs/legal/`.
- [x] Secao legal/suporte no app (`/mais`) com links configuraveis por env.
- [ ] Publicar URLs finais de termos/privacidade/reembolso/suporte.

## 8) Operacao e suporte
- [x] Script suporte/reconciliacao:
  - `backend/scripts/support_tools.py`
- [x] Script de backup Postgres:
  - `backend/scripts/backup_postgres.py`
- [x] Definir rotina operacional (logs, backup e SLA) em ambiente real.
  - `docs/OPERATIONS_RUNBOOK.md`

## 9) Antifraude basico
- [x] Ativacao direta bloqueada no backend.
- [x] Webhook idempotente + reconciliacao segura.
- [x] Registro de checkout/tx/status/timestamps.

## 10) Lancamento controlado
- [ ] Beta pago com grupo reduzido (48-72h).
- [ ] So depois abrir venda geral.
