const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const chat = require("../static/chat.js");

test("mensagem vazia é rejeitada; espaços externos são removidos", () => {
  assert.throws(() => chat.composeMessage(" ", null), /Escreva/);
  assert.equal(chat.composeMessage(" Olá ", null), "Olá");
});

test("arquivo é incluído de verdade no texto encaminhado", () => {
  const message = chat.composeMessage("Corrija", { name: "somar.py", text: "def somar(a,b): return a-b" });
  assert.match(message, /ARQUIVO: somar.py/);
  assert.match(message, /def somar/);
  assert.match(message, /FIM DO ARQUIVO/);
  assert.match(chat.composeMessage("", { name: "a.txt", text: "conteúdo" }), /Analise este arquivo/);
});

test("anexos vazios e binários são rejeitados; arquivos longos são limitados sem exceder 60 mil caracteres", () => {
  assert.throws(() => chat.composeMessage("a", { name: "a.py", text: " " }), /vazio/);
  assert.throws(() => chat.composeMessage("a", { name: "a.py", text: "a\0b" }), /binário/);
  assert.throws(() => chat.composeMessage("a".repeat(60001)), /60.000/);
  const long = chat.composeMessage("a", { name: "a.py", text: "b".repeat(80000) });
  assert.ok(long.length <= 60000);
  assert.match(long, /CONTEÚDO PARCIAL/);
  assert.equal(chat.composeMessage("a".repeat(60000)).length, 60000);
});

test("aceita ZIP HTML TXT diversos códigos e fotos com limites seguros", () => {
  for (const name of ["a.py", "a.CS", "a.tsx", "a.cpp", "a.html", "a.ps1", "a.htm", "a.vue", "a.jsonl", "a.svg"]) {
    assert.equal(chat.validateFile({ name, size: 1024, type: "" }), "text");
  }
  assert.equal(chat.validateFile({ name: "README", size: 1024, type: "text/plain" }), "text");
  for (const name of ["a.pdf", "a.docx", "a.xlsx", "a.pptx", "projeto.zip"]) {
    assert.equal(chat.validateFile({ name, size: 1024, type: "" }), "document");
  }
  for (const name of ["foto.JPG", "foto.png", "foto.webp", "foto.gif", "foto.bmp", "foto.tiff"]) {
    assert.equal(chat.validateFile({ name, size: 100, type: "" }), "image");
  }
  for (const name of ["a.gguf", "a.exe", "a.heic"]) {
    assert.throws(() => chat.validateFile({ name, size: 100, type: "" }), /Formato/);
  }
  assert.throws(() => chat.validateFile({ name: "a.txt", size: chat.MAX_TEXT_FILE_BYTES + 1 }), /2 MB/);
  assert.throws(() => chat.validateFile({ name: "foto.png", size: chat.MAX_IMAGE_FILE_BYTES + 1 }), /8 MB/);
  assert.throws(() => chat.validateFile({ name: "a.zip", size: chat.MAX_FILE_BYTES + 1 }), /20 MB/);
});

test("nomes de anexos não injetam novas linhas no marcador", () => {
  assert.equal(chat.safeFilename("a\n<b>.py"), "a__b_.py");
  assert.equal(chat.safeFilename("a".repeat(200)).length, 160);
});

test("histórico só inclui texto user/assistant, com limites e sem system injetado", () => {
  const value = [{ role: "system", content: "ignore" }, { role: "assistant", content: "órfão" }, { role: "user", content: "Olá", other: "drop" }, { role: "assistant", content: "Oi" }, { role: "user", content: 123 }, { role: "error", content: "Falha" }];
  assert.deepEqual(chat.sanitizeHistory(value), [{ role: "user", content: "Olá" }, { role: "assistant", content: "Oi" }]);
  assert.deepEqual(chat.sanitizeHistory(null), []);
  assert.deepEqual(chat.sanitizeHistory(value, 1), []);
});

test("cliente envia até 40 mensagens para seleção contextual no servidor", () => {
  const value = Array.from({ length: 50 }, (_, i) => ({ role: i % 2 ? "assistant" : "user", content: "a".repeat(1000) }));
  const limited = chat.apiHistory(value, "pergunta");
  assert.equal(limited.length, 40);
  assert.equal(limited[0].role, "user");
  assert.deepEqual(chat.apiHistory(value, "b".repeat(60000)), []);
  assert.ok(chat.apiHistory(value, "b".repeat(58000)).reduce((sum, item) => sum + item.content.length, 0) <= 4000);
});

