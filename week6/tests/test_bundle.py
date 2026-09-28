from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
import hashlib
import zipfile
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parents[1]

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a' and 'href' in a:self.links.append(a['href'])

class Bundle(unittest.TestCase):
    def test_workflow_order_and_separate_handoffs(self):
        data=json.loads((ROOT/'content.json').read_text())
        self.assertEqual([s['id'] for s in data['steps']],
            ['start','link','trial','connect','improve','final','pack','host','auto','report'])
        self.assertEqual(len([s for s in data['steps'] if s['id']!='start']),9)
        self.assertTrue(all(s.get('time') and s.get('files') for s in data['steps'] if s['id']!='start'))
        prompts={p['id']:p['text'] for s in data['steps'] for p in s.get('prompts',[])}
        self.assertNotIn('p-host',prompts)
        self.assertIn('p8-hermes',prompts)
        self.assertIn('p8-vps',prompts)
        self.assertIn('p9-mechanic',prompts)
        self.assertIn('p10',prompts)
        self.assertIn('запроси ссылки на сами источники',prompts['p4'].lower())
        for required in ('GitHub', 'пользовательского аккаунта', 'лицензию', 'постоянное расписание включим в блоке 8', 'Закрытые оригиналы'):
            self.assertIn(required, prompts['p4'])
        self.assertNotIn('расписан',prompts['p6'].lower())
        for gate in ('Дождись подтверждения маршрута', 'Согласуй первый цикл отдельно', 'Только после выбора цикла', 'без согласия не переходи'):
            self.assertIn(gate, prompts['p4'])
        self.assertIn('OTCHET-N6.md',prompts['p10'])
        self.assertIn('PREZENTACIYA-HAKATON.html',prompts['p10'])
    def test_copy_first_packaging_and_no_future_methodology(self):
        data=json.loads((ROOT/'content.json').read_text())
        steps={s['id']:s for s in data['steps']}
        packaging=' '.join(steps['pack']['actions'])+' '+steps['pack']['prompts'][0]['text']
        self.assertIn('коп',packaging.lower())
        self.assertIn('исходн',packaging.lower())
        whole=json.dumps(data,ensure_ascii=False).lower()
        self.assertNotIn('следующую команду',whole)
    def test_prompt_single_source(self):
        data=json.loads((ROOT/'content.json').read_text()); prompts=json.loads((ROOT/'prompts.json').read_text())
        expected={p['id']:p['text'] for s in data['steps'] for p in s.get('prompts',[])}
        self.assertEqual(prompts,expected)
    def test_all_links_resolve(self):
        files=[ROOT/'GUIDE-N6.html',*ROOT.glob('instructions/*.html'),*ROOT.glob('recording/*.html')]
        for f in files:
            parser=Links();parser.feed(f.read_text())
            self.assertEqual(len(parser.ids),len(set(parser.ids)),str(f))
            for href in parser.links:
                u=urlsplit(href)
                if u.scheme: continue
                if href.startswith('#'):self.assertIn(href[1:],parser.ids);continue
                self.assertTrue((f.parent/unquote(u.path)).exists(),f'{f}: {href}')
    def test_guide_links_work_without_kit_folder(self):
        kit='https://raw.githubusercontent.com/Comandosai/ai-komanda-skills/main/week6/downloads/AI-KOMANDA-N6.zip'
        text=(ROOT/'GUIDE-N6.html').read_text()
        self.assertNotIn('__KIT_SOURCE__',text)
        self.assertNotIn('kitSource',text)
        prompts=json.loads((ROOT/'prompts.json').read_text())
        self.assertIn(kit,prompts['p1'])
        self.assertIn('попроси меня скачать архив вручную',prompts['p1'])
        parser=Links();parser.feed(text)
        self.assertIn(kit,parser.links)
        for href in parser.links:
            if href.startswith('#'):self.assertIn(href[1:],parser.ids);continue
            self.assertTrue(href.startswith('https://'),href)
    def test_no_remote_render_dependencies(self):
        for f in [ROOT/'GUIDE-N6.html',ROOT/'assets/shablon-hakatona.html']:
            self.assertFalse(re.search(r'<(?:script|img|link|iframe)\b[^>]*(?:src|href)=["\']https?://',f.read_text()))
    def test_archive_manifest_and_links(self):
        archive=ROOT/'downloads/AI-KOMANDA-N6.zip'
        if not archive.exists(): self.skipTest('Архив ещё не собран')
        with zipfile.ZipFile(archive) as z:
            names=set(z.namelist()); self.assertIsNone(z.testzip())
            self.assertFalse(any('SLEDUYUSHCHAYA-KOMANDA' in name for name in names))
            self.assertIn('materialy-nedeli-6/week6/scripts/render_hackathon.py',names)
            self.assertIn('materialy-nedeli-6/week6/assets/shablon-hakatona.html',names)
            self.assertIn('materialy-nedeli-6/week6/assets/comandos-logo.png',names)
            self.assertIn('materialy-nedeli-6/week6/instructions/USTANOVKA.md',names)
            for item in json.loads(z.read('materialy-nedeli-6/MANIFEST.json')):
                self.assertEqual(hashlib.sha256(z.read(item['path'])).hexdigest(),item['sha256'])
            for name in names:
                self.assertNotIn('.env',Path(name).parts)
                if not name.endswith('.html'):continue
                parser=Links();parser.feed(z.read(name).decode())
                for href in parser.links:
                    u=urlsplit(href)
                    if u.scheme or href.startswith('#'):continue
                    parts=[]
                    for part in (Path(name).parent/Path(unquote(u.path))).parts:
                        if part=='..':parts.pop()
                        elif part!='.':parts.append(part)
                    self.assertIn('/'.join(parts),names,f'{name}: {href}')

if __name__=='__main__':unittest.main()
