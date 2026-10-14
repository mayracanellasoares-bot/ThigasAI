"use strict";

// Apenas o shell PÚBLICO estático do chat é armazenado offline.
// Nunca armazene respostas de API, documentos, anexos ou histórico no CacheStorage.
const CACHE_PREFIX = "thigas-pwa-";
const CACHE_NAME = CACHE_PREFIX + "v28-white";
const APP_SHELL = [
  "/",
  "/manifest.webmanifest",
  "/static/chat.css?v=bottom12",
  "/static/mini-nano-theme.css?v=white15",
  "/static/history-sidebar.css?v=drawer2",
  "/static/chat.js?v=white15",
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

  async function navigate(request) {
    try {
      // O site é público. Não armazenar respostas dinâmicas nem histórico.
      return await fetch(request);
    } catch (_) {
      const cache = await caches.open(CACHE_NAME);
      const home = await cache.match("/");
      if (home) return home;
      return new Response(
        "<!doctype html><html lang='pt-BR'><meta name='viewport' content='width=device-width'><title>THIGAS offline</title><p>Conecte-se à internet para conversar com o THIGAS AI.</p></html>",
        { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
      );
    }
  }

  self.addEventListener("fetch", event => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
    if (request.mode === "navigate") {
      event.respondWith(navigate(request));
      return;
    }
    if (!cacheable(request, self.location.origin)) return;
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const saved = await cache.match(request);
      if (saved) return saved;
      const response = await fetch(request);
      if (response.ok) await cache.put(request, response.clone());
      return response;
    })());
  });
}
