#!/usr/bin/env python3
"""Create a portable copy of an AI-team project without changing its source.

The exporter deliberately has two phases: copy first, then clean the new copy.
It refuses symlinks, removes conventional local state and secret files, replaces
personal absolute paths in text files, scans the result, writes a manifest and
optionally creates a ZIP next to the export directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from datetime import datetime, timezone
import zipfile


ALWAYS_REMOVE_NAMES = {
    ".DS_Store",
    ".bkit",
    ".planning",
    ".env",
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    ".ai-team-export-ignore",
    "node_modules",
    "id_rsa",
    "id_ed25519",
    "Thumbs.db",
}

# These folders are execution history, not the reusable team.  Their directory
# is kept with a short note so the receiving side knows where new state belongs.
STATE_DIR_NAMES = {
    ".board",
    ".tmp",
    "arhiv",
    "archive",
    "dashboard",
    "logs",
    "log",
    "journal",
    "zhurnal",
    "dela",
    "originaly",
    "vhod",
    "vyhod",
    "results",
    "rezultaty",
    "outputs",
    "input",
    "inbox",
    "output",
    "sessions",
    "checkpoints",
}

SECRET_FILE_RE = re.compile(
    r"^(?:\.env\.(?!example$|sample$|template$).+|.*\.(?:pem|p12|pfx|key|kdbx)|credentials(?:\..+)?|secrets?(?:\..+)?)$",
    re.IGNORECASE,
)
SECRET_CONTENT_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(
        r"(?im)^\s*(?:export\s+)?[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)\s*=\s*[\"']?(?!$|<|\$\{|YOUR_|CHANGE_ME|EXAMPLE)[^\s#\"']{8,}"
    ),
)
PERSONAL_PATH_PATTERNS = (
    (re.compile(r"/Users/[^/\s'\"`<>]+"), "${HOME}"),
    (re.compile(r"/home/[^/\s'\"`<>]+"), "${HOME}"),
    (re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s'\"`<>]+"), "${HOME}"),
)
TEXT_SUFFIXES = {
    "",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".py",
    ".js",
    ".mjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".bash",
    ".zsh",
    ".html",
    ".css",
    ".csv",
    ".xml",
}
MAX_TEXT_SCAN_BYTES = 5 * 1024 * 1024


class ExportError(RuntimeError):
    """Expected validation failure with a user-readable message."""


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot(source: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ExportError(f"Симлинк нельзя переносить автоматически: {path.relative_to(source)}")
        if path.is_file():
            result[path.relative_to(source).as_posix()] = _sha256(path)
    return result


def _read_extra_ignores(source: Path) -> set[str]:
    config = source / ".ai-team-export-ignore"
    if not config.exists():
        return set()
    rules: set[str] = set()
    for raw in config.read_text(encoding="utf-8").splitlines():
        value = raw.strip().strip("/")
        if value and not value.startswith("#"):
            if ".." in Path(value).parts or Path(value).is_absolute():
                raise ExportError(f"Небезопасное правило в .ai-team-export-ignore: {raw}")
            rules.add(value)
    return rules


def _matches_relative_rule(relative: Path, rules: set[str]) -> bool:
    posix = relative.as_posix()
    return any(posix == rule or posix.startswith(rule + "/") for rule in rules)


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _clean_copy(export_dir: Path, extra_ignores: set[str]) -> list[str]:
    removed: list[str] = []
    for path in sorted(export_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        relative = path.relative_to(export_dir)
        if not path.exists():
            continue
        remove = (
            path.name in ALWAYS_REMOVE_NAMES
            or SECRET_FILE_RE.match(path.name) is not None
            or _matches_relative_rule(relative, extra_ignores)
        )
        if remove:
            removed.append(relative.as_posix())
            _remove_path(path)

    for path in sorted(export_dir.rglob("*")):
        if path.is_dir() and path.name.lower() in STATE_DIR_NAMES:
            for child in list(path.iterdir()):
                removed.append(child.relative_to(export_dir).as_posix())
                _remove_path(child)
            (path / "README.md").write_text(
                "# Новое состояние\n\nЭта папка очищена при экспорте. Новые журналы и результаты создаются уже на новом рабочем месте.\n",
                encoding="utf-8",
            )
    return sorted(set(removed))


def _is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= MAX_TEXT_SCAN_BYTES


def _replace_personal_paths(export_dir: Path, source: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(export_dir.rglob("*")):
        if not path.is_file() or not _is_text_candidate(path):
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = original.replace(str(source), "${PROJECT_DIR}")
        for pattern, replacement in PERSONAL_PATH_PATTERNS:
            updated = pattern.sub(replacement, updated)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.relative_to(export_dir).as_posix())
    return changed


def _scan_export(export_dir: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(export_dir.rglob("*")):
        relative = path.relative_to(export_dir).as_posix()
        if path.is_symlink():
            problems.append(f"симлинк: {relative}")
            continue
        if not path.is_file() or not _is_text_candidate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(text) for pattern in SECRET_CONTENT_PATTERNS):
            problems.append(f"похожее на секрет содержимое: {relative}")
        if any(pattern.search(text) for pattern, _ in PERSONAL_PATH_PATTERNS):
            problems.append(f"персональный абсолютный путь: {relative}")
    return problems


def _write_metadata(export_dir: Path, removed: list[str], rewritten: list[str]) -> None:
    (export_dir / "README-PEREDACHA.md").write_text(
        """# Передача команды

