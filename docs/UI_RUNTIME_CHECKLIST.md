# Checklist Manual de UI (Runtime)

Objetivo: validar visualmente a aplicacao em execucao real apos as correcoes.

Data: ____/____/______  
Responsavel: ______________________

## Preparacao

1. Executar `python run.py`.
2. Fazer login com uma conta de teste.
3. Garantir que o app abre sem erro visivel no console.

## Tasks Adicionadas (2026-02-27)

1. [x] Corrigir computo da tela de estatisticas (questoes, % acerto, sequencia, revisoes e metas) lendo dados consolidados do banco e sem cache stale.
2. [x] Tornar tela de vantagens/upsell condicional no login: aparece para conta sem premium ativo, nao aparece para premium ativo.

## Criterios Globais (todas as telas)

1. Nao deve aparecer texto corrompido (ex.: `QuestÃ...`, `RevisÃ...`, `ConfiguraÃ...`).
2. Tema claro/escuro deve alternar sem quebrar layout.
3. Sidebar/menu deve navegar sem travar ou sobrepor controles.
4. Nenhum controle principal deve ficar fora da area visivel.

## Tela Login

1. Abrir rota de login.
2. Validar:
   - Labels e botoes legiveis.
   - Erros de credencial aparecem com mensagem correta.
   - Login bem-sucedido redireciona para `/home`.
3. Evidencia (OK/FAIL + observacao): ________________________________

## Tela Quiz (`/quiz`)

1. Ir para `Questoes`.
2. Validar configuracao:
   - Campo de tema.
   - Contagem de questoes.
   - Botao de filtros avancados com contador.
3. Abrir filtro avancado:
   - Buscar em secoes.
   - Selecionar chips.
   - Aplicar e confirmar resumo de filtro ativo.
4. Gerar sessao normal (nao simulado):
   - Render da questao sem bloco cinza grande indevido.
   - Navegacao `Anterior / Pular / Proxima / Confirmar resposta`.
   - `Reportar erro` marca a questao para revisao.
   - Campo de anotacao aparece compacto e funcional.
5. Corrigir:
   - Resultado exibido.
   - CTA de recomendacao coerente.
6. Evidencia (OK/FAIL + observacao): ________________________________

## Simulado (`/simulado` -> `/quiz`)

1. Abrir `Modo Simulado`.
2. Definir tempo e quantidade; iniciar.
3. Validar durante prova:
   - Contador de tempo regressivo atualizando.
   - Mapa da prova visivel e navegavel.
   - Progresso de respostas coerente.
4. Finalizar/corrigir:
   - Relatorio do simulado aparece.
   - Metricas: score, acertos, erros, puladas, tempo.
   - Blocos por disciplina/assunto.
   - CTAs: revisar erradas / adicionar ao caderno / gerar flashcards.
5. Evidencia (OK/FAIL + observacao): ________________________________

## Filtros Salvos (conta)

1. Em `/quiz`, configurar filtro + nome.
2. Clicar em `Salvar filtro`.
3. Validar:
   - Filtro aparece no dropdown de salvos.
   - Aplicar filtro salvo restaura valores (incluindo avancados).
   - Excluir filtro remove do dropdown.
4. Fluxo sem login:
   - Ao tentar salvar sem conta, deve orientar login.
5. Evidencia (OK/FAIL + observacao): ________________________________

## Flashcards (`/flashcards`)

1. Gerar ou entrar com flashcards seedados por erro de questao.
2. Validar:
   - Cartao renderiza corretamente frente/verso.
   - Acoes `Lembrei` e `Rever` funcionam.
   - Navegacao `Anterior/Proximo` funcional.
3. Evidencia (OK/FAIL + observacao): ________________________________

## Resultado Final

1. Status final: [ ] APROVADO  [ ] REPROVADO
2. Bugs encontrados:
   - ________________________________________________________________
   - ________________________________________________________________
   - ________________________________________________________________

3. Prioridade de correcao:
   - P0: ____________________________________________________________
   - P1: ____________________________________________________________
   - P2: ____________________________________________________________
