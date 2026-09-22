"""Package allowlisted course files only, not a generic user-project exporter."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[2]
RELEASE=ROOT/'releases/week6-2026-09-22-v2/materialy-nedeli-6'
SKILL_ROOT=RELEASE if RELEASE.exists() else ROOT
TOPS=('svyazat-komandu','mehanik','otchet','week6')
DENY={'__pycache__','.git','downloads','node_modules','evidence'}
EXT={'.md','.html','.json','.py','.mjs','.txt'}

def candidates():
    files=[]
    for top in TOPS:
        base=ROOT if top=='week6' else SKILL_ROOT
        for p in (base/top).rglob('*'):
            rel=p.relative_to(base)
            if any(part in DENY for part in rel.parts) or p.is_dir(): continue
            if p.is_symlink(): raise ValueError('Симлинк в комплекте: '+str(rel))
            if p.suffix in EXT: files.append(p)
    for n in ('svyazat-komandu','mehanik','otchet'): files.append(SKILL_ROOT/'chatgpt'/f'{n}.txt')
    return sorted(set(files))

def main():
    dest=ROOT/'week6/downloads'; dest.mkdir(exist_ok=True)
    archive=dest/'AI-KOMANDA-N6.zip'; manifest=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in candidates():
            rel=p.relative_to(SKILL_ROOT if p.is_relative_to(SKILL_ROOT) and SKILL_ROOT!=ROOT else ROOT); blob=p.read_bytes()
            # No recursive link to the archive itself inside the extracted package.
            if rel==Path('week6/GUIDE-N6.html'):
                s=blob.decode(); s=re.sub(r'<a href="downloads/AI-KOMANDA-N6.zip"[^>]*>.*?</a>','<span>Комплект уже распакован</span>',s); blob=s.encode()
            if re.search(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|sk-[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{30,}',blob):
                raise ValueError('Подозрение на секрет: '+str(rel))
            name='materialy-nedeli-6/'+rel.as_posix(); z.writestr(name,blob)
            manifest.append(dict(path=name,sha256=hashlib.sha256(blob).hexdigest(),bytes=len(blob)))
        z.writestr('materialy-nedeli-6/START.html','<!doctype html><html lang="ru"><meta charset="utf-8"><title>Неделя 6</title><h1>Неделя 6</h1><p><a href="week6/GUIDE-N6.html">Открыть гайд</a></p><p>Сохраните структуру папок. Не заменяйте рабочий проект этим комплектом.</p></html>')
        z.writestr('materialy-nedeli-6/MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert len(names)==len(set(names))
        assert all(not n.startswith('/') and '..' not in Path(n).parts for n in names)
    print(f'{archive}: {len(manifest)} files, {archive.stat().st_size} bytes')

if __name__=='__main__': main()
