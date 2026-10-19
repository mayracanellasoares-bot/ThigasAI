"""Routes mounted under /octonous on the existing Flask service."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, abort, jsonify, make_response, redirect, request
from werkzeug.exceptions import HTTPException

from .agent import model_answer, skill_by_slug, skills, validate_model
from .providers import (ACTION_PROVIDERS, CURRENT_RUN, PROVIDERS, ProviderError, api,
                        authorize_url, exchange_code, execute_action, search_one)
from .security import (COOKIE, check_password, configured, csrf, login_allowed,
                       new_session, owner_session, require_owner, serializer)
from .storage import Store, new_id, now

bp = Blueprint("octonous", __name__, url_prefix="/octonous")
STATIC = Path(__file__).resolve().parents[1] / "static"
TRIGGERS = {"manual", "github.pr_merged", "google_calendar.meeting_ended",
            "notion.page_created", "gmail.friday", "schedule.daily", "schedule.weekly"}


@bp.errorhandler(HTTPException)
def api_error(error):
    if not request.path.startswith(("/octonous/api/", "/octonous/hooks/")):
        return error
    defaults = {401: "Entre com a senha do proprietário para continuar.",
                403: "Sessão inválida ou expirada. Entre novamente."}
    message = error.description
    if message == type(error).description:
        message = defaults.get(error.code, message)
    response = error.get_response()
    response.set_data(json.dumps({"error": message}, ensure_ascii=False))
    response.mimetype = "application/json"
    return response


@bp.after_request
def private_headers(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


def db():
    try:
        return Store()
    except (RuntimeError, ValueError):
        abort(503, "Configure o banco de dados e a chave de criptografia.")


def configured_model(store):
    saved = store.get("config", "model")
    if saved:
        return saved
    if os.getenv("MARITACA_API_KEY"):
        return {"provider": "maritaca", "model": os.getenv("MARITACA_MODEL", "sabia-4"),
                "api_key": ""}
    return None


def body():
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        abort(400, "Envie um objeto JSON.")
    return value


def safe_error(exc):
    if isinstance(exc, ProviderError):
        return jsonify(error=str(exc)), 422
    if isinstance(exc, requests.RequestException):
        return jsonify(error="Serviço externo indisponível."), 502
    raise exc


def public_connection(provider):
    return {"provider": provider,
            "configured": bool(os.getenv("OCTONOUS_" + PROVIDERS[provider]["env"] + "_CLIENT_ID")
                               and os.getenv("OCTONOUS_" + PROVIDERS[provider]["env"] + "_CLIENT_SECRET"))}


@bp.get("")
@bp.get("/")
def page():
    if not configured():
        return ("<h1>Octonous em preparação</h1><p>Configure senha do proprietário, "
                "segredo de sessão, PostgreSQL e chave de criptografia no Render.</p>"), 503
    response = make_response((STATIC / "octonous.html").read_text(encoding="utf-8"))
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


@bp.post("/api/login")
def login():
    if not configured():
        abort(503)
    if not login_allowed(request.remote_addr or "unknown"):
        return jsonify(error="Muitas tentativas. Aguarde cinco minutos."), 429
    if not check_password(body().get("password", "")):
        return jsonify(error="Senha inválida."), 401
    token = new_session()
    response = jsonify(ok=True)
    response.set_cookie(COOKIE, token, secure=True, httponly=True, samesite="Lax",
                        path="/octonous", max_age=8 * 3600)
    return response


@bp.post("/api/logout")
def logout():
    require_owner(write=True)
    response = jsonify(ok=True)
    response.delete_cookie(COOKIE, path="/octonous")
    return response


@bp.get("/api/session")
def session_info():
    user = owner_session() if configured() else None
    if not user:
        return jsonify(authenticated=False)
    return jsonify(authenticated=True, csrf=csrf(user["sid"]),
                   providers=[public_connection(name) for name in PROVIDERS])


@bp.get("/api/connections")
def connections():
    require_owner()
    store = db()
    return jsonify(connections=[
        {**public_connection(name), "connected": bool(store.get("connection", name))}
        for name in PROVIDERS
    ])


@bp.post("/api/connections/<provider>/start")
def connect(provider):
    user = require_owner(write=True)
    if provider not in PROVIDERS:
        abort(404)
    state = secrets.token_urlsafe(32)
    try:
        url = authorize_url(provider, state)
        db().put("oauth_state", state, {"provider": provider, "sid": user["sid"],
                                       "expires": time.time() + 600})
        return jsonify(url=url)
    except ProviderError as exc:
        return safe_error(exc)


@bp.get("/oauth/<provider>/callback")
def oauth_callback(provider):
    user = require_owner()
    if provider not in PROVIDERS:
        abort(404)
    state = request.args.get("state", "")
    if not state or len(state) > 200:
        abort(400)
    store = db()
    pending = store.delete("oauth_state", state)
    if (not pending or pending.get("provider") != provider
            or pending.get("sid") != user["sid"]
            or pending.get("expires", 0) < time.time()):
        abort(403, "Estado OAuth inválido ou expirado.")
    code = request.args.get("code", "")
    if request.args.get("error") or not code or len(code) > 2048:
        return redirect("/octonous?oauth=cancelado", code=303)
    try:
        token = exchange_code(provider, code)
        store.put("connection", provider, token)
        store.audit(None, provider, "oauth.connect", {"provider": provider},
                    {"connected": True}, "ok")
    except (ProviderError, requests.RequestException):
        return redirect("/octonous?oauth=erro", code=303)
    return redirect("/octonous?oauth=conectado", code=303)


@bp.post("/api/connections/<provider>/disconnect")
def disconnect(provider):
    require_owner(write=True)
    if provider not in PROVIDERS:
        abort(404)
    store = db()
    store.delete("connection", provider)
    store.audit(None, provider, "oauth.disconnect", {}, {}, "ok")
    return jsonify(ok=True)


def search_all(store, query, run_id, allowed=None):
    result = {}
    for provider in PROVIDERS:
        if allowed is not None and provider not in allowed:
            continue
        if not store.get("connection", provider):
            continue
        try:
            matches = search_one(store, provider, query)
            result[provider] = matches
            store.audit(run_id, provider, "search", {"query": query}, matches, "ok")
        except (ProviderError, requests.RequestException) as exc:
            result[provider] = {"error": str(exc) if isinstance(exc, ProviderError)
                                else "Serviço externo indisponível."}
            store.audit(run_id, provider, "search", {"query": query},
                        result[provider], "error")
    return result


@bp.post("/api/search")
def search():
    require_owner(write=True)
    query = str(body().get("query", "")).strip()
    if not 2 <= len(query) <= 150:
        abort(400, "Informe de 2 a 150 caracteres.")
    store = db()
    run_id = new_id()
    token = CURRENT_RUN.set(run_id)
    try:
        return jsonify(run_id=run_id, results=search_all(store, query, run_id))
    finally:
        CURRENT_RUN.reset(token)


@bp.get("/api/skills")
def list_skills():
    require_owner()
    return jsonify(skills=skills())


@bp.get("/api/model")
def get_model():
    require_owner()
    value = configured_model(db())
    return jsonify(model={"provider": value["provider"], "model": value["model"],
                          "origin": value.get("origin", ""), "configured": True}
                  if value else {"configured": False})


@bp.post("/api/model")
def set_model():
    require_owner(write=True)
    try:
        value = validate_model(body())
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    db().put("config", "model", value)
    return jsonify(ok=True)


def queue_approval(store, run_id, proposal):
    action = proposal.get("type")
    payload = proposal.get("payload")
    if not isinstance(action, str) or action not in ACTION_PROVIDERS or not isinstance(payload, dict):
        return None
    if not store.get("connection", ACTION_PROVIDERS[action]):
        return None
    record_id = new_id()
    store.put("approval", record_id,
              {"run_id": run_id, "action": action, "payload": payload,
               "status": "pending", "created_at": now()})
    store.audit(run_id, action, "approval.requested", payload, {"id": record_id}, "pending")
    return record_id


def run_task(store, prompt, *, skill_slug="", workflow=None, event=None, search_enabled=True):
    run_id = new_id()
    token = CURRENT_RUN.set(run_id)
    try:
        return _run_task(store, run_id, prompt, skill_slug=skill_slug, workflow=workflow,
                         event=event, search_enabled=search_enabled)
    finally:
        CURRENT_RUN.reset(token)


def _run_task(store, run_id, prompt, *, skill_slug="", workflow=None, event=None, search_enabled=True):
    skill = skill_by_slug(skill_slug) if skill_slug else None
    allowed = set(workflow.get("apps", [])) if workflow else None
    context = {"event": event or {}, "search": {}}
    if search_enabled:
        context["search"] = search_all(store, prompt[:150], run_id, allowed)
    context_text = json.dumps(context, ensure_ascii=False, default=str)[:16000]
    store.put("run", run_id, {"prompt": prompt, "workflow_id": workflow.get("id") if workflow else None,
                              "status": "running", "created_at": now()})
    try:
        response = model_answer(configured_model(store), prompt, context_text, skill)
        store.audit(run_id, "model", "plan", {"prompt": prompt, "context": context_text},
                    response, "ok")
        proposed = response.get("proposed_action")
        if workflow and proposed and proposed["type"] not in workflow.get("actions", []):
            proposed = None
        approval_id = queue_approval(store, run_id, proposed) if proposed else None
        store.put("run", run_id, {"prompt": prompt, "workflow_id": workflow.get("id") if workflow else None,
                                  "status": "awaiting_approval" if approval_id else "completed",
                                  "answer": response["answer"], "approval_id": approval_id,
                                  "created_at": now()})
        return {"run_id": run_id, "answer": response["answer"],
                "approval_id": approval_id, "proposed_action": proposed if approval_id else None}
    except ProviderError as exc:
        store.put("run", run_id, {"prompt": prompt, "status": "error",
                                  "error": str(exc), "created_at": now()})
        store.audit(run_id, "model", "plan", {"prompt": prompt},
                    {"error": str(exc)}, "error")
        raise


@bp.post("/api/chat")
def chat():
    require_owner(write=True)
    data = body()
    prompt = str(data.get("prompt", "")).strip()
    if not 2 <= len(prompt) <= 5000:
        abort(400, "Escreva uma tarefa de 2 a 5000 caracteres.")
    store = db()
    try:
        return jsonify(run_task(store, prompt, skill_slug=str(data.get("skill", "")),
                                search_enabled=data.get("search", True) is True))
    except ProviderError as exc:
        return safe_error(exc)


@bp.get("/api/workflows")
def workflows():
    require_owner()
    return jsonify(workflows=db().all("workflow"))


@bp.post("/api/workflows")
def create_workflow():
    require_owner(write=True)
    data = body()
    title = str(data.get("title", "")).strip()[:120]
    prompt = str(data.get("prompt", "")).strip()[:5000]
    trigger = data.get("trigger")
    apps = data.get("apps", [])
    actions = data.get("actions", [])
    if (not title or not prompt or not isinstance(trigger, str) or trigger not in TRIGGERS
            or not isinstance(apps, list)
            or any(not isinstance(item, str) or item not in PROVIDERS for item in apps)
            or not isinstance(actions, list)
            or any(not isinstance(item, str) or item not in ACTION_PROVIDERS for item in actions)):
        abort(400, "Definição de automação inválida.")
    if not all(ACTION_PROVIDERS[action] in apps for action in actions):
        abort(400, "Cada ação precisa de permissão para o aplicativo correspondente.")
    skill_slug = str(data.get("skill", ""))
    if skill_slug and not skill_by_slug(skill_slug):
        abort(400, "Skill não encontrada.")
    hour = data.get("hour", 9)
    weekday = data.get("weekday", 4)
    if type(hour) is not int or not 0 <= hour <= 23 or type(weekday) is not int or not 0 <= weekday <= 6:
        abort(400, "Horário ou dia da semana inválido.")
    record = {"title": title, "prompt": prompt, "trigger": trigger, "apps": apps,
              "actions": actions, "skill": skill_slug, "hour": hour,
              "weekday": weekday, "enabled": True, "created_at": now()}
    store = db()
    record_id = new_id()
    store.put("workflow", record_id, record)
    return jsonify(id=record_id, **record), 201


@bp.post("/api/workflows/<workflow_id>/run")
def run_workflow_manually(workflow_id):
    require_owner(write=True)
    store = db()
    workflow = store.get("workflow", workflow_id)
    if not workflow:
        abort(404)
    workflow["id"] = workflow_id
    try:
        return jsonify(run_task(store, workflow["prompt"], workflow=workflow,
                                skill_slug=workflow.get("skill", "")))
    except ProviderError as exc:
        return safe_error(exc)


@bp.post("/api/workflows/<workflow_id>/toggle")
def toggle_workflow(workflow_id):
    require_owner(write=True)
    store = db()
    record = store.get("workflow", workflow_id)
    if not record:
        abort(404)
    record["enabled"] = body().get("enabled") is True
    store.put("workflow", workflow_id, record)
    return jsonify(ok=True, enabled=record["enabled"])


@bp.get("/api/approvals")
def approvals():
    require_owner()
    return jsonify(approvals=db().all("approval", limit=50))


@bp.post("/api/approvals/<approval_id>/decision")
def decide(approval_id):
    require_owner(write=True)
    data = body()
    decision = data.get("decision")
    if decision not in ("approve", "reject"):
        abort(400)
    store = db()
    record = store.get("approval", approval_id)
    if not record or record.get("status") != "pending":
        abort(409, "Esta aprovação já foi processada.")
    if decision == "reject":
        changed = store.transition("approval", approval_id, "pending",
                                   {"status": "rejected", "decided_at": now()})
        if not changed:
            abort(409)
        store.audit(record["run_id"], record["action"], "approval.rejected", {}, {}, "rejected")
        return jsonify(status="rejected")
    payload = data.get("payload", record["payload"])
    if not isinstance(payload, dict) or len(json.dumps(payload)) > 18000:
        abort(400, "Conteúdo inválido.")
    changed = store.transition("approval", approval_id, "pending",
                               {"status": "executing", "payload": payload, "decided_at": now()})
    if not changed:
        abort(409)
    token = CURRENT_RUN.set(changed["run_id"])
    try:
        result = execute_action(store, changed["action"], payload)
        store.audit(changed["run_id"], changed["action"], "write",
                    payload, result, "ok")
        store.transition("approval", approval_id, "executing",
                         {"status": "executed", "result": result, "completed_at": now()})
        return jsonify(status="executed", result=result)
    except (ProviderError, requests.RequestException) as exc:
        message = str(exc) if isinstance(exc, ProviderError) else "Resultado incerto da API; confira o aplicativo antes de tentar novamente."
        store.audit(changed["run_id"], changed["action"], "write",
                    payload, {"error": message}, "error")
        store.transition("approval", approval_id, "executing",
                         {"status": "failed", "error": message, "completed_at": now()})
        return jsonify(status="failed", error=message), 502
    finally:
        CURRENT_RUN.reset(token)


@bp.get("/api/logs")
def logs():
    require_owner()
    return jsonify(logs=db().logs())


def matching_workflows(store, trigger):
    return [item for item in store.all("workflow", limit=200)
            if item.get("enabled") and item.get("trigger") == trigger]


def fire(store, trigger, key, event, workflow_id=None):
    """PostgreSQL dedupe is the durable source of truth across replicas."""
    found = matching_workflows(store, trigger)
    results = []
    for workflow in found:
        if workflow_id is not None and workflow["id"] != workflow_id:
            continue
        event_key = f"{workflow['id']}:{trigger}:{key}"
        if not store.once(event_key):
            continue
        try:
            results.append(run_task(store, workflow["prompt"], workflow=workflow,
                                    skill_slug=workflow.get("skill", ""), event=event))
        except ProviderError as exc:
            store.audit(None, trigger, "trigger", {"event_key": event_key},
                        {"error": str(exc)}, "error")
    return results


@bp.post("/hooks/github")
def github_webhook():
    secret = os.getenv("OCTONOUS_GITHUB_WEBHOOK_SECRET", "")
    if len(secret) < 24:
        abort(503)
    raw = request.get_data(cache=False)
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        abort(403)
    if request.headers.get("X-GitHub-Event") != "pull_request":
        return jsonify(ignored=True)
    try:
        event = json.loads(raw)
    except ValueError:
        abort(400)
    if not isinstance(event, dict) or event.get("action") != "closed" or event.get("pull_request", {}).get("merged") is not True:
        return jsonify(ignored=True)
    delivery = request.headers.get("X-GitHub-Delivery", "")
    if not delivery or len(delivery) > 120:
        abort(400)
    summary = {"repo": event.get("repository", {}).get("full_name"),
               "title": event["pull_request"].get("title"),
               "url": event["pull_request"].get("html_url")}
    return jsonify(runs=fire(db(), "github.pr_merged", delivery, summary))


@bp.post("/hooks/tick")
def scheduler_tick():
    expected = os.getenv("OCTONOUS_TICK_SECRET", "")
    supplied = request.headers.get("X-Octonous-Tick", "")
    if len(expected) < 24 or not hmac.compare_digest(expected, supplied or ""):
        abort(403)
    store = db()
    local = datetime.now(ZoneInfo("America/Sao_Paulo"))
    results = []
    for item in store.all("workflow", limit=200):
        if not item.get("enabled"):
            continue
        trigger = item.get("trigger")
        if trigger == "schedule.daily" and local.hour == item.get("hour", 9):
            results += fire(store, trigger, local.date().isoformat(),
                            {"date": local.isoformat()}, workflow_id=item["id"])
        if (trigger in ("schedule.weekly", "gmail.friday")
                and local.hour == item.get("hour", 9)
                and local.weekday() == (4 if trigger == "gmail.friday" else item.get("weekday", 4))):
            event = {"date": local.isoformat()}
            if trigger == "gmail.friday":
                if not store.get("connection", "gmail"):
                    continue
                try:
                    event["messages"] = search_one(store, "gmail", "newer_than:7d")
                except (ProviderError, requests.RequestException):
                    continue
            results += fire(store, trigger, local.date().isoformat(),
                            event, workflow_id=item["id"])
    if matching_workflows(store, "google_calendar.meeting_ended") and store.get("connection", "google_calendar"):
        try:
            end = datetime.now(timezone.utc)
            start = end - timedelta(minutes=15)
            response = api(store, "google_calendar", "GET",
                           "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                           params={"timeMin": (start - timedelta(hours=12)).isoformat(),
                                   "timeMax": end.isoformat(), "singleEvents": "true",
                                   "maxResults": 100})
            for event in response.get("items", []):
                ended = event.get("end", {}).get("dateTime")
                if not ended:
                    continue
                try:
                    date = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if start <= date.astimezone(timezone.utc) <= end:
                    summary = {"id": event.get("id"), "summary": event.get("summary"),
                               "description": (event.get("description") or "")[:2000],
                               "attendees": [x.get("email") for x in event.get("attendees", [])[:30]]}
                    results += fire(store, "google_calendar.meeting_ended",
                                    str(event.get("id")) + ":" + ended, summary)
        except (ProviderError, requests.RequestException):
            pass
    if matching_workflows(store, "notion.page_created") and store.get("connection", "notion"):
        try:
            recent = datetime.now(timezone.utc) - timedelta(minutes=15)
            response = api(store, "notion", "POST", "https://api.notion.com/v1/search",
                           payload={"sort": {"direction": "descending", "timestamp": "last_edited_time"},
                                    "page_size": 100})
            for page in response.get("results", []):
                created = page.get("created_time", "")
                if page.get("object") == "page" and created and datetime.fromisoformat(
                        created.replace("Z", "+00:00")) >= recent:
                    results += fire(store, "notion.page_created", page["id"],
                                    {"id": page["id"], "url": page.get("url", "")})
        except (ProviderError, requests.RequestException, ValueError):
            pass
    return jsonify(runs=results, checked_at=now())


def install(app):
    app.register_blueprint(bp)
