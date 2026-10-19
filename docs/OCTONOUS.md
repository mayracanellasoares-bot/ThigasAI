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

O Hub oferece seis temas persistidos no navegador: Aurora, Claro, Oceano, Violeta, Floresta e Coral. O login e a separação do chat público permanecem inalterados.

O módulo não inicializa se faltar senha, segredo de sessão, banco ou chave de
criptografia. Todas as linhas de dados do módulo no PostgreSQL são cifradas
antes da gravação. Os logs de chamadas registram entrada, saída e resultado,
sem cabeçalhos de autorização. A sessão do proprietário dura até oito horas e
usa cookie Secure, HttpOnly, SameSite=Lax; ações no navegador também exigem
um token CSRF. Não reutilize a senha do gateway antigo.

## OAuth direto

Crie um aplicativo OAuth em cada serviço e configure o client ID e o client
secret correspondentes no Render:

| App | Variáveis | Redirect URI |
| --- | --- | --- |
| Gmail | `OCTONOUS_GOOGLE_CLIENT_ID`, `OCTONOUS_GOOGLE_CLIENT_SECRET` | `/octonous/oauth/gmail/callback` |
| Google Calendar | as mesmas credenciais Google | `/octonous/oauth/google_calendar/callback` |
| GitHub | `OCTONOUS_GITHUB_CLIENT_ID`, `OCTONOUS_GITHUB_CLIENT_SECRET` | `/octonous/oauth/github/callback` |
| Notion | `OCTONOUS_NOTION_CLIENT_ID`, `OCTONOUS_NOTION_CLIENT_SECRET` | `/octonous/oauth/notion/callback` |
| HubSpot | `OCTONOUS_HUBSPOT_CLIENT_ID`, `OCTONOUS_HUBSPOT_CLIENT_SECRET` | `/octonous/oauth/hubspot/callback` |
| Salesforce | `OCTONOUS_SALESFORCE_CLIENT_ID`, `OCTONOUS_SALESFORCE_CLIENT_SECRET` | `/octonous/oauth/salesforce/callback` |

Prefixe os caminhos acima com `https://thigas-coder-gateway.onrender.com`.
O Google pode exigir verificação do app para escopos Gmail. A integração
Notion precisa receber acesso às páginas escolhidas. O GitHub solicita o
escopo `repo`, que inclui repositórios privados; revise isso antes de
autorizar. Cada conexão pode ser removida na página Conexões.

## Uso

1. Entre em `/octonous` com a senha de proprietário.
2. Conecte os serviços OAuth que deseja usar.
3. Por padrão, o Hub usa `MARITACA_API_KEY` e `MARITACA_MODEL` do gateway, quando presentes, sem duplicar chaves. Em **Modelo e Skills** é possível selecionar Maritaca/Sabiá 4, OpenAI ou Anthropic. Para Ollama, o servidor precisa
   conseguir alcançar uma origem predefinida em `OCTONOUS_OLLAMA_ORIGIN`;
   `localhost` no Render **não é** seu computador ou celular.
4. Busque em todos os apps ou teste uma tarefa no chat.
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
