# THIGAS AI

Assistente de programação distribuído como site e PWA instalável pelo navegador.

**Site:** https://thigas-coder-gateway.onrender.com/

O site usa o layout retro CRT/ASCII, com quatro temas, efeitos opcionais e sons desligados por padrão. As respostas são geradas pela Maritaca AI através do servidor; não há respostas simuladas.

## Conversa no navegador

- Escreva uma pergunta ou cole código. Enter envia; Shift+Enter insere uma linha.
- O clipe lê arquivos de texto/código UTF-8 de até 256 KiB. Mensagem e anexo juntos devem ter até 60.000 caracteres. Imagens, PDF, ZIP e modelos não são interpretados.
- Blocos de código podem ser copiados ou baixados. Nenhum código gerado é executado pelo site.
- Histórico e preferências são salvos somente no navegador atual. LIMPAR apaga a conversa local. Não há sincronização com o histórico do Telegram.
- `/help` mostra os comandos e informações de privacidade.

O conteúdo enviado e parte do histórico são encaminhados à Maritaca. Não envie senhas, chaves ou dados sensíveis. A API consome o saldo do responsável pela chave; publicar o site não torna a inferência gratuita. A hospedagem gratuita pode demorar para despertar.

## Instalar o PWA

Abra o site no Chrome, Edge, Samsung Internet ou Safari e use o botão **INSTALAR**. Quando o navegador não oferecer o prompt automático, o botão mostra as instruções do sistema.

- **Android/Chrome:** menu ⋮ → Instalar aplicativo ou Adicionar à tela inicial.
- **Windows/Chrome ou Edge:** botão de instalação na barra de endereço.
- **iPhone/iPad:** Safari → Compartilhar → Adicionar à Tela de Início.

Por segurança, a interface protegida não é mais armazenada offline. O PWA pode abrir a tela de acesso sem conexão, mas o login, o chat e os documentos precisam de internet. O histórico local anterior não é apagado automaticamente. **Novas respostas exigem internet.** Perguntas não são reenviadas automaticamente quando a conexão volta.

Uma nova versão oferece **ATUALIZAR** sem recarregar a conversa automaticamente. Se houver texto não enviado, anexo ou consulta em andamento, o usuário confirma o descarte antes de recarregar. O histórico já salvo permanece.

O projeto Android, arquivos Gradle e workflow de geração do APK foram retirados da branch principal. Isso não desinstala aplicativos já existentes nos aparelhos nem apaga commits históricos. O workflow **Retirar APKs antigos** remove somente os artefatos `THIGAS-Coder-APK` gerados até 03/10/2026 às 00:34:57 no horário de Brasília, usando uma permissão temporária do Actions e sem chaves pessoais. Ele dispara ao alterar o próprio arquivo; o build Android não é retomado.

## Servidor

O servidor Flask em `server/app.py` oferece:

- `GET /`: interface do chat.
- `GET /manifest.webmanifest`: identidade e ícones do PWA.
- `GET /sw.js`: service worker com escopo da raiz.
- `GET /api`: informações JSON do gateway (antes disponíveis na raiz).
- `GET /health`: estado do serviço.
- `POST /chat`: `{ "message": "...", "history": [] }` → `{ "answer": "...", "model": "..." }`.
- `POST /telegram/webhook`: webhook do Telegram, preservado.

As chaves continuam exclusivamente nas variáveis de ambiente do Render, nunca no JavaScript ou repositório. A rota `/chat` exige sessão autenticada quando a senha única está configurada. O serviço não inicia com acesso público caso falte a senha. Ainda é recomendado aplicar cotas e limites de gastos no provedor. O service worker guarda somente recursos públicos da interface; não intercepta nem coloca mensagens, respostas ou anexos da API no cache.

## Testes locais

```sh
pip install -r server/requirements.txt
python -m unittest discover -s server/tests -v
node --test server/tests/*.test.cjs
```

Os testes usam respostas simuladas **apenas na suíte de testes**, sem consumir a API. Para iniciar localmente:

```sh
python server/app.py
```

Abra `http://127.0.0.1:7860`. Configure `MARITACA_API_KEY` no ambiente para respostas reais. Telegram é opcional no teste local.

O workflow **Verificar PWA THIGAS** executa os testes no GitHub a cada mudança no servidor, ícones ou configuração da suíte.

## Ícones e atualizações

