import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from simulator import run


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = {"id": "fiction", "topic": "Example"}

    def test_one_two_three_roles(self):
        for roles in (1, 2, 3):
            summary = run(self.root / str(roles), self.case, "a", roles)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(len(summary["outputs"]), roles)
            for item in summary["outputs"]:
                target = self.root / str(roles) / "a"
                digest = hashlib.sha256((target / item["result"]).read_bytes()).hexdigest()
                self.assertEqual(json.loads((target / item["check"]).read_text())["result_hash"], digest)

    def test_missing_input(self):
        result = run(self.root, {}, "a")
        self.assertEqual(result["status"], "missing_input")
        self.assertEqual(result["outputs"], [])

    def test_approval_required(self):
        case = dict(self.case, approval_required=True)
        self.assertEqual(run(self.root, case, "waiting")["status"], "waiting_approval")
        accepted = run(self.root, case, "accepted", approved=True)
        self.assertTrue(accepted["manual_approval"])
        self.assertEqual(accepted["status"], "complete")
        self.assertEqual(run(self.root, case, "changed", revision=2)["status"], "waiting_approval")

    def test_duplicate_and_immutable_attempt(self):
        run(self.root, self.case, "a")
        before = (self.root / "a" / "summary.json").read_bytes()
        self.assertEqual(run(self.root, self.case, "b")["status"], "duplicate")
        with self.assertRaises(FileExistsError):
            run(self.root, self.case, "a")
        self.assertEqual(before, (self.root / "a" / "summary.json").read_bytes())

    def test_unavailable(self):
        self.assertEqual(run(self.root, self.case, "a", unavailable=True)["status"], "unavailable")

    def test_correction_regenerates_dependent_results(self):
        first = run(self.root, self.case, "before", roles=3)
        second = run(self.root, self.case, "after", roles=3, revision=2)
        for old, new in zip(first["outputs"], second["outputs"]):
            self.assertNotEqual(old["hash"], new["hash"])
        for i in (2, 3):
            current = json.loads((self.root / "after" / f"role-{i}-result.json").read_text())
            self.assertEqual(current["source_hash"], second["outputs"][i - 2]["hash"])

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            run(self.root, self.case, "../escape")

    def test_three_distinct_final_inputs(self):
        cases = Path(__file__).parent / "cases"
        fingerprints = set()
        for index in (1, 2, 3):
            case = json.loads((cases / f"final-{index}.json").read_text())
            summary = run(self.root, case, f"final-{index}", roles=3)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["external_actions"], 0)
            fingerprints.add(summary["input_hash"])
        self.assertEqual(len(fingerprints), 3)


if __name__ == "__main__":
    unittest.main()
