import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "mwg-guide-reach")


def run(*args, cwd=ROOT):
    return subprocess.run(
        [sys.executable, CLI, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class CleanCorpusTests(unittest.TestCase):
    def test_clean_exit_zero(self):
        proc = run("examples/in/clean")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_clean_json_summary(self):
        proc = run("examples/in/clean", "--json")
        report = json.loads(proc.stdout)
        self.assertEqual(report["summary"]["guide_md_total"], 3)
        self.assertEqual(report["summary"]["reachable"], 3)
        self.assertEqual(report["summary"]["unreachable"], 0)
        self.assertEqual(report["summary"]["errors"], 0)

    def test_clean_matches_expected_output(self):
        proc = run("examples/in/clean", "--json")
        with open(os.path.join(ROOT, "examples/out/clean.json"), encoding="utf-8") as fh:
            expected = json.load(fh)
        self.assertEqual(json.loads(proc.stdout), expected)


class BrokenCorpusTests(unittest.TestCase):
    def setUp(self):
        proc = run("examples/in/broken", "--json")
        self.report = json.loads(proc.stdout)
        self.proc = proc

    def test_broken_exit_one(self):
        self.assertEqual(self.proc.returncode, 1)

    def test_counts(self):
        summary = self.report["summary"]
        self.assertEqual(summary["guide_md_total"], 6)
        self.assertEqual(summary["reachable"], 5)
        self.assertEqual(summary["unreachable"], 1)
        self.assertEqual(summary["errors"], 3)
        self.assertEqual(summary["warnings"], 3)

    def test_unreachable_witness_is_the_nested_guide(self):
        hits = [f for f in self.report["findings"] if f["rule"] == "UNREACHABLE_GUIDE"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(
            hits[0]["path"],
            "guides/performance/lazy-image/variant/guide.md",
        )
        self.assertIn("depth is 2", hits[0]["detail"])

    def test_duplicate_id_points_at_the_invisible_copy(self):
        hits = [f for f in self.report["findings"] if f["rule"] == "DUPLICATE_GUIDE_ID"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["path"], "guides/performance/lazy-image/guide.md")
        self.assertEqual(
            hits[0]["witness"],
            "guides/performance/lazy-image/variant/guide.md",
        )
        self.assertIn("'lazy-image'", hits[0]["detail"])

    def test_stub_demo_rule(self):
        hits = [f for f in self.report["findings"] if f["rule"] == "STUB_DEMO"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["path"], "guides/css/empty-demo/guide.md")

    def test_stub_expectations_is_a_warning(self):
        hits = [f for f in self.report["findings"] if f["rule"] == "STUB_EXPECTATIONS"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "warning")

    def test_id_dir_mismatch_found_twice(self):
        hits = [f for f in self.report["findings"] if f["rule"] == "ID_DIR_MISMATCH"]
        self.assertEqual(len(hits), 2)

    def test_fail_on_warning_still_exits_one(self):
        proc = run("examples/in/broken", "--fail-on", "warning")
        self.assertEqual(proc.returncode, 1)

    def test_broken_matches_expected_output(self):
        with open(os.path.join(ROOT, "examples/out/broken.json"), encoding="utf-8") as fh:
            expected = json.load(fh)
        self.assertEqual(self.report, expected)


class CliContractTests(unittest.TestCase):
    def test_missing_root_is_usage_error(self):
        proc = run("/tmp/definitely-not-a-guide-repo")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no guides/ directory", proc.stderr)

    def test_missing_argument_is_usage_error(self):
        proc = run()
        self.assertEqual(proc.returncode, 2)

    def test_text_output_has_summary_and_findings(self):
        proc = run("examples/in/broken")
        self.assertIn("guide.md: 6 total, 5 reachable, 1 unreachable", proc.stdout)
        self.assertIn("ERROR UNREACHABLE_GUIDE", proc.stdout)
        self.assertIn("3 error(s), 3 warning(s)", proc.stdout)

    def test_output_is_deterministic(self):
        first = run("examples/in/broken", "--json").stdout
        second = run("examples/in/broken", "--json").stdout
        self.assertEqual(first, second)

    def test_targets_directory_makes_a_todo_demo_acceptable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "guides", "css", "with-targets")
            os.makedirs(os.path.join(base, "targets", "daily-grind"))
            with open(os.path.join(base, "guide.md"), "w", encoding="utf-8") as fh:
                fh.write("---\nname: with-targets\n---\n")
            with open(os.path.join(base, "demo.html"), "w", encoding="utf-8") as fh:
                fh.write("<!-- TODO -->\n")
            with open(os.path.join(base, "expectations.md"), "w", encoding="utf-8") as fh:
                fh.write("- ok\n")
            proc = run(tmp, "--json")
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertEqual(json.loads(proc.stdout)["summary"]["errors"], 0)

    def test_quoted_frontmatter_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.join(tmp, "guides", "css", "quoted-id")
            os.makedirs(base)
            with open(os.path.join(base, "guide.md"), "w", encoding="utf-8") as fh:
                fh.write("---\nname: \"quoted-id\"\n---\n")
            with open(os.path.join(base, "demo.html"), "w", encoding="utf-8") as fh:
                fh.write("<p>ok</p>\n")
            proc = run(tmp, "--json")
            report = json.loads(proc.stdout)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(report["summary"]["by_rule"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