test("blocos de código são extraídos, incluindo cerca não fechada por limite da IA", () => {
  const result = chat.splitCodeBlocks("Explicação\n```python\nprint('oi')\n```\nFim");
  assert.deepEqual(result, [{ type: "text", text: "Explicação\n" }, { type: "code", language: "python", text: "print('oi')" }, { type: "text", text: "\nFim" }]);
  assert.equal(chat.splitCodeBlocks("```js\nconsole.log(1)")[0].type, "code");
  assert.deepEqual(chat.splitCodeBlocks("abc"), [{ type: "text", text: "abc" }]);
});

test("conteúdo HTML permanece texto; não há innerHTML, eval nem bot simulado", () => {
  const payload = '<img src=x onerror="alert(1)">';
  assert.equal(chat.splitCodeBlocks(payload)[0].text, payload);
  const source = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  assert.doesNotMatch(source, /\.innerHTML\s*=|\beval\s*\(|generateThigasAIResponse|PixelWizard/);
  assert.match(source, /element\.textContent = text/);
});

test("todos os IDs de elementos referenciados pelo JavaScript existem no HTML", () => {
  const source = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  for (const match of source.matchAll(/byId\("([^"]+)"\)/g)) assert.ok(html.includes('id="' + match[1] + '"'), match[1]);
});

test("download de código escolhe extensão segura", () => {
  assert.equal(chat.codeFilename("python", 1), "thigas_codigo_1.py");
  assert.equal(chat.codeFilename("C++", 2), "thigas_codigo_2.cpp");
  assert.equal(chat.codeFilename("../../evil", 1), "thigas_codigo_1.txt");
});

test("requisição usa /chat e envia histórico e texto sem credencial no cliente", async () => {
  let received;
  const signal = new AbortController().signal;
  const answer = await chat.requestChat(async (url, options) => {
    received = { url, options };
    return { ok: true, json: async () => ({ answer: " Código ", model: "teste" }) };
  }, "Pergunta", [{ role: "user", content: "Antes" }], signal);
  assert.equal(answer.answer, "Código");
  assert.deepEqual(answer.usage, {prompt_tokens: null, completion_tokens: null, total_tokens: null});
  assert.equal(received.url, "/chat");
  assert.equal(received.options.method, "POST");
  assert.equal(received.options.signal, signal);
  assert.equal(received.options.headers.Authorization, undefined);
  assert.deepEqual(JSON.parse(received.options.body), { message: "Pergunta", history: [{ role: "user", content: "Antes" }] });
});

test("cota, resposta inválida/vazia e rede produzem erro, sem reenvio automático", async () => {
  let calls = 0;
  await assert.rejects(chat.requestChat(async () => { calls++; return { ok: false, status: 429, json: async () => ({ error: "Cota atingida" }) }; }, "a", []), /Cota atingida/);
  assert.equal(calls, 1);
  await assert.rejects(chat.requestChat(async () => ({ ok: true, json: async () => ({ answer: " " }) }), "a", []), /vazia/);
  await assert.rejects(chat.requestChat(async () => ({ ok: true, json: async () => { throw new Error("invalid"); } }), "a", []), /válida/);
  await assert.rejects(chat.requestChat(async () => { throw new TypeError("Failed to fetch"); }, "a", []), /fetch/);
});

test("contadores exibem números somente quando medidos pela API", async () => {
  const result = await chat.requestChat(async () => ({
    ok: true,
    json: async () => ({ answer: " Pronto ", usage: {prompt_tokens: 123, completion_tokens: 456, total_tokens: 579}, finish_reason: "stop" }),
  }), "Teste", []);
  assert.equal(result.answer, "Pronto");
  assert.deepEqual(result.usage, { prompt_tokens: 123, completion_tokens: 456, total_tokens: 579 });
  assert.equal(result.finish_reason, "stop");

  const missing = await chat.requestChat(async () => ({
    ok: true, json: async () => ({answer:"Oi", usage: {prompt_tokens: "100", completion_tokens: -5, total_tokens: 12.3}}),
  }), "Oi", []);
  assert.deepEqual(missing.usage, { prompt_tokens: null, completion_tokens: null, total_tokens: null });
});

test("indicadores de tokens existem no layout", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  for(const id of ["tokens-input","tokens-output","tokens-total","tokens-status"]) {
    assert.match(html, new RegExp('id="' + id + '"'));
  }
});

test("somente os três níveis THIGAS AI são enviados pelo navegador", async () => {
  for (const mode of ["fast", "balanced", "thinking"]) {
    let request;
    await chat.requestChat(async (url, options) => {
      assert.equal(url, "/chat");
      request = JSON.parse(options.body);
      return {ok: true, json: async () => ({answer: "Resposta do THIGAS AI", model: "modelo-interno"})};
    }, "Teste", [], undefined, mode);
    assert.equal(request.mode, mode === "fast" ? undefined : mode);
  }
  for (const removed of ["cloud", "nvidia", "nvidia_thinking", "aion", "aion_thinking"]) {
    let payload;
    await chat.requestChat(async (_, options) => {
      payload = JSON.parse(options.body);
      return {ok: true, json: async () => ({answer: "Ok"})};
    }, "Teste", [], undefined, removed);
    assert.equal(payload.mode, undefined);
  }
});

test("seletor de modelos e campos necessários existem no HTML", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  for (const id of ["reasoning-mode", "mode-hint", "model-used"]) {
    assert.match(html, new RegExp('id="' + id + '"'));
  }
});


