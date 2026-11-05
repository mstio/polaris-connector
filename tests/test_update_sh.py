"""update.sh: Zustand fuer den Health-Check vor dessen Aufruf (seit 2026-11-05).

Rueckmeldung von bernhard2804: Der Health-Check im selben Update-Lauf meldete
noch "Update verfuegbar", weil update-check.json erst danach geschrieben wurde.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Eigene git-Einstellungen des Testrechners (Signieren, Hooks) heraushalten.
GITENV = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=GITENV)


class TestUpdateState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="polaris-update-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        up, work = self.tmp / "up.git", self.tmp / "work"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(up)], check=True, env=GITENV)
        subprocess.run(["git", "init", "-q", "-b", "main", str(work)], check=True, env=GITENV)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid")):
            git(work, "config", k, v)
        (work / "extension").mkdir()
        (work / "extension" / "manifest.json").write_text('{"version": "1.0"}')
        shutil.copy(REPO / "update.sh", work / "update.sh")
        git(work, "add", "-A")
        git(work, "commit", "-q", "-m", "a")
        git(work, "remote", "add", "origin", str(up))
        git(work, "push", "-q", "-u", "origin", "main")
        # zweiter Stand nur im Upstream
        other = self.tmp / "other"
        subprocess.run(["git", "clone", "-q", str(up), str(other)], check=True, env=GITENV)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid")):
            git(other, "config", k, v)
        (other / "neu.txt").write_text("x")
        git(other, "add", "-A")
        git(other, "commit", "-q", "-m", "b")
        git(other, "push", "-q")
        self.work = work

    def run_update(self, health_body: str):
        self.seen = self.tmp / "seen.txt"
        self.state = self.home / ".local/state/polaris/update-check.json"
        health = self.tmp / "health.sh"
        health.write_text(f"#!/bin/sh\ncat '{self.state}' >> '{self.seen}' 2>/dev/null; echo >> '{self.seen}'\n"
                          + health_body)
        health.chmod(0o755)
        env = {**GITENV, "HOME": str(self.home), "POLARIS_UPDATE_INSTALL": "true",
               "POLARIS_UPDATE_HEALTH": str(health)}
        return subprocess.run(["bash", str(self.work / "update.sh"), "--yes"], env=env,
                              capture_output=True, text=True)

    def test_health_sees_state_after_update(self):
        r = self.run_update("echo '{\"level\": \"ok\"}'\n")
        seen = self.seen
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = [l for l in seen.read_text().splitlines() if l.strip()]
        # vor dem Update: behind 1; Health-Check danach: behind 0
        self.assertEqual(json.loads(lines[0])["behind"], 1)
        self.assertEqual(json.loads(lines[-1])["behind"], 0)

    def test_rollback_restores_behind_state(self):
        # Health wird nach dem Update rot -> Rueckweg; Zustand nennt wieder den Rueckstand.
        r = self.run_update(f"[ -e '{self.work}/neu.txt' ] && echo '{{\"level\": \"error\"}}' "
                            "|| echo '{\"level\": \"ok\"}'\n")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse((self.work / "neu.txt").exists())
        self.assertEqual(json.loads(self.state.read_text())["behind"], 1)


if __name__ == "__main__":
    unittest.main()
