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

O site e o PWA são públicos, sem senha nem cadastro individual. O service worker guarda apenas o shell estático para abertura offline; chat e documentos precisam de internet. O histórico local anterior não é apagado automaticamente. **Novas respostas exigem internet.** Perguntas não são reenviadas automaticamente quando a conexão volta.

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

As chaves continuam exclusivamente nas variáveis de ambiente do Render, nunca no JavaScript ou repositório. `/chat` é acessível sem senha e está sujeito a um limite de requisições por IP e proteção de origem. Configure também cotas e limites de gastos nos provedores, pois o uso público pode consumir créditos. O service worker não coloca respostas, mensagens ou anexos da API no cache.

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

A área `/workspace` abre sem senha e sem cadastro individual ou OAuth do Google, GitHub e Meta. O visitante pode enviar arquivos PDF, DOCX, XLSX e PPTX (até 20 MB), gerar PDF/Word, revisar uma planilha XLSX enviada e confirmar o download.

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

Segurança: o chat é público e não usa cadastro individual. Qualquer visitante poderá consumir créditos pelos modos de IA habilitados no servidor. Há rate limiting local de 12 solicitações por IP/minuto (configurável por `THIGAS_PUBLIC_RATE_LIMIT_PER_MINUTE`); configure também limites de gastos e alertas nos provedores, já que esse limitador não é distribuído entre várias instâncias. Ativar o modo não torna as requisições gratuitas. Testes unitários não validam acesso real nem cobrança da API.

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


## Acesso público no navegador e PWA

O THIGAS AI abre diretamente em `/` sem login ou senha. A página antiga `/entrar` e as ações legadas `/auth/login` e `/auth/logout` redirecionam para `/`, permitindo recuperar atalhos ou PWAs antigos. A variável `THIGAS_ACCESS_PASSWORD` não é mais consultada e pode ser retirada manualmente do Render; **preserve `THIGAS_SESSION_SECRET`**, pois os documentos ainda dependem dela para cookies de sessão anônima e CSRF.

O chat, links e outros endpoints HTTP continuam protegidos contra chamadas de origem cruzada no navegador. Rotas com maior custo são limitadas, por instância/IP, a 12 POST por minuto (alterável com `THIGAS_PUBLIC_RATE_LIMIT_PER_MINUTE` de 1 a 60). A limitação não é uma defesa contra uso distribuído; antes de divulgar o site, defina cotas/budgets dos provedores Maritaca, Groq, NVIDIA e Aion. As credenciais das APIs permanecem apenas no servidor e nunca são expostas ao navegador.

O service worker `v19-public` substitui o cache da tela de senha pelo shell público do chat. Mensagens, respostas de inferência e documentos continuam fora do cache de rede do service worker. O histórico permanece armazenado no navegador de cada aparelho; páginas antigas no cache serão removidas após a atualização do PWA. O webhook Telegram continua com autenticação própria, independente da abertura pública do site.

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

`/api` público informa apenas a disponibilidade dos provedores e os modelos habilitados, **sem números ou valores de chaves**. O painel não exibe indicadores de chaves API. Colocar segredos em `render.yaml` ou no repositório é proibido: as variáveis estão declaradas apenas com `sync: false`. Para serviços Render existentes, novas variáveis devem ser preenchidas manualmente no Dashboard, pois o `sync: false` em atualizações do Blueprint não solicita novamente os valores. Ao atualizar variáveis, é necessário aplicar a alteração e implantar a nova versão do código.

**Atenção:** a Groq aplica limites no âmbito da organização e projetos, não concede três vezes a quota por haver três chaves. A recuperação é best-effort e pode não funcionar quando todas as credenciais compartilham o mesmo limite. O algoritmo usa cooldown **local a cada processo**, não sincronizado entre vários serviços. A ativação de APIs pagas depende das configurações e limites da conta da Groq. Não foram realizadas chamadas remuneradas para testar essas três chaves.

Fontes oficiais: https://console.groq.com/docs/rate-limits e https://console.groq.com/docs/errors.

Testes sem consumir APIs externas: `python -m unittest discover -s server/tests -v`.

## NVIDIA NIM — duas chaves novas e modo independente

A interface oferece **NVIDIA · padrão** e **NVIDIA · esforço alto** (este último apenas para `openai/gpt-oss-20b`/`openai/gpt-oss-120b`). Utiliza exclusivamente o endpoint oficial `https://integrate.api.nvidia.com/v1/chat/completions` e só executa solicitações quando o usuário seleciona NVIDIA e envia uma mensagem. Maritaca/Groq permanecem em seus modos anteriores.

