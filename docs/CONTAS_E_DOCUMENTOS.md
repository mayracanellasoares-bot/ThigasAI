# Documentos do THIGAS AI — sem cadastro

Abra `https://thigas-coder-gateway.onrender.com/workspace` ou toque em **Documentos** no menu do chat. **Não existe mais login, cadastro, botão Google, GitHub ou Meta.**

## Como funciona

1. Abra o site no celular ou computador. O navegador cria automaticamente uma sessão temporária anônima.
2. Opcionalmente selecione um documento PDF textual, DOCX, XLSX ou PPTX, de até 8 MB.
3. Escreva o pedido e escolha PDF, Word (DOCX) ou edição da planilha XLSX enviada.
4. Confira a prévia e **confirme** para habilitar o download.
5. Salve o arquivo no seu dispositivo. Nenhum documento original é alterado.

PDF digitalizado ainda não tem OCR. Para planilha XLSX, o sistema edita o arquivo enviado; não cria planilhas do zero. O conteúdo do anexo pode ser enviado à API de IA da Maritaca para gerar a resposta; não envie dados ou documentos confidenciais sem avaliar a privacidade.

## Segurança e armazenamento

- Nenhum provedor de identidade, senha, conta pessoal ou banco de cadastros é necessário.
- Cada visitante recebe um identificador aleatório em um **cookie assinado** pelo servidor. Ele separa seus arquivos dos arquivos de outros navegadores/sessões; não identifica uma pessoa e não sincroniza dispositivos.
- As rotas de documentos exigem sessão e token CSRF para modificações; downloads exigem a mesma sessão e a aprovação da saída. Não há acesso irrestrito a arquivos do aparelho.
- Os arquivos e saídas expiram em até 24 horas e são limitados a 20 saídas por sessão durante esse período.
- O armazenamento do Render gratuito é efêmero: reinícios e novos deploys podem apagar os arquivos antes do prazo de expiração. Baixe suas cópias imediatamente.
- O histórico das conversas continua no localStorage do navegador. Conversas salvas sob um identificador de conta antigo não são importadas automaticamente para evitar mesclar dados de perfis distintos.
- O site e a API /chat estão públicos. Cada requisição real à IA pode gerar custos. Recomendam-se cotas de orçamento e controle de abuso no gateway para uso público.

## Variáveis do Render

- `THIGAS_SESSION_SECRET`: **obrigatória para os documentos**. Deve conter pelo menos 32 caracteres aleatórios e permanecer apenas no Render.
- `THIGAS_DATA_DIR`: opcional, por padrão `/tmp/thigas-documents`.
- `MARITACA_API_KEY`: necessária para respostas reais da IA.

O site **não usa mais** `DATABASE_URL`, `THIGAS_ACCOUNTS_DB`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `META_CLIENT_ID`, `META_CLIENT_SECRET` ou `META_GRAPH_VERSION`. Remover essas variáveis do Render é uma etapa de administração separada; a atualização do código não apaga automaticamente o banco Neon nem seus registros anteriores.

A integração com Telegram é independente, preserva seu webhook e continua com a lista de usuários autorizados para comandos com documentos.
