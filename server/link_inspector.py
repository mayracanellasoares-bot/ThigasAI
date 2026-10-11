"""Fetch public web pages without permitting internal-network requests."""
import http.client
import ipaddress
import re
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urlsplit


class PublicPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.title_depth = 0
        self.title = []
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "iframe"):
            self.depth += 1
        if tag == "title":
            self.title_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "iframe"):
            self.depth = max(0, self.depth - 1)
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)

    def handle_data(self, text):
        val = " ".join(text.split())
        if not val or self.depth:
            return
        if self.title_depth:
            self.title.append(val)
        else:
            self.chunks.append(val)


def fetch_public_page(value):
    if not isinstance(value, str) or len(value) > 1800:
        raise ValueError("Informe uma URL de até 1.800 caracteres.")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Informe um link HTTP ou HTTPS público válido.")
    host = parsed.hostname.lower().rstrip(".")
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("Links internos não são permitidos.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise ValueError("Porta inválida.") from None
    if port not in (80, 443) or (parsed.scheme == "https" and port != 443) or (parsed.scheme == "http" and port != 80):
        raise ValueError("Somente HTTP/80 e HTTPS/443 são permitidos.")
    try:
        resolved = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("Não foi possível resolver o domínio.") from None
    addresses = [row[4][0] for row in resolved]
    if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
        raise ValueError("Endereço privado, reservado ou não público bloqueado.")
    target_ip = addresses[0]
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    conn = (http.client.HTTPSConnection(host, port, timeout=7, context=ssl.create_default_context())
            if parsed.scheme == "https" else http.client.HTTPConnection(host, port, timeout=7))
    # DNS is resolved only once: socket connects to the vetted IP, TLS still validates hostname.
    conn._create_connection = lambda address, timeout=None, source_address=None: socket.create_connection(
        (target_ip, port), timeout=timeout, source_address=source_address)
    try:
        conn.request("GET", path, headers={"User-Agent": "THIGAS-AI-LinkInspector/1.0",
                                          "Accept": "text/html,text/plain;q=0.9",
                                          "Accept-Encoding": "identity",
                                          "Host": host})
        response = conn.getresponse()
        status = response.status
        content_type = response.getheader("Content-Type", "").split(";")[0].lower().strip()
        redirect = response.getheader("Location")
        if status in (301, 302, 303, 307, 308):
            return {"url": value.strip(), "status": status, "reachable": True, "redirect": redirect,
                    "title": "", "text": "", "note": "Redirecionamento não seguido por segurança."}
        if content_type not in ("text/html", "text/plain"):
            return {"url": value.strip(), "status": status, "reachable": status < 400,
                    "redirect": None, "title": "", "text": "",
                    "note": "Conteúdo não textual; página não analisada."}
        raw = response.read(256 * 1024 + 1)
        cropped = len(raw) > 256 * 1024
        encoding = "utf-8"
        match = re.search(r"charset=([a-zA-Z0-9_\-]+)", response.getheader("Content-Type", ""))
        if match and match.group(1).lower() in ("utf-8", "iso-8859-1", "windows-1252"):
            encoding = match.group(1)
        decoded = raw[:256 * 1024].decode(encoding, errors="replace")
        if content_type == "text/html":
            parser = PublicPageParser()
            parser.feed(decoded)
            title = " ".join(parser.title)[:220]
            page_text = " ".join(parser.chunks)
        else:
            title, page_text = "", decoded
        return {"url": value.strip(), "status": status, "reachable": 200 <= status < 400,
                "redirect": None, "title": title,
                "text": " ".join(page_text.split())[:18000],
                "note": "Página extensa; conteúdo parcial." if cropped or len(page_text) > 18000 else ""}
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise ValueError("Não foi possível acessar o site com segurança: " + type(exc).__name__) from None
    finally:
        conn.close()
