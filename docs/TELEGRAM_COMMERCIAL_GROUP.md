# Telegram Comercial do Quiz Vance

## Objetivo

Usar o Telegram como canal principal de aquisicao, suporte e distribuicao do app
enquanto o Quiz Vance ainda nao estiver listado nas lojas.

## Estrutura recomendada

Crie um supergrupo com modo forum ativado e deixe o bot como administrador.

Topicos recomendados:

- `Atualizacoes`
- `Comece aqui`
- `Bate-papo`
- `Resultados`
- `Suporte/Ajuda`
- `Feedbacks/Inovacoes`

## Papel de cada topico

- `Atualizacoes`: anuncios do app, APK novo, mudancas de oferta e avisos oficiais.
- `Comece aqui`: onboarding, regras, download e como assinar.
- `Bate-papo`: conversa livre entre membros.
- `Resultados`: prova social, depoimentos e prints de evolucao.
- `Suporte/Ajuda`: instalacao, login, pagamento, bugs.
- `Feedbacks/Inovacoes`: ideias de features, campanhas e melhorias.

## Fluxo comercial sugerido

1. Usuario chega no bot via link publico.
2. Bot entrega menu com `Baixar app`, `Oferta beta`, `Ver resultados`, `FAQ rapido`, `Entrar na comunidade` e `Falar com suporte`.
3. Usuario entra no grupo e cai no topico `Comece aqui`.
4. Se houver interesse de compra, o bot ou atendimento humano leva para checkout.
5. Quando o checkout iniciar ou for aprovado, o backend pode disparar alerta no Telegram para acompanhamento comercial.

## Variaveis de ambiente

Backend:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_COMMUNITY_INVITE_URL`
- `TELEGRAM_SUPPORT_URL`
- `TELEGRAM_DOWNLOAD_URL`
- `TELEGRAM_SALES_URL`
- `TELEGRAM_GROUP_TITLE`
- `TELEGRAM_GROUP_DESCRIPTION`
- `TELEGRAM_ALERT_CHAT_ID`
- `TELEGRAM_ALERT_THREAD_ID`

## Provisionamento

Depois de criar manualmente o supergrupo no Telegram e ativar o modo forum:

```powershell
cd backend
python scripts/telegram_setup.py me
python scripts/telegram_setup.py blueprint
python scripts/telegram_setup.py provision --chat-id -100SEU_CHAT_ID
python scripts/telegram_setup.py set-webhook --public-base-url https://quiz-vance-backend.fly.dev
```

Tambem existe operacao remota pelo backend com `X-App-Secret`:

- `POST /telegram/group/provision`
- `POST /telegram/webhook/configure`
- `POST /telegram/webhook`

## Observacao importante

O bot consegue organizar o forum, criar topicos, responder comandos e receber o
webhook. A criacao inicial do supergrupo e a ativacao do modo forum precisam ser
feitas no proprio Telegram.

Playbook de crescimento: `docs/TELEGRAM_GROWTH_PLAYBOOK.md`
Refresh operacional: `docs/TELEGRAM_REFRESH_OPERACIONAL.md`
