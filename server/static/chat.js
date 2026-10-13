/* THIGAS AI: interface local; geração de respostas exclusivamente pelo POST /chat. */
(async function () {
  "use strict";

  const MAX_MESSAGE = 60000;
  const MAX_FILE_BYTES = 20 * 1024 * 1024;
  const MAX_TEXT_FILE_BYTES = 512 * 1024;
  let STORAGE_KEY = "thigas.crt.history.v1";
  let CONVERSATIONS_KEY = "thigas.conversations.v2";
  let ACTIVE_CONVERSATION_KEY = "thigas.activeConversation.v2";
  const SETTINGS_KEY = "thigas.crt.settings.v1";
  const MAX_SAVED_CONVERSATIONS = 30;
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
      if (file.size > MAX_FILE_BYTES) throw new Error("O documento excede 20 MB.");
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

  function redactAttachmentFromHistory(content) {
    if (typeof content !== "string") return "";
    return content.replace(/\n\n\[ARQUIVO:[^\n]*\]\n[\s\S]*?\n\[FIM DO ARQUIVO\]/g,
      "\n\n[Anexo omitido do histórico local.]");
  }

  function classifyConversationDate(timestamp, today = Date.now()) {
    const todayDate = new Date(today);
    const startToday = new Date(todayDate.getFullYear(), todayDate.getMonth(), todayDate.getDate()).getTime();
    if (timestamp >= startToday) return "Hoje";
    if (timestamp >= startToday - 86400000) return "Ontem";
    if (timestamp >= startToday - 7 * 86400000) return "Últimos 7 dias";
    return "Anteriores";
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
    // Enviar até 40 mensagens permite ao servidor recuperar tópicos antigos
    // relevantes; ele continuará limitando a inferência a 12 mensagens/60k chars.
    return sanitizeHistory(value, Math.max(0, 120000 - 2 * question.length), 40);
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

  function codeRevisionPrompt(answer) {
    return "Revise rigorosamente o código abaixo, que veio de uma resposta anterior. " +
      "Identifique erros de sintaxe, lógica, dependências, nomes, DOM, eventos e compatibilidade. " +
      "Corrija apenas o necessário e entregue a implementação completa sem omitir trechos. " +
      "Não afirme que executou testes sem evidência e indique como validar.\n\n" +
      "RESPOSTA A REVISAR:\n" + String(answer || "").slice(0, 12000);
  }

  async function requestChat(fetcher, message, history, signal, mode = "fast") {
    const payload = { message, history: apiHistory(history, message) };
    if (mode === "thinking" || mode === "cloud") payload.mode = mode;
    const response = await fetcher("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
    let data;
    try { data = await response.json(); } catch (_) {
      throw new Error("O servidor não devolveu uma resposta válida. Pode estar reiniciando; tente novamente mais tarde.");
    }
    if (!data || typeof data !== "object") throw new Error("O servidor devolveu dados inválidos.");
    if (!response.ok) throw new Error(typeof data.error === "string" ? data.error : "Falha na consulta (HTTP " + response.status + ").");
    if (typeof data.answer !== "string" || !data.answer.trim()) throw new Error("A resposta veio vazia.");
    const measured = value => Number.isSafeInteger(value) && value >= 0 ? value : null;
    const usage = data.usage && typeof data.usage === "object" ? data.usage : {};
    return {
      answer: data.answer.trim(),
      model: typeof data.model === "string" ? data.model : null,
      usage: {
        prompt_tokens: measured(usage.prompt_tokens),
        completion_tokens: measured(usage.completion_tokens),
        total_tokens: measured(usage.total_tokens),
      },
      finish_reason: typeof data.finish_reason === "string" ? data.finish_reason : null,
      reasoning_effort: data.reasoning_effort === "high" || data.reasoning_effort === "medium" ? data.reasoning_effort : null,
      quality_flags: Array.isArray(data.quality_flags)
        ? data.quality_flags.filter(flag => ["output_limit", "possible_repetition", "unclosed_code_block", "possible_python_syntax_error", "possible_json_syntax_error"].includes(flag))
        : [],
    };
  }

  // Exportações puras permitem testar o contrato sem DOM, API externa ou saldo.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { MAX_MESSAGE, MAX_FILE_BYTES, MAX_TEXT_FILE_BYTES, safeFilename, validateFile, composeMessage, sanitizeHistory, apiHistory, splitCodeBlocks, codeFilename, extractDocument, requestChat, redactAttachmentFromHistory, classifyConversationDate, codeRevisionPrompt };
  }
  if (typeof document === "undefined") return;

  // Acesso direto: histórico continua no navegador, sem identidade social.
  const byId = id => document.getElementById(id);
  const input = byId("chat-input");
  const logs = byId("chat-logs");
  const usageSent = byId("tokens-input");
  const usageReceived = byId("tokens-output");
  const usageTotal = byId("tokens-total");
  const usageStatus = byId("tokens-status");
  const modeSelector = byId("reasoning-mode");
  const ptNumber = new Intl.NumberFormat("pt-BR");
  function showUsage(usage) {
    const show = value => Number.isSafeInteger(value) && value >= 0 ? ptNumber.format(value) : "—";
    usageSent.textContent = show(usage?.prompt_tokens);
    usageReceived.textContent = show(usage?.completion_tokens);
    usageTotal.textContent = show(usage?.total_tokens);
    usageStatus.textContent = [usage?.prompt_tokens, usage?.completion_tokens, usage?.total_tokens]
      .every(value => Number.isSafeInteger(value) && value >= 0)
      ? "Medição real informada pela API"
      : "— = não informado pela API";
  }
  const scroll = byId("chat-scroll");
  const modal = byId("help-modal");
  const historyModal = byId("history-modal");
  let history = [];
  let conversations = [];
  let activeConversationId = null;
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

  function conversationId() {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
    return "chat-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  function conversationTitle(messages) {
    const first = (messages || []).find(item => item && item.role === "user" && typeof item.content === "string");
    if (!first) return "Nova conversa";
    let title = first.content.split("\n")[0].replace(/^\s+|\s+$/g, "");
    title = title.replace(/^\[ARQUIVO:[^\]]+\]\s*/i, "");
    if (!title) title = "Conversa com THIGAS";
    return title.length > 46 ? title.slice(0, 43) + "…" : title;
  }

  function normalizeConversation(value) {
    if (!value || typeof value !== "object" || typeof value.id !== "string") return null;
    const messages = sanitizeHistory(value.messages, 120000, 40)
      .map(item => ({ role: item.role, content: redactAttachmentFromHistory(item.content) }));
    if (!messages.length) return null;
    return {
      id: value.id.slice(0, 100),
      title: typeof value.title === "string" && value.title.trim() ? value.title.trim().slice(0, 60) : conversationTitle(messages),
      customTitle: value.customTitle === true,
      updatedAt: Number.isFinite(value.updatedAt) ? value.updatedAt : Date.now(),
      messages,
    };
  }

  function loadConversationStore() {
    const saved = readSaved(CONVERSATIONS_KEY);
    conversations = Array.isArray(saved) ? saved.map(normalizeConversation).filter(Boolean) : [];
    conversations.sort((a, b) => b.updatedAt - a.updatedAt);
    conversations = conversations.slice(0, MAX_SAVED_CONVERSATIONS);
    if (conversations.length) storeSaved(CONVERSATIONS_KEY, conversations);

    if (!conversations.length) {
      const legacy = sanitizeHistory(readSaved(STORAGE_KEY)).map(item => ({ role: item.role, content: redactAttachmentFromHistory(item.content) }));
      if (legacy.length) {
        const migrated = { id: conversationId(), title: conversationTitle(legacy), updatedAt: Date.now(), messages: legacy };
        conversations = [migrated];
        storeSaved(CONVERSATIONS_KEY, conversations);
        try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
      }
    }

    const preferredId = readSaved(ACTIVE_CONVERSATION_KEY);
    const preferred = conversations.find(item => item.id === preferredId) || conversations[0] || null;
    activeConversationId = preferred ? preferred.id : null;
    history = preferred ? preferred.messages.slice() : [];
  }

  function persistConversation() {
    history = sanitizeHistory(history, 120000, 40);
    if (!history.length) return;
    if (!activeConversationId) activeConversationId = conversationId();

    const previous = conversations.find(item => item.id === activeConversationId);
    const next = {
      id: activeConversationId,
      title: previous?.customTitle ? previous.title : conversationTitle(history),
      customTitle: previous?.customTitle === true,
      updatedAt: Date.now(),
      messages: history.map(item => ({ role: item.role, content: redactAttachmentFromHistory(item.content) })),
    };
    conversations = [next, ...conversations.filter(item => item.id !== activeConversationId)]
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, MAX_SAVED_CONVERSATIONS);
    storeSaved(CONVERSATIONS_KEY, conversations);
    storeSaved(ACTIVE_CONVERSATION_KEY, activeConversationId);
    renderConversationList();
  }

  const drawer = byId("history-drawer");
  const drawerBackdrop = byId("history-backdrop");
  const drawerSearch = byId("history-search");
  const mobileHistory = window.matchMedia("(max-width: 780px)");

  function setDrawerOpen(open) {
    const mobile = mobileHistory.matches;
    document.body.classList.toggle("history-drawer-open", mobile && open);
    document.body.classList.toggle("history-drawer-collapsed", !mobile && !open);
    drawerBackdrop.hidden = !(mobile && open);
    byId("btn-history-top").setAttribute("aria-expanded", String(mobile ? open : open));
    drawer.setAttribute("aria-hidden", String(mobile && !open));
    if (mobile && open) drawerSearch.focus();
  }

  function isDrawerOpen() {
    return mobileHistory.matches
      ? document.body.classList.contains("history-drawer-open")
      : !document.body.classList.contains("history-drawer-collapsed");
  }

  function dismissMobileDrawer() {
    if (mobileHistory.matches) setDrawerOpen(false);
  }

  function renderSidebarHistory() {
    const list = byId("drawer-conversations");
    list.replaceChildren();
    const query = drawerSearch.value.trim().toLocaleLowerCase("pt-BR");
    const results = conversations.filter(item => item.title.toLocaleLowerCase("pt-BR").includes(query));
    if (!results.length) {
      list.append(make("p", "drawer-empty", query ? "Nenhuma conversa encontrada." : "Inicie uma conversa para vê-la aqui."));
      return;
    }
    let lastGroup = "";
    for (const conversation of results) {
      const group = classifyConversationDate(conversation.updatedAt);
      if (group !== lastGroup) {
        list.append(make("div", "drawer-group", group));
        lastGroup = group;
      }
      const row = make("div", "drawer-conversation" + (conversation.id === activeConversationId ? " selected" : ""));
      const open = make("button", "drawer-open");
      open.type = "button";
      open.setAttribute("aria-label", "Abrir " + conversation.title);
      const title = make("strong", "", conversation.title);
      const firstUser = conversation.messages.find(m => m.role === "user");
      const preview = make("small", "", (firstUser?.content || "").replace(/\s+/g, " ").slice(0, 64) || "Conversa salva");
      const stamp = make("time", "", new Date(conversation.updatedAt).toLocaleTimeString("pt-BR", { hour:"2-digit", minute:"2-digit" }));
      open.append(make("span", "drawer-chat-icon", "▢"), title, preview);
      open.addEventListener("click", () => openConversation(conversation.id));
      const rename = make("button", "drawer-item-action", "✎");
      rename.type = "button";
      rename.title = "Renomear";
      rename.setAttribute("aria-label", "Renomear " + conversation.title);
      rename.addEventListener("click", () => {
        const proposed = window.prompt("Novo nome da conversa:", conversation.title);
        if (proposed === null) return;
        const next = proposed.trim().replace(/\s+/g, " ").slice(0, 60);
        if (!next) return;
        conversation.title = next;
        conversation.customTitle = true;
        storeSaved(CONVERSATIONS_KEY, conversations);
        renderConversationList();
      });
      const remove = make("button", "drawer-item-action", "×");
      remove.type = "button";
      remove.title = "Excluir";
      remove.setAttribute("aria-label", "Excluir " + conversation.title);
      remove.addEventListener("click", () => deleteConversation(conversation.id));
      row.append(open, stamp, rename, remove);
      list.append(row);
    }
  }

  function renderConversationList() {
    renderSidebarHistory();
    const list = byId("conversation-list");
    if (!list) return;
    list.replaceChildren();
    if (!conversations.length) {
      list.append(make("p", "history-empty", "Nenhuma conversa salva ainda."));
      return;
    }
    for (const conversation of conversations) {
      const row = make("div", "conversation-row" + (conversation.id === activeConversationId ? " active" : ""));
      const open = make("button", "conversation-open");
      open.type = "button";
      const title = make("strong", "", conversation.title);
      const date = make("span", "", new Date(conversation.updatedAt).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }));
      open.append(title, date);
      open.addEventListener("click", () => openConversation(conversation.id));
      const remove = make("button", "conversation-delete", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", "Excluir " + conversation.title);
      remove.title = "Excluir conversa";
      remove.addEventListener("click", () => deleteConversation(conversation.id));
      row.append(open, remove);
      list.append(row);
    }
  }

  function showCurrentConversation() {
    logs.replaceChildren();
    for (const message of history) renderMessage(message.role, message.content);
    if (history.length) scrollBottom();
  }

  function openConversation(id) {
    if (requestActive || readingFile) {
      info("Aguarde a operação atual terminar antes de trocar de conversa.", true);
      return;
    }
    const conversation = conversations.find(item => item.id === id);
    if (!conversation) return;
    activeConversationId = conversation.id;
    history = conversation.messages.slice();
    storeSaved(ACTIVE_CONVERSATION_KEY, activeConversationId);
    input.value = "";
    removeAttachment();
    resizeInput();
    showCurrentConversation();
    renderConversationList();
    if (historyModal && historyModal.open) historyModal.close();
    dismissMobileDrawer();
    input.focus();
  }

  function startNewConversation() {
    if (requestActive && activeController) activeController.abort();
    conversationEpoch++;
    readingEpoch++;
    activeController = null;
    requestActive = readingFile = false;
    activeConversationId = null;
    history = [];
    storeSaved(ACTIVE_CONVERSATION_KEY, null);
    logs.replaceChildren();
    input.value = "";
    removeAttachment();
    resizeInput();
    setBusy();
    renderConversationList();
    dismissMobileDrawer();
    input.focus();
  }

  function deleteConversation(id) {
    const conversation = conversations.find(item => item.id === id);
    if (!conversation) return;
    if (!window.confirm("Excluir esta conversa do histórico deste navegador?")) return;
    conversations = conversations.filter(item => item.id !== id);
    storeSaved(CONVERSATIONS_KEY, conversations);
    if (activeConversationId === id) {
      activeConversationId = null;
      history = [];
      storeSaved(ACTIVE_CONVERSATION_KEY, null);
      logs.replaceChildren();
    }
    renderConversationList();
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
    if (role === "assistant") {
      const avatar = make("img", "assistant-avatar");
      avatar.src = "/static/icons/icon.svg";
      avatar.alt = "THIGAS AI";
      entry.prepend(avatar);
    }
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
    if (role === "assistant" && codeIndex > 0) {
      const reviewButton = make("button", "text-btn", "REVISAR CÓDIGO");
      reviewButton.type = "button";
      reviewButton.addEventListener("click", () => {
        if (requestActive || readingFile) return;
        input.value = codeRevisionPrompt(text);
        resizeInput();
        input.focus();
        info("Pedido de revisão preparado. Confira antes de enviar; nova consulta pode consumir créditos.");
      });
      actions.append(reviewButton);
    }
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
    modeSelector.disabled = busy;
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
    const currentId = activeConversationId;
    if (currentId) {
      const conversation = conversations.find(item => item.id === currentId);
      if (conversation && !window.confirm("Apagar esta conversa do histórico deste navegador?")) return;
      conversations = conversations.filter(item => item.id !== currentId);
      storeSaved(CONVERSATIONS_KEY, conversations);
    }
    startNewConversation();
  }

  function handleCommand(value) {
    if (!value.startsWith("/")) return { handled: false, question: value };
    const [command, ...args] = value.split(/\s+/);
    if (command.toLowerCase() === "/thigas") return { handled: false, question: args.join(" ") };
    switch (command.toLowerCase()) {
      case "/help": case "/ajuda": modal.showModal(); break;
      case "/novo": startNewConversation(); break;
      case "/clear": clearConversation(); break;
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
    const raw = input.value.trim().replace(/^@(?:documento|codigo|site)\s+/i, (match) => ({ "@documento": "Considere o documento anexado: ", "@codigo": "Revise o código a seguir: ", "@site": "Analise o site a seguir: " })[match.trim().toLowerCase()] || match);
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
    const timeout = setTimeout(() => controller.abort(), 325000);
    try {
      const result = await requestChat(window.fetch.bind(window), message, history, controller.signal, modeSelector.value);
      if (epoch !== conversationEpoch) return;
      pending.remove();
      const answer = result.answer;
      renderMessage("assistant", answer);
      showUsage(result.usage);
      byId("model-used").textContent = result.model
        ? (result.reasoning_effort === "high" ? "Alto · " : "") + result.model
        : "Modelo não informado";
      const qualityMessages = {
        output_limit: "A resposta atingiu o limite de saída; pode estar incompleta.",
        possible_repetition: "Possível loop de repetição detectado; confira o conteúdo antes de utilizá-lo.",
        unclosed_code_block: "Um bloco de código não foi fechado; a resposta pode estar incompleta.",
        possible_python_syntax_error: "O código Python gerado pode conter erro de sintaxe. Confira e teste antes de executar.",
        possible_json_syntax_error: "O JSON gerado não é válido. Use Revisar Código para pedir uma correção.",
      };
      const flags = result.quality_flags.slice();
      if (result.finish_reason === "length" && !flags.includes("output_limit")) flags.push("output_limit");
      const warnings = flags.map(flag => qualityMessages[flag]).filter(Boolean);
      if (warnings.length) info(warnings.join(" "), true);
      history = sanitizeHistory([...history, { role: "user", content: message }, { role: "assistant", content: answer }]);
      persistConversation();
      // Não apaga uma nova pergunta digitada enquanto a resposta estava chegando.
      if (input.value === originalText) input.value = "";
      if (attachment === originalAttachment) removeAttachment();
      resizeInput();
      beep("reply");
    } catch (error) {
      if (epoch !== conversationEpoch) return;
      pending.remove();
      showUsage(null);
      byId("model-used").textContent = "—";
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

  async function loadModelCapabilities() {
    // The UI never enables paid advanced modes without server authorization.
    try {
      const response = await fetch("/api", { cache: "no-store" });
      if (!response.ok) return;
      const capabilities = await response.json();
      const allowThinking = capabilities?.thinking_enabled === true;
      const thinking = modeSelector.querySelector('option[value="thinking"]');
      thinking.disabled = !allowThinking;
      const activeThinkingModel = typeof capabilities?.models?.thinking === "string" ? capabilities.models.thinking : "";
      const supportsHighEffort = capabilities?.thinking_effort_high === true;
      thinking.textContent = !allowThinking ? "Avançado (indisponível)" :
        supportsHighEffort ? "Esforço: alto (GPT-OSS)" : "Modelo avançado";
      thinking.title = activeThinkingModel ? "Modelo: " + activeThinkingModel : "Modelo avançado não configurado";
      if (modeSelector.selectedOptions[0]?.disabled) modeSelector.value = "fast";
      byId("mode-hint").textContent = !allowThinking ? "Modo avançado indisponível." :
        supportsHighEffort ? "Esforço alto realmente configurado no modelo GPT-OSS." : "Modelo avançado ativo; esforço alto numérico não está disponível neste provedor.";
    } catch (_) {
      // Fail closed: existing fast mode works, advanced modes stay disabled.
    }
  }

  const savedSettings = readSaved(SETTINGS_KEY);
  if (savedSettings && typeof savedSettings === "object") {
    if (THEMES.includes(savedSettings.theme)) settings.theme = savedSettings.theme;
    settings.sound = savedSettings.sound === true;
    settings.crt = savedSettings.crt !== false;
    settings.colorMode = savedSettings.colorMode === "light" ? "light" : "dark";
  }
  applySettings();
  loadConversationStore();
  showCurrentConversation();
  renderConversationList();
  if (!history.length) info("THIGAS AI pronto. Pergunte normalmente ou use /help. Não envie senhas ou chaves de API.");
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
  byId("btn-clear").addEventListener("click", startNewConversation);
  byId("btn-new-top").addEventListener("click", startNewConversation);
  byId("btn-history-top").addEventListener("click", () => setDrawerOpen(!isDrawerOpen()));
  byId("btn-close-drawer").addEventListener("click", () => setDrawerOpen(false));
  drawerBackdrop.addEventListener("click", () => setDrawerOpen(false));
  byId("btn-drawer-new").addEventListener("click", startNewConversation);
  drawerSearch.addEventListener("input", renderSidebarHistory);
  byId("btn-drawer-settings").addEventListener("click", () => { dismissMobileDrawer(); modal.showModal(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && isDrawerOpen() && mobileHistory.matches) setDrawerOpen(false); });
  if (mobileHistory.addEventListener) mobileHistory.addEventListener("change", () => setDrawerOpen(!mobileHistory.matches));
  setDrawerOpen(!mobileHistory.matches);
  byId("btn-history").addEventListener("click", () => { renderConversationList(); historyModal.showModal(); });
  byId("btn-close-history").addEventListener("click", () => historyModal.close());
  byId("btn-help").addEventListener("click", () => modal.showModal());
  byId("btn-privacy").addEventListener("click", () => modal.showModal());
  byId("btn-close-help").addEventListener("click", () => modal.close());
  const attachMenu = byId("attach-menu");
  const shortcutMenu = byId("slash-menu");
  function closeMenus() {
    attachMenu.hidden = true;
    shortcutMenu.hidden = true;
    byId("btn-attach").setAttribute("aria-expanded", "false");
  }
  byId("btn-attach").addEventListener("click", () => {
    const opening = attachMenu.hidden;
    closeMenus();
    attachMenu.hidden = !opening;
    byId("btn-attach").setAttribute("aria-expanded", String(opening));
  });
  byId("attach-document").addEventListener("click", () => { closeMenus(); byId("file-input").click(); });
  byId("attach-image").addEventListener("click", () => { closeMenus(); byId("image-input").click(); });
  byId("attach-workspace").addEventListener("click", () => { window.location.href = "/workspace"; });
  byId("image-input").addEventListener("change", async event => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || file.size > 8 * 1024 * 1024) {
      info("Use imagem PNG, JPEG ou WebP de até 8 MB.", true);
      event.target.value = "";
      return;
    }
    readingFile = true;
    setBusy();
    try {
      const form = new FormData();
      form.append("image", file);
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);
      let response;
      try { response = await fetch("/image/describe", { method: "POST", body: form, signal: controller.signal }); }
      finally { clearTimeout(timeout); }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Não consegui analisar a imagem.");
      attachment = { name: file.name + ".txt", text: "[Descrição da imagem enviada]\n" + result.description };
      byId("attachment-preview").hidden = false;
      byId("attachment-label").textContent = "▧ " + file.name + " · imagem interpretada";
    } catch(error) {
      info(error.message || "Erro ao processar a imagem.", true);
    } finally {
      event.target.value = "";
      readingFile = false;
      setBusy();
    }
  });
  input.addEventListener("input", () => {
    const value = input.value.slice(0, input.selectionStart).trim();
    shortcutMenu.hidden = !(/^(?:\/|@)[\wÀ-ÿ]*$/.test(value) && value.length <= 24);
  });
  shortcutMenu.querySelectorAll("button[data-insert]").forEach(button => button.addEventListener("click", () => {
    const value = button.dataset.insert;
    input.value = value;
    shortcutMenu.hidden = true;
    input.focus();
    resizeInput();
  }));
  document.addEventListener("click", event => {
    if (!event.target.closest(".composer-tools") && !event.target.closest("#slash-menu")) closeMenus();
  });
  const mic = byId("btn-microphone");
  const BrowserSpeech = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  if (!BrowserSpeech) {
    mic.disabled = true;
    mic.title = "Ditado indisponível neste navegador";
  } else {
    mic.addEventListener("click", () => {
      if (recognizer) { recognizer.stop(); return; }
      const speech = new BrowserSpeech();
      recognizer = speech;
      speech.lang = "pt-BR";
      speech.interimResults = false;
      speech.continuous = false;
      speech.onresult = event => {
        const transcript = Array.from(event.results).map(r => r[0]?.transcript || "").join(" ").trim();
        if (transcript) {
          input.value = (input.value.trim() + " " + transcript).trim();
          resizeInput();
          input.focus();
        }
      };
      speech.onerror = event => { info("Ditado: " + (event.error || "não disponível"), true); };
      speech.onend = () => { recognizer = null; mic.setAttribute("aria-pressed", "false"); mic.classList.remove("is-recording"); };
      try { speech.start(); mic.setAttribute("aria-pressed", "true"); mic.classList.add("is-recording"); }
      catch (_) { recognizer = null; info("O navegador não permitiu iniciar o microfone.", true); }
    });
  }

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
  void loadModelCapabilities();
})();
