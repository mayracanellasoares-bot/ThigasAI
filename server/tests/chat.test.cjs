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
  assert.throws(() => chat.validateFile({ name: "a.pdf", size: chat.MAX_FILE_BYTES + 1 }), /8 MB/);
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

test("histórico da API fica limitado a 12 mensagens e ao orçamento de caracteres", () => {
  const value = Array.from({ length: 50 }, (_, i) => ({ role: i % 2 ? "assistant" : "user", content: "a".repeat(1000) }));
  const limited = chat.apiHistory(value, "pergunta");
  assert.equal(limited.length, 12);
  assert.equal(limited[0].role, "user");
  assert.deepEqual(chat.apiHistory(value, "b".repeat(60000)), []);
  assert.ok(chat.apiHistory(value, "b".repeat(58000)).reduce((sum, item) => sum + item.content.length, 0) <= 2000);
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
