/* THIGAS AI: interface local; geração de respostas exclusivamente pelo POST /chat. */
(function () {
  "use strict";

  const MAX_MESSAGE = 60000;
  const MAX_FILE_BYTES = 8 * 1024 * 1024;
  const MAX_TEXT_FILE_BYTES = 512 * 1024;
  const STORAGE_KEY = "thigas.crt.history.v1";
  const SETTINGS_KEY = "thigas.crt.settings.v1";
  const THEMES = ["green", "amber", "cyan", "pink"];
  const THEME_NAMES = { green: "VERDE", amber: "ÂMBAR", cyan: "CIANO", pink: "ROSA" };
  const TEXT_EXTENSIONS = new Set("txt md py js mjs cjs ts tsx jsx json yaml yml toml csv xml html css scss sh ps1 bat c h cpp hpp cs java go rs rb php sql kt swift dart lua r".split(" "));
  const DOCUMENT_EXTENSIONS = new Set("pdf docx xlsx pptx".split(" "));

  function safeFilename(name) {
    return String(name || "arquivo.txt").replace(/[\r\n\t<>\x00-\x1f]/g, "_").slice(0, 160);
  }

  function validateFile(file) {
    if (!file) throw new Error("Selecione um arquivo.");
    const extension = String(file.name || "").split(".").pop().toLowerCase();
    const mime = String(file.type || "").toLowerCase();
    if (DOCUMENT_EXTENSIONS.has(extension)) {
      if (file.size > MAX_FILE_BYTES) throw new Error("O documento excede 8 MB.");
      return "document";
    }
    if (file.size > MAX_TEXT_FILE_BYTES) throw new Error("Arquivos de texto ou código podem ter até 512 KiB.");
    if (!TEXT_EXTENSIONS.has(extension) && !mime.startsWith("text/") && !["application/json", "application/xml"].includes(mime)) {
      throw new Error("Formato não suportado. Use PDF, DOCX, XLSX, PPTX, texto ou código.");
    }
    return "text";
  }

  function composeMessage(question, attachment) {
    const prompt = String(question || "").trim();
    if (!prompt && !attachment) throw new Error("Escreva uma pergunta ou anexe um arquivo.");
    let message = prompt;
    if (attachment) {
      if (typeof attachment.text !== "string" || !attachment.text.trim()) throw new Error("O arquivo está vazio.");
      if (attachment.text.includes("\0")) throw new Error("O arquivo parece binário; envie texto ou código.");
      message = (prompt || "Analise este arquivo e explique seu conteúdo.") +
        "\n\n[ARQUIVO: " + safeFilename(attachment.name) + "]\n" + attachment.text + "\n[FIM DO ARQUIVO]";
    }
    if (message.length > MAX_MESSAGE) throw new Error("Mensagem e arquivo juntos excedem 60.000 caracteres. Reduza o trecho.");
    return message;
  }

  function sanitizeHistory(value, maxCharacters = 120000, maxMessages = 40) {
    if (!Array.isArray(value)) return [];
    const result = value.filter(item => item && ["user", "assistant"].includes(item.role) &&
      typeof item.content === "string" && item.content.trim() && item.content.length <= MAX_MESSAGE)
      .map(item => ({ role: item.role, content: item.content })).slice(-maxMessages);
    let size = result.reduce((total, item) => total + item.content.length, 0);
    while (size > maxCharacters && result.length) size -= result.shift().content.length;
    while (result.length && result[0].role !== "user") result.shift();
    return result;
  }

  function apiHistory(value, question) {
    // Um teto em caracteres evita reenviar indefinidamente arquivos grandes.
    return sanitizeHistory(value, Math.max(0, 60000 - question.length), 12);
  }

  function splitCodeBlocks(text) {
    const source = String(text).replace(/\r\n/g, "\n");
    const parts = [];
    const fences = /^```([^\n`]*)\n([\s\S]*?)(?:^```[ \t]*(?=\n|$)|(?![\s\S]))/gm;
    let match;
    let last = 0;
    while ((match = fences.exec(source)) !== null) {
      if (match.index > last) parts.push({ type: "text", text: source.slice(last, match.index) });
      parts.push({ type: "code", language: match[1].trim(), text: match[2].replace(/\n$/, "") });
      last = fences.lastIndex;
    }
    if (last < source.length) parts.push({ type: "text", text: source.slice(last) });
    return parts;
  }

  function codeFilename(language, index) {
    const extensions = { python: "py", py: "py", javascript: "js", js: "js", typescript: "ts", ts: "ts", jsx: "jsx", tsx: "tsx", html: "html", css: "css", json: "json", java: "java", c: "c", cpp: "cpp", "c++": "cpp", "c#": "cs", csharp: "cs", cs: "cs", go: "go", rust: "rs", bash: "sh", shell: "sh", powershell: "ps1", sql: "sql", yaml: "yaml", php: "php" };
    return "thigas_codigo_" + index + "." + (extensions[String(language).toLowerCase()] || "txt");
  }

  async function extractDocument(fetcher, file, signal) {
    const form = new FormData();
    form.append("file", file);
    const response = await fetcher("/document/extract", { method: "POST", body: form, signal });
    let data;
    try { data = await response.json(); } catch (_) { throw new Error("O servidor não conseguiu interpretar o documento."); }
    if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "Falha ao ler o documento.");
    if (!data || typeof data.text !== "string" || !data.text.trim()) throw new Error("O documento não contém texto legível.");
    return { name: safeFilename(data.filename || file.name), text: data.text.trim(), truncated: data.truncated === true };
  }

  async function requestChat(fetcher, message, history, signal) {
    const response = await fetcher("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: apiHistory(history, message) }),
      signal,
    });
    let data;
    try { data = await response.json(); } catch (_) {
      throw new Error("O servidor não devolveu uma resposta válida. Pode estar reiniciando; tente novamente mais tarde.");
    }
    if (!data || typeof data !== "object") throw new Error("O servidor devolveu dados inválidos.");
    if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "Falha na consulta (HTTP " + response.status + ").");
    if (typeof data.answer !== "string" || !data.answer.trim()) throw new Error("A resposta veio vazia.");
    return data.answer.trim();
  }

  // Exportações puras permitem testar o contrato sem DOM, API externa ou saldo.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { MAX_MESSAGE, MAX_FILE_BYTES, MAX_TEXT_FILE_BYTES, safeFilename, validateFile, composeMessage, sanitizeHistory, apiHistory, splitCodeBlocks, codeFilename, extractDocument, requestChat };
  }
  if (typeof document === "undefined") return;

  const byId = id => document.getElementById(id);
  const input = byId("chat-input");
  const logs = byId("chat-logs");
  const scroll = byId("chat-scroll");
  const modal = byId("help-modal");
  let history = [];
  let attachment = null;
  let requestActive = false;
  let readingFile = false;
  let readingEpoch = 0;
  let conversationEpoch = 0;
  let activeController = null;
  let audioContext = null;
  let settings = { theme: "green", sound: false, crt: true, colorMode: "dark" };

  function readSaved(key) {
    try { return JSON.parse(localStorage.getItem(key) || "null"); } catch (_) { return null; }
  }

  function storeSaved(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) {
      byId("request-status").textContent = "ARMAZENAMENTO LOCAL INDISPONÍVEL";
    }
  }

  function scrollBottom() { scroll.scrollTop = scroll.scrollHeight; }
  function now() { return new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); }
  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function info(message, error = false) {
    const entry = make("div", "log-entry " + (error ? "error" : "info"));
    entry.append(make("div", "message-text", "[" + now() + "] " + (error ? "ERRO > " : "SISTEMA > ") + message));
    logs.append(entry);
    scrollBottom();
  }

  async function copy(text, button) {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "COPIADO";
      setTimeout(() => { if (button.isConnected) button.textContent = "COPIAR"; }, 1500);
    } catch (_) { info("Não foi possível copiar automaticamente. Selecione o texto para copiar.", true); }
  }

  function download(text, filename) {
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const link = make("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function renderMessage(role, text) {
    const entry = make("article", "log-entry " + role);
    const meta = make("div", "log-meta");
    meta.append(make("span", "", "[" + now() + "] "), make("strong", "", role === "user" ? "VOCÊ" : "THIGAS"), document.createTextNode(" >"));
    entry.append(meta);
    const parts = role === "assistant" ? splitCodeBlocks(text) : [{ type: "text", text }];
    let codeIndex = 0;
    for (const part of parts) {
      if (part.type === "text") {
        entry.append(make("div", "message-text", part.text));
        continue;
      }
      codeIndex++;
      const filename = codeFilename(part.language, codeIndex);
      const block = make("section", "code-block");
      const toolbar = make("div", "code-toolbar");
      const actions = make("div", "actions");
      const copyButton = make("button", "text-btn", "COPIAR");
      const saveButton = make("button", "text-btn", "BAIXAR");
      copyButton.type = saveButton.type = "button";
      copyButton.addEventListener("click", () => copy(part.text, copyButton));
      saveButton.addEventListener("click", () => download(part.text, filename));
      actions.append(copyButton, saveButton);
      toolbar.append(make("span", "", part.language || "CÓDIGO"), actions);
      const pre = make("pre");
      pre.append(make("code", "", part.text));
      block.append(toolbar, pre);
      entry.append(block);
    }
    const actions = make("div", "message-actions");
    const copyButton = make("button", "text-btn", "COPIAR");
    copyButton.type = "button";
    copyButton.addEventListener("click", () => copy(text, copyButton));
    actions.append(copyButton);
    entry.append(actions);
    logs.append(entry);
    scrollBottom();
  }

  function applySettings() {
    document.body.classList.remove(...THEMES.map(theme => "theme-" + theme));
    document.body.classList.add("theme-" + settings.theme);
    byId("terminal").classList.toggle("scanlines", settings.crt);
    byId("btn-theme").textContent = "TEMA: " + THEME_NAMES[settings.theme];
    byId("btn-scanlines").textContent = "CRT: " + (settings.crt ? "ON" : "OFF");
    byId("btn-scanlines").setAttribute("aria-pressed", String(settings.crt));
    byId("btn-sound").textContent = "SOM: " + (settings.sound ? "ON" : "OFF");
    byId("btn-sound").setAttribute("aria-pressed", String(settings.sound));
    document.body.classList.toggle("light-mode", settings.colorMode === "light");
    const colorModeLabel = byId("color-mode-label");
    const colorModeIcon = byId("color-mode-icon");
    const colorModeButton = byId("btn-color-mode");
    if (colorModeLabel) colorModeLabel.textContent = settings.colorMode === "light" ? "Tema: Claro" : "Tema: Escuro";
    if (colorModeIcon) colorModeIcon.textContent = settings.colorMode === "light" ? "☀" : "☾";
    if (colorModeButton) {
      const nextMode = settings.colorMode === "light" ? "escuro" : "claro";
      colorModeButton.setAttribute("aria-label", "Mudar para tema " + nextMode);
      colorModeButton.title = "Mudar para tema " + nextMode;
    }
    const themeMeta = byId("theme-color-meta");
    if (themeMeta) themeMeta.setAttribute("content", settings.colorMode === "light" ? "#f7f7f8" : "#0b0b0b");
    storeSaved(SETTINGS_KEY, settings);
  }

  function beep(kind = "send") {
    if (!settings.sound) return;
    try {
      const Audio = window.AudioContext || window.webkitAudioContext;
      if (!Audio) return;
      if (!audioContext) audioContext = new Audio();
      void audioContext.resume();
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      const time = audioContext.currentTime;
      oscillator.type = "square";
      oscillator.frequency.setValueAtTime(kind === "error" ? 110 : kind === "reply" ? 660 : 330, time);
      gain.gain.setValueAtTime(.018, time);
      gain.gain.exponentialRampToValueAtTime(.001, time + .09);
      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start(time);
      oscillator.stop(time + .1);
    } catch (_) { /* O navegador pode bloquear som; o chat permanece utilizável. */ }
  }

  function resizeInput() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 144) + "px";
  }

  function setBusy() {
    const busy = requestActive || readingFile;
    byId("btn-send").disabled = busy;
    byId("btn-attach").disabled = busy;
    byId("btn-remove-file").disabled = requestActive;
    const sendArrow = byId("btn-send").querySelector(".send-arrow");
    if (sendArrow) sendArrow.textContent = requestActive ? "…" : "↑";
    byId("btn-send").setAttribute("aria-label", requestActive ? "Aguardando resposta" : "Enviar mensagem");
    logs.setAttribute("aria-busy", String(requestActive));
    byId("request-status").textContent = requestActive ? "PROCESSANDO…" : readingFile ? "LENDO ARQUIVO…" : "PRONTO ▉";
  }

  function removeAttachment() {
    attachment = null;
    byId("file-input").value = "";
    byId("attachment-preview").hidden = true;
  }

  function clearConversation() {
    if (logs.children.length > 1 && !window.confirm("Apagar a conversa salva neste navegador?")) return;
    const wasActive = requestActive;
    conversationEpoch++;
    readingEpoch++;
    if (activeController) activeController.abort();
    activeController = null;
    requestActive = readingFile = false;
    history = [];
    storeSaved(STORAGE_KEY, history);
    logs.replaceChildren();
    input.value = "";
    removeAttachment();
    resizeInput();
    setBusy();
    info("Conversa limpa." + (wasActive ? " A resposta foi descartada; a solicitação já enviada ainda pode consumir saldo." : " Pode enviar sua próxima pergunta."));
    input.focus();
  }

  function handleCommand(value) {
    if (!value.startsWith("/")) return { handled: false, question: value };
    const [command, ...args] = value.split(/\s+/);
    if (command.toLowerCase() === "/thigas") return { handled: false, question: args.join(" ") };
    switch (command.toLowerCase()) {
      case "/help": case "/ajuda": modal.showModal(); break;
      case "/clear": case "/novo": clearConversation(); break;
      case "/sound": settings.sound = !settings.sound; applySettings(); beep(); break;
      case "/theme":
        if (!THEMES.includes(args[0])) info("Use /theme green, amber, cyan ou pink.", true);
        else { settings.theme = args[0]; applySettings(); }
        break;
      case "/cat": info(" /\_/\\\n( o.o )\n > ^ <"); break;
      default: info("Comando não reconhecido. Use /help ou escreva sua pergunta normalmente.", true);
    }
    return { handled: true };
  }

  async function send(event) {
    event.preventDefault();
    if (requestActive || readingFile) return;
    const raw = input.value.trim();
    const command = attachment ? { handled: false, question: raw } : handleCommand(raw);
    if (command.handled) { input.value = ""; resizeInput(); return; }
    if (navigator.onLine === false) {
      info("Você está sem internet. O histórico continua disponível; conecte-se para pedir uma nova resposta.", true);
      return;
    }
    let message;
    try { message = composeMessage(command.question, attachment); }
    catch (error) { info(error.message, true); beep("error"); return; }
    const epoch = conversationEpoch;
    const originalText = input.value;
    const originalAttachment = attachment;
    const controller = new AbortController();
    activeController = controller;
    requestActive = true;
    setBusy();
    renderMessage("user", message);
    const pending = make("div", "log-entry pending", "[" + now() + "] THIGAS > Consultando a IA…");
    logs.append(pending);
    scrollBottom();
    beep("send");
    const timeout = setTimeout(() => controller.abort(), 150000);
    try {
      const answer = await requestChat(window.fetch.bind(window), message, history, controller.signal);
      if (epoch !== conversationEpoch) return;
      pending.remove();
      renderMessage("assistant", answer);
      history = sanitizeHistory([...history, { role: "user", content: message }, { role: "assistant", content: answer }]);
      storeSaved(STORAGE_KEY, history);
      // Não apaga uma nova pergunta digitada enquanto a resposta estava chegando.
      if (input.value === originalText) input.value = "";
      if (attachment === originalAttachment) removeAttachment();
      resizeInput();
      beep("reply");
    } catch (error) {
      if (epoch !== conversationEpoch) return;
      pending.remove();
      const explanation = error.name === "AbortError" ? "O tempo de espera terminou. O servidor pode estar despertando. A consulta enviada pode ter consumido saldo; não houve reenvio automático." : error instanceof TypeError ? "Não foi possível conectar ao servidor. Confira a internet e tente mais tarde." : error.message;
      info(explanation, true);
      beep("error");
    } finally {
      clearTimeout(timeout);
      if (epoch === conversationEpoch) { requestActive = false; activeController = null; setBusy(); }
    }
  }

  async function selectFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    const epoch = ++readingEpoch;
    readingFile = true;
    setBusy();
    try {
      const kind = validateFile(file);
      let next;
      if (kind === "document") {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 60000);
        try { next = await extractDocument(window.fetch.bind(window), file, controller.signal); }
        finally { clearTimeout(timeout); }
      } else {
        const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
        next = { name: safeFilename(file.name), text };
      }
      if (epoch !== readingEpoch) return;
      composeMessage(input.value, next);
      attachment = next;
      const ext = next.name.includes(".") ? next.name.split(".").pop().toUpperCase() : "TXT";
      byId("attachment-label").textContent = "📎 " + ext + " · " + next.name + " · " + next.text.length.toLocaleString("pt-BR") + " caracteres" + (next.truncated ? " · conteúdo truncado" : "");
      byId("attachment-preview").hidden = false;
    } catch (error) {
      if (epoch !== readingEpoch) return;
      info(error instanceof TypeError ? "O arquivo não é texto UTF-8 válido." : error.message, true);
    } finally {
      if (epoch === readingEpoch) { readingFile = false; event.target.value = ""; setBusy(); }
    }
  }

  async function checkHealth() {
    if (navigator.onLine === false) { showOffline(); return; }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch("/health", { signal: controller.signal, cache: "no-store" });
      const data = await response.json();
      if (navigator.onLine === false) { showOffline(); return; }
      if (!response.ok || data.status !== "ok") throw new Error("health");
      byId("connection-status").textContent = "SERVIDOR DISPONÍVEL";
      byId("power-lamp").classList.add("online");
    } catch (_) {
      if (navigator.onLine === false) showOffline();
      else {
        byId("connection-status").textContent = "SERVIDOR NÃO VERIFICADO";
        byId("power-lamp").classList.remove("online");
      }
    }
    finally { clearTimeout(timeout); }
  }

  function showOffline() {
    document.body.classList.add("is-offline");
    byId("connection-status").textContent = "OFFLINE — HISTÓRICO DISPONÍVEL";
    byId("power-lamp").classList.remove("online");
  }

  window.addEventListener("offline", showOffline);
  window.addEventListener("online", () => {
    document.body.classList.remove("is-offline");
    void checkHealth();
  });

  const savedSettings = readSaved(SETTINGS_KEY);
  if (savedSettings && typeof savedSettings === "object") {
    if (THEMES.includes(savedSettings.theme)) settings.theme = savedSettings.theme;
    settings.sound = savedSettings.sound === true;
    settings.crt = savedSettings.crt !== false;
    settings.colorMode = savedSettings.colorMode === "light" ? "light" : "dark";
  }
  applySettings();
  history = sanitizeHistory(readSaved(STORAGE_KEY));
  info("THIGAS AI pronto. Pergunte normalmente ou use /help. Não envie senhas ou chaves de API.");
  for (const message of history) renderMessage(message.role, message.content);
  if (history.length) info("Histórico restaurado deste navegador.");
  byId("chat-form").addEventListener("submit", send);
  input.addEventListener("input", resizeInput);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); byId("chat-form").requestSubmit(); }
  });
  byId("btn-theme").addEventListener("click", () => { settings.theme = THEMES[(THEMES.indexOf(settings.theme) + 1) % THEMES.length]; applySettings(); });
  byId("btn-color-mode").addEventListener("click", () => {
    settings.colorMode = settings.colorMode === "light" ? "dark" : "light";
    applySettings();
  });
  byId("btn-sound").addEventListener("click", () => { settings.sound = !settings.sound; applySettings(); beep(); });
  byId("btn-scanlines").addEventListener("click", () => { settings.crt = !settings.crt; applySettings(); });
  byId("btn-clear").addEventListener("click", clearConversation);
  byId("btn-help").addEventListener("click", () => modal.showModal());
  byId("btn-privacy").addEventListener("click", () => modal.showModal());
  byId("btn-close-help").addEventListener("click", () => modal.close());
  byId("btn-attach").addEventListener("click", () => byId("file-input").click());
  byId("file-input").addEventListener("change", selectFile);
  byId("btn-remove-file").addEventListener("click", removeAttachment);
  document.querySelectorAll(".starter-chip").forEach(button => button.addEventListener("click", () => {
    input.value = button.dataset.prompt || "";
    resizeInput();
    input.focus();
  }));
  function updateClock() { byId("clock-display").textContent = now(); }
  updateClock();
  setInterval(updateClock, 30000);
  resizeInput();
  void checkHealth();
})();
