#!/usr/bin/env python3
"""Fill the canonical week 6 HTML deck without rewriting its layout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


START = "/* WEEK6_DATA_START — этот блок заменяет render_hackathon.py */"
END = "/* WEEK6_DATA_END */"
BLOCK = re.compile(
    re.escape(START) + r"\s*const DATA = [\s\S]*?;\s*" + re.escape(END)
)


def render(template: Path, data_path: Path, output: Path) -> None:
    source = template.read_text(encoding="utf-8")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Корневое значение данных презентации должно быть объектом")
    if not BLOCK.search(source):
        raise ValueError("В шаблоне не найден единственный блок WEEK6_DATA")

    encoded = json.dumps(data, ensure_ascii=False, indent=2)
    encoded = encoded.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    replacement = f"{START}\nconst DATA = {encoded};\n{END}"
    rendered, count = BLOCK.subn(lambda _: replacement, source, count=1)
    if count != 1:
        raise ValueError(f"Ожидалась одна замена блока данных, выполнено: {count}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "assets" / "shablon-hakatona.html",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    render(args.template, args.data, args.output)


if __name__ == "__main__":
    main()
