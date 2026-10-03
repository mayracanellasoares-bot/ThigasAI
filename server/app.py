import os
from typing import Any

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

MARITACA_URL = os.getenv(
    "MARITACA_URL",
    "https://chat.maritaca.ai/api/chat/completions",
).strip()
MARITACA_MODEL = os.getenv("MARITACA_MODEL", "sabiazinho-4").strip()
MARITACA_API_KEY = os.getenv("MARITACA_API_KEY", "").strip()
try:
    MARITACA_MAX_TOKENS = int(os.getenv("MARITACA_MAX_TOKENS", "3072"))
except ValueError:
    MARITACA_MAX_TOKENS = 3072

SYSTEM_PROMPT = """
Você é o THIGAS Coder, assistente de programação configurado por Thiago Fillipe Soares.

Responda sempre em português do Brasil.
Ajude a criar, explicar, revisar e corrigir códigos.
Produza respostas completas e úteis, sem encerrar antes de concluir o raciocínio ou o código.
Quando corrigir um código:
1. Explique a causa do problema de forma clara.
2. Entregue o código completo corrigido.
3. Inclua testes quando forem úteis.
4. Nunca diga que executou testes se eles não foram executados.
5. Se houver dúvida, informe claramente.
6. Preserve a intenção original do usuário.
7. Use blocos Markdown com a linguagem correta.
8. Não invente bibliotecas, APIs, resultados ou arquivos.
""".strip()


def text_content(value: Any) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or "")

    if isinstance(value, list):
        parts = []
        for block in value:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content") or ""
                if text:
                    parts.append(str(text))
        return "\n".join(parts)

    return ""


def build_messages(question: str, history: Any) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    previous = []

    for item in history if isinstance(history, list) else []:
        if isinstance(item, dict):
            role = item.get("role")
            content = text_content(item.get("content", ""))
            if role in ("user", "assistant") and content.strip():
                previous.append({"role": role, "content": content.strip()})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            old_question = text_content(item[0]).strip()
            old_answer = text_content(item[1]).strip()
            if old_question:
                previous.append({"role": "user", "content": old_question})
            if old_answer:
                previous.append({"role": "assistant", "content": old_answer})

    messages.extend(previous[-12:])
    messages.append({"role": "user", "content": question})
    return messages


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.get("/")
def index():
    return jsonify(
        {
            "name": "THIGAS Coder Gateway",
            "status": "ok",
            "endpoint": "/chat",
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "provider": "maritaca"})


@app.route("/chat", methods=["OPTIONS"])
def chat_options():
    return ("", 204)


@app.post("/chat")
def chat():
    body = request.get_json(silent=True) or {}
    question = text_content(body.get("message", body.get("question", ""))).strip()

    if not question:
        return jsonify({"error": "Envie uma pergunta no campo message."}), 400

    if len(question) > 60000:
        return jsonify({"error": "A mensagem ou arquivo excede o limite de 60000 caracteres."}), 413

    if not MARITACA_API_KEY:
        return jsonify({"error": "MARITACA_API_KEY não configurada no servidor."}), 503

    payload = {
        "model": MARITACA_MODEL,
        "messages": build_messages(question, body.get("history", [])),
        "temperature": 0.2,
        "max_tokens": MARITACA_MAX_TOKENS,
        "stream": False,
    }

    try:
        upstream = requests.post(
            MARITACA_URL,
            headers={
                "Authorization": f"Bearer {MARITACA_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=75,
        )
    except requests.Timeout:
        app.logger.warning("Timeout ao consultar a Maritaca")
        return jsonify({"error": "A Maritaca demorou para responder."}), 504
    except requests.RequestException as exc:
        app.logger.warning("Falha de conexão com a Maritaca: %s", exc.__class__.__name__)
        return jsonify({"error": "Não foi possível conectar à Maritaca."}), 502

    if upstream.status_code == 401:
        return jsonify({"error": "A chave da Maritaca foi recusada."}), 502

    if upstream.status_code == 429:
        return jsonify({"error": "A Maritaca informou limite ou cota excedida."}), 429

    if upstream.status_code >= 400:
        return jsonify({"error": f"A Maritaca recusou a consulta (HTTP {upstream.status_code})."}), 502

    try:
        data = upstream.json()
    except ValueError:
        return jsonify({"error": "A Maritaca retornou uma resposta inválida."}), 502

    choices = data.get("choices") or []
    if not choices:
        return jsonify({"error": "A Maritaca não retornou uma resposta."}), 502

    choice = choices[0] or {}
    message = choice.get("message") or {}
    answer = text_content(message.get("content", "")).strip()
    if not answer:
        answer = text_content(choice.get("text", "")).strip()

    if not answer:
        return jsonify({"error": "A resposta da Maritaca veio vazia."}), 502

    return jsonify({"answer": answer, "model": MARITACA_MODEL})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    app.run(host="0.0.0.0", port=port)
