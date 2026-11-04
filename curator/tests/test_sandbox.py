"""Sandbox fuer Fremdinhalte (Sicherheitspruefung 2026-11-04)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401

from polaris_curator import sandbox, systemhealth as sh


@unittest.skipUnless(sandbox.available(), "bubblewrap nicht nutzbar")
class TestSandboxIsolation(unittest.TestCase):
    def test_home_is_invisible(self):
        secret = Path.home() / ".config"
        r = subprocess.run(sandbox.wrap(["ls", str(secret)]), capture_output=True)
        self.assertNotEqual(r.returncode, 0)

    def test_only_granted_paths_are_visible(self):
        d = Path(tempfile.mkdtemp())
        (d / "in.txt").write_text("hallo", encoding="utf-8")
        r = subprocess.run(sandbox.wrap(["cat", str(d / "in.txt")], ro=[d]), capture_output=True, text=True)
        self.assertEqual(r.stdout, "hallo")
        r = subprocess.run(sandbox.wrap(["sh", "-c", f"echo x > {d}/out.txt"], ro=[d]), capture_output=True)
        self.assertNotEqual(r.returncode, 0, "ro-Freigabe darf nicht beschreibbar sein")

    def test_no_network_unless_granted(self):
        r = subprocess.run(sandbox.wrap(["sh", "-c", "cat /proc/net/dev | wc -l"]), capture_output=True, text=True)
        # Nur Loopback im eigenen Netz-Namensraum: Kopfzeilen + lo
        self.assertLessEqual(int(r.stdout.strip() or 0), 3)


@unittest.skipUnless(sandbox.available(), "bubblewrap nicht nutzbar")
class TestCommandRuntimeIsSandboxed(unittest.TestCase):
    def test_command_cli_cannot_see_home(self):
        from polaris_curator import config, llm
        probe = Path.home() / ".config"
        cmd = ["sh", "-c", f"if [ -e '{probe}' ]; then echo '{{\"seen\": true}}'; "
                           "else echo '{\"seen\": false}'; fi"]
        cfg = config.CuratorConfig(runtime="command", command=cmd)
        r = llm._run_command("x", "m", cfg, schema={"type": "object"})
        self.assertEqual(r.data, {"seen": False})

    def test_extra_paths_only_from_local_config(self):
        from polaris_curator import config
        cfg = config.CuratorConfig().merged_with({"command_sandbox_ro": ["~/.mycli"]})
        self.assertEqual(cfg.command_sandbox_ro, ["~/.mycli"])
        self.assertNotIn("command_sandbox_ro", config.PROJECT_OVERRIDE_KEYS)
        self.assertNotIn("command_sandbox_rw", config.PROJECT_OVERRIDE_KEYS)


class TestSandboxFallbackIsLoud(unittest.TestCase):
    def test_disabled_sandbox_is_reported(self):
        sandbox.available.cache_clear()
        try:
            with patch.dict(os.environ, {"POLARIS_NO_SANDBOX": "1"}):
                self.assertEqual(sandbox.wrap(["true"]), ["true"])
                self.assertIn("POLARIS_NO_SANDBOX", sandbox.status())
        finally:
            sandbox.available.cache_clear()

    def test_health_check_warns_without_sandbox(self):
        with patch.object(sandbox, "status", return_value="bubblewrap (bwrap) fehlt"), \
                patch("polaris_curator.llm.runtime_binaries", return_value={"codex": "/x", "claude": "/y"}), \
                patch("polaris_curator.llm.main_binary", return_value="codex"):
            c = sh.check_llm()
        self.assertEqual(c["level"], "warn")
        self.assertIn("ohne Sandbox", c["detail"])


if __name__ == "__main__":
    unittest.main()
