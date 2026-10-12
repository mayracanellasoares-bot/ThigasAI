"use strict";

// Apenas os recursos PÚBLICOS são armazenados offline.
// Nunca armazene HTML do chat, API, workspace, anexos ou histórico no CacheStorage.
const CACHE_PREFIX = "thigas-pwa-";
const CACHE_NAME = CACHE_PREFIX + "v18-auth";
const APP_SHELL = [
  "/entrar",
  "/manifest.webmanifest",
  "/static/login.js?v=access1",
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
      // Nunca persistir páginas autenticadas, mesmo após login ou redirecionamentos.
      return await fetch(request);
    } catch (_) {
      const cache = await caches.open(CACHE_NAME);
      const login = await cache.match("/entrar");
      if (login) return login;
      return new Response(
        "<!doctype html><html lang='pt-BR'><meta name='viewport' content='width=device-width'><title>THIGAS offline</title><p>Conecte-se à internet para abrir o THIGAS pela primeira vez e informar a senha.</p></html>",
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
