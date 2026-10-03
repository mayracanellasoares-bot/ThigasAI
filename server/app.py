import os
import threading
from concurrent.futures import ThreadPoolExecutor
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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").strip().rstrip("/")
if not TELEGRAM_WEBHOOK_URL and RENDER_EXTERNAL_URL:
    TELEGRAM_WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/telegram/webhook"

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


class GatewayError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


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


def ask_maritaca(question: str, history: Any) -> str:
    if not MARITACA_API_KEY:
        raise GatewayError(
            "MARITACA_API_KEY não configurada no servidor.",
            503,
        )

    payload = {
        "model": MARITACA_MODEL,
        "messages": build_messages(question, history),
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
        raise GatewayError("A Maritaca demorou para responder.", 504)
    except requests.RequestException as exc:
        app.logger.warning(
            "Falha de conexão com a Maritaca: %s",
            exc.__class__.__name__,
        )
        raise GatewayError("Não foi possível conectar à Maritaca.", 502)

    if upstream.status_code == 401:
        raise GatewayError("A chave da Maritaca foi recusada.", 502)

    if upstream.status_code == 429:
        raise GatewayError(
            "A Maritaca informou limite ou cota excedida.",
            429,
        )

    if upstream.status_code >= 400:
        raise GatewayError(
            f"A Maritaca recusou a consulta (HTTP {upstream.status_code}).",
            502,
        )

    try:
        data = upstream.json()
    except ValueError:
        raise GatewayError(
            "A Maritaca retornou uma resposta inválida.",
            502,
        )

    choices = data.get("choices") or []
    if not choices:
        raise GatewayError(
            "A Maritaca não retornou uma resposta.",
            502,
        )

    choice = choices[0] or {}
    message = choice.get("message") or {}
    answer = text_content(message.get("content", "")).strip()
    if not answer:
        answer = text_content(choice.get("text", "")).strip()

    if not answer:
        raise GatewayError(
            "A resposta da Maritaca veio vazia.",
            502,
        )

    return answer


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
            "telegram_webhook": "/telegram/webhook",
        }
    )


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "provider": "maritaca",
            "telegram": "configured" if TELEGRAM_BOT_TOKEN else "not_configured",
        }
    )


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
        return jsonify(
            {"error": "A mensagem ou arquivo excede o limite de 60000 caracteres."}
        ), 413

    try:
        answer = ask_maritaca(question, body.get("history", []))
    except GatewayError as exc:
        return jsonify({"error": exc.message}), exc.status_code

    return jsonify({"answer": answer, "model": MARITACA_MODEL})


telegram_executor = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="telegram",
)
telegram_histories: dict[str, list[dict[str, str]]] = {}
telegram_history_lock = threading.Lock()


def telegram_api(method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not TELEGRAM_BOT_TOKEN:
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, json=payload, timeout=20)
    except requests.RequestException as exc:
        app.logger.warning(
            "Falha na API do Telegram (%s): %s",
            method,
            exc.__class__.__name__,
        )
        return None

    if response.status_code >= 400:
        app.logger.warning(
            "API do Telegram recusou %s (HTTP %s)",
            method,
            response.status_code,
        )
        return None

    try:
        data = response.json()
    except ValueError:
        app.logger.warning("Resposta inválida da API do Telegram (%s)", method)
        return None

    if not data.get("ok"):
        app.logger.warning("API do Telegram retornou ok=false em %s", method)
        return None

    return data


def split_telegram_text(text: str, limit: int = 3900) -> list[str]:
    text = text.strip()
    if not text:
        return ["Não consegui gerar uma resposta."]

    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut < 500:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    parts.append(text)
    return parts


def telegram_send_message(chat_id: Any, text: str) -> None:
    for part in split_telegram_text(text):
        telegram_api(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": part,
                "disable_web_page_preview": True,
            },
        )


def telegram_get_history(chat_id: str) -> list[dict[str, str]]:
    with telegram_history_lock:
        return list(telegram_histories.get(chat_id, []))


def telegram_save_exchange(
    chat_id: str,
    question: str,
    answer: str,
) -> None:
    with telegram_history_lock:
        history = telegram_histories.setdefault(chat_id, [])
        history.extend(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        )
        telegram_histories[chat_id] = history[-12:]


