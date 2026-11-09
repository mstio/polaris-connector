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


if __name__ == "__main__":
    unittest.main()
