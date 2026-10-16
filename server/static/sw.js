"use strict";

// Apenas o shell PÚBLICO estático do chat é armazenado offline.
// Nunca armazene respostas de API, documentos, anexos ou histórico no CacheStorage.
const CACHE_PREFIX = "thigas-pwa-";
const CACHE_NAME = CACHE_PREFIX + "69809d09461c082c";
const APP_SHELL = [
  "/",
  "/manifest.webmanifest",
  "/static/icons/icon.svg",
  "/static/icons/icon-192.png",
  "/static/chat-ui.css?v=64268e027aeb3dc7",
  "/static/chat.js?v=33dfded3173bac91",
  "/static/pwa.js?v=90a93615620c09e8",
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
    let timer;
    let home;
    try {
      const cache = await caches.open(CACHE_NAME);
      home = await cache.match("/");
    } catch (_) { /* Storage restrictions must not break online navigation. */ }
    try {
      // O site é público. Não armazenar respostas dinâmicas nem histórico.
      const network = fetch(request);
      const response = home ? await Promise.race([
        network,
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error("navigation_timeout")), 4000);
        }),
      ]) : await network;
      if (response.status >= 500 && home) return home;
      return response;
    } catch (_) {
      if (home) return home;
      return new Response(
        "<!doctype html><html lang='pt-BR'><meta name='viewport' content='width=device-width'><title>THIGAS offline</title><p>Conecte-se à internet para conversar com o THIGAS AI.</p></html>",
        { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
      );
    } finally {
      clearTimeout(timer);
    }
  }

  self.addEventListener("fetch", event => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
    if (request.mode === "navigate") {
      // Documents/account pages must never receive a cached public chat shell.
      if (url.pathname === "/") event.respondWith(navigate(request));
      return;
    }
    if (!cacheable(request, self.location.origin)) return;
    event.respondWith((async () => {
      let cache;
      try {
        cache = await caches.open(CACHE_NAME);
        const saved = await cache.match(request);
        if (saved) return saved;
      } catch (_) { /* Continue online if CacheStorage is unavailable. */ }
      const response = await fetch(request);
      if (response.ok && cache) {
        try { await cache.put(request, response.clone()); } catch (_) { /* Quota/storage error. */ }
      }
      return response;
    })());
  });
}
