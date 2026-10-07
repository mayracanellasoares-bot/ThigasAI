# Documentos reais pelo Telegram

Esta mudança mantém Flask, Render e Maritaca e acrescenta um fluxo de documentos. Não implanta ainda o ecossistema 24/7 de CRM, finanças e projetos.

## Configuração no Render

Mantenha as variáveis MARITACA_API_KEY, MARITACA_MODEL, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL e TELEGRAM_WEBHOOK_SECRET. O segredo do webhook agora é obrigatório. Use um valor aleatório seguro; nunca o publique ou envie em conversas.

Defina THIGAS_TELEGRAM_ALLOWED_USERS com os IDs numéricos dos usuários autorizados, separados por vírgula. Sem essa configuração, o chat funciona, mas as ferramentas de documentos ficam bloqueadas. Após publicar esta versão, envie /id ao bot e use o ID retornado nessa variável.

THIGAS_DATA_DIR aponta para o diretório de armazenamento SQLite. O padrão /tmp/thigas-documents é temporário e pode desaparecer no reinício/redeploy do Render. Para persistência, configure um disco persistente e aponte para um diretório dentro do ponto de montagem. O render.yaml continua no plano gratuito: esta mudança não contrata recursos nem garante disponibilidade contínua.

O registro automático do webhook inclui message e callback_query. Se você configurar o webhook manualmente, mantenha os dois tipos e o mesmo secret_token.

## Editar uma planilha

1. Abra o chat privado do bot com um usuário autorizado.
2. Envie um arquivo XLSX como documento. Limite: 8 MB.
3. Envie uma instrução, por exemplo:

/planilha Na aba Semana 2, coloque Programação Python em B5 e Google Colab em B6. Preserve as demais células.

Também é possível colocar a instrução na legenda do próprio XLSX.

4. A Maritaca recebe uma representação limitada da planilha, com nomes de abas e coordenadas das células.
5. O servidor exige um plano JSON com células e valores. Se faltar informação, devolve a pergunta em vez de criar uma edição fictícia.
6. O servidor valida o plano e prepara uma cópia local. Você recebe a revisão das células antes/depois; revisões longas recebem também um TXT completo.
7. Toque em Confirmar cópia. O bot entrega o XLSX revisado como anexo. Cancelar impede a entrega aprovada. A operação não sobrescreve o original no Google Drive, OneDrive ou aparelho.

A aprovação pertence ao mesmo usuário e chat privado, usa decisão única e expira junto com o registro após 24 horas. Se a entrega falhar, use /arquivo ID com o identificador da revisão. A ferramenta gera uma cópia com openpyxl; elementos avançados não suportados pela biblioteca podem não ser preservados. Não use o fluxo para arquivos com macros ou recursos complexos sem conferir o resultado.

## Gerar PDF

/pdf Crie um plano de aula sobre listas em Python para o 8º ano, com objetivo, atividade e avaliação.

O modelo escreve o conteúdo e ReportLab gera um PDF real, enviado pelo bot. Isso não consulta catálogo comercial, concilia valores ou envia e-mail para clientes. Revise informações e valores antes de usar o documento.

PDF, DOCX e PPTX enviados ao bot são extraídos e podem ser resumidos ou consultados. PDF digitalizado precisa de OCR, ainda não incluído. Não há edição desses anexos; /pdf gera um novo documento textual.

## Proteções e limites

- Chat privado e lista explícita de usuários para documentos.
- Webhook com comparação segura do segredo.
- Apenas arquivos PDF, DOCX, XLSX e PPTX; arquivos Office limitados também pelo tamanho expandido do ZIP.
- Até 200 alterações por revisão. Fórmulas existentes não podem ser sobrescritas. Novos textos interpretáveis como fórmulas são recusados.
- Células mescladas devem usar a célula inicial; abas e coordenadas precisam existir dentro dos limites.
- Modelos não executam Python, comandos de terminal ou código recebido em documentos.
- Até 20 registros de saída por usuário durante a retenção; a limpeza de dados expirados acontece ao acessar o armazenamento.
- /apagar_documentos remove os anexos e revisões armazenados desse usuário/chat.
- Anexos e instruções são enviados à Maritaca para interpretação. Não envie segredos ou dados que não possam ser tratados pelo provedor.

## O que falta para 24/7

O executor atual ainda fica dentro do processo web. Reinício pode interromper um processamento em andamento; não há fila durável de atualizações nem agendamento periódico. A etapa de produção contínua exige worker separado, fila durável, banco/arquivos persistentes, deduplicação de update_id, retomada e reconciliação de entregas. O plano gratuito do Render pode suspender o serviço por inatividade.

Integrações com Gmail/Outlook, CRM, Google/OneDrive, Trello/Asana e Slack/Teams continuam sendo etapas distintas. Pagamentos e envio de propostas para terceiros não estão implementados por este fluxo.

## Verificação

A suíte testa alterações reais em XLSX, preservação de fórmulas e formatação comum, proteção de células, geração de PDF legível, autorização e confirmação única. Chamadas de Maritaca/Telegram são simuladas nos testes, não validadas com contas reais.