As credenciais NVIDIA são lidas no Render pelas variáveis `NVIDIA_API_KEY`, `NVIDIA_API_KEY_2`, `NVIDIA_API_KEY_3` ou aliases `THIGAS_NVIDIA_API_KEY`, `THIGAS_NVIDIA_API_KEY_2`, `THIGAS_NVIDIA_API_KEY_3`. **Uma ou duas chaves bastam**; não é necessário cadastrar a primária quando apenas `_2` e `_3` estiverem preenchidas. O servidor evita repetição de chaves e distribui chamadas entre as disponíveis. Em 401/403/429/5xx HTTP, efetua failover limitado, sem repetir automaticamente após timeout. O pool NVIDIA é independente do pool Groq; nunca troca credenciais entre provedores.

Configure `THIGAS_NVIDIA_MODEL` com um ID existente em `https://docs.api.nvidia.com/nim/reference/llm-apis` (padrão `openai/gpt-oss-20b`); `THIGAS_NVIDIA_ENABLED` controla o acesso (padrão `true`, mas o botão fica desativado se não houver chave). A NVIDIA pode impor limites por conta e modelo; chaves adicionais não garantem aumento de quota. Uma resposta de produção só pode ser considerada verificada após uma consulta real autorizada.

As novas variáveis em `render.yaml` usam `sync: false`; no Render já existente, os valores precisam ser configurados no painel do serviço. **Não insira as chaves no GitHub ou chat**. O endpoint público `/api` não expõe quantidades nem valores de credenciais; a rotação continua exclusiva do servidor.

Fontes: https://docs.api.nvidia.com/nim/reference/openai-gpt-oss-20b-infer e https://docs.api.nvidia.com/nim/reference/llm-apis.


### Alternância automática reforçada (13/10/2026)

Ao enviar uma pergunta no modo **Groq ou NVIDIA**, o THIGAS AI escolhe uma chave disponível. Se o provedor recusar uma chave com status HTTP `401`, `403`, `429` ou certos erros de servidor `5xx`, tenta a próxima chave válida **do mesmo provedor**. Agora também alterna quando ocorre um `ConnectTimeout` (não foi possível estabelecer a conexão HTTP), preservando o mesmo modelo e a mesma pergunta.

- Cada chave é tentada **no máximo uma vez por consulta**. O número total de tentativas é limitado ao número de chaves disponíveis (até três).
- Chaves com falha recebem pausa em memória (10 segundos para falha de conexão, até 60 segundos para `429`, 5 minutos para `401/403` e 5 segundos para erros de servidor), e voltam a ser elegíveis depois.
- Não repete automaticamente ao sofrer `ReadTimeout`, `ConnectionError` genérico ou timeout cujo envio seja incerto; isso evita duplicar solicitações e possíveis cobranças.
- Se uma segunda chave resolver a consulta, o chat informa **“Alternância automática realizada”**, mostrando só o total de tentativas. Nunca mostra chaves, índice da chave ou valores de ambiente.
- Não muda silenciosamente de NVIDIA para Groq ou vice-versa; cada provedor mantém sua configuração, limites, preços e escolhas do usuário.
- A rotação/pausa ocorre localmente em cada processo do Gunicorn. Não é monitoramento independente nem garante continuidade se o provedor inteiro estiver indisponível ou todas as chaves compartilharem o limite da organização.

Os cenários são validados por testes locais simulados, sem chamar os serviços pagos. A aplicação continua exigindo `THIGAS_CLOUD_ENABLED=true` para ativar Groq no chat, e `THIGAS_NVIDIA_ENABLED=true` para NVIDIA.

## Aion Labs no THIGAS AI

O chat oferece agora **Aion Labs · padrão** e **Aion Labs · esforço alto** com integração server-side independente da Maritaca, Groq e NVIDIA. Nenhuma chave Aion é transmitida ao navegador. As consultas só são enviadas quando o usuário seleciona um dos modos Aion e envia a pergunta, evitando consumir créditos involuntariamente.

**Variáveis no Render:** a chave principal pode estar configurada como `AION_API_KEY`, `AION_LABS_API_KEY`, `AIONLABS_API_KEY`, `THIGAS_AION_API_KEY` ou `AION_KEY`. São aceitas outras duas chaves (opcionais) com os nomes `AION_API_KEY_2` e `AION_API_KEY_3`, inclusive as variantes `THIGAS_AION_API_KEY_2/_3` ou `AION_LABS_API_KEY_2/_3`. Todas ficam privadas. Com várias chaves, o servidor faz rodízio e failover limitado após erros HTTP recuperáveis ou `ConnectTimeout`; nunca muda de provedor sozinho.