test("conteúdo de anexos não é persistido no histórico local", () => {
  const attachmentText = "Veja o relatório.\n\n[ARQUIVO: privado.pdf]\nDADOS PESSOAIS SIGILOSOS\n[FIM DO ARQUIVO]";
  const safe = chat.redactAttachmentFromHistory(attachmentText);
  assert.match(safe, /Veja o relatório/);
  assert.match(safe, /Anexo omitido do histórico local/);
  assert.doesNotMatch(safe, /DADOS PESSOAIS SIGILOSOS/);
  assert.equal(chat.redactAttachmentFromHistory("Conversa comum"), "Conversa comum");
});

test("datas de conversas aparecem em grupos previsíveis", () => {
  const now = new Date(2026, 9, 11, 18, 0).getTime();
  assert.equal(chat.classifyConversationDate(new Date(2026, 9, 11, 9).getTime(), now), "Hoje");
  assert.equal(chat.classifyConversationDate(new Date(2026, 9, 10, 23).getTime(), now), "Ontem");
  assert.equal(chat.classifyConversationDate(new Date(2026, 9, 6, 12).getTime(), now), "Últimos 7 dias");
  assert.equal(chat.classifyConversationDate(new Date(2026, 9, 1, 12).getTime(), now), "Anteriores");
});

test("menu de histórico lateral existe e mantém funções de conversa", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "../static/history-sidebar.css"), "utf8");
  for (const id of ["history-drawer", "drawer-conversations", "history-search", "btn-drawer-new", "btn-close-drawer", "history-backdrop"]) {
    assert.match(html, new RegExp('id="' + id + '"'));
  }
  for (const fn of ["renderSidebarHistory", "setDrawerOpen", "openConversation", "deleteConversation", "persistConversation"]) {
    assert.ok(js.includes(fn), fn);
  }
  assert.ok(css.includes("@media(max-width:780px)"));
});

test("cliente preserva fatos antigos para seleção contextual do backend", () => {
  const history = [
    { role: "user", content: "Meu cachorro se chama Pipoca." },
    { role: "assistant", content: "Entendi." },
  ];
  for (let i = 0; i < 14; i++) history.push({ role: "user", content: "Assunto " + i }, { role: "assistant", content: "Certo." });
  const sent = chat.apiHistory(history, "Qual era o nome do meu cachorro?");
  assert.equal(sent.length, 30);
  assert.match(sent[0].content, /Pipoca/);
});

test("alertas de qualidade só aceitam indicadores reconhecidos pelo cliente", async () => {
  const response = await chat.requestChat(async () => ({
    ok: true,
    json: async () => ({
      answer: "resposta",
      quality_flags: ["possible_repetition", "desconhecido", "possible_python_syntax_error"],
    }),
  }), "Faça um teste", []);
  assert.deepEqual(response.quality_flags, ["possible_repetition", "possible_python_syntax_error"]);
});

