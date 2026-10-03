(function () {
  "use strict";
  const installButton = document.getElementById("btn-install");
  const installModal = document.getElementById("install-modal");
  const updateNotice = document.getElementById("pwa-update");
  const updateButton = document.getElementById("btn-update");
  const displayMode = window.matchMedia("(display-mode: standalone)");
  let installPrompt = null;
  let waitingWorker = null;
  let applyingUpdate = false;

  function refreshInstalled() {
    installButton.hidden = displayMode.matches || window.navigator.standalone === true;
  }
  refreshInstalled();
  if (displayMode.addEventListener) displayMode.addEventListener("change", refreshInstalled);

  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    installPrompt = event;
    refreshInstalled();
  });
  window.addEventListener("appinstalled", () => {
    installPrompt = null;
    installButton.hidden = true;
  });
  installButton.addEventListener("click", async () => {
    if (!installPrompt) { installModal.showModal(); return; }
    const prompt = installPrompt;
    installPrompt = null;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      if (choice.outcome === "accepted") installButton.hidden = true;
    } catch (_) { installModal.showModal(); }
  });
  document.getElementById("btn-close-install").addEventListener("click", () => installModal.close());

  function showUpdate(worker) {
    waitingWorker = worker;
    updateNotice.hidden = !worker;
  }
  updateButton.addEventListener("click", () => {
    if (!waitingWorker) return;
    const unsentText = document.getElementById("chat-input").value.trim();
    const hasAttachment = !document.getElementById("attachment-preview").hidden;
    const busy = document.getElementById("chat-logs").getAttribute("aria-busy") === "true";
    if ((unsentText || hasAttachment || busy) && !window.confirm("Atualizar recarrega a tela. A mensagem não enviada ou a resposta em andamento será descartada. Continuar?")) return;
    applyingUpdate = true;
    updateButton.disabled = true;
    waitingWorker.postMessage({ type: "SKIP_WAITING" });
  });

  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    // Uma primeira instalação não recarrega a conversa em andamento.
    if (applyingUpdate) window.location.reload();
  });
  navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).then(registration => {
    if (registration.waiting) showUpdate(registration.waiting);
    registration.addEventListener("updatefound", () => {
      const worker = registration.installing;
      if (!worker) return;
      worker.addEventListener("statechange", () => {
        if (worker.state === "installed" && navigator.serviceWorker.controller) showUpdate(registration.waiting || worker);
      });
    });
  }).catch(() => {
    // Falha do cache offline não impede o chat online ou revela dados ao usuário.
    console.warn("THIGAS: não foi possível preparar o modo offline nesta visita.");
  });
})();
