"""Ende-zu-Ende über die echten Befehle (ADR 003, Stufe 1, Schritt 6).

Erweiterung -> (Ereignis in der Inbox) -> `polaris process` (Bridge) ->
raw/ im Projektordner -> `polaris-curator run` mit Fake-Modell
(runtime: command) -> knowledge.md. Eigenes Wegwerf-HOME je Test, kein Netz.
Dazu der Störfall „Projektordner weg“ (Cloud-Laufwerk nicht eingehängt):
nichts darf angelegt werden, nach der Rückkehr läuft alles weiter.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POLARIS = REPO / "bridge" / "bin" / "polaris"
CURATOR = REPO / "curator" / "bin" / "polaris-curator"
EVENT = json.loads((REPO / "tests" / "contracts" / "bridge-event-chatgpt.json").read_text(encoding="utf-8"))
FACT = "Angebot Musterfirma bis Freitag prüfen (E2E-Testeintrag)."

# Gueltiges Aenderungsobjekt aus der Curator-Testhilfe (gleiches Schema), in
# einem eigenen Prozess: die Curator-Tests haben gleichnamige Module
# (conftest_helpers, test_storage_mtime), die diese Suite nicht sehen darf.
_GEN = ("import json, sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]\n"
        "from conftest_helpers import make_change\n"
        "print(json.dumps(make_change(knowledge_updates=[{'section': 'Aktueller Status', 'content': sys.argv[3]}])))")
CHANGE = json.loads(subprocess.run(
    [sys.executable, "-c", _GEN, str(REPO / "curator"), str(REPO / "curator" / "tests"), FACT],
    capture_output=True, text=True, check=True, timeout=60).stdout)

FAKE_MODEL = f"""#!{sys.executable}
import sys, json
sys.stdin.read()
print({json.dumps(CHANGE)!r})
"""


class TestEndToEnd(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="polaris-e2e-"))
        self.addCleanup(shutil.rmtree, self.home, True)
        self.root = self.home / "Projekte"
        self.project = self.root / EVENT["project"]["name"]
        self.project.mkdir(parents=True)
        cfg_dir = self.home / ".config" / "polaris"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.yaml").write_text(f"project_roots:\n  - {self.root}\n", encoding="utf-8")
        fake = self.home / "fake-model"
        fake.write_text(FAKE_MODEL, encoding="utf-8")
        fake.chmod(0o755)
        (cfg_dir / "curator.yaml").write_text(
            "runtime: command\nmodel: fake\nfallback_model: null\n"
            f"command: [\"{fake}\"]\nmonitoring:\n  chat_sources: [chatgpt]\n", encoding="utf-8")
        self.env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "LANG": "C.UTF-8", "POLARIS_NO_NOTIFY": "1", "POLARIS_USAGE_OFF": "1",
                    "POLARIS_HEALTH_NO_CACHE": "1", "POLARIS_LANG": "de",
                    # Fake-Modell bewusst ohne bubblewrap (in der Sandbox laeuft es in test_sandbox)
                    "POLARIS_NO_SANDBOX": "1", "TMPDIR": str(self.home)}

    def run_cli(self, *argv):
        return subprocess.run([str(a) for a in argv], env=self.env, capture_output=True, text=True, timeout=120)

    def capture(self):
        inbox = self.home / "Downloads" / "polaris-inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / "event.json").write_text(json.dumps(EVENT), encoding="utf-8")
        r = self.run_cli(POLARIS, "process")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_capture_to_curated_knowledge(self):
        self.capture()
        raw = self.project / "raw" / "chatgpt" / "messages" / f"{EVENT['message']['id']}.json"
        self.assertTrue(raw.is_file(), "Bridge hat nichts abgelegt")
        r = self.run_cli(CURATOR, "run", self.project.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        knowledge = (self.project / "knowledge.md").read_text(encoding="utf-8")
        self.assertIn(FACT, knowledge)
        # zweiter Lauf: nichts Neues, nichts doppelt
        r = self.run_cli(CURATOR, "run", self.project.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.project / "knowledge.md").read_text(encoding="utf-8").count(FACT), 1)

    def test_missing_project_folder_creates_nothing_and_recovers(self):
        self.capture()
        away = self.home / "weg"
        self.project.rename(away)                       # Laufwerk nicht eingehaengt
        r = self.run_cli(CURATOR, "run", self.project.name)
        self.assertNotEqual(r.returncode, 0, "Lauf ohne Projektordner darf nicht als Erfolg gelten")
        self.assertFalse(self.project.exists(), "Curator hat unter dem fehlenden Ordner etwas angelegt")
        away.rename(self.project)                       # Laufwerk wieder da
        r = self.run_cli(CURATOR, "run", self.project.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(FACT, (self.project / "knowledge.md").read_text(encoding="utf-8"))



def _bwrap_usable() -> bool:
    try:
        return subprocess.run(["bwrap", "--ro-bind", "/", "/", "--", "/usr/bin/true"],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@unittest.skipUnless(_bwrap_usable(), "bubblewrap nicht nutzbar")
class TestEndToEndInSandbox(TestEndToEnd):
    """Dieselbe Kette mit echter Sandbox (Gutachten agy 2026-11-07: die
    Integrationskette lief bisher nur mit POLARIS_NO_SANDBOX=1)."""

    def setUp(self):
        super().setUp()
        self.env.pop("POLARIS_NO_SANDBOX")


if __name__ == "__main__":
    unittest.main()
