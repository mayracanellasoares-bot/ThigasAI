"""Build a single CSS request and synchronize content versions with PWA precache.

No Node dependency is required. Run after editing public assets; Render also runs
this before deployment. --check fails if committed outputs are stale.
"""
import hashlib
import re
import sys
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "server" / "static"


def build(check=False):
    outputs = {}
    css = "\n".join((STATIC / name).read_text() for name in (
        "chat.css", "history-sidebar.css", "mini-nano-theme.css", "ui-tokens.css"))
    outputs[STATIC / "chat-ui.css"] = css

    def version(name):
        path = STATIC / name
        data = outputs[path].encode() if path in outputs else path.read_bytes()
        return hashlib.sha256(data).hexdigest()[:16]

    html_path = STATIC / "index.html"
    html = html_path.read_text()
    html = re.sub(r'(/static/([^"?]+\.(?:css|js)))(?:\?v=[^" ]+)?',
                  lambda m: m[1] + "?v=" + version(m[2]), html)
    outputs[html_path] = html
    shell = ["/", "/manifest.webmanifest"]
    shell.extend(re.findall(r'(?:src|href)="(/static/[^\"]+)"', html))
    shell.append("/static/icons/icon-512.png")
    shell = list(dict.fromkeys(shell))
    shell_text = "const APP_SHELL = [\n" + "".join(f'  "{p}",\n' for p in shell) + "];"
    # Includes HTML and every shell asset so HTML-only changes update offline too.
    digest = hashlib.sha256(html.encode())
    for url in shell:
        if not url.startswith("/static/"):
            if url == "/manifest.webmanifest":
                digest.update((STATIC / "manifest.webmanifest").read_bytes())
            continue
        path = STATIC / url.removeprefix("/static/").split("?")[0]
        digest.update(outputs[path].encode() if path in outputs else path.read_bytes())
    worker_path = STATIC / "sw.js"
    worker = re.sub(r'const APP_SHELL = \[.*?\];', lambda _: shell_text,
                    worker_path.read_text(), flags=re.S)
    worker = re.sub(r'const CACHE_NAME = .*?;',
                    'const CACHE_NAME = CACHE_PREFIX + "' + digest.hexdigest()[:16] + '";', worker)
    outputs[worker_path] = worker
    stale = [path for path, content in outputs.items()
             if not path.exists() or path.read_text() != content]
    if check:
        if stale:
            print("Stale web assets: " + ", ".join(p.name for p in stale))
            return 1
    else:
        for path in stale:
            path.write_text(outputs[path])
    return 0


if __name__ == "__main__":
    raise SystemExit(build("--check" in sys.argv))
