"""Offline corpus builder for THIGAS DeepQA (no public write endpoint).

Usage:
  python server/build_deepqa_index.py --source corpus --index /data/thigas/deepqa.sqlite

The SQLite FTS5 index is built from .txt/.md/.html/.json/.py/.js/.css/.csv
and similar text files. To retain it across Render deploys, configure a
persistent disk and THIGAS_DEEPQA_INDEX_PATH pointing at this exact file.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sqlite3
from pathlib import Path

from deepqa import add_corpus_documents, open_index

SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm", ".json",
            ".jsonl", ".py", ".js", ".ts", ".css", ".csv", ".xml"}
MAX_FILES = 10000
MAX_FILE_BYTES = 1024 * 1024


def build(source: Path, target: Path, *, reset: bool = False) -> dict[str, int]:
    if not source.is_dir():
        raise ValueError("O diretório do corpus não existe.")
    if target.is_symlink():
        raise ValueError("Não é permitido gravar em índice simbólico.")
    if target.exists() and not reset:
        raise ValueError("Índice já existe. Use --reset para reconstruí-lo.")
    db = open_index(str(target))
    files = 0
    entries = 0
    try:
        with db:
            db.execute("DELETE FROM passages")
        for file in sorted(source.rglob("*")):
            if files >= MAX_FILES:
                break
            if file.is_symlink() or not file.is_file() or file.suffix.lower() not in SUFFIXES:
                continue
            if file.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                body = file.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError):
                continue
            if "\x00" in body:
                continue
            if file.suffix.lower() in {".htm", ".html"}:
                body = html.unescape(re.sub(r"<[^>]*>", " ", body))
            if not body.strip():
                continue
            relative = str(file.relative_to(source)).replace(os.sep, "/")
            entries += add_corpus_documents(db, [{
                "id": "C" + str(files + 1), "title": relative, "text": body[:60000],
            }])
            files += 1
    finally:
        db.close()
    if os.name == "posix":
        target.chmod(0o600)
    return {"files": files, "passages": entries}


def main():
    parser = argparse.ArgumentParser(description="Construir índice DeepQA FTS5")
    parser.add_argument("--source", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    print(build(Path(args.source), Path(args.index), reset=args.reset))


if __name__ == "__main__":
    main()
