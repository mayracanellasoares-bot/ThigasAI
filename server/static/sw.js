"use strict";

// O shell HTML, o histórico e as sessões NUNCA entram no CacheStorage.
// Sem rede, o acesso por senha não pode ser verificado.
const CACHE_PREFIX = "thigas-pwa-";
const CACHE_NAME = CACHE_PREFIX + "v18-auth";
const APP_SHELL = [
  "/manifest.webmanifest",
  "/static/chat.css?v=caret1",
  "/static/mini-nano-theme.css?v=drawer2",
  "/static/history-sidebar.css?v=drawer2",
  "/static/chat.js?v=drawer2",
  "/static/pwa.js?v=llama2",
  "/static/icons/icon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

function cacheable(request, origin) {
  if (request.method !== "GET") return false;
  const url = new URL(request.url);
  if (url.origin !== origin) return false;
  return APP_SHELL.includes(url.pathname + url.search);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { CACHE_NAME, CACHE_PREFIX, APP_SHELL, cacheable };
}

if (typeof self !== "undefined" && self.addEventListener) {
  self.addEventListener("install", event => {
    event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  });

  self.addEventListener("activate", event => {
    event.waitUntil((async () => {
      for (const name of await caches.keys()) {
        if (name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME) await caches.delete(name);
      }
      await self.clients.claim();
    })());
  });

  self.addEventListener("message", event => {
    if (event.data && event.data.type === "SKIP_WAITING") void self.skipWaiting();
  });

  self.addEventListener("fetch", event => {
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;

    // Navegações (inclusive /, /workspace e /login) sempre passam pelo servidor.
    if (event.request.mode === "navigate") {
      event.respondWith(fetch(event.request).catch(() => new Response(
        "<!doctype html><html lang='pt-BR'><meta name='viewport' content='width=device-width'><title>THIGAS offline</title><p>Conecte-se à internet para validar seu acesso ao THIGAS AI.</p></html>",
        { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } }
      )));
      return;
    }

    if (!cacheable(event.request, self.location.origin)) return;
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const saved = await cache.match(event.request);
      if (saved) return saved;
      const response = await fetch(event.request);
      if (response.ok) await cache.put(event.request, response.clone());
      return response;
    })());
  });
}