Это отдельная экспортная копия. Исходная рабочая папка не изменялась.

Начните с `ПРИНЯТЬ-КОМАНДУ.md` в этой папке. Принимающий исполнитель ведёт `АКТ-ПРИЁМКИ.md` и выполняет этапы по порядку. Статус «принята» возможен только после ручного сквозного дела с проверенным результатом и журналом.

`${HOME}` и `${PROJECT_DIR}` в документах являются обозначениями, а не буквальными путями. Рабочую директорию нужно определить на новом месте.
""",
        encoding="utf-8",
    )
    (export_dir / "ПРИНЯТЬ-КОМАНДУ.md").write_text(
        """# Приёмка команды в Hermes

Работай в отдельно распакованной папке. Не меняй исходный ZIP. Создай `АКТ-ПРИЁМКИ.md` со статусами «ожидает», «прошло», «блокер»; для каждого пункта запиши проверенный факт и путь к свидетельству. При блокере остановись и объясни владельцу, что нужно исправить. Не объявляй команду принятой по наличию файлов.

1. Запиши абсолютный путь проекта и проверь файлы по `MANIFEST.json`: наличие, размер и SHA-256; отдельно зафиксируй лишние файлы. Если проверка не сошлась, остановись.
2. Прочитай правила проекта, карту процесса, паспорт диспетчера, паспорта ролей, контракты и инструкции запуска. Назови конкретное правило из каждого обязательного документа. Укажи отсутствующие файлы. Проверь, какой проектный файл Hermes действительно загрузил в контекст.
3. Сверь инструменты, пути, форматы входа и выхода, зависимости и расположение проектных навыков. Экспорт не содержит `.git`: если проектные навыки в этой версии Hermes требуют Git-корень, инициализируй его только в распакованной папке, без remote и push. Если навыки не обнаруживаются Hermes, предложи адаптацию расположения и доверия к ним; бизнес-правила не переписывай. Запиши, какие роли реально исполняются отдельно, а какие последовательно одной моделью.
4. Проверь необходимые подключения на новом месте. Секреты настраивает владелец через локальный механизм Hermes; не проси их в чат и не записывай в акт. Внешние отправки и постоянное расписание пока выключены.
5. Проведи одно безопасное дело через диспетчера. Сверь вход, каждый переход, итог, проверку результата и журнал с исходными критериями. Запиши путь результата и конкретные расхождения. Не используй реальные клиентские данные для учебной приёмки.
6. Покажи владельцу короткую команду ручного запуска, куда положить новое дело, где забрать результат, как увидеть статус и как остановить команду. Проверь этот способ отдельным ручным вызовом.
7. После всех успешных проверок предложи настройку gateway или расписания как отдельный этап. Для gateway нужен правильный рабочий каталог, для cron — абсолютный `--workdir`. Проверяй только один активный источник запуска. Отдельно согласуй запуск механика.

