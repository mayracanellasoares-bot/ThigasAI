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

Depois da primeira visita online com o service worker instalado, a interface e o histórico local podem abrir sem internet. **Novas respostas exigem internet.** Perguntas não são reenviadas automaticamente quando a conexão volta.

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

As chaves continuam exclusivamente nas variáveis de ambiente do Render, nunca no JavaScript ou repositório. A rota `/chat` é pública: antes de divulgar amplamente, configure limite de gastos na Maritaca e avalie autenticação/controle de uso no servidor. O service worker guarda somente recursos públicos da interface; não intercepta nem coloca mensagens, respostas ou anexos da API no cache.

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

## Documentos no navegador — sem cadastro

A área `/workspace` agora abre **diretamente, sem Google, GitHub, Facebook, login ou cadastro**. O visitante pode enviar arquivos PDF, DOCX, XLSX e PPTX (até 20 MB), gerar PDF/Word, revisar uma planilha XLSX enviada e confirmar o download.

Os arquivos temporários são segregados por uma sessão anônima assinada no navegador (cookie HTTP-only, SameSite=Lax, Secure e token CSRF). É necessário manter `THIGAS_SESSION_SECRET` (mínimo 32 caracteres) configurado no Render para essa proteção. A sessão e os arquivos expiram em até 24 horas; como `THIGAS_DATA_DIR` permanece no disco efêmero do Render, podem se perder antes. O histórico do chat é guardado no navegador, sem sincronização.

O código **não usa mais** `DATABASE_URL`, Neon, OAuth ou a tabela antiga de usuários. Os cadastros antigos no Neon **não foram apagados**; nenhuma exclusão de banco foi executada. As variáveis antigas do Render podem ser retiradas manualmente após validar o deploy. Consulte [documentação de uso e privacidade](docs/CONTAS_E_DOCUMENTOS.md).

## Modelos maiores em nuvem (8B ou 20B)

O THIGAS AI é um gateway de chat, não o próprio modelo de linguagem. Mudar de um modelo 3B para 8B ou 20B significa conectar um modelo diferente, não aumentar os pesos de um modelo existente. O Render executa o backend Flask e o PWA; a inferência do modelo de 20B ocorre no provedor externo da nuvem.

O chat mantém o modo Rápido (Maritaca Sabiazinho 4) como padrão e agora pode oferecer modos Nuvem (GPT-OSS 20B na Groq) e Sabiá 4 Thinking BR-SP (Maritaca). Os modos pagos ficam desabilitados por padrão, inclusive na interface pública.

Para ativar o GPT-OSS 20B, configure em Render > Environment:

    THIGAS_CLOUD_API_KEY=<SUA_CHAVE_GROQ>
    THIGAS_CLOUD_ENABLED=true
    THIGAS_CLOUD_MODEL=openai/gpt-oss-20b
    THIGAS_CLOUD_URL=https://api.groq.com/openai/v1/chat/completions

Para ativar também a Maritaca Thinking, mantenha a MARITACA_API_KEY já configurada e defina THIGAS_ENABLE_THINKING=true e MARITACA_THINKING_MODEL=sabia-4-thinking-br-sp.

Compatibilidade: POST /chat aceita o modo opcional fast, cloud ou thinking. Sem modo informado, usa fast, preservando Telegram e clientes antigos. GET /api indica disponibilidade dos modos sem retornar credenciais. A API Key da nuvem fica apenas no backend.

Para um modelo 8B, a mesma integração suporta um endpoint compatível com Chat Completions, mas altere THIGAS_CLOUD_MODEL e THIGAS_CLOUD_URL para IDs e URLs verificados no provedor escolhido. Não use o antigo llama-3.1-8b-instant da Groq: ele foi descontinuado em agosto de 2026. O modelo 20B atualmente documentado é openai/gpt-oss-20b.

Segurança: o chat continua público e sem cadastro. Se ativar o modelo de nuvem, qualquer visitante poderá consumir créditos pelo endpoint /chat. Configure cotas e alertas no provedor e adicione rate limiting/autorização robustos antes de divulgar o serviço. Ativar o modo não torna as requisições gratuitas. Testes unitários não validam acesso real nem cobrança da API.

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

- Motor: Maritaca `sabiazinho-4`, cujo limite documentado é até 32K tokens de saída; THIGAS solicita **até 16.384 tokens** de saída em cada requisição. Variável `MARITACA_MAX_TOKENS=16384` (o servidor impede valores acima de 16.384 e usa esse padrão se estiver ausente ou for inválido).
- A resposta de `POST /chat` inclui `usage.prompt_tokens` (enviados), `usage.completion_tokens` (recebidos), `usage.total_tokens` (total consumido), `max_output_tokens` e `finish_reason`. Todos os contadores vêm diretamente da resposta do provedor externo selecionado. Sem `usage`, os campos retornam `null` e o navegador mostra **— / não informado**; **não há estimativa por caractere ou soma fictícia**.
- O painel de tokens mostra **apenas a última requisição de chat**, não uma soma entre múltiplas chamadas. Documentos no `/workspace` e comandos Telegram preservam o formato anterior e não exibem painel próprio de tokens.
- O histórico de entrada continua limitado pelo aplicativo a 12 mensagens anteriores, com orçamento máximo de 60 mil caracteres (além do prompt de sistema). Este valor **não é** uma medição de tokens.
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