`node scripts/build_pwa_icons.cjs` regenera os ícones de 192×192 e 512×512. Os PNGs prontos ficam versionados para evitar dependências na hospedagem. Consulte `LEIA-ME.md` para o guia de uso.

Ao mudar a interface, altere a versão do cache em `server/static/sw.js`, os parâmetros de versão do HTML e a lista `APP_SHELL` juntos. Somente caches com prefixo `thigas-pwa-` são limpos; o histórico em localStorage não é removido pela atualização.

## Documentos pelo Telegram

O bot agora pode receber XLSX e preparar uma cópia editada por `/planilha`, com revisão e botões de confirmação. `/pdf` gera um PDF real. `/id` informa o ID para configurar a lista de usuários autorizados. Veja [configuração e limites](docs/TELEGRAM_DOCUMENTOS.md).

As ferramentas exigem `THIGAS_TELEGRAM_ALLOWED_USERS` e `TELEGRAM_WEBHOOK_SECRET`. O armazenamento temporário e o plano gratuito atuais não constituem uma implantação 24/7; o guia descreve os componentes que ainda faltam.

## Documentos no navegador — sem cadastro individual

A área `/workspace` abre após informar **a mesma senha única de acesso**, sem cadastro individual ou OAuth do Google, GitHub e Meta. O visitante pode enviar arquivos PDF, DOCX, XLSX e PPTX (até 20 MB), gerar PDF/Word, revisar uma planilha XLSX enviada e confirmar o download.

Os arquivos temporários são segregados por uma sessão anônima assinada no navegador (cookie HTTP-only, SameSite=Lax, Secure e token CSRF). É necessário manter `THIGAS_SESSION_SECRET` (mínimo 32 caracteres) configurado no Render para essa proteção. A sessão e os arquivos expiram em até 24 horas; como `THIGAS_DATA_DIR` permanece no disco efêmero do Render, podem se perder antes. O histórico do chat é guardado no navegador, sem sincronização.

O código **não usa mais** `DATABASE_URL`, Neon, OAuth ou a tabela antiga de usuários. Os cadastros antigos no Neon **não foram apagados**; nenhuma exclusão de banco foi executada. As variáveis antigas do Render podem ser retiradas manualmente após validar o deploy. Consulte [documentação de uso e privacidade](docs/CONTAS_E_DOCUMENTOS.md).

## Modelos maiores em nuvem (8B ou 20B)

O THIGAS AI é um gateway de chat, não o próprio modelo de linguagem. Mudar de um modelo 3B para 8B ou 20B significa conectar um modelo diferente, não aumentar os pesos de um modelo existente. O Render executa o backend Flask e o PWA; a inferência do modelo de 20B ocorre no provedor externo da nuvem.

O chat mantém o modo Rápido (Maritaca Sabiá 4) como padrão e agora pode oferecer modos Nuvem (GPT-OSS 20B na Groq) e Sabiá 4 Thinking BR-SP (Maritaca). Os modos pagos ficam desabilitados por padrão, inclusive na interface pública.

Para ativar o GPT-OSS 20B, configure em Render > Environment:

    THIGAS_CLOUD_API_KEY=<SUA_CHAVE_GROQ>
    THIGAS_CLOUD_ENABLED=true
    THIGAS_CLOUD_MODEL=openai/gpt-oss-20b
    THIGAS_CLOUD_URL=https://api.groq.com/openai/v1/chat/completions

Para ativar também a Maritaca Thinking, mantenha a MARITACA_API_KEY já configurada e defina THIGAS_ENABLE_THINKING=true e MARITACA_THINKING_MODEL=sabia-4-thinking-br-sp.

Compatibilidade: POST /chat aceita o modo opcional fast, cloud ou thinking. Sem modo informado, usa fast, preservando Telegram e clientes antigos. GET /api indica disponibilidade dos modos sem retornar credenciais. A API Key da nuvem fica apenas no backend.

Para um modelo 8B, a mesma integração suporta um endpoint compatível com Chat Completions, mas altere THIGAS_CLOUD_MODEL e THIGAS_CLOUD_URL para IDs e URLs verificados no provedor escolhido. Não use o antigo llama-3.1-8b-instant da Groq: ele foi descontinuado em agosto de 2026. O modelo 20B atualmente documentado é openai/gpt-oss-20b.

Segurança: o chat exige a senha única compartilhada e não usa cadastro individual. Quem conhece essa senha poderá consumir créditos pelo endpoint /chat. Configure cotas e alertas no provedor e adicione rate limiting/autorização robustos antes de divulgar o serviço. Ativar o modo não torna as requisições gratuitas. Testes unitários não validam acesso real nem cobrança da API.

