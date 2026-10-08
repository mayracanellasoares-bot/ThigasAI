# Contas e documentos no navegador

Acesse `/workspace` pelo link **Documentos e conta**. No primeiro login social, o cadastro é criado automaticamente. Google, GitHub e Facebook (Meta) são identidades separadas: não há união automática por e-mail.

## Configuração necessária antes de liberar cadastros

O código não cria aplicativos OAuth nos provedores nem contrata armazenamento. Configure no servidor:

- `THIGAS_PUBLIC_URL`: `https://thigas-coder-gateway.onrender.com` (sem barra final).
- `THIGAS_SESSION_SECRET`: segredo aleatório de pelo menos 32 caracteres; gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Nunca publique no GitHub.
- `DATABASE_URL` (**recomendado para produção**): string de conexão do PostgreSQL do Neon, obtida em **Connect** no projeto. Copie a URL completa, incluindo `sslmode=require`, e configure-a **somente em Environment no Render**. Nunca cole a senha do banco no chat, GitHub ou frontend.
- `THIGAS_ACCOUNTS_DB` (**alternativa local**): caminho SQLite, por exemplo `./data/accounts.sqlite3`. Se `DATABASE_URL` estiver configurada, o PostgreSQL tem prioridade; o SQLite não é consultado.
- `THIGAS_DATA_DIR`: diretório para documentos; use o mesmo disco, em outra subpasta, se quiser sobreviver a reinícios. Arquivos expiram após 24 horas.
- `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET`: aplicativo web Google, callback `https://thigas-coder-gateway.onrender.com/auth/callback/google`.
- `GITHUB_CLIENT_ID` e `GITHUB_CLIENT_SECRET`: OAuth App GitHub, callback `https://thigas-coder-gateway.onrender.com/auth/callback/github`.
- `META_CLIENT_ID` e `META_CLIENT_SECRET`: aplicativo Facebook Login, callback `https://thigas-coder-gateway.onrender.com/auth/callback/meta`.
- `META_GRAPH_VERSION`: versão habilitada no painel do aplicativo Meta, no formato `vNN.N`. Não há versão presumida no código.

Somente provedores inteiramente configurados aparecem. São necessários HTTPS, segredo de sessão e caminho do banco. Configure consentimento, domínio, URLs de privacidade/exclusão e disponibilidade pública nos painéis dos provedores. Aplicativos em modo de testes podem aceitar apenas testadores. Tokens sociais não são guardados no banco nem enviados ao JavaScript.

**Persistência do cadastro:** use Neon PostgreSQL via `DATABASE_URL`. A tabela `users` é criada automaticamente na primeira consulta ao banco; não é necessário executar SQL manualmente. O aplicativo não migra usuários antigos de um SQLite para o Neon: cadastros antigos exigem migração separada ou novo login. Não use SQLite no disco efêmero do Render para contas de produção.

**Persistência dos documentos:** `THIGAS_DATA_DIR` ainda usa armazenamento local temporário, mesmo quando as contas estão no Neon. Em hospedagem gratuita do Render os anexos e saídas poderão desaparecer em reinicializações/deploys, antes da retenção de 24 horas. Neon neste passo guarda somente os cadastros. Para documentos duráveis, será necessário armazenamento de objetos com controle de acesso, como R2 ou S3.

## Uso

1. Entre com um dos provedores. O primeiro acesso cria o cadastro.
2. Selecione um PDF textual, DOCX, XLSX ou PPTX de até 8 MB e clique em enviar.
3. Escreva o pedido e selecione PDF, Word ou edição do XLSX enviado.
4. Confira a prévia completa e confirme para liberar o download. Cancelar bloqueia a entrega.
5. Baixe a cópia. O original no aparelho nunca é sobrescrito.

PDF e Word recebem rascunho e revisão editorial, ambos com a fonte anexada quando selecionada. Não há pesquisa externa ou comprovação automática de fatos. Planilhas recebem um plano limitado de células, preservando as proteções de fórmulas existentes. Fonte extensa pode ser parcial. PDF digitalizado ainda não tem OCR. Não há geração de apresentações nem de planilhas do zero nesta versão.

O navegador abre o seletor nativo do computador/celular. Isso não concede leitura irrestrita, varredura de pastas ou acesso remoto ao aparelho. Não há integração Google Drive, OneDrive, WhatsApp ou Instagram. “Meta” nesta versão significa Facebook Login.

## Isolamento e limites

APIs de documentos exigem sessão e token CSRF, e downloads verificam proprietário e aprovação. Cadastro guarda identificador do provedor e nome, sem senha. Exclusão de conta remove cadastro e documentos temporários; não apaga arquivos já baixados nem revoga consentimento no provedor. Cada usuário pode manter até 20 saídas no período de retenção. A cota é verificada antes de consultar a IA e novamente ao salvar.

Ao configurar pelo menos um provedor, o chat e a extração também exigem login. Até a configuração, o chat legado continua funcionando, mas os documentos da área de conta ficam bloqueados. Histórico do chat permanece no navegador, em chaves separadas por usuário; não é sincronizado entre aparelhos e não é armazenamento criptografado. Use perfis separados em aparelhos compartilhados.

A área de conta, os documentos, as APIs e os callbacks não entram no cache offline do PWA. Fluxos OAuth reais exigem teste com credenciais de cada provedor; testes locais simulam os provedores. O timeout do Gunicorn foi elevado para 180 segundos para acomodar as duas consultas. Geração continua síncrona e pode atingir timeout do servidor em pedidos longos. Não há fila durável, OCR, antivírus ou limite global de gastos implementado nesta mudança.

Referências técnicas: [Authlib Flask](https://docs.authlib.org/en/latest/oauth2/client/web/flask.html), [GitHub OAuth](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps), [Facebook Login](https://developers.facebook.com/docs/facebook-login/).