test("modelo e esforço informados pelo backend são exibíveis sem métricas inventadas", async () => {
  const result = await chat.requestChat(async () => ({
    ok: true,
    json: async () => ({
      answer: "Código revisado", model: "openai/gpt-oss-20b",
      reasoning_effort: "high", quality_flags: ["possible_json_syntax_error"],
    }),
  }), "Crie um código Python", []);
  assert.equal(result.model, "openai/gpt-oss-20b");
  assert.equal(result.reasoning_effort, "high");
  assert.deepEqual(result.quality_flags, ["possible_json_syntax_error"]);
  assert.equal(result.usage.total_tokens, null);
});

test("revisão de código prepara mensagem sem fazer outra chamada automática", () => {
  const review = chat.codeRevisionPrompt("```python\nprint('teste')\n```");
  assert.match(review, /Revise rigorosamente/);
  assert.match(review, /print\('teste'\)/);
  assert.match(review, /Não afirme que executou testes/);
  assert.ok(review.length < 15000);
  assert.match(chat.codeRevisionPrompt("x".repeat(20000)), /x{50}/);
});

test("planeta ao lado do microfone existe e está desligado inicialmente", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const micIndex = html.indexOf('id="btn-microphone"');
  const globeIndex = html.indexOf('id="btn-web-search"');
  const sendIndex = html.indexOf('id="btn-send"');
  assert.ok(micIndex > 0 && globeIndex > micIndex && sendIndex > globeIndex);
  assert.match(html.slice(globeIndex, globeIndex + 180), /aria-pressed="false"/);
  assert.match(html.slice(globeIndex, globeIndex + 240), /🌐/);
});

test("pesquisa online envia web_search true somente com planeta ativado", async () => {
  let received;
  const fakeFetch = async (_, options) => {
    received = JSON.parse(options.body);
    return {
      ok: true, json: async () => ({
        answer: "Fonte [1]", search_provider: "wikipedia",
        sources: [{title: "Título", url: "https://pt.wikipedia.org/?curid=17",
                   snippet: "Trecho da fonte"}],
      }),
    };
  };
  const searched = await chat.requestChat(fakeFetch, "Pesquise Python", [], undefined, "fast", true);
  assert.equal(received.web_search, true);
  assert.equal(searched.search_provider, "wikipedia");
  assert.equal(searched.sources[0].title, "Título");
  assert.equal(searched.usage.total_tokens, null);
  await chat.requestChat(fakeFetch, "Pergunta normal", [], undefined, "fast", false);
  assert.equal(Object.hasOwn(received, "web_search"), false);
});

test("links inválidos não são expostos pela UI", async () => {
  const result = await chat.requestChat(async () => ({
    ok: true, json: async () => ({
      answer: "Resultado", search_provider: "brave",
      sources: [{title: "Fonte", url: "javascript:alert(1)"}, {title: "Boa", url: "https://example.org"}]
    })
  }), "Busca", [], undefined, "fast", true);
  assert.deepEqual(result.sources.map(x => x.title), ["Boa"]);
});

test("atalho /limpar é implementado e mantém /clear como alias", () => {
  const source = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  assert.match(html, /data-insert="\/limpar"/);
  assert.match(source, /case "\/clear": case "\/limpar": clearConversation\(\)/);
});

