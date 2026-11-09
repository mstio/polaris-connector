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

    def run_update(self, health_body: str, install: str = "true", active: str = ""):
        self.seen = self.tmp / "seen.txt"
        self.state = self.home / ".local/state/polaris/update-check.json"
        health = self.tmp / "health.sh"
        health.write_text(f"#!/bin/sh\ncat '{self.state}' >> '{self.seen}' 2>/dev/null; echo >> '{self.seen}'\n"
                          + health_body)
        health.chmod(0o755)
        # systemctl-Ersatz: "is-active" ist wahr nur fuer die genannten Units.
        sysctl = self.tmp / "systemctl.sh"
        sysctl.write_text("#!/bin/sh\nfor a in \"$@\"; do case \" " + active + " \" in *\" $a \"*) exit 0 ;; esac; done\nexit 3\n")
        sysctl.chmod(0o755)
        env = {**GITENV, "HOME": str(self.home), "POLARIS_UPDATE_INSTALL": install,
               "POLARIS_UPDATE_HEALTH": str(health), "POLARIS_UPDATE_SYSTEMCTL": str(sysctl)}
        return subprocess.run(["bash", str(self.work / "update.sh"), "--yes"], env=env,
                              capture_output=True, text=True)

    @staticmethod
    def health_json(*errors: str) -> str:
        checks = [{"id": "base", "level": "ok"}] + [{"id": e, "level": "error"} for e in errors]
        return json.dumps({"level": "error" if errors else "ok", "checks": checks})

    def health_switch(self, before: tuple, after: tuple) -> str:
        """Health-Skript: vor dem Update `before`-Fehler, danach `after`-Fehler."""
        return (f"[ -e '{self.work}/neu.txt' ] && echo '{self.health_json(*after)}' "
                f"|| echo '{self.health_json(*before)}'\n")

    def test_new_error_on_already_broken_install_rolls_back(self):
        # vorher schon rot (a), danach zusaetzlich b -> zurueck (frueher: kein Rueckweg)
        r = self.run_update(self.health_switch(("a",), ("a", "b")))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse((self.work / "neu.txt").exists())
        self.assertIn("b", r.stderr)

    def test_same_errors_before_and_after_keep_update(self):
        r = self.run_update(self.health_switch(("a",), ("a",)))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.work / "neu.txt").exists())

    def test_unreadable_health_before_and_after_warns(self):
        # Gremium Codex 2026-11-09: vorher wie nachher unlesbar ist kein neuer
        # Fehler (Update bleibt), darf aber nicht still als geprueft gelten.
        r = self.run_update("echo kaputt\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("nicht lesbar", r.stderr)

    def test_readable_health_gives_no_unreadable_warning(self):
        r = self.run_update(self.health_switch((), ()))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("nicht lesbar", r.stderr)

    def test_failing_install_rolls_back_and_logs(self):
        r = self.run_update(self.health_switch((), ()), install="false")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse((self.work / "neu.txt").exists())
        logs = list((self.home / ".local/state/polaris").glob("update-*.log"))
        self.assertTrue(logs, "Rueckweg ohne Protokoll")

    def test_update_works_in_a_git_worktree(self):
        # Live-Stand als worktree (ADR 003): .git ist dort eine Datei.
        live = self.tmp / "live"
        git(self.work, "worktree", "add", "-q", "-b", "live", str(live), "main")
        git(live, "branch", "-q", "--set-upstream-to", "origin/main")
        shutil.copy(self.work / "update.sh", live / "update.sh")
        self.work = live
        r = self.run_update(self.health_switch((), ()))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((live / "neu.txt").exists())

    def test_dev_checkout_refuses_when_live_is_a_worktree(self):
        app = self.home / ".local/share/polaris/app"
        app.parent.mkdir(parents=True)
        git(self.work, "worktree", "add", "-q", "-b", "live", str(app), "main")
        r = self.run_update(self.health_switch((), ()))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("worktree", r.stderr)
        self.assertFalse((self.work / "neu.txt").exists())

    def _extras_repo(self):
        """omarchy-backup als Extra mit einem neuen Commit im Upstream."""
        up = self.tmp / "ob-up.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(up)], check=True, env=GITENV)
        seed = self.tmp / "ob-seed"
        subprocess.run(["git", "clone", "-q", str(up), str(seed)], check=True, env=GITENV)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid")):
            git(seed, "config", k, v)
        (seed / "a").write_text("1"); git(seed, "add", "-A"); git(seed, "commit", "-q", "-m", "a")
        git(seed, "push", "-q", "origin", "HEAD:main")
        ob = self.home / ".local/share/polaris/extras/omarchy-backup"
        ob.parent.mkdir(parents=True)
        subprocess.run(["git", "clone", "-q", str(up), str(ob)], check=True, env=GITENV)
        (seed / "b").write_text("2"); git(seed, "add", "-A"); git(seed, "commit", "-q", "-m", "fremd")
        git(seed, "push", "-q", "origin", "HEAD:main")
        return ob

    def test_extras_are_shown_not_pulled_with_yes(self):
        # Gutachten Codex 2026-11-07: Fremdcode der Extras nicht ungesehen ziehen.
        ob = self._extras_repo()
        r = self.run_update(self.health_switch((), ()))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("fremd", r.stdout)                       # angezeigt
        self.assertFalse((ob / "b").exists())                   # nicht gezogen
        self.assertIn("POLARIS_UPDATE_EXTRAS=1", r.stdout)

    def test_no_switch_while_a_polaris_service_runs(self):
        r = self.run_update(self.health_switch((), ()), active="polaris-curator.service")
        self.assertEqual(r.returncode, 75, r.stdout + r.stderr)
        self.assertFalse((self.work / "neu.txt").exists())
        self.assertIn("polaris-curator.service", r.stderr)

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
