"""Health-Check-Meldung an den Standard-Agenten (seit 2026-11-05)."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401 - sys.path
from polaris_curator import healthagent as ha
from polaris_curator import default_agent
from polaris_curator import systemhealth as sh

DATA = {"components": [{"id": "storage", "label": "Speicher", "level": "warn", "detail": "Repos: x\x1b[31m.md",
                        "command": "git -C ~/r add -- x.md",
                        "parts": [{"id": "repos", "label": "Repos", "level": "warn", "detail": "x.md"},
                                  {"id": "mount", "label": "Projektordner", "level": "ok", "detail": "gut"}]}],
        "checks": [], "system": [{"id": "reboot", "label": "Neustart", "level": "warn", "detail": "bitte"}]}


def which(present):
    return lambda name: f"/usr/bin/{name}" if name in present else None


class TestHealthAgent(unittest.TestCase):
    def test_omarchy_default_uses_first_line_only(self):
        with tempfile.TemporaryDirectory() as folder:
            choice = Path(folder) / "agent"
            choice.write_text("claude\ncodex\n", encoding="utf-8")
            self.assertEqual(default_agent.omarchy_default(choice), "claude")
            choice.write_text("\nclaude\n", encoding="utf-8")
            self.assertIsNone(default_agent.omarchy_default(choice))
            choice.write_text("claude" + " " * 200 + "bad\n", encoding="utf-8")
            self.assertIsNone(default_agent.omarchy_default(choice))

    def test_unknown_or_malformed_id_refused(self):
        for cid in ("nope", "../x", "a b", "", "x;rm"):
            with patch.object(ha.subprocess, "Popen") as popen:
                self.assertFalse(ha.ask(DATA, cid, "claude")["ok"], cid)
                popen.assert_not_called()

    def test_launches_omarchy_default_independently_of_curator(self):
        with patch.object(ha.shutil, "which", side_effect=which({"claude", "codex", "omarchy-launch-tui"})), \
                patch.object(ha, "omarchy_default", return_value="claude"), \
                patch.object(ha.subprocess, "Popen") as popen:
            r = ha.ask(DATA, "storage")
        self.assertEqual(r, {"ok": True, "agent": "claude"})
        argv = popen.call_args.args[0]
        self.assertEqual(argv[:3], ["omarchy-launch-tui", "--app-id=org.omarchy.agent", "claude"])
        self.assertEqual(len(argv), 4)
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_explicit_choice_and_no_silent_fallback(self):
        with patch.object(ha.shutil, "which", side_effect=which({"claude"})), \
                patch.object(ha, "omarchy_default", return_value="claude"):
            self.assertEqual(ha.pick_agent("default"), "claude")
            self.assertEqual(ha.pick_agent("claude"), "claude")
            self.assertIsNone(ha.pick_agent("codex"))
            self.assertIsNone(ha.pick_agent("command"))
            self.assertIsNone(ha.pick_agent(["claude"]))
        with patch.object(ha.shutil, "which", side_effect=which({"claude", "codex"})), \
                patch.object(ha, "omarchy_default", return_value="claude"):
            self.assertEqual(ha.pick_agent("codex"), "codex")

    def test_no_agent_is_reported(self):
        with patch.object(ha.shutil, "which", side_effect=which({"omarchy-launch-tui"})), \
                patch.object(ha, "omarchy_default", return_value="claude"):
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
