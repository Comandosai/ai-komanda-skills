"""Offline teaching fixture, NOT an LLM runner or proof of autonomous execution."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def run(root, case, attempt, roles=2, approved=False, unavailable=False, revision=1):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", attempt):
        raise ValueError("Unsafe attempt name")
    if roles not in (1, 2, 3) or revision < 1:
        raise ValueError("roles must be 1..3; revision must be positive")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / attempt
    # Never overwrite an attempt, including stopped and failed attempts.
    target.mkdir(exist_ok=False)
    fingerprint = hashlib.sha256(json.dumps(case, sort_keys=True).encode()).hexdigest()
    for old in root.glob("*/summary.json"):
        previous = json.loads(old.read_text())
        if previous["input_hash"] == fingerprint and previous["revision"] == revision and previous["status"] == "complete":
            status = "duplicate"
            break
    else:
        status = "missing_input" if not case.get("topic") else "unavailable" if unavailable else "waiting_approval" if case.get("approval_required") and not approved else "complete"
    summary = dict(disclaimer="SIMULATION ONLY: no model, integration or external action", input_hash=fingerprint,
                   revision=revision, roles=roles, status=status, attempt=attempt,
                   manual_approval=bool(approved), external_actions=0, outputs=[])
    journal = ["# Учебный журнал симулятора, не журнал недели 5", "", "| Дело | Попытка | Роль | Исход | Результат | Проверка |", "|---|---|---|---|---|---|"]
    if status == "complete":
        upstream = fingerprint
        for index in range(1, roles + 1):
            result = dict(role=index, revision=revision, source_hash=upstream, topic=case["topic"], fictional=True)
            output = target / f"role-{index}-result.json"
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            upstream = hashlib.sha256(output.read_bytes()).hexdigest()
            check = target / f"role-{index}-check.json"
            check.write_text(json.dumps(dict(verified=True, result_hash=upstream, method="deterministic fixture checks, not independent AI review"), indent=2) + "\n")
            summary["outputs"].append(dict(result=output.name, check=check.name, hash=upstream))
            journal.append(f"| {case.get('id', 'demo')} | {attempt} | role-{index} | готово | {output.name} | {check.name} |")
    else:
        journal.append(f"| {case.get('id', 'demo')} | {attempt} | диспетчер | {status} | нет | причина в summary.json |")
    (target / "journal.md").write_text("\n".join(journal) + "\n")
    (target / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--attempt", required=True)
    p.add_argument("--roles", type=int, default=2)
    p.add_argument("--revision", type=int, default=1)
    p.add_argument("--approved", action="store_true")
    p.add_argument("--unavailable", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.output, json.loads(a.input.read_text()), a.attempt, a.roles, a.approved, a.unavailable, a.revision), ensure_ascii=False, indent=2))