Kanban создавай лишь тогда, когда владелец использует отдельные Hermes-профили для ролей и ему нужен видимый переход задач. Акт приёмки обязателен при любом варианте.
""",
        encoding="utf-8",
    )
    manifest_files = []
    for path in sorted(export_dir.rglob("*")):
        if path.is_file():
            manifest_files.append(
                {
                    "path": path.relative_to(export_dir).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    manifest = {
        "format": 1,
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_modified": False,
        "removed_from_copy": removed,
        "personal_paths_rewritten_in_copy": rewritten,
        "files": manifest_files,
    }
    (export_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _make_zip(export_dir: Path, archive: Path) -> None:
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(export_dir.rglob("*")):
            if path.is_file():
                bundle.write(path, Path(export_dir.name) / path.relative_to(export_dir))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ExportError("Проверка ZIP не пройдена")
        for name in bundle.namelist():
            archive_path = Path(name)
            if archive_path.is_absolute() or ".." in archive_path.parts:
                raise ExportError(f"Небезопасный путь в ZIP: {name}")


def export_team(source: Path, output_parent: Path, name: str, make_zip: bool = True) -> tuple[Path, Path | None]:
    source = source.expanduser().resolve()
    output_parent = output_parent.expanduser().resolve()
    if not source.is_dir():
        raise ExportError(f"Исходная папка не найдена: {source}")
    if source == Path(source.anchor) or source == Path.home().resolve():
        raise ExportError("Нельзя экспортировать корень диска или домашнюю папку целиком")
    export_dir = output_parent / name
    archive = output_parent / f"{name}.zip"
    staging = output_parent / f".{name}.staging-{os.getpid()}"
    if _inside(export_dir, source) or _inside(output_parent, source):
        raise ExportError("Экспорт должен находиться вне исходной рабочей папки")
    if export_dir.exists() or archive.exists() or staging.exists():
        raise ExportError(f"Путь экспорта или временная копия уже существует: {export_dir}")

    before = _snapshot(source)
    extra_ignores = _read_extra_ignores(source)
    output_parent.mkdir(parents=True, exist_ok=True)
    try:
        # Requirement: first make an independent copy, then clean only it.
        shutil.copytree(source, staging)
        removed = _clean_copy(staging, extra_ignores)
        rewritten = _replace_personal_paths(staging, source)
        problems = _scan_export(staging)
        if problems:
            raise ExportError("Экспорт остановлен:\n- " + "\n- ".join(problems))
        _write_metadata(staging, removed, rewritten)
        final_problems = _scan_export(staging)
        if final_problems:
            raise ExportError("Финальная проверка остановлена:\n- " + "\n- ".join(final_problems))
        staging.rename(export_dir)
        if make_zip:
            _make_zip(export_dir, archive)
        after = _snapshot(source)
        if before != after:
            raise ExportError("Исходная папка изменилась во время экспорта; результат удалён")
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        if export_dir.exists():
            shutil.rmtree(export_dir)
        if archive.exists():
            archive.unlink()
        raise
    return export_dir, archive if make_zip else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Создать очищенную переносимую копию команды, не меняя исходную папку."
    )
    parser.add_argument("source", type=Path, help="исходная рабочая папка команды")
    parser.add_argument(
        "--output-parent",
        type=Path,
        help="куда положить экспорт; по умолчанию рядом с исходной папкой",
    )
    parser.add_argument("--name", help="имя экспортной папки без пути")
    parser.add_argument("--no-zip", action="store_true", help="не создавать ZIP")
    return parser


def main() -> int:
    args = _parser().parse_args()
    source = args.source.expanduser().resolve()
    output_parent = args.output_parent or source.parent
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = args.name or f"{source.name}-export-{stamp}"
    if Path(name).name != name or name in {"", ".", ".."}:
        print("Ошибка: --name должен быть одним безопасным именем папки", file=sys.stderr)
        return 2
    try:
        export_dir, archive = export_team(source, output_parent, name, make_zip=not args.no_zip)
    except (ExportError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    print(f"Экспортная папка: {export_dir}")
    if archive:
        print(f"ZIP: {archive}")
    print("Исходная рабочая папка проверена: не изменена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
