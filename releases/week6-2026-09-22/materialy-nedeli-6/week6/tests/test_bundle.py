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
                if href=='downloads/AI-KOMANDA-N6.zip':continue # built after test
                self.assertTrue((f.parent/unquote(u.path)).exists(),f'{f}: {href}')
    def test_no_remote_render_dependencies(self):
        for f in [ROOT/'GUIDE-N6.html',ROOT/'assets/shablon-hakatona.html']:
            self.assertFalse(re.search(r'(?:src|href)=["\']https?://',f.read_text()))
    def test_no_long_dashes_in_new_source(self):
        for f in ROOT.rglob('*'):
            if f.suffix in ('.md','.html','.json') and not {'downloads','evidence'}.intersection(f.parts):
                self.assertNotRegex(f.read_text(),'[\u2013\u2014]',str(f))
    def test_archive_manifest_and_links(self):
        archive=ROOT/'downloads/AI-KOMANDA-N6.zip'
        if not archive.exists(): self.skipTest('Архив ещё не собран')
        with zipfile.ZipFile(archive) as z:
            names=set(z.namelist()); self.assertIsNone(z.testzip())
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
