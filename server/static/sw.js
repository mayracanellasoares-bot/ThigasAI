"use strict";

const CACHE_PREFIX = "thigas-pwa-";
const CACHE_NAME = CACHE_PREFIX + "v2";
const APP_SHELL = [
  "/",
  "/manifest.webmanifest",
  "/static/chat.css?v=llama2",
  "/static/chat.js?v=llama2",
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

  async function navigation(request, event) {
    const cache = await caches.open(CACHE_NAME);
    const network = fetch(request).then(async response => {
      if (!response.ok) throw new Error("Navegação indisponível");
      await cache.put("/", response.clone());
      return response;
    });
    event.waitUntil(network.catch(() => undefined));
    let timeout;
    try {
      return await Promise.race([network, new Promise((_, reject) => {
        timeout = setTimeout(() => reject(new Error("Navegação lenta")), 5000);
      })]);
    } catch (_) {
      const saved = await cache.match("/");
      if (saved) return saved;
      return new Response("<!doctype html><html lang='pt-BR'><meta name='viewport' content='width=device-width'><title>THIGAS offline</title><p>Conecte-se à internet para abrir o THIGAS pela primeira vez.</p></html>", { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } });
    } finally { clearTimeout(timeout); }
  }

  self.addEventListener("fetch", event => {
    if (!cacheable(event.request, self.location.origin)) return;
    const url = new URL(event.request.url);
    if (event.request.mode === "navigate" && url.pathname === "/") {
      event.respondWith(navigation(event.request, event));
      return;
    }
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
