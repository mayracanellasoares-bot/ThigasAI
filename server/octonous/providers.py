"""Direct OAuth connections and narrowly scoped app operations."""

from __future__ import annotations

import base64
from contextvars import ContextVar
import json
import os
import re
import time
from email.message import EmailMessage
from urllib.parse import urlencode, quote

import requests

from .storage import now

BASE = "https://thigas-coder-gateway.onrender.com"
NOTION_VERSION = "2022-06-28"
CURRENT_RUN = ContextVar("octonous_run", default=None)

PROVIDERS = {
    "gmail": {
        "env": "GOOGLE", "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
    },
    "google_calendar": {
        "env": "GOOGLE", "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/calendar.events.readonly",
    },
    "github": {
        "env": "GITHUB", "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token", "scope": "repo",
    },
    "notion": {
        "env": "NOTION", "authorize": "https://api.notion.com/v1/oauth/authorize",
        "token": "https://api.notion.com/v1/oauth/token", "scope": "",
    },
    "hubspot": {
        "env": "HUBSPOT", "authorize": "https://app.hubspot.com/oauth/authorize",
        "token": "https://api.hubapi.com/oauth/v1/token",
        "scope": "crm.objects.contacts.read crm.objects.contacts.write",
    },
    "salesforce": {
        "env": "SALESFORCE", "authorize": "https://login.salesforce.com/services/oauth2/authorize",
        "token": "https://login.salesforce.com/services/oauth2/token",
        "scope": "api refresh_token",
    },
}


class ProviderError(Exception):
    pass


