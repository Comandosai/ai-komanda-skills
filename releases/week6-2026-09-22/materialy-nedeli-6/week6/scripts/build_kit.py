"""Build offline participant guide from one source; no network or user-project writes."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = """
:root{color-scheme:dark;--bg:#0d0e0f;--card:#181a1b;--line:#363a3b;--lime:#c8ff00;--text:#f0f0f0;--muted:#b9bfc0}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:17px/1.65 Arial,Helvetica,sans-serif}
a{color:var(--lime);text-underline-offset:4px}a:hover{color:#e1ff78}button{font:inherit;cursor:pointer;background:var(--lime);color:#10120a;border:0;border-radius:6px;padding:10px 18px}button:focus-visible,a:focus-visible{outline:3px solid #fff;outline-offset:4px}
header{border-bottom:1px solid var(--line);padding:16px max(20px,calc((100vw - 1000px)/2));font-weight:bold;letter-spacing:.08em}
main{max-width:1000px;margin:auto;padding:48px 24px 100px}h1{font-size:clamp(38px,7vw,76px);line-height:1.04;letter-spacing:-.04em;margin:14px 0 24px;max-width:850px}h2{font-size:clamp(26px,4vw,40px);line-height:1.2;letter-spacing:-.02em}h3{font-size:21px;margin-top:28px}p{max-width:850px}.eyebrow{color:var(--lime);font-size:13px;letter-spacing:.12em;text-transform:uppercase}.intro{font-size:22px;color:var(--muted)}nav{display:flex;flex-wrap:wrap;gap:9px;margin:32px 0}nav a{padding:8px 12px;border:1px solid var(--line);border-radius:5px;text-decoration:none;font-size:14px}
section{border-top:1px solid var(--line);margin-top:46px;padding-top:24px;scroll-margin-top:24px}.chat{color:var(--lime);font-weight:bold}li{padding:5px 0}ol{padding-left:26px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#090b0c;border:1px solid var(--line);padding:20px;border-radius:8px;font:15px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace}code{overflow-wrap:anywhere;font-size:.92em}.prompt{margin:25px 0}.prompt button{font-size:14px}.result{border-left:4px solid var(--lime);padding:4px 0 4px 20px;margin:28px 0}.note{color:var(--muted);font-size:15px}.links{display:flex;flex-wrap:wrap;gap:18px;margin:20px 0}.status{background:#252518;border:1px solid #646334;border-radius:8px;padding:16px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}img{max-width:100%}.table-wrap{overflow-x:auto}footer{margin-top:50px;color:var(--muted);font-size:14px}blockquote{border-left:3px solid var(--lime);margin-left:0;padding-left:18px}
@media(max-width:520px){main{padding:28px 18px 70px}body{font-size:16px}pre{padding:14px;font-size:14px}h1{font-size:42px}}
@media print{body{background:white;color:black;font-size:11pt}header,nav,button{display:none}main{max-width:none;padding:0}section{break-inside:auto}pre,.status{background:#f5f5f5;color:black}a,.chat,.eyebrow,.note{color:#333}h1{font-size:32pt}h2{font-size:22pt}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""
JS = """async function copyPrompt(id,button){const el=document.getElementById(id);try{await Promise.race([navigator.clipboard.writeText(el.textContent),new Promise((_,reject)=>setTimeout(()=>reject(new Error('clipboard timeout')),800))]);button.textContent='Скопировано';}catch(e){const range=document.createRange();range.selectNodeContents(el);const sel=window.getSelection();sel.removeAllRanges();sel.addRange(range);button.textContent='Текст выделен: Ctrl+C / ⌘C';}setTimeout(()=>button.textContent='Скопировать промпт',3500);} """

def page(title, body, back='GUIDE-N6.html'):
    return '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+CSS+'</style></head><body><header>COMANDOS AI / ПРАКТИКУМ</header><main>'+body+'<footer><a href="'+back+'">Вернуться к гайду</a><p>Неделя 6 · комплект от 22.09.2026. Инструкции не заменяют проверку возможностей вашей среды.</p></footer></main><script>'+JS+'</script></body></html>'

def inline(s):
    s=html.escape(s)
    s=re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s=re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    def link(m):
        url=m[2]
        if not re.match(r'^(?:https?://|[A-Za-z0-9_./#-])',url) or re.match(r'^[a-zA-Z]+:',url) and not url.startswith(('https://','http://')):
            return m[1]
        if url.endswith('.md'): url=url[:-3]+'.html'
        return '<a href="'+url+'">'+m[1]+'</a>'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,s)

def markdown(s):
    s=re.sub(r'^---\n.*?\n---\n','',s,flags=re.S)
    out=[]; code=[]; in_code=False; listed=False
    for line in s.splitlines():
        if line.startswith('```'):
            if listed: out.append('</ul>'); listed=False
            if in_code: out.append('<pre>'+html.escape('\n'.join(code))+'</pre>'); code=[]
            in_code=not in_code; continue
        if in_code: code.append(line); continue
        if line.startswith('- '):
            if not listed: out.append('<ul>'); listed=True
            out.append('<li>'+inline(line[2:])+'</li>'); continue
        if listed: out.append('</ul>'); listed=False
        m=re.match(r'^(#{1,6}) (.*)',line)
        if m: out.append(f'<h{len(m[1])}>'+inline(m[2])+f'</h{len(m[1])}>')
        elif line.startswith('> '): out.append('<blockquote>'+inline(line[2:])+'</blockquote>')
        elif line.strip(): out.append('<p>'+inline(line)+'</p>')
    if listed: out.append('</ul>')
    return '\n'.join(out)

def build():
    data=json.loads((ROOT/'content.json').read_text())
    esc=html.escape
    out=['<p class="eyebrow">Продолжение недели 5</p><h1>'+esc(data['title'])+'</h1><p class="intro">'+esc(data['subtitle'])+'</p>',
         '<p>Все шаги на одной странице. Основной путь выполняют все; VPS и Hermes выбирайте, если нужен перенос. Видео добавим после записи.</p>',
         '<div class="links"><a href="downloads/AI-KOMANDA-N6.zip" download>Скачать комплект</a><a href="recording/SCENARIY-VIDEO.html">Для ведущего: сценарии записи</a><a href="PROVERKA.html">Что проверено</a></div>',
         '<nav aria-label="Шаги">'+''.join('<a href="#'+s['id']+'">'+esc(s['title'])+'</a>' for s in data['steps'])+'</nav>']
    prompts={}
    for s in data['steps']:
        out.append('<section id="'+s['id']+'"><h2>'+esc(s['title'])+'</h2><p class="chat">'+esc(s['chat'])+'</p><p>'+esc(s['why'])+'</p><ol>'+''.join('<li>'+esc(a)+'</li>' for a in s['actions'])+'</ol>')
        for p in s.get('prompts',[]):
            prompts[p['id']]=p['text']
            out.append('<div class="prompt"><h3>'+esc(p['label'])+'</h3><pre id="'+p['id']+'">'+esc(p['text'])+'</pre><button onclick="copyPrompt(\''+p['id']+'\',this)">Скопировать промпт</button></div>')
        out.append('<div class="result"><strong>Проверьте результат</strong><p>'+esc(s['result'])+'</p></div><p class="note">'+esc(s['stop'])+'</p>')
        out.append('<div class="links">'+''.join('<a href="'+esc(url)+'">'+esc(label)+'</a>' for label,url in s.get('links',[]))+'</div></section>')
    (ROOT/'GUIDE-N6.html').write_text(page(data['title'],'\n'.join(out)))
    (ROOT/'prompts.json').write_text(json.dumps(prompts,ensure_ascii=False,indent=2)+'\n')
    for folder in [ROOT,ROOT/'instructions',ROOT/'recording']:
        for f in folder.glob('*.md'):
            if f.name=='README.md': continue
            title=next((l[2:] for l in f.read_text().splitlines() if l.startswith('# ')),f.stem)
            f.with_suffix('.html').write_text(page(title,markdown(f.read_text()),'../GUIDE-N6.html' if folder!=ROOT else 'GUIDE-N6.html'))
    print('Built GUIDE-N6.html, prompts.json and supporting HTML pages')

if __name__=='__main__': build()
