const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const worker = require("../static/sw.js");
const ORIGIN = "https://thigas.test";

function workerHarness(fetcher) {
  const listeners = {};
  const buckets = new Map();
  const key = request => new URL(typeof request === "string" ? request : request.url, ORIGIN).href;
  let claimed = false, skipped = false;
  const cacheStorage = {
    keys: async () => [...buckets.keys()],
    delete: async name => buckets.delete(name),
    open: async name => {
      if (!buckets.has(name)) buckets.set(name, new Map());
      const bucket = buckets.get(name);
      return {
        put: async (request, response) => bucket.set(key(request), response.clone()),
        match: async request => bucket.get(key(request))?.clone(),
        addAll: async resources => {
          const values = await Promise.all(resources.map(async resource => {
            const response = await fetcher(new Request(new URL(resource, ORIGIN)));
            if (!response.ok) throw new Error("Precache failed");
            return [key(resource), response];
          }));
          for (const [url, response] of values) bucket.set(url, response.clone());
        },
      };
    },
  };
  const source = fs.readFileSync(path.join(__dirname, "../static/sw.js"), "utf8");
  vm.runInNewContext(source, {
    self: { location: { origin: ORIGIN }, addEventListener: (type, callback) => { listeners[type] = callback; }, clients: { claim: async () => { claimed = true; } }, skipWaiting: async () => { skipped = true; } },
    caches: cacheStorage, fetch: fetcher, URL, Request, Response, setTimeout, clearTimeout,
  });
  return {
    buckets, cacheStorage, claimed: () => claimed, skipped: () => skipped,
    async lifecycle(type, data) {
      const waits = [];
      listeners[type]({ data, waitUntil: promise => waits.push(promise) });
      await Promise.all(waits);
    },
    async request(url, method = "GET", mode = "cors") {
      let result;
      const waits = [];
      listeners.fetch({ request: { url: new URL(url, ORIGIN).href, method, mode }, respondWith: promise => { result = promise; }, waitUntil: promise => waits.push(promise) });
      const response = result ? await result : undefined;
      await Promise.all(waits);
      return response;
    },
  };
}

test("manifest possui identidade, escopo e ícones realmente presentes", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, "../static/manifest.webmanifest"), "utf8"));
  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.start_url, manifest.scope);
  assert.equal(manifest.prefer_related_applications, false);
  for (const icon of manifest.icons) {
    const data = fs.readFileSync(path.join(__dirname, "..", icon.src.replace(/^\/static/, "static")));
    assert.equal(data.readUInt32BE(16), Number(icon.sizes.split("x")[0]));
    assert.equal(data.readUInt32BE(20), Number(icon.sizes.split("x")[1]));
    assert.equal(icon.type, "image/png");
  }
});

test("cache aceita somente recursos públicos, nunca chat, health, API, anexos ou terceiros", () => {
  for (const resource of worker.APP_SHELL) assert.equal(worker.cacheable(new Request(new URL(resource, ORIGIN)), ORIGIN), true);
  for (const resource of ["/chat", "/health", "/api", "/telegram/webhook", "/upload", "/static/secret.txt"]) {
    assert.equal(worker.cacheable(new Request(new URL(resource, ORIGIN)), ORIGIN), false);
    assert.equal(worker.cacheable(new Request(new URL(resource, ORIGIN), { method: "POST" }), ORIGIN), false);
  }
  assert.equal(worker.cacheable(new Request(ORIGIN + "/", { method: "POST" }), ORIGIN), false);
  assert.equal(worker.cacheable(new Request("https://other.test/"), ORIGIN), false);
});

test("instalação salva interface completa e ativação mantém caches alheios e histórico fora do cache", async () => {
  const seen = [];
  const harness = workerHarness(async request => { seen.push(new URL(request.url).pathname); return new Response("shell"); });
  await harness.cacheStorage.open("thigas-pwa-antigo");
  await harness.cacheStorage.open("outra-aplicacao");
  await harness.lifecycle("install");
  assert.equal(harness.buckets.get(worker.CACHE_NAME).size, worker.APP_SHELL.length);
  assert.ok(!seen.includes("/chat"));
  await harness.lifecycle("activate");
  assert.equal(harness.claimed(), true);
  assert.equal(harness.buckets.has("thigas-pwa-antigo"), false);
  assert.equal(harness.buckets.has("outra-aplicacao"), true);
  assert.equal(harness.buckets.has(worker.CACHE_NAME), true);
});

test("offline abre a tela salva e entrega CSS sem solicitar inferência", async () => {
  let online = true, calls = 0;
  const harness = workerHarness(async request => {
    calls++;
    if (!online) throw new TypeError("offline");
    return new Response(new URL(request.url).pathname === "/" ? "THIGAS HTML" : "asset");
  });
  await harness.lifecycle("install");
  online = false;
  const page = await harness.request("/", "GET", "navigate");
  assert.equal(await page.text(), "THIGAS HTML");
  const beforeAsset = calls;
  const css = await harness.request("/static/chat.css?v=pwa1");
  assert.equal(await css.text(), "asset");
  assert.equal(calls, beforeAsset);
  assert.equal(await harness.request("/chat", "POST"), undefined);
});

test("navegação online atualiza cache da raiz sem persistir resposta da IA", async () => {
  let version = "v1";
  const harness = workerHarness(async () => new Response(version));
  await harness.lifecycle("install");
  version = "v2";
  const response = await harness.request("/", "GET", "navigate");
  assert.equal(await response.text(), "v2");
  const cache = await harness.cacheStorage.open(worker.CACHE_NAME);
  assert.equal(await (await cache.match("/")).text(), "v2");
  assert.equal(await harness.request("/health"), undefined);
});

test("primeiro acesso offline sem cache informa a necessidade de conexão", async () => {
  const harness = workerHarness(async () => { throw new TypeError("offline"); });
  const response = await harness.request("/", "GET", "navigate");
  assert.equal(response.status, 503);
  assert.match(await response.text(), /primeira vez/);
});

test("nova versão só ativa imediatamente após comando explícito", async () => {
  const harness = workerHarness(async () => new Response("shell"));
  await harness.lifecycle("install");
  assert.equal(harness.skipped(), false);
  await harness.lifecycle("message", { type: "SKIP_WAITING" });
  assert.equal(harness.skipped(), true);
});

test("recursos versionados do HTML e ícones pertencem ao precache", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  for (const match of html.matchAll(/(?:src|href)="(\/static\/[^\"]+)"/g)) assert.ok(worker.APP_SHELL.includes(match[1]), match[1]);
});

test("elementos do instalador e aviso de atualização existem e são seguros", () => {
  const html = fs.readFileSync(path.join(__dirname, "../static/index.html"), "utf8");
  const source = fs.readFileSync(path.join(__dirname, "../static/pwa.js"), "utf8");
  for (const match of source.matchAll(/getElementById\("([^\"]+)"\)/g)) assert.ok(html.includes('id="' + match[1] + '"'), match[1]);
  assert.doesNotMatch(source, /\.innerHTML\s*=|\beval\s*\(/);
  assert.match(source, /window\.isSecureContext/);
});
