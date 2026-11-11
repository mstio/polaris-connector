"""Sandbox fuer Fremdinhalte (Sicherheitspruefung 2026-11-04)."""
import os
import json
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

    def test_health_check_without_sandbox(self):
        # Seit fail-closed (ADR 003): ohne Sandbox laeuft keine Kuratierung -> rot;
        # bewusst abgeschaltet (POLARIS_NO_SANDBOX=1) -> gelb.
        with patch.object(sandbox, "status", return_value="bubblewrap (bwrap) fehlt"), \
                patch("polaris_curator.llm.runtime_binaries", return_value={"codex": "/x", "claude": "/y"}), \
                patch("polaris_curator.llm.main_binary", return_value="codex"):
            with patch.dict(os.environ, {"POLARIS_NO_SANDBOX": ""}):
                c = sh.check_llm()
            self.assertEqual(c["level"], "error")
            self.assertIn("Kuratierung ausgesetzt", c["detail"])
            with patch.dict(os.environ, {"POLARIS_NO_SANDBOX": "1"}):
                c = sh.check_llm()
            self.assertEqual(c["level"], "warn")
            self.assertIn("ohne Sandbox", c["detail"])



class TestFailClosed(unittest.TestCase):
    """Ohne nutzbare Sandbox kein ungeschuetzter Lauf (ADR 003, 2026-11-07)."""

    def setUp(self):
        sandbox.available.cache_clear()
        self.addCleanup(sandbox.available.cache_clear)

    def test_wrap_refuses_without_bwrap_unless_opted_out(self):
        with patch.object(sandbox, "available", return_value=False), \
                patch.dict(os.environ, {"POLARIS_NO_SANDBOX": ""}):
            with self.assertRaises(sandbox.SandboxUnavailable):
                sandbox.wrap(["true"])
            with self.assertRaises(sandbox.SandboxUnavailable):
                sandbox.enabled()
        with patch.object(sandbox, "available", return_value=False), \
                patch.dict(os.environ, {"POLARIS_NO_SANDBOX": "1"}):
            self.assertEqual(sandbox.wrap(["true"]), ["true"])
            self.assertFalse(sandbox.enabled())

    def test_model_runtime_is_unavailable_without_sandbox(self):
        from polaris_curator import llm
        with patch.object(sandbox, "available", return_value=False), \
                patch.dict(os.environ, {"POLARIS_NO_SANDBOX": ""}):
            with self.assertRaises(llm.LlmUnavailableError):
                llm._sandbox_on()

    def test_missing_cli_never_runs_unwrapped(self):
        # Zweitpruefung 2026-11-07: erst Sandbox, dann CLI - keine Abkuerzung.
        from polaris_curator import llm
        from polaris_curator.config import CuratorConfig
        c = CuratorConfig(runtime="command", model="m", fallback_model="m2",
                          command=["gibt-es-nicht-xyz"], llm_timeout_seconds=5)
        with patch.object(sandbox, "available", return_value=False), \
                patch.dict(os.environ, {"POLARIS_NO_SANDBOX": ""}), \
                patch.object(llm.subprocess, "run") as run:
            with self.assertRaises(llm.LlmSandboxError):
                llm.call_llm("p", c)              # auch kein Ersatzmodell-Versuch
            run.assert_not_called()
        with patch.object(sandbox, "available", return_value=True), \
                patch.dict(os.environ, {"POLARIS_NO_SANDBOX": ""}), \
                patch.object(llm.subprocess, "run") as run:
            with self.assertRaises(llm.LlmUnavailableError):
                llm._run_command("p", "m", c, None)
            run.assert_not_called()

    def test_pdf_waits_without_sandbox(self):
        from polaris_curator import documents_source
        with patch.object(sandbox, "available", return_value=False), \
                patch.dict(os.environ, {"POLARIS_NO_SANDBOX": ""}), \
                patch.object(documents_source.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                documents_source._extract_pdf_bytes(b"%PDF-1.4")
            run.assert_not_called()


class TestCredentialSyncBack(unittest.TestCase):
    """Rueckschreiben der Anmeldung aus der Sandbox nur in gleicher Form."""

    def _run(self, before: dict, after):
        from polaris_curator import llm
        d = Path(tempfile.mkdtemp())
        self.state = d / "credential-sync.json"
        patcher = patch.object(llm, "CRED_SYNC_STATE", self.state)
        patcher.start()
        self.addCleanup(patcher.stop)
        real, private = d / "auth.json", d / "private.json"
        b = json.dumps(before).encode()
        real.write_bytes(b)
        private.write_bytes(after if isinstance(after, bytes) else json.dumps(after).encode())
        llm._sync_back_codex_auth(private, real, b)
        return json.loads(real.read_bytes())

    def test_renewed_token_is_written_back(self):
        out = self._run({"access_token": "a", "expiresAt": 1}, {"access_token": "b", "expiresAt": 2})
        self.assertEqual(out["access_token"], "b")

    def test_real_claude_refresh_shape_is_written_back(self):
        # Zweitpruefung 2026-11-07: Claude Code schreibt beim Refresh auch
        # refreshTokenExpiresAt - fehlte es in der Positivliste, ginge die Anmeldung verloren.
        before = {"claudeAiOauth": {"accessToken": "a", "refreshToken": "r", "expiresAt": 100,
                                    "refreshTokenExpiresAt": 1000, "scopes": ["user:inference"],
                                    "subscriptionType": "max", "subscriptionTypeSource": "x", "rateLimitTier": "t"}}
        after = {"claudeAiOauth": {**before["claudeAiOauth"], "accessToken": "b", "refreshToken": "r2",
                                   "expiresAt": 200, "refreshTokenExpiresAt": 2000}}
        self.assertEqual(self._run(before, after)["claudeAiOauth"]["refreshToken"], "r2")
        self.assertIsNone(json.loads(self.state.read_text())["refused"])

    def test_refused_write_back_is_recorded_without_values(self):
        before = {"access_token": "a", "endpoint": "https://api.example"}
        self._run(before, {**before, "endpoint": "https://geheim-fremd"})
        rec = json.loads(self.state.read_text())
        self.assertEqual(rec["refused"], ["endpoint"])
        self.assertNotIn("geheim-fremd", self.state.read_text())

    def test_only_token_fields_may_change(self):
        # Positivliste (Gutachten Codex/agy 2026-11-07): sonst nichts veraenderbar
        before = {"access_token": "a", "endpoint": "https://api.example", "flags": ["x"]}
        self.assertEqual(self._run(before, {**before, "access_token": "b", "endpoint": "https://fremd"}), before)
        self.assertEqual(self._run(before, {**before, "access_token": "b", "flags": ["y"]}), before)

    def test_nested_refresh_is_written_back(self):
        before = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None,
                  "tokens": {"id_token": "i1", "access_token": "a1", "refresh_token": "r1", "account_id": "acc"},
                  "last_refresh": "2026-11-01"}
        after = {**before, "tokens": {**before["tokens"], "access_token": "a2", "refresh_token": "r2"},
                 "last_refresh": "2026-11-07"}
        self.assertEqual(self._run(before, after)["tokens"]["refresh_token"], "r2")

    def test_account_or_key_swap_is_rejected(self):
        before = {"auth_mode": "chatgpt", "OPENAI_API_KEY": None,
                  "tokens": {"access_token": "a1", "account_id": "acc"}}
        self.assertEqual(self._run(before, {**before, "OPENAI_API_KEY": "sk-fremd"}), before)      # null-Joker
        self.assertEqual(self._run(before, {**before, "auth_mode": "apikey"}), before)
        self.assertEqual(self._run(before, {**before, "tokens": {"access_token": "a2", "account_id": "fremd"}}), before)
        claude = {"claudeAiOauth": {"accessToken": "a", "refreshToken": "r", "expiresAt": 100, "scopes": ["user:inference"]}}
        ok = {"claudeAiOauth": {**claude["claudeAiOauth"], "accessToken": "b", "expiresAt": 200}}
        self.assertEqual(self._run(claude, ok)["claudeAiOauth"]["accessToken"], "b")
        for bad in ({**claude["claudeAiOauth"], "scopes": ["user:inference", "org:admin"]},
                    {**claude["claudeAiOauth"], "expiresAt": 50}):
            self.assertEqual(self._run(claude, {"claudeAiOauth": bad}), claude)

    def test_different_shape_is_rejected(self):
        before = {"access_token": "a", "expiresAt": 1}
        self.assertEqual(self._run(before, {"access_token": "b", "expiresAt": 2, "extra": "x"}), before)
        self.assertEqual(self._run(before, {"access_token": ["b"], "expiresAt": 2}), before)
        self.assertEqual(self._run(before, ["access_token"]), before)
        self.assertEqual(self._run(before, {"access_token": "x" * 70000, "expiresAt": 2}), before)


