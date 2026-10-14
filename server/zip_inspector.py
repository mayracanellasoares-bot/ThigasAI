"""Bounded ZIP text inspection. No extraction to disk or executable content."""
from io import BytesIO
from pathlib import PurePosixPath
import stat
import zipfile

MAX_ZIP_FILES = 100
MAX_UNCOMPRESSED = 6 * 1024 * 1024
MAX_MEMBER = 1 * 1024 * 1024
MAX_CHARS = 45000
TEXT_SUFFIXES = {".txt",".md",".markdown",".html",".htm",".css",".js",".mjs",".cjs",
                 ".ts",".tsx",".jsx",".json",".jsonl",".yaml",".yml",".toml",
                 ".xml",".csv",".py",".sh",".ps1",".bat",".sql",".php",".java",
                 ".go",".rs",".rb",".kt",".swift",".dart",".lua",".r",".c",
                 ".h",".cpp",".hpp",".cs",".scss",".vue",".svelte",".ini",
                 ".cfg",".conf",".log",".svg",".gitignore",".env.example"}

def extract_zip_text(data: bytes) -> tuple[str,bool]:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            files = archive.infolist()
            if len(files) > MAX_ZIP_FILES:
                raise ValueError("ZIP com mais de 100 entradas. Divida em arquivos menores.")
            if sum(x.file_size for x in files) > MAX_UNCOMPRESSED:
                raise ValueError("ZIP expandido excede 6 MB; reduza o projeto.")
            lines = []
            truncated = False
            total_chars = 0
            for member in files:
                if member.is_dir():
                    continue
                path = PurePosixPath(member.filename.replace("\\","/"))
                if path.is_absolute() or ".." in path.parts or not path.parts:
                    raise ValueError("ZIP contém caminho inseguro.")
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError("ZIP com links simbólicos não é permitido.")
                if member.flag_bits & 1:
                    raise ValueError("ZIP criptografado não é suportado.")
                if member.file_size > MAX_MEMBER:
                    truncated = True
                    continue
                if member.file_size and member.file_size > 150 * max(1, member.compress_size):
                    raise ValueError("ZIP com proporção de compressão insegura.")
                if path.suffix.lower() not in TEXT_SUFFIXES and path.name.lower() not in {"readme","dockerfile","makefile"}:
                    continue
                try:
                    body = archive.read(member).decode("utf-8-sig")
                except (UnicodeError, OSError, RuntimeError, zipfile.BadZipFile):
                    truncated = True
                    continue
                if "\x00" in body:
                    truncated = True
                    continue
                title = "[ARQUIVO NO ZIP: " + str(path)[:180] + "]\n"
                remaining = MAX_CHARS - total_chars - len(title)
                if remaining <= 0:
                    truncated = True
                    break
                snippet = body[:remaining]
                lines.append(title + snippet)
                total_chars += len(title) + len(snippet)
                if len(body) > len(snippet):
                    truncated = True
                    break
            if not lines:
                raise ValueError("ZIP sem arquivos de texto ou código legíveis.")
            return "\n\n".join(lines), truncated
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValueError("ZIP inválido ou corrompido.") from exc
