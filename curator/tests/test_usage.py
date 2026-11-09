"""Tests fuer polaris_curator/usage.py (Nutzungszaehler, seit 2026-11-05)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401 - setzt POLARIS_USAGE_OFF
from polaris_curator import usage


class TestUsage(unittest.TestCase):
    def test_counts_names_only_and_is_off_in_tests(self):
        home = Path(tempfile.mkdtemp())
        with patch.object(Path, "home", return_value=home):
            usage.count("x")
            self.assertFalse(usage.path().exists())  # in Tests abgeschaltet
            with patch.dict(os.environ, {"POLARIS_USAGE_OFF": ""}):
                usage.count("cli:run")
                usage.count("cli:run")
                usage.path().write_text(usage.path().read_text())  # bleibt lesbar
                d = json.loads(usage.path().read_text())
                self.assertEqual(d["cli:run"]["count"], 2)
                self.assertEqual(set(d["cli:run"]), {"count", "first", "last"})
                usage.path().write_text("kaputt")
                usage.count("y")  # darf nicht werfen, faengt neu an
                self.assertEqual(json.loads(usage.path().read_text())["y"]["count"], 1)

    def test_mark_counts_once_per_process(self):
        home = Path(tempfile.mkdtemp())
        with patch.object(Path, "home", return_value=home), \
                patch.dict(os.environ, {"POLARIS_USAGE_OFF": ""}), \
                patch.object(usage, "_MARKED", set()):
            for _ in range(5):
                usage.mark("doc:.pdf")
            self.assertEqual(json.loads(usage.path().read_text())["doc:.pdf"]["count"], 1)

    def test_parallel_processes_lose_no_counts(self):
        # Bridge, Curator und Widget zaehlen gleichzeitig (Dateisperre seit ADR 003).
        import subprocess
        import sys
        home = tempfile.mkdtemp()
        env = {**os.environ, "HOME": home, "POLARIS_USAGE_OFF": "",
               "PYTHONPATH": str(Path(usage.__file__).resolve().parents[1])}
        code = "from polaris_curator import usage\nfor _ in range(25): usage.count('p')"
        procs = [subprocess.Popen([sys.executable, "-c", code], env=env) for _ in range(6)]
        for pr in procs:
            pr.wait(timeout=60)
        d = json.loads((Path(home) / ".local/state/polaris/usage.json").read_text())
        self.assertEqual(d["p"]["count"], 150)

    def test_widget_calls_are_counted_separately(self):
        import subprocess
        import sys
        home = tempfile.mkdtemp()
        env = {**os.environ, "HOME": home, "POLARIS_USAGE_OFF": "", "POLARIS_USAGE_VIA": "widget",
               "PYTHONPATH": str(Path(usage.__file__).resolve().parents[1])}
        subprocess.run([sys.executable, "-m", "polaris_curator.cli", "quarantine", "list"],
                       env=env, capture_output=True, timeout=60)
        subprocess.run([sys.executable, "-m", "polaris_curator.usage", "widget:open:knowledge"],
                       env=env, capture_output=True, timeout=60)
        d = json.loads((Path(home) / ".local/state/polaris/usage.json").read_text())
        self.assertIn("widget:open:knowledge", d)
        self.assertIn("widget:cli:quarantine", d)
        self.assertNotIn("cli:quarantine", d)

    def test_days_counts_once_per_day_and_writes_only_on_change(self):
        home = Path(tempfile.mkdtemp())
        with patch.object(Path, "home", return_value=home), \
                patch.dict(os.environ, {"POLARIS_USAGE_OFF": ""}):
            usage.days(["health:day", "health-warn:backup"])
            mtime = usage.path().stat().st_mtime_ns
            usage.days(["health:day", "health-warn:backup"])
            self.assertEqual(usage.path().stat().st_mtime_ns, mtime)  # nichts Neues, nicht geschrieben
            d = json.loads(usage.path().read_text())
            self.assertEqual(d["health-warn:backup"]["count"], 1)
            with patch.object(usage.time, "strftime", return_value="2099-01-01"):
                usage.days(["health:day"])
            d = json.loads(usage.path().read_text())
            self.assertEqual(d["health:day"]["count"], 2)
            self.assertEqual(d["health-warn:backup"]["count"], 1)

    def test_health_records_alarm_days_by_id_only(self):
        from polaris_curator import systemhealth as sh
        home = Path(tempfile.mkdtemp())
        with patch.object(Path, "home", return_value=home), \
                patch.dict(os.environ, {"POLARIS_USAGE_OFF": ""}):
            sh._count_alarm_days([{"id": "backup", "level": "warn", "detail": "geheim/pfad"},
                                  {"id": "llm", "level": "ok"}, {"id": "disk", "level": "error"}])
            text = usage.path().read_text()
            self.assertEqual(set(json.loads(text)), {"health:day", "health-warn:backup", "health-error:disk"})
            self.assertNotIn("geheim", text)


if __name__ == "__main__":
    unittest.main()
