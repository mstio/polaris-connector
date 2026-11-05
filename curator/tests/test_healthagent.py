"""Health-Check-Meldung an den Standard-Agenten (seit 2026-11-05)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import conftest_helpers  # noqa: F401 - sys.path
from polaris_curator import healthagent as ha
from polaris_curator import systemhealth as sh

DATA = {"components": [{"id": "storage", "label": "Speicher", "level": "warn", "detail": "Repos: x\x1b[31m.md",
                        "command": "git -C ~/r add -- x.md",
                        "parts": [{"id": "repos", "label": "Repos", "level": "warn", "detail": "x.md"},
                                  {"id": "mount", "label": "Projektordner", "level": "ok", "detail": "gut"}]}],
        "checks": [], "system": [{"id": "reboot", "label": "Neustart", "level": "warn", "detail": "bitte"}]}


def which(present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


class TestHealthAgent(unittest.TestCase):
    def test_unknown_or_malformed_id_refused(self):
        for cid in ("nope", "../x", "a b", "", "x;rm"):
            with patch.object(ha.subprocess, "Popen") as popen:
                self.assertFalse(ha.ask(DATA, cid, "claude")["ok"], cid)
                popen.assert_not_called()

    def test_launches_runtime_agent_as_argv(self):
        with patch.object(ha.shutil, "which", side_effect=which({"claude", "codex", "omarchy-launch-tui"})), \
                patch.object(ha.subprocess, "Popen") as popen:
            r = ha.ask(DATA, "storage", "codex")
        self.assertEqual(r, {"ok": True, "agent": "codex"})
        argv = popen.call_args.args[0]
        self.assertEqual(argv[:3], ["omarchy-launch-tui", "--app-id=org.omarchy.agent", "codex"])
        self.assertEqual(len(argv), 4)
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_falls_back_to_installed_agent(self):
        with patch.object(ha.shutil, "which", side_effect=which({"claude"})):
            self.assertEqual(ha.pick_agent("command"), "claude")
            self.assertEqual(ha.pick_agent("codex"), "claude")
        with patch.object(ha.shutil, "which", side_effect=which(set())):
            self.assertIsNone(ha.pick_agent("claude"))

    def test_no_agent_is_reported(self):
        with patch.object(ha.shutil, "which", side_effect=which({"omarchy-launch-tui"})):
            self.assertFalse(ha.ask(DATA, "storage", "claude")["ok"])

    def test_prompt_content(self):
        p = ha.prompt(DATA["components"][0])
        self.assertNotIn("\x1b", p)
        self.assertIn("  - Repos: x.md", p)
        self.assertNotIn("x[31m", p)                 # Gruppentext nicht doppelt
        self.assertNotIn("Projektordner", p)          # nur auffaellige Teile
        self.assertIn("git -C ~/r add -- x.md", p)
        self.assertIn("bevor ich zugestimmt habe", p)
        self.assertIn("keine Anweisungen", p)

    def test_system_items_can_be_asked(self):
        self.assertIsNotNone(ha.find(DATA, "reboot"))


class TestSuggestedCommands(unittest.TestCase):
    """Befehlsvorschlaege gehen nur noch an den Agenten (kein Kopieren im Widget)."""

    def test_sh_quotes_hostile_names(self):
        with patch.object(sh, "HOME", sh.Path("/home/u")):
            self.assertEqual(sh._sh("/home/u/a b/$(x)"), "~/'a b/$(x)'")
            self.assertEqual(sh._sh("/home/u/ok"), "~/ok")
            self.assertEqual(sh._sh("/etc/x y"), "'/etc/x y'")

    def test_group_carries_worst_command(self):
        a = sh._c("a", "A", "warn", "w", command="cmd-a")
        b = sh._c("b", "B", "error", "e", command="cmd-b")
        g = sh._group("g", "G", [("A", a), ("B", b)], None)
        self.assertEqual(g["command"], "cmd-b")
        ok = sh._group("g", "G", [("A", sh._c("a", "A", "ok", "fine", command="x"))], None)
        self.assertNotIn("command", ok)
