from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


class Slides(HTMLParser):
    def __init__(self):
        super().__init__()
        self.slides = 0

    def handle_starttag(self, tag, attrs):
        if tag == "section" and "slide" in dict(attrs).get("class", "").split():
            self.slides += 1


def deck_data(path):
    text = path.read_text()
    match = re.search(
        r'<script id="dannye" type="application/json">\s*(.*?)\s*</script>',
        text,
        re.S,
    )
    if not match:
        raise AssertionError(f"No JSON data block in {path}")
    return json.loads(match.group(1))


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

    def test_template_has_nine_offline_safe_screens(self):
        path = ROOT / "assets/shablon-hakatona.html"
        text = path.read_text()
        parser = Slides()
        parser.feed(text)
        self.assertEqual(parser.slides, 9)
        self.assertNotIn("innerHTML", text)
        self.assertNotRegex(text, r'<(?:script|img|link|iframe)\b[^>]*(?:src|href)=["\']https?://')
        self.assertIn("textContent", text)
        data = deck_data(path)
        self.assertIsNone(data["money"]["rate"])
        self.assertIsNone(data["pipeline"]["runTime"])

    def test_demo_is_explicitly_simulated_and_consistent(self):
        report = (ROOT / "demo/final-report/OTCHET-N6.md").read_text()
        deck = ROOT / "demo/final-report/PREZENTACIYA-HAKATON.html"
        parser = Slides()
        parser.feed(deck.read_text())
        data = deck_data(deck)
        self.assertEqual(parser.slides, 9)
        self.assertIn("said, смоделировано", report)
        self.assertIn("не являются ответами\n> Дмитрия", report)
        self.assertIn("9,2 часа в месяц", report)
        self.assertEqual(data["money"]["hoursFreed"]["v"], "9,2 ч/мес")
        self.assertEqual(data["money"]["hoursFreed"]["src"], "fore")
        self.assertEqual(data["hero"]["facts"][1]["v"], "0 из 3")
        self.assertIsNone(data["money"]["rate"])
        self.assertIsNone(data["money"]["potential"])
        self.assertIn("смоделированы", data["hero"]["lede"])


if __name__ == "__main__":
    unittest.main()