- `THIGAS_AION_MODEL`: modelo selecionado, padrão `aion-labs/aion-3.5-mini`. Se não estiver definida, a variável `AION_MODEL` também é aceita.
- `THIGAS_AION_ENABLED`: chave de ativação, padrão `true`; `AION_ENABLED` é aceito como alternativa. Sem uma chave, ambos os modos permanecem desabilitados.
- **Endpoint oficial e fixo:** `https://api.aionlabs.ai/v1/chat/completions`. Não aceita redirecionar tokens para URLs arbitrárias.
- **Padrão:** modelos Aion 2.0/3.0/3.5 conhecidos enviam `reasoning_effort=low`; **alto:** envia `reasoning_effort=high`. O modelo roleplay 8B não oferece modo alto. Não inclui parâmetros exclusivos da Groq ou NVIDIA.
- **Tokens:** a UI exibe somente números de uso recebidos na resposta da Aion, sem estimativas. O limite de saída do servidor permanece até 16384 tokens, mas o provedor pode impor limites próprios.
- **Timeout:** a documentação Aion informa limite de 120 segundos para respostas não streaming; respostas extensas podem expirar. Este gateway continua não streaming.
- **Preço e limites:** a disponibilidade de chaves, créditos e cobrança segue sua conta Aion Labs. Múltiplas chaves não garantem cotas independentes.

Para serviços Render que já existem, declarar `sync: false` em `render.yaml` **não cria nem lê a chave do painel**. Se você já cadastrou `AION_API_KEY`, basta garantir que o nome corresponde e que a alteração foi aplicada. Caso contrário, cadastre-a em **Render → thigas-coder-gateway → Environment** sem publicá-la no GitHub. A rota `/api` pública divulga somente disponibilidade e modelo, sem valores nem quantidades de chaves.

Documentação oficial: https://api.aionlabs.ai/docs/api-reference/ e https://www.aionlabs.ai/docs/quickstart/.
Testes isolados sem consumir créditos: `python -m unittest discover -s server/tests -v` e `node --test server/tests/chat.test.cjs`.

## Maritaca com três níveis, respostas progressivas e formatação limpa

O THIGAS AI oferece no seletor os modelos `sabiazinho-4` (rápido), `sabia-4` (equilibrado) e `sabia-4-thinking` (avançado). A seleção depende de `MARITACA_API_KEY`, e o modo Thinking requer também `THIGAS_ENABLE_THINKING=true`. A opção BR-SP de residência de dados fica disponível manualmente por `MARITACA_THINKING_MODEL=sabia-4-thinking-br-sp`, com custo adicional do provedor. A configuração recomendada de baixo custo utiliza o modelo padrão `sabia-4-thinking` somente em tarefas complexas.

O backend mantém o `/chat` convencional para compatibilidade e adiciona `/chat/stream` para Sabiá/Sabiazinho via SSE. O streaming é selecionado automaticamente no chat quando a Maritaca está configurada, o usuário escolheu um dos três modos e a pesquisa web está desligada. A pesquisa web continua na rota convencional, pois ela depende de contexto externo. O endpoint progressivo usa `stream_options.include_usage=true`; nenhum número de tokens é inventado. A resposta é considerada concluída apenas após o marcador final oficial `[DONE]`. Erros durante a geração não promovem texto parcial ao histórico; não há reenvio automático de consulta possivelmente cobrada.

Os textos de respostas são apresentados com parágrafos e negrito renderizados em DOM seguro, sem expor marcadores Markdown. Blocos de código delimitados por crases triplas continuam com botões **Copiar**, **Baixar** e **Revisar código**. Enquanto a IA ainda não produziu conteúdo, a interface exibe um ícone animado `🧠` com **Pensando…**; depois passa a mostrar **Respondendo…** e o texto progressivamente. O usuário pode desativar animações nas preferências de redução de movimento do dispositivo.

Variáveis no Render: `MARITACA_FAST_MODEL=sabiazinho-4`, `MARITACA_MODEL=sabia-4`, `MARITACA_THINKING_MODEL=sabia-4-thinking`, `THIGAS_ENABLE_THINKING=true`. **A chave existente `MARITACA_API_KEY` é preservada; não é enviada ao navegador.** Para trocar o modelo, use o Playground e teste instruções com casos reais antes de alterar os modelos do serviço. O Playground não treina os pesos; serve para comparar saídas e calibrar temperatura, custo e instruções.

Documentação oficial: https://docs.maritaca.ai/pt/modelos e https://docs.maritaca.ai/api/pt/completion. A API remunera o consumo por tokens em reais: consulte sua conta e configure créditos e alertas antes de liberar modos avançados a um site público. Testes simulados: `python -m unittest discover -s server/tests -v` e `node --test server/tests/*.test.cjs`.
