#!/usr/bin/env python3
"""Read-only journal aggregation. Writes only dashboard artifacts; no network/deps."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

OUTCOMES = {'начал', 'готово', 'отказ: данные', 'отказ: инструмент',
            'принято', 'поправил', 'отклонил'}
SERIES = {'trial', 'baseline', 'repeat', 'other'}


def inside(root, value):
    root = Path(root).resolve()
    if not value or not isinstance(value, str):
        raise ValueError('Пустой или неверный путь')
    path = (root / value).resolve()
    if path == root or root not in path.parents:
        raise ValueError('Путь вне проекта: ' + value)
    return path


def parse_journal(content):
    rows, warnings, seen = [], [], set()
    for number, line in enumerate(content.splitlines(), 1):
        if '|' not in line:
            if line.strip() and not line.lstrip().startswith('#'):
                warnings.append(f'Строка {number}: не таблица, не учтена')
            continue
        parts = [p.strip().replace('\\|', '|') for p in
                 re.split(r'(?<!\\)\|', line.strip().strip('|'))]
        if parts and (parts[0].lower() == 'когда' or
                      all(re.fullmatch(r'[:\-\s]*', p) for p in parts)):
            continue
        if len(parts) != 6:
            warnings.append(f'Строка {number}: ожидалось 6 колонок, не учтена')
            continue
        key = tuple(parts)
        if key in seen:
            warnings.append(f'Строка {number}: точный дубль, не учтён')
            continue
        seen.add(key)
        when, case, step, actor, outcome, note = parts
        match = re.search(r'(?:^|[;\s])run=([A-Za-z0-9_-]+)(?=;|\s|$)', note)
        rows.append(dict(line=number, when=when, case=case, step=step, actor=actor,
                         outcome=outcome, note=note, run=match[1] if match else None))
    return rows, warnings


def aggregate(root, config, content):
    steps = config.get('steps', [])
    if not isinstance(steps, list) or not steps or len(set(steps)) != len(steps) or not all(isinstance(x, str) and x for x in steps):
        raise ValueError('steps: непустой список уникальных шагов')
    attempts = config.get('attempts', [])
    ids = [a['id'] for a in attempts]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_-]+', x) for x in ids):
        raise ValueError('id попыток должны быть уникальными безопасными строками')
    rows, warnings = parse_journal(content)
    actors = set(config.get('actors', [])) | {'я'}
    unassigned = [r for r in rows if r['run'] not in ids]
    if unassigned:
        warnings.append(f'Не распределено по попыткам: {len(unassigned)} событий')
    case_ids = set(config.get('cases', [])) | {a['case'] for a in attempts} | {r['case'] for r in rows}
    output = []
    # A result/check reused between attempts is not independent evidence.
    paths = {}
    for a in attempts:
        for field in ('result', 'check'):
            if a.get(field):
                p = str(inside(root, a[field]))
                paths.setdefault(p, set()).add(a['id'])
    for a in attempts:
        if a.get('series') not in SERIES:
            raise ValueError('Неверная серия: ' + str(a.get('series')))
        events = [r for r in rows if r['run'] == a['id']]
        problems = []
        cells = []
        # Unparseable lines could hide a touch/failure, so all outcomes are uncertain.
        uncertain = any('не учтена' in w and 'дубль' not in w for w in warnings)
        uncertain |= any(r['case'] == a['case'] for r in unassigned)
        valid = []
        for r in events:
            parts = r['step'].split('→')
            step_ok = len(parts) in (1, 2) and all(s in steps for s in parts)
            if (r['case'] != a['case'] or r['outcome'] not in OUTCOMES or
                    r['actor'] not in actors or not step_ok):
                problems.append(f"Строка {r['line']}: неизвестный автор/шаг/исход либо другое дело")
                uncertain = True
            else:
                valid.append(r)
        touches = sum(r['actor'] == 'я' and r['outcome'] != 'принято' for r in valid)
        data_errors = sum(r['outcome'] == 'отказ: данные' for r in valid)
        tool_errors = sum(r['outcome'] == 'отказ: инструмент' for r in valid)
        acceptance = None
        for step in steps:
            ev = [r for r in valid if r['step'] == step]
            done, accepted, state = False, False, 'net'
            ready_line = 0
            finished = 0
            for r in ev:
                o = r['outcome']
                if o == 'готово':
                    done, accepted, state = True, False, 'proshlo'
                    ready_line = r['line']
                    finished += 1
                elif o == 'принято':
                    if done:
                        accepted = True
                    else:
                        problems.append(f"Строка {r['line']}: приёмка без завершения")
                        uncertain = True
                else:
                    done, accepted = False, False
                    state = 'idet' if o == 'начал' else 'vstalo'
                if step == steps[-1]:
                    acceptance = o if o in {'принято', 'поправил', 'отклонил'} else None
            cells.append(dict(step=step, state=state, done=done, accepted=accepted, ready_line=ready_line,
                              touches=sum(r['actor'] == 'я' and r['outcome'] != 'принято' for r in ev),
                              reworks=max(0, finished - 1)))
        files_ok = True
        for field in ('result', 'check'):
            p = inside(root, a[field]) if a.get(field) else None
            if not p or not p.is_file():
                files_ok = False
            elif len(paths[str(p)]) > 1:
                files_ok = False
                problems.append('Файл используется разными попытками: ' + a[field])
        # Handoff refusal/start must be followed by handoff ready, never ignored.
        handoffs = {}
        for r in valid:
            if '→' in r['step']:
                handoffs[r['step']] = r['outcome']
        handoff_ok = all(o in {'готово', 'принято'} for o in handoffs.values())
        in_order = all(cells[i]['ready_line'] < cells[i+1]['ready_line'] for i in range(len(cells)-1))
        complete = (not uncertain and bool(cells) and all(c['done'] for c in cells) and in_order
                    and cells[-1]['accepted'] and files_ok and handoff_ok)
        if not files_ok and any(c['done'] for c in cells):
            problems.append('Нет отдельных файлов результата и проверки текущей попытки')
        output.append(dict(id=a['id'], case=a['case'], series=a['series'],
                           synthetic=a.get('synthetic'), observed=a.get('observed') is True,
                           complete=complete, no_hands=complete and a.get('touches_known') is True and touches == 0,
                           touches_known=a.get('touches_known') is True, touches=touches,
                           data_errors=data_errors, tool_errors=tool_errors,
                           acceptance=acceptance, cells=cells, problems=problems,
                           uncertain=bool(uncertain), events=len(events),
                           input_hash=a.get('input_hash'), scope_version=a.get('scope_version')))
    summaries = {}
    for series in ('trial', 'baseline', 'repeat', 'other'):
        group = [a for a in output if a['series'] == series]
        summaries[series] = dict(total=len(group), observed=sum(a['observed'] for a in group),
                                 complete=sum(a['complete'] for a in group),
                                 no_hands=sum(a['no_hands'] for a in group))
    before = [a for a in output if a['series'] == 'baseline']
    after = [a for a in output if a['series'] == 'repeat']
    comparable = bool(before and after)
    comparable &= len({a['case'] for a in before}) == len(before)
    comparable &= len({a['case'] for a in after}) == len(after)
    comparable &= {a['case'] for a in before} == {a['case'] for a in after}
    bmap = {a['case']: a for a in before}
    for a in after:
        b = bmap.get(a['case'], {})
        comparable &= bool(a.get('input_hash') and a['input_hash'] == b.get('input_hash')
                           and a.get('scope_version') and a['scope_version'] == b.get('scope_version'))
    comparable &= all(a['observed'] and not a['uncertain'] and a['touches_known'] for a in before + after)
    return dict(title=config.get('title', 'Команда'), live=config.get('live') is True,
                mode='локальный расчёт по журналу', updated=dt.datetime.now(dt.timezone.utc).isoformat(),
                source=config.get('journal'), steps=steps, attempts=output, series=summaries,
                comparison=dict(comparable=bool(comparable),
                                delta=summaries['repeat']['no_hands']-summaries['baseline']['no_hands'] if comparable else None),
                warnings=warnings, unassigned=unassigned,
                cases_without_journal=sorted(case_ids - {r['case'] for r in rows}))


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.dashboard-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def build(project):
    root = Path(project).resolve()
    config = json.loads(inside(root, 'dashboard/config.json').read_text(encoding='utf-8'))
    journal = inside(root, config['journal'])
    content = journal.read_text(encoding='utf-8') if journal.is_file() else ''
    data = aggregate(root, config, content)
    if not journal.is_file():
        data['warnings'].append('Журнал не найден: ' + config['journal'])
    template = Path(__file__).resolve().parents[1] / 'assets' / 'shablon-dashboarda.html'
    html = template.read_text(encoding='utf-8')
    payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
    marker = '<script type="application/json" id="dannye">null</script>'
    if html.count(marker) != 1:
        raise ValueError('Неверный шаблон данных')
    html = html.replace(marker, '<script type="application/json" id="dannye">' + payload + '</script>')
    output = inside(root, 'dashboard/index.html')
    snapshot = inside(root, 'dashboard/snimki/' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-') + uuid.uuid4().hex[:8] + '.json')
    atomic_write(snapshot, json.dumps(data, ensure_ascii=False, indent=2))
    atomic_write(output, html)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    try:
        result = build(args.project)
        print(json.dumps({'attempts': len(result['attempts']), 'warnings': result['warnings'],
                          'comparison': result['comparison']}, ensure_ascii=False))
    except (ValueError, KeyError, TypeError, OSError) as e:
        parser.exit(1, 'Дашборд не обновлён: ' + str(e) + '\n')