Referências: https://console.groq.com/docs/models e https://console.groq.com/docs/api-reference e https://docs.maritaca.ai/pt/modelos.

## Assistente de documentos e prompt de sistema

O THIGAS AI possui instruções de sistema ampliadas: ajuda com programação, revisão textual, análise de documentos, explicações e respostas em português brasileiro, com limites claros e sem simular operações externas.

Em **Documentos** (`/workspace`), o usuário pode enviar PDF, DOCX, XLSX ou PPTX de até 20 MB, pedir uma revisão ou um documento novo e receber uma **cópia real**, após conferir a prévia e aprovar o download.

- **PDF (.pdf)**: novo documento gerado pelo servidor com ReportLab.
- **Word (.docx)**: novo documento editável, gerado com python-docx.
- **Excel (.xlsx)**: revisão de planilha **anexada** com alterações limitadas a células autorizadas. Preserva fórmulas, formato e o arquivo original. Não cria uma planilha nova sem arquivo base.
- **PowerPoint (.pptx)**: cria apresentação nova e editável com python-pptx a partir de texto revisado. Não mantém o design original do PPTX enviado.

A extração de texto não equivale a interpretação visual de páginas digitalizadas. Não há OCR automático, execução de código produzido pelo modelo ou verificação de fatos em fontes externas. A prévia e a aprovação são exigidas antes da entrega. O armazenamento é temporário e separado por sessão, sem cadastro.

## Tokens e contador real de consumo

- Motor: Maritaca `sabia-4`, cujo limite documentado é até 32K tokens de saída; THIGAS solicita **até 16.384 tokens** de saída em cada requisição. Variável `MARITACA_MAX_TOKENS=16384` (o servidor impede valores acima de 16.384 e usa esse padrão se estiver ausente ou for inválido).
- A resposta de `POST /chat` inclui `usage.prompt_tokens` (enviados), `usage.completion_tokens` (recebidos), `usage.total_tokens` (total consumido), `max_output_tokens` e `finish_reason`. Todos os contadores vêm diretamente da resposta do provedor externo selecionado. Sem `usage`, os campos retornam `null` e o navegador mostra **— / não informado**; **não há estimativa por caractere ou soma fictícia**.
- O painel de tokens mostra **apenas a última requisição de chat**, não uma soma entre múltiplas chamadas. Documentos no `/workspace` e comandos Telegram preservam o formato anterior e não exibem painel próprio de tokens.
- O navegador pode encaminhar até 40 mensagens do histórico local para o backend, que seleciona **no máximo 12 mensagens** relevantes/recentes, dentro do orçamento de 60 mil caracteres incluindo a pergunta (além do prompt de sistema). Este valor **não é** uma medição de tokens.
- Foram aumentados os tempos de espera para chamadas longas: timeout de leitura da API (300 s), cancelamento visual da conversa (325 s) e worker Gunicorn (660 s). Isso **não garante** que qualquer resposta de 16 mil tokens concluirá dentro desses prazos.
- Para o site em produção, confirme no Render **Environment** que `MARITACA_MAX_TOKENS` não tenha um valor antigo como `3072`. O `render.yaml` define 16.384 para novos Blueprints, mas uma variável manual existente pode ter precedência.
- Cada resposta pode consumir mais tokens e saldo da Maritaca. Considere configurar limite de gastos e controle de uso por origem no backend, pois o chat permanece público e sem cadastro.