if __name__ == "__main__":
    unittest.main()


class TestBwrapEffect(unittest.TestCase):
    """Fable 2026-11-11 (H2): ein falsches bwrap, das nur ausfuehrt, galt als Sandbox."""

    def test_fake_bwrap_is_not_available(self):
        import tempfile, shutil as _sh
        from polaris_curator import sandbox
        d = Path(tempfile.mkdtemp())
        self.addCleanup(_sh.rmtree, d, True)
        fake = d / "bwrap"
        fake.write_text('#!/bin/sh\nwhile [ "$1" != "--" ]; do shift; done; shift; exec "$@"\n')
        fake.chmod(0o755)
        sandbox.available.cache_clear()
        self.addCleanup(sandbox.available.cache_clear)
        with patch.object(sandbox, "bwrap_path", return_value=str(fake)), \
                patch.dict(os.environ, {"POLARIS_NO_SANDBOX": ""}):
            self.assertFalse(sandbox.available())

    def test_system_bwrap_preferred_over_path(self):
        from polaris_curator import sandbox
        with patch("os.path.isfile", side_effect=lambda p: p == "/usr/bin/bwrap"), \
                patch("shutil.which", return_value="/home/u/.local/bin/bwrap"):
            self.assertEqual(sandbox.bwrap_path(), "/usr/bin/bwrap")