def telegram_clear_history(chat_id: str) -> None:
    with telegram_history_lock:
        telegram_histories.pop(chat_id, None)


def telegram_error_message(error: GatewayError) -> str:
    if error.status_code == 429:
        return "A cota da Maritaca foi atingida. Tente novamente em alguns minutos."
    if error.status_code == 504:
        return "A Maritaca demorou para responder. Tente novamente."
    if error.status_code == 503:
        return "O servidor ainda não está configurado para responder."
    return "Não consegui consultar a Maritaca agora. Tente novamente em instantes."


def process_telegram_update(update: dict[str, Any]) -> None:
    message = update.get("message") or update.get("edited_message") or {}
    if not isinstance(message, dict):
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    raw_text = message.get("text") or message.get("caption") or ""
    text = text_content(raw_text).strip()
    chat_key = str(chat_id)

    if not text:
        if message.get("document") or message.get("photo"):
            telegram_send_message(
                chat_id,
                "Recebi o arquivo. Nesta primeira versão, o bot responde a mensagens de texto; a leitura de anexos será adicionada em seguida.",
            )
        return

    command = text.split(maxsplit=1)[0].lower().split("@")[0]
    if command == "/start":
        telegram_clear_history(chat_key)
        telegram_send_message(
            chat_id,
            "Olá! Eu sou o THIGAS AI. Posso ajudar com programação, dúvidas e explicações. Envie sua pergunta.",
        )
        return

    if command in ("/ajuda", "/help"):
        telegram_send_message(
            chat_id,
            "Envie uma pergunta normalmente. Comandos disponíveis:\n/start — iniciar\n/novo — limpar a conversa\n/ajuda — mostrar esta ajuda",
        )
        return

    if command in ("/novo", "/new"):
        telegram_clear_history(chat_key)
        telegram_send_message(chat_id, "Conversa limpa. Pode enviar a próxima pergunta.")
        return

    if text.startswith("/"):
        telegram_send_message(
            chat_id,
            "Não reconheci esse comando. Use /ajuda ou envie uma pergunta normalmente.",
        )
        return

    history = telegram_get_history(chat_key)
    try:
        answer = ask_maritaca(text, history)
    except GatewayError as exc:
        app.logger.warning(
            "Falha ao responder Telegram (status %s)",
            exc.status_code,
        )
        telegram_send_message(chat_id, telegram_error_message(exc))
        return

    telegram_save_exchange(chat_key, text, answer)
    telegram_send_message(chat_id, answer)


@app.post("/telegram/webhook")
def telegram_webhook():
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN não configurado."}), 503

    if TELEGRAM_WEBHOOK_SECRET:
        received_secret = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token",
            "",
        )
        if received_secret != TELEGRAM_WEBHOOK_SECRET:
            return jsonify({"error": "webhook não autorizado"}), 403

    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        return jsonify({"error": "atualização inválida"}), 400

    telegram_executor.submit(process_telegram_update, update)
    return jsonify({"ok": True})


def configure_telegram_webhook() -> None:
    if not TELEGRAM_BOT_TOKEN:
        app.logger.info("Telegram não configurado: token ausente")
        return

    if not TELEGRAM_WEBHOOK_URL:
        app.logger.warning("Telegram não configurado: URL pública ausente")
        return

    if not TELEGRAM_WEBHOOK_URL.startswith("https://"):
        app.logger.warning("URL do webhook Telegram precisa usar HTTPS")
        return

    payload: dict[str, Any] = {
        "url": TELEGRAM_WEBHOOK_URL,
        "allowed_updates": ["message"],
    }
    if TELEGRAM_WEBHOOK_SECRET:
        payload["secret_token"] = TELEGRAM_WEBHOOK_SECRET

    result = telegram_api("setWebhook", payload)
    if result is not None:
        app.logger.info("Webhook do Telegram configurado: %s", TELEGRAM_WEBHOOK_URL)


if TELEGRAM_BOT_TOKEN:
    threading.Thread(
        target=configure_telegram_webhook,
        name="telegram-webhook-config",
        daemon=True,
    ).start()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    app.run(host="0.0.0.0", port=port)
