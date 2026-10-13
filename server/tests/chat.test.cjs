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

test("anexos vazios, binários e mensagem acima do limite são rejeitados", () => {
  assert.throws(() => chat.composeMessage("a", { name: "a.py", text: " " }), /vazio/);
  assert.throws(() => chat.composeMessage("a", { name: "a.py", text: "a\0b" }), /binário/);
  assert.throws(() => chat.composeMessage("a".repeat(60001)), /60.000/);
  assert.throws(() => chat.composeMessage("a", { name: "a.py", text: "b".repeat(60000) }), /60.000/);
  assert.equal(chat.composeMessage("a".repeat(60000)).length, 60000);
});

test("aceita texto, código e documentos suportados; bloqueia formatos e tamanhos inválidos", () => {
  for (const name of ["a.py", "a.CS", "a.tsx", "a.cpp", "a.html", "a.ps1"]) assert.equal(chat.validateFile({ name, size: 1024, type: "" }), "text");
  assert.equal(chat.validateFile({ name: "README", size: 1024, type: "text/plain" }), "text");
  for (const name of ["a.pdf", "a.docx", "a.xlsx", "a.pptx"]) assert.equal(chat.validateFile({ name, size: 1024, type: "" }), "document");
  for (const name of ["a.png", "a.zip", "a.gguf"]) assert.throws(() => chat.validateFile({ name, size: 100, type: "" }), /Formato/);
  assert.throws(() => chat.validateFile({ name: "a.txt", size: chat.MAX_TEXT_FILE_BYTES + 1 }), /512/);
  assert.throws(() => chat.validateFile({ name: "a.pdf", size: chat.MAX_FILE_BYTES + 1 }), /20 MB/);
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

test("modo nuvem só altera o provedor solicitado; credencial continua no servidor", async () => {
  let received;
  const reply = await chat.requestChat(async (url, options) => {
    received = { url, options };
    return { ok: true, json: async () => ({ answer: "20B online", model: "openai/gpt-oss-20b" }) };
  }, "Teste", [], undefined, "cloud");
  assert.equal(reply.answer, "20B online");
  assert.equal(reply.model, "openai/gpt-oss-20b");
  assert.equal(received.url, "/chat");
  assert.deepEqual(JSON.parse(received.options.body), { message: "Teste", history: [], mode: "cloud" });
  assert.equal(received.options.headers.Authorization, undefined);
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

test("UI mostra número de chaves Groq sem revelar credenciais", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const js = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  assert.match(html, /id="cloud-key-status"/);
  assert.match(js, /capabilities\.cloud_key_count/);
  assert.match(js, /Groq: modo nuvem desativado/);
  assert.match(js, /chaves configuradas/);
  assert.doesNotMatch(html, /gsk_[A-Za-z0-9_-]{10,}/);
});

test("modelos NVIDIA aparecem no seletor mas aguardam autorização do servidor", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  assert.match(html, /<option value="nvidia" disabled>/);
  assert.match(html, /<option value="nvidia_thinking" disabled>/);
  assert.match(html, /id="nvidia-key-status"/);
});

test("modo NVIDIA usa endpoint do chat do site, sem expor chaves", async () => {
  let body;
  const reply = await chat.requestChat(async (url, options) => {
    assert.equal(url, "/chat");
    body = JSON.parse(options.body);
    return { ok: true, json: async () => ({
      answer: "NVIDIA respondeu", model: "openai/gpt-oss-20b",
      reasoning_effort: "high",
    }) };
  }, "Revise este código", [], undefined, "nvidia_thinking", false);
  assert.equal(body.mode, "nvidia_thinking");
  assert.equal(body.web_search, undefined);
  assert.equal(reply.reasoning_effort, "high");
  assert.equal(reply.usage.total_tokens, null);
});

test("alternância de chaves é informada sem dados secretos", async () => {
  const result = await chat.requestChat(async (path, options) => {
    assert.equal(path, "/chat");
    assert.equal(JSON.parse(options.body).mode, "nvidia");
    return {ok: true, json: async () => ({
      answer: "Recuperado pela segunda chave",
      model: "openai/gpt-oss-20b",
      provider_attempt_count: 2,
      provider_failover_used: true,
    })};
  }, "Teste do fallback", [], undefined, "nvidia", false);
  assert.equal(result.provider_attempt_count, 2);
  assert.equal(result.provider_failover_used, true);
  assert.equal(result.usage.total_tokens, null);
  const source = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  assert.match(source, /Alternância automática realizada/);
});

test("telemetria de failover inválida não é exibida", async () => {
  const result = await chat.requestChat(async () => ({ok: true, json: async () => ({
    answer: "Ok", provider_attempt_count: "many", provider_failover_used: "true",
  })}), "Teste", [], undefined, "fast", false);
  assert.equal(result.provider_attempt_count, 0);
  assert.equal(result.provider_failover_used, false);
});

test("Aion aparece no seletor, inicialmente bloqueado até confirmação do servidor", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const frontend = fs.readFileSync(path.join(__dirname, "../static/chat.js"), "utf8");
  assert.match(html, /<option value="aion" disabled>/);
  assert.match(html, /<option value="aion_thinking" disabled>/);
  assert.match(html, /id="aion-key-status"/);
  assert.match(frontend, /capabilities\?\.aion_enabled/);
  assert.match(frontend, /capabilities\?\.aion_thinking_enabled/);
  assert.doesNotMatch(html, /sk-[A-Za-z0-9_-]{12,}/);
});

test("Aion usa o backend privado e preserva contagem real sem inventar tokens", async () => {
  for (const mode of ["aion", "aion_thinking"]) {
    const result = await chat.requestChat(async (url, options) => {
      assert.equal(url, "/chat");
      const body = JSON.parse(options.body);
      assert.equal(body.mode, mode);
      return { ok: true, json: async () => ({
        answer: "Resposta Aion", model: "aion-labs/aion-3.5-mini",
        reasoning_effort: mode === "aion" ? "low" : "high",
        usage: { prompt_tokens: 9, completion_tokens: 11, total_tokens: 20 },
        provider_attempt_count: 1, provider_failover_used: false,
      }) };
    }, "Explique um texto", [], undefined, mode, false);
    assert.equal(result.answer, "Resposta Aion");
    assert.equal(result.model, "aion-labs/aion-3.5-mini");
    assert.equal(result.reasoning_effort, mode === "aion" ? "low" : "high");
    assert.equal(result.usage.total_tokens, 20);
    assert.equal(result.provider_failover_used, false);
  }
});

test("Aion sem medição mantém tokens não informados", async () => {
  const result = await chat.requestChat(async () => ({ ok: true, json: async () => ({
    answer: "Ok", model: "aion-labs/aion-3.5-mini",
  }) }), "Teste", [], undefined, "aion", false);
  assert.equal(result.usage.total_tokens, null);
  assert.equal(result.provider_attempt_count, 0);
});
