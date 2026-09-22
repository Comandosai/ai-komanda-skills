"""Read-only evidence checks; writes a NEW W6 snapshot, never modifies W5."""
import argparse
from collections import Counter, defaultdict
import html
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

SAFE = re.compile(r'^[A-Za-z0-9_-]+$')

def checked_file(root, value, attempt_dir=None):
    if not isinstance(value,str) or not value or '\\' in value: return False
    p=Path(value)
    if p.is_absolute() or '..' in p.parts: return False
    target=(root/p).resolve()
    try:
        target.relative_to(root.resolve())
        if attempt_dir is not None: target.relative_to(attempt_dir.resolve())
    except ValueError: return False
    return target.is_file() and target.stat().st_size>0

def summarize(root, data):
    if data.get('schema_version')!=1 or not isinstance(data.get('attempts'),list):
        raise ValueError('Нужен реестр schema_version=1 с attempts[]')
    attempts=data['attempts']
    if any(not isinstance(a,dict) for a in attempts): raise ValueError('Попытка должна быть объектом')
    ids=Counter(str(a.get('id')) for a in attempts)
    used=Counter()
    for a in attempts:
        for field in ('result_files','check_files'):
            if not isinstance(a.get(field,[]),list): raise ValueError(field+' должен быть массивом')
        for f in a.get('result_files',[]) + a.get('check_files',[]):
            if isinstance(f,str): used[str((root/f).resolve())]+=1
    groups=defaultdict(list)
    for a in attempts:
        reasons=[]
        aid=a.get('id'); case=a.get('case_id')
        identity=isinstance(aid,str) and bool(SAFE.fullmatch(aid)) and isinstance(case,str) and bool(SAFE.fullmatch(case))
        if not identity: reasons.append('Некорректное имя дела или попытки')
        if ids[str(aid)]!=1: reasons.append('Номер попытки повторяется')
        result=a.get('result_files',[]); checks=a.get('check_files',[])
        folder=root/'dela'/str(case)/str(aid)
        files_ok=identity and bool(result) and bool(checks) and isinstance(result,list) and isinstance(checks,list)
        if files_ok:
            files_ok=all(checked_file(root,f,folder) for f in result+checks)
            resolved=[str((root/f).resolve()) for f in result+checks if isinstance(f,str)]
            files_ok=files_ok and len(set(resolved))==len(result+checks) and all(used[f]==1 for f in resolved)
        if not files_ok: reasons.append('Нет полного раздельного комплекта результата и проверки внутри папки попытки')
        inputs=a.get('input_files')
        if not isinstance(inputs,list) or not inputs or not all(checked_file(root,f) for f in inputs):
            reasons.append('Входные файлы отсутствуют или недоступны')
        if a.get('mode') not in ('trial','final','safety'): reasons.append('Неизвестный режим')
        for field in ('process_id','scope_version','config_version','series_id'):
            if not isinstance(a.get(field),str) or not a[field].strip(): reasons.append('Не задано '+field)
        if a.get('status')!='completed': reasons.append(a.get('reason') or 'Попытка не завершена')
        if a.get('check_passed') is not True: reasons.append('Проверка не подтверждает завершение')
        complete=not reasons
        touches=a.get('touches'); corrections=a.get('content_corrections')
        known=type(touches) is int and touches>=0
        corrected_known=type(corrections) is int and corrections>=0
        key=tuple(str(a.get(f,'не задано')) for f in ('process_id','scope_version','config_version','series_id','mode'))
        groups[key].append(dict(id=aid,case_id=case,complete=complete,accepted=complete and a.get('accepted') is True,
            no_hands=complete and known and touches==0,touches=touches if known else None,
            no_corrections=complete and corrected_known and corrections==0,
            problems=reasons,result_files=[f for f in result if checked_file(root,f,folder)],check_files=[f for f in checks if checked_file(root,f,folder)],
            trigger=a.get('trigger','неизвестно'),data_kind=a.get('data_kind','неизвестно')))
    return [dict(key=list(k),attempts=v,total=len(v),complete=sum(a['complete'] for a in v),
                 accepted=sum(a['accepted'] for a in v),no_hands=sum(a['no_hands'] for a in v),
                 unknown_touches=sum(a['touches'] is None for a in v),
                 distinct_completed_cases=len({a['case_id'] for a in v if a['complete']})) for k,v in groups.items()]

def render(groups):
    e=lambda x:html.escape(str(x))
    parts=['<h1>Результаты недели 6</h1><p>Снимок по реестру и наличию файлов. Содержательная проверка, независимость и запуск от триггера требуют отдельных свидетельств. Неделя 5 не пересчитывается.</p>']
    if not groups: parts.append('<p>Попыток пока нет. Это не ноль успешных дел, а отсутствие наблюдений.</p>')
    for g in groups:
        parts.append('<section><h2>'+e(' / '.join(g['key']))+'</h2><p>Дошло: '+str(g['complete'])+'/'+str(g['total'])+' · Принято: '+str(g['accepted'])+' · Без рук: '+str(g['no_hands'])+' · Касания неизвестны: '+str(g['unknown_touches'])+'</p><p>Разных завершённых дел: '+str(g['distinct_completed_cases'])+'</p><table><tr><th>Дело / попытка</th><th>Итог</th><th>Касания</th><th>Причина</th></tr>')
        for a in g['attempts']:
            links=' '.join('<a style="color:#c8ff00" href="'+quote(f,safe='/')+'">'+e(Path(f).name)+'</a>' for f in a['result_files']+a['check_files'])
            parts.append('<tr><td>'+e(a['case_id'])+' / '+e(a['id'])+'<br>'+links+'</td><td>'+('Дошло' if a['complete'] else 'Не подтверждено')+'</td><td>'+e(a['touches'] if a['touches'] is not None else 'неизвестно')+'</td><td>'+e('; '.join(a['problems']))+'</td></tr>')
        parts.append('</table></section>')
    return '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Неделя 6: результаты</title><style>body{background:#0d0e0f;color:#eee;font:17px/1.6 Arial;margin:32px;max-width:1100px}h1,h2{color:#c8ff00}section{margin:40px 0;overflow:auto}td,th{padding:12px;text-align:left;border-bottom:1px solid #444}h2{font-size:22px;overflow-wrap:anywhere}</style>'+''.join(parts)+'</html>'

def main():
    p=argparse.ArgumentParser(); p.add_argument('--project',required=True); args=p.parse_args()
    root=Path(args.project).resolve(); source=root/'dashboard/week6.json'; dest=root/'DASHBOARD-N6.html'
    if dest.is_symlink(): raise ValueError('Выход не должен быть симлинком')
    groups=summarize(root,json.loads(source.read_text()))
    fd,tmp=tempfile.mkstemp(dir=root,prefix='.week6-',suffix='.tmp')
    try:
        with os.fdopen(fd,'w') as f: f.write(render(groups))
        os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    print(dest)

if __name__=='__main__': main()
