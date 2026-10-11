"use strict";
(() => {
 const $ = (id) => document.getElementById(id);
 async function inspect(analyze) {
   const url = $("url").value.trim();
   if (!url) { $("status").textContent = "Insira o endereço de um site."; return; }
   const mode = $("mode").value;
   $("verify").disabled = true; $("analyze").disabled = true;
   $("status").textContent = analyze ? "Lendo e analisando o conteúdo público…" : "Verificando o link…";
   $("result-section").hidden = true;
   try {
     const controller = new AbortController();
     const timeout = setTimeout(() => controller.abort(), 45000);
     let response;
     try { response = await fetch("/link/check", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url,analyze,mode}),signal:controller.signal}); }
     finally { clearTimeout(timeout); }
     const data = await response.json();
     if (!response.ok) throw new Error(data.error || "Não foi possível verificar o link.");
     const lines = [
       "Endereço: " + data.url,
       "HTTP: " + data.status,
       "Acessível: " + (data.reachable ? "Sim" : "Não"),
       data.redirect ? "Redirecionamento informado: " + data.redirect : "",
       data.title ? "Título: " + data.title : "",
       data.note || "",
       data.analysis ? "\nAnálise do conteúdo:\n" + data.analysis : "",
       !analyze && data.text ? "\nTrecho da página:\n" + data.text.slice(0,1400) : ""
     ].filter(Boolean);
     $("result").textContent = lines.join("\n");
     $("result-section").hidden = false;
     $("status").textContent = "Verificação concluída.";
   } catch(error) { $("status").textContent = error.name === "AbortError" ? "Tempo limite excedido." : error.message; }
   finally { $("verify").disabled = false; $("analyze").disabled = false; }
 }
 $("verify").addEventListener("click", () => inspect(false));
 $("analyze").addEventListener("click", () => inspect(true));
})();