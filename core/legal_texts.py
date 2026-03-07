# -*- coding: utf-8 -*-
"""Textos legais padronizados para o aplicativo Quiz Vance."""

TERMOS_DE_USO = """TERMOS E CONDIÇÕES DE USO

1. SOBRE O APLICATIVO
O Quiz Vance é uma plataforma de estudos em formato de quiz interativo, focado na geração de questões por Inteligência Artificial (IA) e fixação de conteúdo para as provas e cursos da Marinha do Brasil (EMA, CIAA, entre outros). O aplicativo é uma iniciativa independente e não possui vínculo oficial com a Marinha do Brasil ou Ministério da Defesa.

2. USO DA INTELIGÊNCIA ARTIFICIAL
A geração de questões via IA está sujeita à disponibilidade das provedoras subjacentes (Google, Groq). O aplicativo utiliza uma "Cota Diária de IA" para usuários do plano Gratuito e limites balanceados ("Fair Use") para usuários Premium, com o objetivo de evitar o abuso de requisições. O usuário que inserir uma chave de API própria concorda com os termos de serviço dessa provedora externa.

3. CONTA E RESPONSABILIDADE
Você é responsável por manter a confidencialidade de suas credenciais de acesso. O Quiz Vance não se responsabiliza por perdas advindas de acessos não autorizados causados por negligência do usuário na guarda de senhas.

4. MATERIAL DO USUÁRIO
Ao fazer upload de arquivos PDF para geração de simulados, o usuário declara ter os direitos legais para fazê-lo. O Quiz Vance atua apenas como processador para extração de texto, enviando blocos de conteúdo curtos para a IA exclusivamente para fins educacionais e estudo pessoal (non-commercial fair use).

5. ASSINATURAS PREMIUM
Os planos Premium garantem cota expandida de IA, quizzes ilimitados e acompanhamento de estatísticas sem travas diárias. A renovação das assinaturas ocorre automaticamente de acordo com o período escolhido, salvo cancelamento prévio pelo usuário antes do vencimento.

6. LIMITAÇÃO DE RESPONSABILIDADE
As questões geradas via IA são baseadas em modelos probabilísticos e, embora submetidas a filtros de segurança, podem ocasionalmente conter imprecisões históricas ou teóricas. Cabe ao estudante o uso do bom senso e a consulta paralela ao material original (Bíblia da prova, apostilas, códigos) para confrontar a veracidade."""


POLITICA_PRIVACIDADE = """POLÍTICA DE PRIVACIDADE E TRATAMENTO DE DADOS

O Quiz Vance respeita sua privacidade e se compromete a proteger seus dados pessoais, em conformidade com a Lei Geral de Proteção de Dados (LGPD - nº 13.709/2018).

1. DADOS COLETADOS E FINALIDADE
Coletamos os seguintes dados essenciais para o funcionamento do app:
- E-mail e Nome/Sobrenome (via login ou Google OAuth) para identificação da conta;
- Metadados de uso do app (quantidade de questões geradas, tempo de resposta, histórico de erros/acertos) para calcular estatísticas de Gamificação (XP, nível), prover recomendações de estudo e sincronização de backup na nuvem.

2. SENHAS E CHAVES DE API
- Senhas: Não temos acesso à sua senha em texto puro; armazenamos apenas os hashes de segurança gerados pelos provedores locais ou de terceiros (Google Auth).
- Chaves de API de terceiros (Gemini/Groq): Caso você configure sua própria chave nas ferramentas avançadas, ela será encriptada ao ser salva em nosso banco de dados, sendo estritamente utilizada apenas para as aquisições do seu usuário em seu próprio dispositivo.

3. INTELIGÊNCIA ARTIFICIAL (CONTEÚDO E PDFS)
O conteúdo textual (excepcionando dados sensíveis e pessoais) gerado e enviado (seja PDFs ou filtros digitados para matérias do EMA/CIAA) será repassado, sem o vínculo do seu nome/email associado, às APIs de linguagens de Parceiros (como o Google Gemini) para a finalidade estrita de obter a geração das questões do seu simulado. Os provedores garantem, em caráter geral, que não utilizam esses prompts para treinar seus modelos de fundação públicos.

4. SEUS DIREITOS
Você possui o direito de:
1. Obter acesso pleno aos dados associados à sua conta;
2. Retificar quaisquer dados incorretos ou desatualizados em sua aba de "Perfil";
3. Solicitar a Exclusão Definitiva de sua conta e de todo o seu histórico logado (via botão dentro do app ou contato no suporte).

5. CONTATO
Qualquer solicitação, dúvida ou ocorrência sobre privacidade pode ser enviada para: quizvance@gmail.com."""


POLITICA_REEMBOLSO = """POLÍTICA DE REEMBOLSO E CANCELAMENTO

Por se tratar de um serviço majoritariamente digital ("Software as a Service"), o acesso e recebimento imediato de créditos ocorrem assim que a assinatura é compensada. Pautamo-nos pela boa-fé e pelo Código de Defesa do Consumidor.

1. DIREITO DE ARREPENDIMENTO (GARANTIA DE 7 DIAS)
Para a primeira aquisição do plano Premium, você possui o direito irrevogável de pedir o reembolso integral por insatisfação em até 7 (sete) dias corridos após a data de cobrança inicial. Bastará entrar em contato conosco pelo e-mail quizvance@gmail.com informando o seu email de cadastro e não será exigida qualquer documentação adicional — faremos o estorno sem burocracias.

2. MENSALIDADES E RENOVAÇÕES FUTURAS
Nossos planos baseiam-se em assinaturas recorrentes pré-pagas. O cancelamento interrompe cobranças *futuras*, e pode ser efetuado a qualquer hora na janela respectiva da loja de pagamento.
Seja como for, mensalidades já iniciadas que extrapolem o período legal de garantia de 7 dias da compra original não são elegíveis para reembolso pro-rata nem para devolução retroativa em caso de ausência de uso voluntário da plataforma.

3. EXCEÇÕES E BLOQUEIO DE CONTA
Não realizamos reembolso (independentemente dos 7 dias) se verificarmos objetivamente violações graves aos Termos de Uso (ex. Compartilhamento em massa de senhas que fere a segurança sistêmica; engenharia reversa para extrair as bases de dados de maneira automatizada não natural). A conta sofrerá banimento e a assinatura não terá direito a devolução sob penalidade legal aplicável.

4. PRAZO BANCÁRIO DO ESTORNO
Uma vez processado e aprovado o seu estorno do lado do Quiz Vance, a devolução real à sua conta via faturas de Cartão de Crédito ou PIX pode levar o tempo de compensação padrão de sua instituição bancária ou gateway intermédio (1 a 10 dias úteis)."""
