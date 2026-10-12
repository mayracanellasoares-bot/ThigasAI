(function () {
  "use strict";
  const params = new URLSearchParams(window.location.search);
  const errors = {
    senha: "Senha incorreta. Verifique e tente novamente.",
    limite: "Muitas tentativas. Tente novamente em alguns minutos.",
    config: "A senha ainda não foi configurada pelo administrador no servidor."
  };
  const notice = document.getElementById("notice");
  if (errors[params.get("erro")]) {
    notice.textContent = errors[params.get("erro")];
    notice.hidden = false;
  }
  const installButton = document.getElementById("btn-install-login");
  const hint = document.getElementById("install-hint");
  let pendingInstall = null;
  const installed = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  if (installed()) installButton.hidden = true;
  window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    pendingInstall = event;
  });
  window.addEventListener("appinstalled", () => {
    pendingInstall = null;
    installButton.hidden = true;
  });
  installButton.addEventListener("click", async () => {
    if (pendingInstall) {
      const event = pendingInstall;
      pendingInstall = null;
      try {
        await event.prompt();
        const result = await event.userChoice;
        if (result.outcome === "accepted") installButton.hidden = true;
      } catch (_) { /* Orientação manual abaixo. */ }
    }
    if (!installButton.hidden) {
      hint.textContent = "Android/Chrome: menu ⋮ → Instalar aplicativo. Computador: ícone de instalação do Chrome/Edge. iPhone: Safari → Compartilhar → Adicionar à Tela de Início.";
      hint.hidden = false;
    }
  });
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {});
  }
})();
