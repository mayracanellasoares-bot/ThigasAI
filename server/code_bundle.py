"""Entrega segura de arquivos de código gerados pelo chat em um único ZIP.

Arquiva apenas strings. Não interpreta nem executa o código incluído.
"""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
import re

MAX_FILES = 20
MAX_FILE_BYTES = 350_000
MAX_TOTAL_BYTES = 1_000_000
_ALLOWED_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\Z")


def make_code_zip(files):
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError("Envie de 1 a 20 arquivos de código.")
    reviewed = []
    seen = set()
    total = 0
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Estrutura de arquivo inválida.")
        name, content = item.get("name"), item.get("content")
        if (not isinstance(name, str) or not _ALLOWED_NAME.fullmatch(name)
                or ".." in name or name.casefold() in seen):
            raise ValueError("Nome de arquivo inválido ou repetido.")
        if not isinstance(content, str) or not content or "\x00" in content:
            raise ValueError("O arquivo deve conter código em texto.")
        binary = content.encode("utf-8")
        total += len(binary)
        if len(binary) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("Código excede o limite de 350 KB por arquivo ou 1 MB no total.")
        seen.add(name.casefold())
        reviewed.append((name, binary))
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for name, binary in reviewed:
            archive.writestr(name, binary)
    return output.getvalue()
