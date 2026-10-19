"use strict";

const labels = {
  gmail: "Gmail", google_calendar: "Google Calendar", github: "GitHub",
  notion: "Notion", google_drive: "Google Drive", hubspot: "HubSpot", salesforce: "Salesforce",
};
const actionLabels = {
  "gmail.send": "Enviar e-mail", "github.issue.create": "Criar issue no GitHub",
  "notion.page.create": "Criar página no Notion",
  "google_drive.document.create": "Criar documento no Google Docs",
  "google_drive.spreadsheet.create": "Criar planilha no Google Sheets",
  "google_drive.presentation.create": "Criar apresentação no Google Slides",
  "hubspot.contact.create": "Criar contato no HubSpot",
  "salesforce.task.create": "Criar tarefa no Salesforce",
};
const state = { csrf: "", connections: [], workflows: [], approvals: [], skills: [], lastPrompt: "" };
const $ = id => document.getElementById(id);

function node(tag, className, value) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (value !== undefined) el.textContent = String(value);
  return el;
}
function toast(message) {
  const target = $("toast");
  target.textContent = message;
  target.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { target.hidden = true; }, 5000);
}
async function call(path, method = "GET", data) {
  const headers = { Accept: "application/json" };
  if (method !== "GET") {
    headers["Content-Type"] = "application/json";
    if (state.csrf) headers["X-Octonous-CSRF"] = state.csrf;
  }
  const response = await fetch("/octonous" + path, {
    method, headers, credentials: "same-origin",
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  let value;
  try { value = await response.json(); }
  catch { throw new Error("O servidor não retornou JSON."); }
  if (!response.ok) throw new Error(value.error || "Falha no servidor (" + response.status + ").");
  return value;
}
function show(view) {
  document.querySelectorAll(".view").forEach(el => el.classList.toggle("active", el.id === "view-" + view));
  document.querySelectorAll(".nav").forEach(el => el.classList.toggle("active", el.dataset.view === view));
  const current = document.querySelector('.nav[data-view="' + view + '"]');
  $("page-name").textContent = current?.textContent?.trim() || "Visão geral";
  document.querySelector(".sidebar").classList.remove("open");
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function showAuth(authenticated) {
  $("login-screen").hidden = authenticated;
  $("app").hidden = !authenticated;
  if (!authenticated) $("owner-password").focus();
}
function busy(button, active) {
  button.disabled = active;
  if (active) button.dataset.oldText = button.textContent;
  button.textContent = active ? "Aguarde…" : (button.dataset.oldText || button.textContent);
}
function empty(element, message) {
  element.replaceChildren(node("p", "muted", message));
}
function addBubble(message, role) {
  const bubble = node("div", role === "user" ? "user-bubble" : "assistant-bubble", message);
  $("conversation").append(bubble);
  $("conversation").scrollTop = $("conversation").scrollHeight;
}
function suggestWorkflow(prompt) {
  const text = prompt.toLowerCase();
  let trigger = "manual";
  if (/reuni[aã]o|meeting/.test(text)) trigger = "google_calendar.meeting_ended";
  else if (/(?:pull request|\bpr\b).*(?:mesclad|merged)|(?:mesclad|merged).*(?:pull request|\bpr\b)/.test(text)) trigger = "github.pr_merged";
  else if (/sexta-feira|toda sexta/.test(text)) trigger = "gmail.friday";
  else if (/notion/.test(text) && /p[aá]gina/.test(text)) trigger = "notion.page_created";
  $("workflow-trigger").value = trigger;
  const related = {
    "google_calendar.meeting_ended": ["google_calendar", "gmail"],
    "github.pr_merged": ["github"], "gmail.friday": ["gmail"],
    "notion.page_created": ["notion"],
  }[trigger] || [];
  document.querySelectorAll('input[name="app"]').forEach(box => {
    box.checked = related.includes(box.value);
  });
  $("workflow-title").value = {
    "google_calendar.meeting_ended": "Acompanhamento após reunião",
    "github.pr_merged": "Acompanhamento de PR",
    "gmail.friday": "Revisão semanal de e-mails",
    "notion.page_created": "Nova página no Notion",
  }[trigger] || "";
  if (trigger === "google_calendar.meeting_ended" && state.skills.some(x => x.slug === "post-meeting-followup")) {
    $("workflow-skill").value = "post-meeting-followup";
  }
}
function renderConnections() {
  const list = $("connection-list");
  list.replaceChildren();
  for (const item of state.connections) {
    const card = node("article", "connection-card");
    const row = node("div", "connection-card-top");
    row.append(node("span", "app-icon", labels[item.provider]?.[0] || "?"));
    row.append(node("span", "badge" + (item.connected ? " connected" : ""),
      item.connected ? "Conectado" : "Desconectado"));
    card.append(row, node("h3", "", labels[item.provider]), node("p", "",
      item.configured ? "Autorização direta pelo aplicativo." : "Configure o aplicativo OAuth no Render."));
    const button = node("button", "", item.connected ? "Desconectar →" : "Conectar →");
    button.type = "button";
    button.addEventListener("click", async () => {
      busy(button, true);
      try {
        if (item.connected) {
          if (!confirm("Desconectar " + labels[item.provider] + "?")) return;
          await call("/api/connections/" + item.provider + "/disconnect", "POST", {});
          await refresh();
        } else {
          const result = await call("/api/connections/" + item.provider + "/start", "POST", {});
          window.location.assign(result.url);
        }
      } catch (error) { toast(error.message); }
      finally { busy(button, false); }
    });
    card.append(button);
    list.append(card);
  }
  $("stat-connections").textContent = state.connections.filter(x => x.connected).length;
}
function renderSearch(results) {
  const target = $("search-results");
  target.replaceChildren();
  const entries = Object.entries(results);
  if (!entries.length) return empty(target, "Conecte um aplicativo para pesquisar.");
  for (const [provider, matches] of entries) {
    const group = node("section", "search-group");
    group.append(node("h3", "", labels[provider] || provider));
    if (matches.error) group.append(node("p", "muted", matches.error));
    else if (!matches.length) group.append(node("p", "muted", "Nenhum resultado."));
    else for (const hit of matches) {
      const link = hit.url?.startsWith("https://") ? node("a", "search-hit") : node("div", "search-hit");
      if (link.tagName === "A") { link.href = hit.url; link.target = "_blank"; link.rel = "noopener noreferrer"; }
      link.append(node("b", "", hit.title || "(sem título)"), node("small", "", hit.summary || ""));
      group.append(link);
    }
    target.append(group);
  }
}
function renderSkills() {
  const select = $("workflow-skill"), list = $("skill-list");
  select.replaceChildren(new Option("Sem Skill", ""));
  list.replaceChildren();
  for (const skill of state.skills) {
    select.add(new Option(skill.name + " · " + skill.description, skill.slug));
    const card = node("article", "list-card");
    card.append(node("h3", "", skill.name), node("p", "", skill.description),
      node("span", "card-meta", "Gatilhos: " + (skill.triggers || []).join(", ")));
    list.append(card);
  }
  if (!state.skills.length) empty(list, "Nenhuma Skill instalada.");
}
function renderWorkflowChoices() {
  const apps = $("workflow-apps"), actions = $("workflow-actions");
  apps.replaceChildren(); actions.replaceChildren();
  for (const [key, label] of Object.entries(labels)) {
    const wrap = node("label"), box = node("input");
    box.type = "checkbox"; box.value = key; box.name = "app";
    wrap.append(box, document.createTextNode(label)); apps.append(wrap);
  }
  for (const [key, label] of Object.entries(actionLabels)) {
    const wrap = node("label"), box = node("input");
    box.type = "checkbox"; box.value = key; box.name = "action";
    wrap.append(box, document.createTextNode(label)); actions.append(wrap);
  }
}
function renderWorkflows() {
  const list = $("workflow-list");
  list.replaceChildren();
  $("stat-workflows").textContent = state.workflows.length;
  if (!state.workflows.length) return empty(list, "Você ainda não salvou uma automação.");
  for (const flow of state.workflows) {
    const card = node("article", "list-card");
    card.append(node("h3", "", flow.title), node("p", "", flow.prompt),
      node("span", "card-meta", flow.trigger + " · " + (flow.enabled ? "Ativa" : "Pausada") +
        " · Apps: " + flow.apps.map(x => labels[x] || x).join(", ")));
    const actions = node("div", "card-actions");
    const run = node("button", "secondary", "Testar agora");
    run.type = "button";
    run.addEventListener("click", async () => {
      busy(run, true);
      try {
        const result = await call("/api/workflows/" + flow.id + "/run", "POST", {});
        show("chat"); addBubble("Teste do fluxo: " + flow.title, "user");
        addBubble(result.answer + (result.approval_id ? "\n\nAção aguardando aprovação." : ""), "assistant");
        await refresh();
      } catch (error) { toast(error.message); }
      finally { busy(run, false); }
    });
    const toggle = node("button", "secondary", flow.enabled ? "Pausar" : "Ativar");
    toggle.type = "button";
    toggle.addEventListener("click", async () => {
      try {
        await call("/api/workflows/" + flow.id + "/toggle", "POST", { enabled: !flow.enabled });
        await refresh();
      } catch (error) { toast(error.message); }
    });
    actions.append(run, toggle); card.append(actions); list.append(card);
  }
}
function renderApprovals() {
  const list = $("approval-list");
  list.replaceChildren();
  const pending = state.approvals.filter(x => x.status === "pending");
  $("stat-approvals").textContent = pending.length;
  $("approval-count").textContent = pending.length ? String(pending.length) : "";
  if (!state.approvals.length) return empty(list, "Nenhuma ação proposta até agora.");
  for (const item of state.approvals) {
    const card = node("article", "list-card");
    card.append(node("h3", "", actionLabels[item.action] || item.action),
      node("span", "card-meta", "Estado: " + item.status + " · " + item.created_at));
    const editor = node("textarea", "payload-editor");
    editor.value = JSON.stringify(item.payload, null, 2);
    editor.setAttribute("aria-label", "Conteúdo da ação proposta");
    editor.readOnly = item.status !== "pending";
    card.append(editor);
    if (item.error) card.append(node("p", "", item.error));
    if (item.status === "pending") {
      const row = node("div", "card-actions");
      const approve = node("button", "primary", "Aprovar e executar");
      const reject = node("button", "danger", "Rejeitar");
      approve.type = reject.type = "button";
      approve.addEventListener("click", async () => {
        let payload;
        try { payload = JSON.parse(editor.value); }
        catch { return toast("O conteúdo precisa ser JSON válido."); }
        if (!confirm("Executar " + (actionLabels[item.action] || item.action) + " agora?")) return;
        busy(approve, true);
        try {
          const result = await call("/api/approvals/" + item.id + "/decision", "POST",
            { decision: "approve", payload });
          toast(result.status === "executed" ? "Ação executada." : "Confira o resultado.");
          await refresh();
        } catch (error) { toast(error.message); await refresh(); }
        finally { busy(approve, false); }
      });
      reject.addEventListener("click", async () => {
        try {
          await call("/api/approvals/" + item.id + "/decision", "POST", { decision: "reject" });
          await refresh();
        } catch (error) { toast(error.message); }
      });
      row.append(approve, reject); card.append(row);
    }
    list.append(card);
  }
}
function renderLogs(logs) {
  const list = $("log-list");
  list.replaceChildren();
  if (!logs.length) return empty(list, "Nenhuma atividade registrada.");
  for (const log of logs) {
    const card = node("details", "list-card");
    card.append(node("summary", "", (log.tool || "Agente") + " · " + log.operation +
      " · " + log.status + " · " + new Date(log.at).toLocaleString("pt-BR")));
    card.append(node("pre", "log-detail",
      JSON.stringify({ input: log.input, output: log.output, run_id: log.run_id }, null, 2)));
    list.append(card);
  }
}
async function refresh() {
  const [connections, workflows, approvals, skills, model, logs] = await Promise.all([
    call("/api/connections"), call("/api/workflows"), call("/api/approvals"),
    call("/api/skills"), call("/api/model"), call("/api/logs"),
  ]);
  state.connections = connections.connections; state.workflows = workflows.workflows;
  state.approvals = approvals.approvals; state.skills = skills.skills;
  renderConnections(); renderWorkflows(); renderApprovals(); renderSkills(); renderLogs(logs.logs);
  if (model.model.configured) {
    $("model-provider").value = model.model.provider;
    $("model-name").value = model.model.model;
    $("ollama-origin").value = model.model.origin || "http://127.0.0.1:11434";
    $("model-status").textContent = model.model.provider === "maritaca"
      ? "Sabiá configurado. Sem chave informada, será usada a do Render."
      : "Modelo configurado. Para alterar, informe novamente a chave.";
    toggleModelFields();
  }
}
function toggleModelFields() {
  const provider = $("model-provider").value;
  const local = provider === "ollama";
  $("api-key-label").hidden = local;
  $("ollama-label").hidden = !local;
  $("model-key").required = !local && provider !== "maritaca";
}
async function bootstrap() {
  try {
    const session = await call("/api/session");
    showAuth(session.authenticated);
    if (session.authenticated) {
      state.csrf = session.csrf;
      await refresh();
      const oauth = new URL(location.href).searchParams.get("oauth");
      if (oauth) { toast(oauth === "conectado" ? "Aplicativo conectado." : "Conexão não concluída."); history.replaceState(null, "", "/octonous"); }
    }
  } catch (error) { toast(error.message); }
}
document.querySelectorAll("[data-view]").forEach(btn =>
  btn.addEventListener("click", () => show(btn.dataset.view)));
document.querySelectorAll("[data-go]").forEach(btn =>
  btn.addEventListener("click", () => show(btn.dataset.go)));
document.querySelectorAll("[data-prompt]").forEach(btn => btn.addEventListener("click", () => {
  $("prompt").value = btn.dataset.prompt; show("chat"); $("prompt").focus();
}));
$("menu-toggle").addEventListener("click", () => document.querySelector(".sidebar").classList.toggle("open"));
$("login-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  busy(button, true);
  try {
    await call("/api/login", "POST", { password: $("owner-password").value });
    $("owner-password").value = "";
    $("login-message").textContent = "";
    await bootstrap();
  } catch (error) { $("login-message").textContent = error.message; }
  finally { busy(button, false); }
});
$("logout").addEventListener("click", async () => {
  try { await call("/api/logout", "POST", {}); state.csrf = ""; showAuth(false); }
  catch (error) { toast(error.message); }
});
$("search-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  busy(button, true);
  try {
    const data = await call("/api/search", "POST", { query: $("search-query").value });
    renderSearch(data.results);
    const logs = await call("/api/logs"); renderLogs(logs.logs);
  } catch (error) { toast(error.message); }
  finally { busy(button, false); }
});
$("chat-form").addEventListener("submit", async event => {
  event.preventDefault();
  const prompt = $("prompt").value.trim();
  if (!prompt) return;
  const button = event.currentTarget.querySelector("button");
  busy(button, true); addBubble(prompt, "user");
  try {
    const result = await call("/api/chat", "POST", { prompt, search: $("chat-search").checked });
    state.lastPrompt = prompt;
    $("workflow-prompt").value = prompt;
    suggestWorkflow(prompt);
    addBubble(result.answer + (result.approval_id ? "\n\nAção proposta: revise na aba Aprovações." : ""), "assistant");
    $("prompt").value = "";
    await refresh();
  } catch (error) { addBubble("Erro: " + error.message, "assistant"); }
  finally { busy(button, false); }
});
$("workflow-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const apps = [...form.querySelectorAll('input[name="app"]:checked')].map(x => x.value);
  const actions = [...form.querySelectorAll('input[name="action"]:checked')].map(x => x.value);
  const button = form.querySelector("button[type=submit]");
  busy(button, true);
  try {
    await call("/api/workflows", "POST", {
      title: $("workflow-title").value, prompt: $("workflow-prompt").value,
      trigger: $("workflow-trigger").value, skill: $("workflow-skill").value,
      hour: Number($("workflow-hour").value), weekday: Number($("workflow-weekday").value),
      apps, actions,
    });
    toast("Automação salva."); await refresh();
  } catch (error) { toast(error.message); }
  finally { busy(button, false); }
});
$("model-provider").addEventListener("change", toggleModelFields);
$("model-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button");
  busy(button, true);
  try {
    await call("/api/model", "POST", {
      provider: $("model-provider").value, model: $("model-name").value,
      api_key: $("model-key").value, origin: $("ollama-origin").value,
    });
    $("model-key").value = "";
    toast("Modelo salvo."); await refresh();
  } catch (error) { toast(error.message); }
  finally { busy(button, false); }
});
const themes = new Set(["aurora", "claro", "oceano", "violeta", "floresta", "coral"]);
let storedTheme = "aurora";
try { storedTheme = localStorage.getItem("thigas-hub-theme") || "aurora"; } catch {}
$("theme-select").value = themes.has(storedTheme) ? storedTheme : "aurora";
document.body.dataset.theme = $("theme-select").value;
$("theme-select").addEventListener("change", event => {
  document.body.dataset.theme = event.target.value;
  try { localStorage.setItem("thigas-hub-theme", event.target.value); } catch {}
});
$("model-name").value = "sabia-4";
renderWorkflowChoices();
toggleModelFields();
bootstrap();
