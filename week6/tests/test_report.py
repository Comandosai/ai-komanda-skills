from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import base64


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


class Slides(HTMLParser):
    def __init__(self):
        super().__init__()
        self.slides = 0

    def handle_starttag(self, tag, attrs):
        if tag == "section" and "slide" in dict(attrs).get("class", "").split():
            self.slides += 1

class Week6Report(unittest.TestCase):
    def test_skill_routes_week_6_to_one_two_file_run(self):
        skill = (REPO / "otchet/SKILL.md").read_text()
        ref = (REPO / "otchet/references/nedelya-6.md").read_text()
        flat = (REPO / "chatgpt/otchet.txt").read_text()
        self.assertIn("references/nedelya-6.md", skill)
        self.assertIn("OTCHET-N6.md", ref)
        self.assertIn("PREZENTACIYA-HAKATON.html", ref)
        self.assertIn("# Вложенная инструкция: references/nedelya-6.md", flat)
        self.assertIn("Один запуск навыка создаёт два результата", flat)

    def test_template_is_the_approved_light_deck(self):
        path = ROOT / "assets/shablon-hakatona.html"
        text = path.read_text()
        parser = Slides()
        parser.feed(text)
        self.assertEqual(parser.slides, 9)
        self.assertNotRegex(text, r'<(?:script|img|link|iframe)\b[^>]*(?:src|href)=["\']https?://')
        self.assertIn("--bg:#F4EFE3", text)
        self.assertIn("Молочный благородный", text)
        self.assertIn("Режим выступления", text)
        self.assertIn('id="btnBefore"', text)
        self.assertIn('class="brand-logo"', text)
        self.assertIn('src="comandos-logo.png"', text)
        self.assertIn("WEEK6_DATA_START", text)
        self.assertIn("WEEK6_DATA_END", text)
        logo = ROOT / "assets/comandos-logo.png"
        self.assertTrue(logo.is_file())
        self.assertGreater(logo.stat().st_size, 1000)

    def test_demo_is_explicitly_simulated_and_consistent(self):
        report = (ROOT / "demo/final-report/OTCHET-N6.md").read_text()
        deck = ROOT / "demo/final-report/PREZENTACIYA-HAKATON.html"
        data = json.loads((ROOT / "demo/final-report/dannye-prezentacii.json").read_text())
        parser = Slides()
        parser.feed(deck.read_text())
        self.assertEqual(parser.slides, 9)
        self.assertIn("said, смоделировано", report)
        self.assertIn("не являются\n> ответами Дмитрия", report)
        self.assertIn("35 часов в месяц", report)
        self.assertEqual(data["org"], "Гранит-Сервис")
        self.assertEqual(data["hoursFreed"], 35)
        self.assertEqual(len(data["roles"]), 3)
        self.assertEqual(len(data["steps"]), 7)

    def test_renderer_replaces_only_data_and_escapes_script_breakout(self):
        template = ROOT / "assets/shablon-hakatona.html"
        data = json.loads((ROOT / "demo/final-report/dannye-prezentacii.json").read_text())
        data["heroTitle"] = '<img src=x onerror="window.pwned=1">'
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "data.json"
            out = Path(tmp) / "deck.html"
            src.write_text(json.dumps(data, ensure_ascii=False))
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/render_hackathon.py"),
                 "--template", str(template), "--data", str(src), "--output", str(out)],
                check=True,
            )
            rendered = out.read_text()
        self.assertIn(r"\u003cimg", rendered)
        self.assertNotIn('<img src=x onerror="window.pwned=1">', rendered)
        self.assertEqual(rendered.count("WEEK6_DATA_START"), 1)
        expected_logo = base64.b64encode((ROOT / "assets/comandos-logo.png").read_bytes()).decode("ascii")
        self.assertIn(f'data:image/png;base64,{expected_logo}', rendered)
        self.assertNotIn('src="comandos-logo.png"', rendered)


if __name__ == "__main__":
    unittest.main()
