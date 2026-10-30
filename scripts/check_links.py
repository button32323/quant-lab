#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 Markdown 内部链接（相对路径）是否存在。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\]\(([^)]+)\)")
SKIP_DIRS = {".git", "data", "paper", ".venv", "__pycache__"}


def md_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        out.append(p)
    return sorted(out)


def main() -> int:
    broken = []
    checked = 0
    for f in md_files():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for m in LINK.finditer(text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (f.parent / path_part).resolve()
            checked += 1
            if not resolved.exists():
                broken.append(f"{f.relative_to(ROOT)} -> {target}")
    print(f"checked {checked} internal links in {len(md_files())} markdown files")
    if broken:
        print("BROKEN:")
        for b in broken:
            print(" ", b)
        return 1
    print("all internal links OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
