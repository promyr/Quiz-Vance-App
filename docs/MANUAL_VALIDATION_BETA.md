# Validacao Manual Beta (Passo a Passo)

Objetivo: validar apenas o que ainda depende de uso manual em app/dispositivo.

Data: ____/____/______  
Responsavel: ______________________

## 1) Preparacao

1. Abrir app atualizado.
2. Garantir backend online:
   - `python scripts/smoke_go_live.py --online --backend-url https://quiz-vance-backend.fly.dev`
3. Entrar com conta real de teste (a mesma que virou premium).

Resultado esperado:
- Login normal, sem travar.
- Conta aparece premium.

## 2) Fluxo de compra e plano (manual)

1. Ir em `Plano`.
2. Verificar status atual da assinatura.
3. Clicar em `Atualizar pagamento`.
4. Voltar para `Plano`.

Resultado esperado:
- Plano permanece premium.
- Nao aparece erro de reconciliacao.

## 3) Quiz - correcoes de UI reportadas

1. Abrir `Questoes`.
2. Responder uma questao errada.
3. Confirmar resposta.

Resultado esperado:
- Texto das alternativas nao fica cortado.
- Bloco de feedback mostra `Incorreto.` e botao `Praticar o tema`.
- Ao mudar para outra tela e voltar, estado da questao segue coerente.

## 4) Flashcards continuo

1. A partir de erro no quiz, clicar em gerar flashcards.
2. Entrar no fluxo continuo.
3. Avancar ate passar de 10 cards.

Resultado esperado:
- Nao para em 10 cards.
- Novos cards sao adicionados automaticamente.
- Navegacao anterior/proximo continua fluida.

## 5) Navegacao e botao voltar

1. Navegar: `Inicio` -> `Questoes` -> `Revisao` -> `Plano`.
2. Usar botao voltar.

Resultado esperado:
- Volta para tela anterior acessada (historico), nao fixa sempre na home.

## 6) Menu lateral

1. Abrir menu lateral.
2. Verificar rotulo do antigo `Plano de estudo`.

Resultado esperado:
- Item aparece como `Cards`.

## 7) Teste em 2 dispositivos (mesma conta)

1. Dispositivo A: abrir conta, validar premium.
2. Dispositivo B: abrir mesma conta, validar premium.
3. Em um dispositivo, concluir uma acao curta (ex.: responder 1 questao).
4. No outro, atualizar tela.

Resultado esperado:
- Conta premium em ambos.
- Sem logout inesperado.
- Sem divergencia grave de estado.

## 8) Criterio de aprovacao beta

- [ ] Fluxo premium ok
- [ ] Correcoes de quiz ok
- [ ] Flashcards continuo ok
- [ ] Navegacao voltar ok
- [ ] Menu `Cards` ok
- [ ] 2 dispositivos ok

Status final: [ ] APROVADO  [ ] REPROVADO
