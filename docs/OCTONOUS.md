# THIGAS Hub em /octonous

Módulo de automações integrado ao serviço existente em
`https://thigas-coder-gateway.onrender.com/octonous`. A interface pública do
THIGAS AI continua em Flask. O Render encerra TLS na borda, portanto este
serviço não usa Caddy. A migração integral da aplicação para
FastAPI/Next.js/Caddy não é necessária para operar esta área e não foi feita.

## Segurança e persistência

Configure no serviço `thigas-coder-gateway`:

- `OCTONOUS_OWNER_PASSWORD`: senha exclusiva de pelo menos 16 caracteres.
- `OCTONOUS_SESSION_SECRET`: segredo aleatório com pelo menos 32 caracteres.
- `OCTONOUS_ENCRYPTION_KEY`: chave Fernet persistente, gerada uma única vez:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- `OCTONOUS_DATABASE_URL`: **Internal Database URL completa** de um PostgreSQL persistente, iniciando com `postgresql://` ou `postgres://`. O nome `thigas_octonous_db` sozinho **não é** uma URL. Copie a conexão pelo dashboard privado do Render; nunca cole credenciais no GitHub. Não
  troque a chave de criptografia sem migrar os dados: tokens, planos e logs
  anteriores ficariam ilegíveis.
- `OCTONOUS_REDIS_URL`: URL interna do Render Key Value (Redis), usada para
  limitar tentativas de login entre instâncias. Se configurada e indisponível,
  o login falha fechado.
- `OCTONOUS_PUBLIC_URL`: origem pública HTTPS, por exemplo
  `https://thigas-coder-gateway.onrender.com`.
- `OCTONOUS_TICK_SECRET`: segredo aleatório de pelo menos 24 caracteres para
  o endpoint de agendamento.
- `OCTONOUS_GITHUB_WEBHOOK_SECRET`: segredo aleatório de pelo menos 24
  caracteres, também configurado no webhook do GitHub.

### Diagnóstico do banco no próprio Render

Após entrar com a senha de proprietário, o Hub consulta
`GET /octonous/api/database/status` para testar a conexão PostgreSQL.
A verificação executa apenas `SELECT 1`, sem escrever dados nem retornar
a URL, usuário ou senha. Se a conexão falhar, o Hub mostra a orientação no
topo da interface, em vez de deixar os painéis vazios e sem explicação.
Erros de operações PostgreSQL são apresentados como HTTP 503, sem
exibir credenciais ou stack traces.

O banco `thigas-octonous-db` pode estar com status "available" no Render
enquanto o serviço Flask ainda está com `OCTONOUS_DATABASE_URL` inválida.
O nome isolado `thigas_octonous_db` **não funciona**: copie a
**Internal Database URL** no painel privado do PostgreSQL e cole seu valor
completo em **thigas-coder-gateway → Environment →
OCTONOUS_DATABASE_URL**. Não envie a URL em mensagens, arquivos ou
commits. Este código não consegue extrair credenciais privadas do Render.

O Hub oferece seis temas persistidos no navegador: Aurora, Claro, Oceano, Violeta, Floresta e Coral. O login e a separação do chat público permanecem inalterados.

O módulo não inicializa se faltar senha, segredo de sessão, banco ou chave de
criptografia. Todas as linhas de dados do módulo no PostgreSQL são cifradas
antes da gravação. Os logs de chamadas registram entrada, saída e resultado,
sem cabeçalhos de autorização. A sessão do proprietário dura até oito horas e
usa cookie Secure, HttpOnly, SameSite=Lax; ações no navegador também exigem
um token CSRF. Não reutilize a senha do gateway antigo.

## Google Drive sem cliente OAuth: ponte Google Apps Script

Esta é uma alternativa à conexão OAuth direta. Não altera as integrações
existentes de Gmail e Calendar e não compartilha sessões/tokens do ChatGPT.
A ponte **não está ativa até a implantação na própria conta Google**.

1. Crie/identifique uma pasta específica no Drive. Copie apenas o ID da URL
   `https://drive.google.com/drive/folders/ID_DA_PASTA`. Pode autorizar mais
   de uma pasta, separando os IDs com vírgulas.