Fontes: [Modelos Maritaca](https://docs.maritaca.ai/pt/modelos), [Resposta e contadores de tokens](https://docs.maritaca.ai/api/pt/completion-response).


## Identidade capivara e análise de links

A interface responsiva do THIGAS AI usa a capivara fornecida como marca visual e tons areia/verde-oliva, com acesso ao chat, documentos e ao novo verificador de links em `/links`.

**Verificação de sites**: a rota `POST /link/check` recebe `{ "url": "https://exemplo.com", "analyze": false }` e retorna HTTP, título, texto limitado e redirecionamento (não seguido automaticamente). Para análise do conteúdo com IA, envie `analyze: true`; o texto da página é tratado como fonte não confiável e resumido pelo modo escolhido (Rápido como padrão). Apenas HTTP/80 e HTTPS/443 para IPs públicos são permitidos. Conexões usam IP validado, verificação de certificado para HTTPS, tempo limite, máximo de 256 KiB de resposta, nenhuma execução de scripts e 8 solicitações por minuto por origem. Não há garantia de que o site seja seguro, genuíno ou livre de fraude. Sites JavaScript podem não expor conteúdo legível.


## Integração do layout Mini Nano

A folha `server/static/mini-nano-theme.css` incorpora e adapta as regras visuais do projeto [THIGAS Mini Nano](https://github.com/thiagollipe-web/thigasai_mini_nano), mediante autorização do titular comunicada pelo usuário. Este estilo carrega por último, com cabeçalho limpo, chat centralizado de 810 px, sugestões em duas colunas e compositor responsivo em tons off-white e verde-oliva. Os contratos JavaScript, Flask, documentos, menus +, ditado, histórico e PWA do THIGAS AI permanecem os do aplicativo principal; não há dependência do backend ou das credenciais do Mini Nano.


## Histórico lateral de conversas (outubro de 2026)

O chat exibe histórico na lateral esquerda no desktop e um painel recolhível no celular, com grupos Hoje / Ontem / Últimos 7 dias / Anteriores, busca por título, renomeação, exclusão e Nova conversa. As conversas ficam no `localStorage` deste navegador, limitadas a 30 conversas com 40 mensagens cada; **não sincronizam entre aparelhos**. O aplicativo omite o conteúdo delimitado por `[ARQUIVO: ...]` e `[FIM DO ARQUIVO]` antes de armazenar mensagens localmente; mensagens antigas são saneadas ao carregar. Não inclua segredos nas perguntas de texto normal.

O ícone SVG foi atualizado com moldura coral e capivara, como o visual aprovado. Os ícones PNG de 192 e 512 pixels foram regenerados com o mesmo símbolo coral para instalação no PWA. Aparelhos que já instalaram o aplicativo podem precisar atualizar ou reinstalar o atalho para ver o novo ícone.


## Correção de confiabilidade do chat

- O servidor limita o histórico e a pergunta a 60 mil caracteres quando a pergunta cabe nesse orçamento; fontes web adicionadas são limitadas separadamente pelo leitor. Esse limite é uma proteção por caracteres, não uma contagem de tokens. O sistema fica fora desse orçamento.
- Mensagens antigas são removidas primeiro, sem iniciar o histórico com uma resposta órfã. Uma pergunta ainda pendente duplicada no fim do histórico não é enviada duas vezes.
- O prompt prioriza a solicitação atual, correções e encerramento da resposta, sem exigir uma apresentação a cada interação. Isso não garante ausência de repetição pelo modelo.
- Se `THIGAS_ENABLE_THINKING=true` e houver chave Maritaca, `thinking` usa `MARITACA_THINKING_MODEL`. Caso contrário, preserva o provedor de nuvem habilitado, como nas versões anteriores. `cloud` continua exclusivo da nuvem.
- `gunicorn.conf.py` aplica uma instância com duas threads, timeout de 660 segundos e encerramento gracioso de 60 segundos, inclusive ao comando Render sem esses argumentos. Argumentos explícitos do Gunicorn têm precedência.
- JSON inválido é recusado com HTTP 400; modos inválidos são recusados antes de acessar links.


## Senha única do site e do PWA

O mesmo login por senha é aplicado ao site no navegador e ao PWA instalado no Android, iOS ou desktop, **sem cadastro individual**. O botão **Instalar aplicativo** também aparece na tela pública `/entrar`. Depois de instalar, o usuário informa a senha antes de usar o chat ou os documentos. O acesso é validado pelo servidor, não por JavaScript.

Configure **antes de incorporar esta mudança à main** no Render → serviço `thigas-coder-gateway` → Environment:

- `THIGAS_ACCESS_PASSWORD`: uma senha forte e exclusiva, de 12 a 256 caracteres (marque como segredo no painel; **não publique no GitHub ou na conversa**).
- `THIGAS_SESSION_SECRET`: segredo de assinatura já utilizado pelos documentos, com pelo menos 32 caracteres. **Preserve o valor atual** para não invalidar as sessões existentes sem necessidade.

Depois configure essas variáveis no serviço já existente e publique a nova versão. A aplicação falha de forma fechada caso falte a senha ou o segredo de sessão, sem abrir chat nem documentos ao público. Rotas de saúde, manifesto, ícones, tela de acesso e webhook Telegram (com sua própria chave) continuam acessíveis. Há limitação básica em memória de tentativas de senha: dez falhas por IP em cinco minutos; não substitui um rate limiter compartilhado para múltiplos workers ou instâncias.

A sessão é mantida em cookie assinado, HttpOnly, Secure e SameSite=Lax e expira em até 24h; trocas de senha revogam os cookies autenticados. O botão **Sair** encerra a sessão no servidor. O histórico anterior permanece no armazenamento local do aparelho: uma senha compartilhada **não separa conversas por pessoa** e não impede leitura local por quem tem acesso ao navegador/dispositivo. Use aparelho e perfil de navegador confiáveis.

O service worker `v18-auth` elimina caches antigos do próprio PWA e nunca armazena páginas privadas, respostas ou documentos. A tela de login pode abrir offline, porém não é possível autenticar sem conexão. `/chat`, `/workspace`, `/links`, `/api`, `/document/extract` e demais endpoints privados exigem a sessão, inclusive por requisições diretas fora da interface. `MARITACA_API_KEY` e `THIGAS_ACCESS_PASSWORD` são credenciais **diferentes** e permanecem somente no servidor.


## Evolução cognitiva verificável — baseline PT-BR

A evolução cognitiva do **gateway** começa com um verificador aritmético restrito em `server/cognitive_math.py`: expressões simples são calculadas sem API, usando frações exatas e AST de operações permitidas. Problemas textuais, programação e perguntas não reconhecidas seguem pelo provedor externo normal. O retorno direto sinaliza `model: thigas-arithmetic-verifier-v1` e contadores de tokens nulos, sem fingir inferência neural.

Há três conjuntos separados em `eval/train.jsonl`, `eval/val.jsonl` e `eval/test.jsonl`. Para validar os casos sem gastar créditos:

```sh
python scripts/evaluate_cognition.py
python -m unittest discover -s server/tests -v
```

Para obter um **baseline real**, veja [a auditoria e as instruções de avaliação](docs/EVOLUCAO_COGNITIVA_BASELINE.md). A coleta remota exige uma opção explícita que confirma possíveis custos. Não há alegação de treinamento próprio ou ganho percentual medido nesta etapa: os pesos, o tokenizer e os checkpoints da LLM não estão presentes neste repositório.


## Retenção de contexto e avisos de qualidade (v2)

O backend agora considera até 40 mensagens anteriores recebidas do cliente, prioriza as trocas mais recentes e pode recuperar uma troca antiga quando ela compartilha termos significativos com a pergunta atual. Mantém a ordem original, pares íntegros e limite de até 12 mensagens na inferência. **Não adiciona memória permanente** nem altera pesos da LLM.

O backend também pode devolver `quality_flags` quando encontra repetição contígua anormal, saída truncada, um bloco de código não fechado ou possível sintaxe Python inválida. São alertas de revisão apresentados no chat, e **não** uma verificação geral de veracidade; não executam o código.

Para comparar o recorte anterior com a seleção atual, sem API externa:

```sh
python scripts/bench_context_retention.py
```

Para avaliar a acurácia **real** nas duas versões, é necessário autenticação e autorização de custos do provedor. Há um comparador para resultados JSONL: `scripts/compare_cognition.py --before baseline_test.jsonl --after candidato_test.jsonl`. Consulte [o relatório de contexto e confiabilidade](docs/EVOLUCAO_COGNITIVA_V2.md).


## Esforço alto: configuração real para programação

O modo avançado utiliza o provedor configurado no servidor. Quando o modelo ativo for GPT-OSS 20B/120B **na Groq**, o modo `thinking` agora envia `reasoning_effort=high`; o modo `cloud` usa `medium`. Com Sabiá Thinking o parâmetro exclusivo da Groq não é enviado. O chat mostra o modelo efetivamente selecionado e não afirma que um modelo externo compilou ou executou código.

Pedidos de programação recebem critérios adicionais de qualidade. O verificador estático avisa sobre sintaxe Python e JSON potencialmente inválida, mas não valida a lógica do programa. O botão **REVISAR CÓDIGO** prepara um pedido de correção para revisão e envio pelo usuário; ele não consome créditos até que o usuário envie.

Consulte [o diagnóstico e a implementação](docs/ESFORCO_ALTO_CODIGO.md).


## Pesquisa online pelo botão 🌐

O botão **🌐**, imediatamente ao lado do microfone, ativa/desativa a pesquisa online na próxima mensagem. Quando está ativo, fica destacado em verde. Não realiza consulta ao clicar: a busca só ocorre quando o usuário envia uma pergunta. O botão fica desabilitado durante uma requisição e volta a ficar disponível no fim.

- **Funcionamento gratuito padrão:** pesquisa até 5 resultados na API pública da **Wikipédia em português**, sem chave adicional. É uma busca enciclopédica, **não** uma busca irrestrita na web. As fontes e links são exibidos junto da resposta.
- **Pesquisa web geral opcional:** o proprietário pode configurar `THIGAS_BRAVE_SEARCH_KEY` e habilitar conscientemente `THIGAS_BRAVE_SEARCH_ENABLED=true` no Render. Isso habilita a API oficial Brave Search, sujeita às cotas e preços do provedor. Nenhuma chave fica no navegador e Brave permanece desligado por padrão.
- O chat envia `web_search: true` apenas se o planeta estiver ativo; o backend encaminha os trechos encontrados ao modelo com rótulo de **conteúdo externo não confiável** e instrui o modelo a citar os itens por número. Fontes são exibidas como links clicáveis.
- Se não houver resultados ou o provedor falhar, o sistema devolve uma mensagem de erro clara, sem deixar a IA inventar uma pesquisa. A limitação básica é 6 pesquisas por minuto e IP, por worker.
- A consulta pode sair do servidor para Wikipédia ou Brave; conteúdos de arquivos identificados pelo delimitador `[ARQUIVO: ...]` são excluídos do termo de busca. A pergunta do usuário ainda segue para o provedor de IA usado normalmente pelo THIGAS.
- Referências de desenvolvimento: https://www.mediawiki.org/wiki/API:Search e https://api-dashboard.search.brave.com/api-reference/web/search/get

Teste local sem chamadas externas:

```sh
python -m unittest discover -s server/tests -v
node --test server/tests/*.test.cjs
```

A pesquisa por trecho e resultado de busca não equivale a conferência de fatos por múltiplas fontes independentes. A Wikipédia pode estar desatualizada, e a Brave pode incorrer em custos se explicitamente ativada pelo proprietário.


## Três chaves Groq com alternância e failover (13/10/2026)

O THIGAS AI utiliza agora **até três credenciais privadas**, sem enviar ou registrar os valores no navegador. As chaves são lidas exclusivamente do ambiente Render:

- Primária: `THIGAS_CLOUD_API_KEY` (compatível com `GROQ_API_KEY`).
- Segunda: `THIGAS_CLOUD_API_KEY_2` (compatível com `GROQ_API_KEY_2` ou `GROQ_API_KEY2`).
- Terceira: `THIGAS_CLOUD_API_KEY_3` (compatível com `GROQ_API_KEY_3` ou `GROQ_API_KEY3`).

O uso exige `THIGAS_CLOUD_ENABLED=true` no serviço. O backend seleciona chaves distintas em rodízio, alternando para outras elegíveis em caso de HTTP 401, 403, 429, 498 ou erros 500/502/503/504 retornados **pela Groq**. Chaves recusadas entram em cooldown temporário (429 respeita Retry-After, limitado a 60 segundos por processo; credenciais 401/403 permanecem em cooldown por cinco minutos). Não repete automaticamente uma solicitação após timeout ou erro de conexão que possa ter consumido tokens; não altera contratos da Maritaca nem compartilha reservas de chaves com provedores externos.

`/api` autenticado divulga **somente o número de chaves configuradas**, não quais são; o painel exibe o total. Colocar segredos em `render.yaml` ou no repositório é proibido: as variáveis estão declaradas apenas com `sync: false`. Para serviços Render existentes, novas variáveis devem ser preenchidas manualmente no Dashboard, pois o `sync: false` em atualizações do Blueprint não solicita novamente os valores. Ao atualizar variáveis, é necessário aplicar a alteração e implantar a nova versão do código.

**Atenção:** a Groq aplica limites no âmbito da organização e projetos, não concede três vezes a quota por haver três chaves. A recuperação é best-effort e pode não funcionar quando todas as credenciais compartilham o mesmo limite. O algoritmo usa cooldown **local a cada processo**, não sincronizado entre vários serviços. A ativação de APIs pagas depende das configurações e limites da conta da Groq. Não foram realizadas chamadas remuneradas para testar essas três chaves.

Fontes oficiais: https://console.groq.com/docs/rate-limits e https://console.groq.com/docs/errors.

Testes sem consumir APIs externas: `python -m unittest discover -s server/tests -v`.