def public_url():
    url = (os.getenv("OCTONOUS_PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or BASE).rstrip("/")
    if not url.startswith("https://") or "/" in url[8:]:
        raise ProviderError("OCTONOUS_PUBLIC_URL precisa ser uma origem HTTPS.")
    return url


def oauth_settings(provider):
    if provider not in PROVIDERS:
        raise ProviderError("Aplicativo desconhecido.")
    name = PROVIDERS[provider]["env"]
    client_id = os.getenv("OCTONOUS_" + name + "_CLIENT_ID", "")
    client_secret = os.getenv("OCTONOUS_" + name + "_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ProviderError(f"Configure o client ID e o client secret de {name} no Render.")
    return client_id, client_secret


def callback_url(provider):
    return public_url() + "/octonous/oauth/" + provider + "/callback"


def authorize_url(provider, state):
    config = PROVIDERS[provider]
    client_id, _ = oauth_settings(provider)
    params = {"client_id": client_id, "redirect_uri": callback_url(provider), "state": state}
    if provider == "notion":
        params.update(owner="user", response_type="code")
    else:
        params.update(response_type="code", scope=config["scope"])
    if provider in ("gmail", "google_calendar"):
        params.update(access_type="offline", prompt="consent", include_granted_scopes="false")
    return config["authorize"] + "?" + urlencode(params)


def exchange_code(provider, code):
    config = PROVIDERS[provider]
    client_id, client_secret = oauth_settings(provider)
    data = {"grant_type": "authorization_code", "code": code,
            "redirect_uri": callback_url(provider)}
    headers = {"Accept": "application/json"}
    auth = None
    if provider in ("github", "notion"):
        auth = (client_id, client_secret)
    else:
        data.update(client_id=client_id, client_secret=client_secret)
    if provider == "github":
        data = {"client_id": client_id, "client_secret": client_secret, "code": code,
                "redirect_uri": callback_url(provider)}
        auth = None
    if provider == "notion":
        headers["Content-Type"] = "application/json"
        response = requests.post(config["token"], json=data, auth=auth, headers=headers, timeout=12)
    else:
        response = requests.post(config["token"], data=data, auth=auth, headers=headers, timeout=12)
    if not response.ok:
        raise ProviderError(f"{provider}: autorização recusada ({response.status_code}).")
    result = response.json()
    if not result.get("access_token"):
        raise ProviderError(f"{provider}: resposta OAuth sem token de acesso.")
    result["received_at"] = time.time()
    return result


def refresh(provider, token):
    if not token.get("refresh_token"):
        raise ProviderError(f"{provider}: reconecte o aplicativo para renovar o acesso.")
    config = PROVIDERS[provider]
    client_id, client_secret = oauth_settings(provider)
    data = {"grant_type": "refresh_token", "refresh_token": token["refresh_token"],
            "client_id": client_id, "client_secret": client_secret}
    if provider == "notion":
        response = requests.post(config["token"], json=data,
                                 auth=(client_id, client_secret), timeout=12)
    else:
        response = requests.post(config["token"], data=data, timeout=12)
    if not response.ok:
        raise ProviderError(f"{provider}: sessão expirada; reconecte o aplicativo.")
    updated = response.json()
    if not updated.get("access_token"):
        raise ProviderError(f"{provider}: falha ao renovar acesso.")
    return {**token, **updated, "received_at": time.time()}


def api(store, provider, method, url, *, params=None, payload=None):
    """Fixed upstream URLs only; this function never accepts client-supplied URLs."""
    token = store.get("connection", provider)
    if not token:
        raise ProviderError(f"{provider} não conectado.")
    if token.get("expires_in") and time.time() > token.get("received_at", 0) + int(token["expires_in"]) - 90:
        token = refresh(provider, token)
        store.put("connection", provider, token)
    headers = {"Authorization": "Bearer " + token["access_token"], "Accept": "application/json"}
    if provider == "notion":
        headers["Notion-Version"] = NOTION_VERSION
    response = requests.request(method, url, headers=headers, params=params,
                                json=payload, timeout=15)
    if response.status_code == 401 and token.get("refresh_token"):
        token = refresh(provider, token)
        store.put("connection", provider, token)
        headers["Authorization"] = "Bearer " + token["access_token"]
        response = requests.request(method, url, headers=headers, params=params,
                                    json=payload, timeout=15)
    if not response.ok:
        store.audit(CURRENT_RUN.get(), provider, method + " " + url,
                    {"params": params, "payload": payload},
                    {"status_code": response.status_code}, "error")
        raise ProviderError(f"{provider}: API retornou {response.status_code}.")
    try:
        result = response.json() if response.content else {}
    except ValueError as exc:
        store.audit(CURRENT_RUN.get(), provider, method + " " + url,
                    {"params": params, "payload": payload},
                    {"error": "Resposta JSON inválida"}, "error")
        raise ProviderError(f"{provider}: resposta inválida da API.") from exc
    store.audit(CURRENT_RUN.get(), provider, method + " " + url,
                {"params": params, "payload": payload},
                {"response": json.dumps(result, ensure_ascii=False, default=str)[:64000]},
                "ok")
    return result


def search_one(store, provider, query):
    """Return a short, uniform list. Data never appears in another provider's request."""
    q = query[:150]
    if provider == "gmail":
        root = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        found = api(store, provider, "GET", root,
                    params={"q": q, "maxResults": 6}).get("messages", [])
        result = []
        for item in found[:6]:
            message = api(store, provider, "GET", root + "/" + quote(item["id"], safe=""),
                          params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]})
            headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
            result.append({"title": headers.get("subject", "(sem assunto)"),
                           "summary": message.get("snippet", "")[:350],
                           "detail": headers.get("from", "")[:120],
                           "url": "https://mail.google.com/mail/u/0/#all/" + item["id"]})
        return result
    if provider == "google_calendar":
        events = api(store, provider, "GET",
                     "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                     params={"q": q, "maxResults": 8, "singleEvents": "true"}).get("items", [])
        return [{"title": x.get("summary", "(evento)"), "summary": x.get("description", "")[:350],
                 "detail": x.get("start", {}).get("dateTime", x.get("start", {}).get("date", "")),
                 "url": x.get("htmlLink", "")} for x in events]
    if provider == "github":
        issues = api(store, provider, "GET", "https://api.github.com/search/issues",
                     params={"q": q, "per_page": 8}).get("items", [])
        return [{"title": x.get("title", ""), "summary": (x.get("body") or "")[:350],
                 "detail": x.get("repository_url", "").rsplit("/", 2)[-1],
                 "url": x.get("html_url", "")} for x in issues]
    if provider == "notion":
        pages = api(store, provider, "POST", "https://api.notion.com/v1/search",
                    payload={"query": q, "page_size": 8}).get("results", [])
        return [{"title": " ".join(part.get("plain_text", "") for parts in
                         x.get("properties", {}).values() if parts.get("type") == "title"
                         for part in parts.get("title", [])) or "(página)",
                 "summary": "Busca por título do Notion", "detail": x.get("last_edited_time", ""),
                 "url": x.get("url", "")} for x in pages]
    if provider == "hubspot":
        contacts = api(store, provider, "POST",
                       "https://api.hubapi.com/crm/v3/objects/contacts/search",
                       payload={"query": q, "limit": 8,
                                "properties": ["email", "firstname", "lastname"]}).get("results", [])
        return [{"title": " ".join(filter(None, [x.get("properties", {}).get("firstname"),
                                                   x.get("properties", {}).get("lastname")])) or "(contato)",
                 "summary": x.get("properties", {}).get("email", ""), "detail": x["id"],
                 "url": ""} for x in contacts]
    if provider == "salesforce":
        instance = store.get("connection", provider).get("instance_url", "")
        if not re.fullmatch(r"https://[A-Za-z0-9.-]+\.(?:salesforce\.com|force\.com)", instance):
            raise ProviderError("Instância Salesforce inválida.")
        safe = re.sub(r"[^\w @.-]", " ", q).strip()
        if not safe:
            return []
        sosl = f"FIND {{{safe}}} IN ALL FIELDS RETURNING Account(Id,Name),Contact(Id,Name,Email)"
        found = api(store, provider, "GET", instance + "/services/data/v60.0/search/",
                    params={"q": sosl})
        return [{"title": x.get("Name", ""), "summary": x.get("Email", ""),
                 "detail": x.get("attributes", {}).get("type", ""), "url": ""}
                for x in found[:8]]
    raise ProviderError("Busca não suportada.")


def execute_action(store, action, payload):
    """Only explicit action IDs reach fixed provider endpoints after an approval."""
    if action == "gmail.send":
        recipient = str(payload.get("to", "")).strip()
        if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", recipient):
            raise ProviderError("Destinatário de e-mail inválido.")
        msg = EmailMessage()
        msg["To"] = recipient
        msg["Subject"] = re.sub(r"[\r\n]+", " ", str(payload.get("subject", "")))[:180]
        msg.set_content(str(payload.get("body", ""))[:12000])
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")
        sent = api(store, "gmail", "POST",
                   "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                   payload={"raw": raw})
        return {"id": sent.get("id"), "threadId": sent.get("threadId")}
    if action == "github.issue.create":
        repo = str(payload.get("repo", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ProviderError("Repositório inválido; use owner/repo.")
        result = api(store, "github", "POST",
                     "https://api.github.com/repos/" + repo + "/issues",
                     payload={"title": str(payload.get("title", ""))[:200],
                              "body": str(payload.get("body", ""))[:10000]})
        return {"url": result.get("html_url"), "number": result.get("number")}
    if action == "notion.page.create":
        parent = str(payload.get("parent_id", ""))
        if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", parent):
            raise ProviderError("ID da página pai inválido.")
        title = str(payload.get("title", ""))[:200]
        content = str(payload.get("body", ""))[:12000]
        page = {"parent": {"page_id": parent},
                "properties": {"title": {"type": "title", "title":
                             [{"type": "text", "text": {"content": title}}]}}}
        if content:
            page["children"] = [
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text":
                    [{"type": "text", "text": {"content": content[start:start + 2000]}}]}}
                for start in range(0, len(content), 2000)
            ]
        result = api(store, "notion", "POST", "https://api.notion.com/v1/pages",
                     payload=page)
        return {"url": result.get("url"), "id": result.get("id")}
    if action == "hubspot.contact.create":
        email = str(payload.get("email", "")).strip()
        if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", email):
            raise ProviderError("E-mail do contato inválido.")
        result = api(store, "hubspot", "POST",
                     "https://api.hubapi.com/crm/v3/objects/contacts",
                     payload={"properties": {"email": email,
                        "firstname": str(payload.get("firstname", ""))[:100],
                        "lastname": str(payload.get("lastname", ""))[:100]}})
        return {"id": result.get("id")}
    if action == "salesforce.task.create":
        instance = store.get("connection", "salesforce")
        if not instance or not re.fullmatch(
            r"https://[A-Za-z0-9.-]+\.(?:salesforce\.com|force\.com)",
            instance.get("instance_url", ""),
        ):
            raise ProviderError("Instância Salesforce inválida.")
        result = api(store, "salesforce", "POST",
                     instance["instance_url"] + "/services/data/v60.0/sobjects/Task/",
                     payload={"Subject": str(payload.get("subject", ""))[:200],
                              "Status": "Not Started",
                              "Description": str(payload.get("description", ""))[:10000]})
        return {"id": result.get("id")}
    raise ProviderError("Ação fora da lista permitida.")


ACTION_PROVIDERS = {
    "gmail.send": "gmail", "github.issue.create": "github",
    "notion.page.create": "notion", "hubspot.contact.create": "hubspot",
    "salesforce.task.create": "salesforce",
}