2. Em [script.google.com](https://script.google.com/), crie um projeto,
   substitua o `Code.gs` pelo arquivo
   [integrations/google_apps_script/Code.gs](../integrations/google_apps_script/Code.gs).
3. Em **Configurações do projeto → Propriedades do script**, crie
   `ALLOWED_FOLDER_IDS` com os IDs autorizados. Crie também `HUB_SECRET`:
   um segredo aleatório exclusivo de pelo menos 32 caracteres. Gere com
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Nunca coloque esse segredo no código nem no GitHub.
4. Execute **autorizarAcesso** no editor e conceda as permissões Google
   necessárias. Em **Implantar → Nova implantação → App da Web**, selecione
   **Executar como: eu**, **Quem tem acesso: qualquer pessoa** e implante.
   Copie o endereço HTTPS terminado em `/exec`.
5. No serviço **thigas-coder-gateway** no Render, configure:
   - `OCTONOUS_DRIVE_SCRIPT_URL`: URL HTTPS da implantação Apps Script `/exec`;
   - `OCTONOUS_DRIVE_SCRIPT_SECRET`: o mesmo valor de `HUB_SECRET`.
   Salve as variáveis e faça o deploy.
6. Abra o THIGAS Hub, entre com a senha de proprietário, consulte
   **Conexões** (Google Drive exibirá "Apps Script ativo"), e pesquise
   um nome de arquivo ou use **pastas** para listar pastas permitidas.
7. Solicite "Crie um Google Docs intitulado ... na pasta autorizada ...".
   A proposta deve ser revisada em **Aprovações**. Para uma subpasta,
   inclua `folder_id` no JSON aprovado. O script confirma a ancestralidade
   em relação a `ALLOWED_FOLDER_IDS`, inclusive em requisições adulteradas.

**Segurança:** "Qualquer pessoa" torna pública a URL do web app, mas **não
autoriza operações sem o segredo de servidor**. Não divulgue a URL/segredo,
restrinja os IDs a pastas dedicadas e rotacione o segredo se houver suspeita
de vazamento. O script executa **com suas permissões Google**, portanto
comprometer o segredo permite ler nomes de arquivos e criar documentos nas
pastas listadas; não habilite essa ponte em instalações públicas sem entender
essa delegação. Mantenha as aprovações do Hub e o login de proprietário.
A solução tem cotas do Google Apps Script e as buscas são limitadas a
50 pastas e 300 arquivos por solicitação.

O OAuth original do Google Drive permanece disponível quando as variáveis
da ponte não estiverem configuradas. Configurar a ponte dá preferência
à ponte sobre o OAuth do Drive existente. Para desligar a ponte, **remova
as duas variáveis no Render** e faça deploy; o botão de desconexão OAuth
não desativa uma configuração no servidor.

## OAuth direto

Crie um aplicativo OAuth em cada serviço e configure o client ID e o client
secret correspondentes no Render:

| App | Variáveis | Redirect URI |
| --- | --- | --- |
| Gmail | `OCTONOUS_GOOGLE_CLIENT_ID`, `OCTONOUS_GOOGLE_CLIENT_SECRET` | `/octonous/oauth/gmail/callback` |
| Google Calendar | as mesmas credenciais Google | `/octonous/oauth/google_calendar/callback` |
| Google Drive | as mesmas credenciais Google | `/octonous/oauth/google_drive/callback` |
| GitHub | `OCTONOUS_GITHUB_CLIENT_ID`, `OCTONOUS_GITHUB_CLIENT_SECRET` | `/octonous/oauth/github/callback` |
| Notion | `OCTONOUS_NOTION_CLIENT_ID`, `OCTONOUS_NOTION_CLIENT_SECRET` | `/octonous/oauth/notion/callback` |
| HubSpot | `OCTONOUS_HUBSPOT_CLIENT_ID`, `OCTONOUS_HUBSPOT_CLIENT_SECRET` | `/octonous/oauth/hubspot/callback` |
| Salesforce | `OCTONOUS_SALESFORCE_CLIENT_ID`, `OCTONOUS_SALESFORCE_CLIENT_SECRET` | `/octonous/oauth/salesforce/callback` |

Prefixe os caminhos acima com `https://thigas-coder-gateway.onrender.com`.
Para o Google Drive, habilite **Google Drive API, Google Docs API, Google Sheets API
e Google Slides API** no Google Cloud do seu OAuth Client. Inclua a URL
`https://thigas-coder-gateway.onrender.com/octonous/oauth/google_drive/callback`
entre as URIs autorizadas. O Hub solicita `drive.readonly` para localizar arquivos
já existentes e `drive.file` para criar e editar **apenas os arquivos acessíveis
por esse escopo**. O uso de `drive.readonly` pode exigir verificação de consentimento
e avaliação de segurança em aplicativos publicados externamente. O conector
Google Drive do ChatGPT **não concede tokens** automaticamente ao site Render.

O agente pode sugerir `google_drive.document.create` com `{title,body}`,
`google_drive.spreadsheet.create` com `{title,csv}` e
`google_drive.presentation.create` com `{title,outline}`.
Cada slide do `outline` começa com um título e os slides são separados por
uma linha com `---`. A criação no Google só acontece depois de uma aprovação
explícita em **Aprovações**. Em caso de falha entre a criação do arquivo e seu
preenchimento, verifique o Google Drive antes de repetir para não gerar
arquivos duplicados.

O Google pode exigir verificação do app para escopos Gmail. A integração
Notion precisa receber acesso às páginas escolhidas. O GitHub solicita o
escopo `repo`, que inclui repositórios privados; revise isso antes de
autorizar. Cada conexão pode ser removida na página Conexões.

## Uso

1. Entre em `/octonous` com a senha de proprietário. Antes, configure a **Internal Database URL** completa em `OCTONOUS_DATABASE_URL` no Render; apenas `thigas_octonous_db` não é uma string de conexão válida.
2. Conecte os serviços OAuth que deseja usar, incluindo **Google Drive** em Conexões.
3. Por padrão, o Hub usa `MARITACA_API_KEY` e `MARITACA_MODEL` do gateway, quando presentes, sem duplicar chaves. Em **Modelo e Skills** é possível selecionar Maritaca/Sabiá 4, OpenAI ou Anthropic. Para Ollama, o servidor precisa
   conseguir alcançar uma origem predefinida em `OCTONOUS_OLLAMA_ORIGIN`;
   `localhost` no Render **não é** seu computador ou celular.
4. Busque arquivos no Google Drive ou solicite no chat: "Crie um documento no Google Docs sobre [assunto]".
5. Salve o prompt como automação e selecione os apps e as ações autorizadas.
6. Revise o JSON da proposta em Aprovações. A escrita ocorre somente após
   clicar em **Aprovar e executar**.

As Skills ficam em `skills/<nome>/SKILL.md`, com `name` e `description`
no frontmatter YAML. `triggers` e `permissions` são metadados adicionais.
O arquivo de acompanhamento pós-reunião vem incluído.

## Gatilhos

- GitHub: configure um webhook de evento **Pull requests** no repositório,
  URL `/octonous/hooks/github`, Content-Type `application/json`, usando
  exatamente o segredo de `OCTONOUS_GITHUB_WEBHOOK_SECRET`.
- Reunião encerrada e página criada no Notion: a rota
  `POST /octonous/hooks/tick` consulta eventos recentes a cada execução.
  "Página publicada" não possui a mesma semântica de "página criada" na API;
  a interface indica o evento implementado com precisão.
- Tarefas diárias, semanais e sexta-feira: a mesma rota verifica horário
  na zona `America/Sao_Paulo` e evita repetição via chave única no banco.
  Para Gmail na sexta, o agente deve ter acesso à caixa e um prompt que
  especifique a busca desejada.

O endpoint tick exige cabeçalho `X-Octonous-Tick: <OCTONOUS_TICK_SECRET>`.
Programe uma execução externa a cada cinco minutos, por exemplo em um
Render Cron Job. O serviço gratuito pode adormecer; sem cron, os gatilhos de
tempo não rodam. A janela de consulta de reuniões é de 15 minutos.

## Limites

As buscas retornam trechos curtos: Notion busca títulos, HubSpot busca
contatos e Salesforce busca Account/Contact. O modelo só **propõe** uma das
cinco ações implementadas: enviar Gmail, criar issue GitHub, página Notion,
contato HubSpot ou tarefa Salesforce. Outras ações exigem adaptadores
específicos. Uma falha após aprovação pode ter resultado incerto no serviço
externo; confira o aplicativo antes de repetir manualmente.

O Render usa o serviço Flask/Python já existente. Não há processo Next.js,
FastAPI nem proxy Caddy na implantação atual. Isso mantém o chat/PWA
compatíveis e evita migrar o gateway inteiro para liberar esta área.
