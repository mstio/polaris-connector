"""Private Polaris-Ordner nur fuer den eigenen Benutzer (0700) und Widget-Cache
nur lesbar fuer ihn (0600). Nach dem Hinweis von HANCORE-linux im
Omarchy-Plugin-Marktplatz (#13877, 2026-11-08): Statuswarnungen mit Chat-Titeln
lagen mit umask 022 lesbar im State-Ordner."""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import conftest_helpers  # noqa: F401  (HOME umbiegen, bevor polaris importiert wird)
from conftest_helpers import TempHome

REPO = Path(__file__).resolve().parents[1]
STATUS_JSON = REPO / "omarchy-plugin" / "mst.polaris-curator" / "bin" / "status-json"


def mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


class BridgeDirsTest(unittest.TestCase):
    def test_ensure_dirs_tightens_existing_and_new_dirs(self):
        with TempHome() as _:
            from polaris import config
            config.STATE_DIR.mkdir(parents=True, exist_ok=True)
            config.STATE_DIR.chmod(0o755)            # bestehende Installation
            config.ensure_dirs()
            for d in config.private_dirs():
                self.assertEqual(mode(d), 0o700, d)


class WidgetCacheTest(unittest.TestCase):
    def test_status_json_writes_private_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stub = base / "bin"
            stub.mkdir()
            (stub / "polaris-curator").write_text(
                '#!/bin/sh\n'
                'case "$1" in status-all) echo \'{"projects":[],"summary":{"warnings":["Titel geheim"]}}\';;\n'
                '  health) echo \'{"level":"ok","components":[],"system":[]}\';; esac\n')
            (stub / "systemctl").write_text("#!/bin/sh\nexit 1\n")
            for f in stub.iterdir():
                f.chmod(0o755)
            state = base / "state"
            (state / "polaris").mkdir(parents=True)
            (state / "polaris").chmod(0o755)          # vorhandener, zu offener Ordner
            env = {"HOME": str(base), "XDG_STATE_HOME": str(state), "PATH": f"{stub}:/usr/bin:/bin"}
            r = subprocess.run(["bash", "-c", f'umask 022; exec "{STATUS_JSON}"'], env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Titel geheim", r.stdout)
            cache = state / "polaris" / "widget-status.json"
            self.assertIn("Titel geheim", cache.read_text())
            self.assertEqual(mode(cache), 0o600)
            self.assertEqual(mode(state / "polaris"), 0o700)
            self.assertEqual([p.name for p in (state / "polaris").iterdir()], ["widget-status.json"])

    def test_early_returns_repair_legacy_cache(self):
        """Marktplatz #13877, HANCORE-linux 2026-11-10: gesperrt, CLI fehlt oder Status
        fehlgeschlagen - auch dann darf ein alter, lesbarer Cache nicht offen bleiben."""
        cases = {
            "gesperrt": {"polaris-awake": "#!/bin/sh\nexit 1\n"},
            "ohne-cli": {},
            "status-fehler": {"polaris-curator": "#!/bin/sh\nexit 3\n"},
        }
        for name, stubs in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                stub = base / "bin"
                stub.mkdir()
                for fname, body in {**stubs, "systemctl": "#!/bin/sh\nexit 1\n"}.items():
                    (stub / fname).write_text(body)
                    (stub / fname).chmod(0o755)
                state = base / "state" / "polaris"
                state.mkdir(parents=True)
                cache = state / "widget-status.json"
                cache.write_text('{"summary":{"warnings":["alter Titel"]}}\n')
                tmpfile = state / "widget-status.json.tmp"  # Rest vor 0.3.3
                tmpfile.write_text("alter Titel\n")
                state.chmod(0o755)
                cache.chmod(0o644)                    # Altbestand vor 0.3.3
                tmpfile.chmod(0o644)
                env = {"HOME": str(base), "XDG_STATE_HOME": str(base / "state"),
                       "PATH": f"{stub}:/usr/bin:/bin"}
                r = subprocess.run([str(STATUS_JSON)], env=env, capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(mode(state), 0o700, name)
                self.assertEqual(mode(cache), 0o600, name)
                self.assertEqual(mode(tmpfile), 0o600, name)

    def test_symlinked_cache_is_not_followed(self):
        """chmod darf keinem Symlink folgen (Zweitpruefung 2026-11-10)."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stub = base / "bin"
            stub.mkdir()
            (stub / "polaris-awake").write_text("#!/bin/sh\nexit 1\n")
            (stub / "polaris-awake").chmod(0o755)
            target = base / "fremdes-ziel"
            target.write_text("x\n")
            target.chmod(0o644)
            state = base / "state" / "polaris"
            state.mkdir(parents=True)
            (state / "widget-status.json").symlink_to(target)
            env = {"HOME": str(base), "XDG_STATE_HOME": str(base / "state"), "PATH": f"{stub}:/usr/bin:/bin"}
            r = subprocess.run([str(STATUS_JSON)], env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(mode(target), 0o644)
            self.assertEqual(mode(state), 0o700)


if __name__ == "__main__":
    unittest.main()