test("medidor de modelo e tokens deixa de ser ocultado pelos dois temas", () => {
  const css = fs.readFileSync(path.join(__dirname, "../static/chat.css"), "utf8");
  const theme = fs.readFileSync(path.join(__dirname, "../static/mini-nano-theme.css"), "utf8");
  assert.doesNotMatch(css, /\.token-meter,\.composer-footer,\.site-footer\{display:none!important\}/);
  assert.doesNotMatch(theme, /\.token-meter\{display:none!important\}/);
  assert.match(css, /\.token-meter\{display:flex!important/);
  assert.match(theme, /\.token-meter\{display:flex!important/);
  assert.match(css, /\.composer-footer\{display:flex!important/);
});

test("fontes externas rejeitam javascript, URLs com credenciais e destinos locais", async () => {
  const invalid = [
    "javascript:alert(1)", "http://example.org", "https://user:pass@example.org",
    "https://localhost/", "https://127.0.0.1/", "https://router.local/",
    "https://[::1]/", "https://example.org:1234/", "https://example.org/\nattack",
  ];
  for (const url of invalid) assert.equal(chat.safeSourceUrl(url), null, url);
  assert.equal(chat.safeSourceUrl("https://example.org/docs"), "https://example.org/docs");
  const response = await chat.requestChat(async () => ({
    ok: true, json: async () => ({
      answer: "resposta", sources: [
        ...invalid.map(url => ({title:"inseguro",url})),
        {title:"Manual público",url:"https://example.org/docs"},
      ],
    }),
  }), "Pesquisar", [], undefined, "fast", true);
  assert.deepEqual(response.sources.map(source => source.title), ["Manual público"]);
});

test("interface limpa não mostra marcações ou contagem de chaves API", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  for (const id of ["cloud-key-status", "nvidia-key-status", "aion-key-status"]) {
    assert.doesNotMatch(html, new RegExp(id));
    assert.doesNotMatch(js, new RegExp(id));
  }
  for (const key of ["cloud_key_count", "nvidia_key_count", "aion_key_count"]) {
    assert.doesNotMatch(js, new RegExp(key));
  }
  assert.match(html, /id="model-used"/);
  assert.match(html, /id="tokens-total"/);
  assert.doesNotMatch(html, /gsk_[A-Za-z0-9_-]{10,}/);
});

test("THIGAS AI mostra somente Rápido, Equilibrado e Avançado", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  const options = [...html.matchAll(/<option value="([^"]+)"(?: disabled)?>([^<]+)<\/option>/g)]
    .filter(match => ["fast", "balanced", "thinking", "nvidia", "aion", "cloud", "nvidia_thinking", "aion_thinking"].includes(match[1]));
  assert.deepEqual(options.map(match => [match[1], match[2]]), [
    ["fast", "Rápido"], ["balanced", "Equilibrado"], ["thinking", "Avançado"],
  ]);
  assert.doesNotMatch(html, /Sabiazinho|Sabiá|Maritaca|Groq|NVIDIA|Aion|GPT-OSS/);
  assert.doesNotMatch(js, /Sabiá|Maritaca|Groq|NVIDIA|Aion|GPT-OSS/);
  assert.match(js, /model-used"\)\.textContent = \(\{fast: "Rápido", balanced: "Equilibrado", thinking: "Avançado"\}\)/);
});

test("Maritaca streaming lê SSE em blocos divididos e confirma resposta completa", async () => {
  const encoder = new TextEncoder();
  const full = [
    'event: delta\ndata: {"text":"Olá **mundo**"}\n\n',
    'event: delta\ndata: {"text":"!\\n```python\\nprint(1)\\n```"}\n\n',
    'event: done\ndata: {"answer":"Olá **mundo**!\\n```python\\nprint(1)\\n```","model":"sabiazinho-4","usage":{"prompt_tokens":4,"completion_tokens":8,"total_tokens":12}}\n\n',
  ].join("");
  const chunks = [full.slice(0,19), full.slice(19,47), full.slice(47,63), full.slice(63)];
  let n = 0, posted;
  const stream = { getReader: () => ({ read: async () => n < chunks.length
    ? {value:encoder.encode(chunks[n++]),done:false} : {done:true}, cancel: async () => {} }) };
  const previews = [];
  const result = await chat.requestChatStream(async (url, options) => {
    assert.equal(url, "/chat/stream");
    posted = JSON.parse(options.body);
    return {ok:true,body:stream};
  }, "Olá", [], undefined, "fast", value => previews.push(value));
  assert.deepEqual(posted, {message:"Olá",history:[],mode:"fast"});
  assert.equal(previews.length, 2);
  assert.equal(result.answer, "Olá **mundo**!\n```python\nprint(1)\n```");
  assert.equal(result.usage.total_tokens, 12);
});

test("streaming incompleto não confirma respostas; não gera consumo inventado", async () => {
  let read = false;
  const stream = {getReader:() => ({ read:async() => read ? {done:true} :
    (read = true, {value:new TextEncoder().encode('event: delta\ndata: {"text":"incompleto"}\n\n'),done:false}), cancel:async()=>{} })};
  await assert.rejects(chat.requestChatStream(async() => ({ok:true,body:stream}), "Oi", []), /sem resposta completa/);
});

test("markdown seguro apresenta negrito sem asteriscos nem tags HTML", () => {
  assert.deepEqual(chat.readableSegments("Texto **forte** e `x=1`."), [
    {kind:"plain", value:"Texto "}, {kind:"bold",value:"forte"},
    {kind:"plain",value:" e "}, {kind:"inline-code",value:"x=1"}, {kind:"plain",value:"."},
  ]);
  assert.deepEqual(chat.readableLines("# Título\n- item"), [
    {text:"Título",heading:true},{text:"item",heading:false},
  ]);
  assert.ok(chat.streamingPreview("```python\nprint(2)\n```").includes("print(2)"));
  const html = require("node:fs").readFileSync(require("node:path").join(__dirname, "../static/index.html"), "utf8");
  assert.match(html, /<option value="fast">Rápido<\/option>/);
  assert.match(html, /<option value="balanced">Equilibrado<\/option>/);
  assert.doesNotMatch(html, /Sabiazinho|Sabiá|Maritaca/);
  const source = require("node:fs").readFileSync(require("node:path").join(__dirname, "../static/chat.js"), "utf8");
  assert.match(source, /Pensando…/);
  assert.match(source, /COPIAR/);
  assert.doesNotMatch(source, /\.innerHTML\s*=/);
});

test("barra do chat inicia compacta no rodapé e expande com o texto", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "../static/chat.css"), "utf8");
  const theme = fs.readFileSync(path.join(__dirname, "../static/mini-nano-theme.css"), "utf8");
  const script = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  assert.match(html, /id="chat-input" rows="2"/);
  assert.ok(html.indexOf('class="token-meter"') < html.indexOf('id="chat-form"'), "medidor de tokens deve estar acima da caixa");
  assert.ok(html.indexOf('id="chat-form"') < html.indexOf('class="composer-footer"'), "campo deve estar próximo do rodapé");
  assert.match(css, /\.chat-panel > \.composer-wrap \{ margin-top: auto; flex: 0 0 auto; \}/);
  assert.match(css, /min-height: 56px/);
  assert.match(css, /\.composer-wrap > \.token-meter \{ margin-top: 0; margin-bottom: 6px; \}/);
  assert.match(css, /max-height: min\(320px, 40dvh\)/);
  assert.match(theme, /min-height:56px;max-height:min\(360px,40dvh\)/);
  assert.match(script, /const minHeight = 56/);
  assert.match(script, /Math\.min\(window\.innerWidth <= 580 \? 320 : 360/);
  assert.match(script, /input\.style\.overflowY = contentHeight > maxHeight/);
  assert.match(script, /window\.addEventListener\("resize", resizeInput\)/);
  assert.doesNotMatch(css, /min-height: 108px;\s*max-height: min\(380px, 42dvh\)/);
});

