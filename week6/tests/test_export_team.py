import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_team.py"
SPEC = importlib.util.spec_from_file_location("export_team", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class ExportTeamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "working-team"
        (self.source / "agenty").mkdir(parents=True)
        (self.source / "logs").mkdir()
        (self.source / ".git").mkdir()
        (self.source / ".bkit" / "state").mkdir(parents=True)
        (self.source / ".planning").mkdir()
        (self.source / "agenty" / "dispetcher.md").write_text(
            "Проект /Users/alex/Projects/team и ${PROJECT_DIR}.\n", encoding="utf-8"
        )
        (self.source / "run.py").write_text("print('ok')\n", encoding="utf-8")
        (self.source / ".env").write_text("SERVICE_TOKEN=real-secret-value\n", encoding="utf-8")
        (self.source / ".env.example").write_text("SERVICE_TOKEN=CHANGE_ME\n", encoding="utf-8")
        (self.source / "logs" / "client.log").write_text("private history\n", encoding="utf-8")
        for folder in ("vhod", "vyhod", "originaly", "arhiv", "dashboard", ".board"):
            (self.source / folder).mkdir()
            (self.source / folder / "customer.txt").write_text("private client data\n", encoding="utf-8")
        (self.source / ".git" / "config").write_text("history\n", encoding="utf-8")
        (self.source / ".bkit" / "state" / "memory.json").write_text("{}\n", encoding="utf-8")
        (self.source / ".planning" / "HANDOFF.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_copy_is_clean_and_source_is_unchanged(self):
        before = tree_snapshot(self.source)
        export_dir, archive = MODULE.export_team(
            self.source, self.root / "exports", "portable-team"
        )
        self.assertEqual(before, tree_snapshot(self.source))
        self.assertFalse((export_dir / ".git").exists())
        self.assertFalse((export_dir / ".bkit").exists())
        self.assertFalse((export_dir / ".planning").exists())
        self.assertFalse((export_dir / ".env").exists())
        self.assertTrue((export_dir / ".env.example").exists())
        self.assertFalse((export_dir / "logs" / "client.log").exists())
        self.assertTrue((export_dir / "logs" / "README.md").exists())
        for folder in ("vhod", "vyhod", "originaly", "arhiv", "dashboard", ".board"):
            self.assertFalse((export_dir / folder / "customer.txt").exists())
        self.assertTrue((export_dir / "ПРИНЯТЬ-КОМАНДУ.md").exists())
        dispatcher = (export_dir / "agenty" / "dispetcher.md").read_text(encoding="utf-8")
        self.assertIn("${HOME}/Projects/team", dispatcher)
        self.assertNotIn("/Users/alex", dispatcher)
        self.assertIsNotNone(archive)
        self.assertTrue(archive.exists())
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            self.assertFalse(any(name.endswith("/.env") or "/.git/" in name for name in names))
            self.assertTrue(any(name.endswith("/.env.example") for name in names))
        manifest = json.loads((export_dir / "MANIFEST.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["source_modified"])
        self.assertIn(".env", manifest["removed_from_copy"])

    def test_detects_embedded_secret_and_removes_failed_copy(self):
        (self.source / "bad.md").write_text(
            "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456\n", encoding="utf-8"
        )
        before = tree_snapshot(self.source)
        output = self.root / "exports"
        with self.assertRaises(MODULE.ExportError):
            MODULE.export_team(self.source, output, "must-fail")
        self.assertEqual(before, tree_snapshot(self.source))
        self.assertFalse((output / "must-fail").exists())
        self.assertFalse((output / "must-fail.zip").exists())

    def test_refuses_destination_inside_source(self):
        with self.assertRaises(MODULE.ExportError):
            MODULE.export_team(self.source, self.source / "exports", "nested")

    def test_custom_ignore_is_applied_only_to_copy(self):
        private = self.source / "client-data" / "customer.csv"
        private.parent.mkdir()
        private.write_text("name,email\nIvan,private@example.test\n", encoding="utf-8")
        ignore = self.source / ".ai-team-export-ignore"
        ignore.write_text("client-data\n", encoding="utf-8")
        before = tree_snapshot(self.source)
        export_dir, _ = MODULE.export_team(self.source, self.root / "exports", "without-client")
        self.assertEqual(before, tree_snapshot(self.source))
        self.assertFalse((export_dir / "client-data").exists())
        self.assertFalse((export_dir / ".ai-team-export-ignore").exists())

    def test_refuses_symlink(self):
        target = self.root / "outside.txt"
        target.write_text("outside\n", encoding="utf-8")
        link = self.source / "outside-link"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(MODULE.ExportError):
            MODULE.export_team(self.source, self.root / "exports", "no-links")


if __name__ == "__main__":
    unittest.main()