test("resposta SSE conserva alerta de código incorreto sem inventar medição", async () => {
  const packet = [
    'event: delta\ndata: {"text":"```python\\nif True print(1)\\n```"}\n\n',
    'event: done\ndata: {"answer":"```python\\nif True print(1)\\n```","quality_flags":["possible_python_syntax_error","output_limit","unsupported"],"finish_reason":"length","model":"sabia-4"}\n\n',
  ].join("");
  const stream = {getReader: () => {
    let sent = false;
    return {read: async () => sent ? {done:true} : (sent = true, {done:false,value:new TextEncoder().encode(packet)}),
      cancel: async () => {}};
  }};
  const reply = await chat.requestChatStream(async () => ({ok:true,body:stream}), "Corrija o código", []);
  assert.deepEqual(reply.quality_flags, ["possible_python_syntax_error", "output_limit"]);
  assert.equal(reply.usage.total_tokens, null);
  assert.equal(reply.finish_reason, "length");
});

test("seleção múltipla compõe até dez arquivos separados, com cortes seguros", () => {
  const ten = Array.from({length: 10}, (_, i) => ({name: "arquivo_" + i + ".txt", text: ("código" + i).repeat(9500)}));
  const result = chat.composeMessage("Analise o projeto", ten);
  assert.ok(result.length <= chat.MAX_MESSAGE);
  for (let i = 0; i < 10; i++) {
    assert.match(result, new RegExp("ARQUIVO: arquivo_" + i + ".txt"));
  }
  assert.match(result, /CONTEÚDO PARCIAL/);
  assert.throws(() => chat.composeMessage("Oi", [...ten, {name:"mais.txt", text:"mais"}]), /10 arquivos/);
  assert.equal((chat.redactAttachmentFromHistory(result).match(/Anexo omitido/g) || []).length, 10);
});

test("picker HTML permite múltiplos tipos e diversas fotos", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  assert.match(html, /id="file-input" hidden multiple/);
  assert.match(html, /id="image-input" hidden multiple/);
  assert.match(html, /\.zip,\.pdf/);
  assert.match(html, /image\/tiff/);
  assert.match(html, /Arquivos e ZIP \(até 10\)/);
});
