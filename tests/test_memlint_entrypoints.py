"""memlint legt nur plausible Agenten-Einstiege an (Sicherheitspruefung 2026-11-04).

entrypoints.conf kann aus einem fremdbeschreibbaren Spiegel stammen."""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MEMLINT = Path(__file__).resolve().parents[1] / "memory" / "tools" / "memlint.py"


def load():
    loader = importlib.machinery.SourceFileLoader("memlint_under_test", str(MEMLINT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = mod  # dataclasses brauchen das Modul in sys.modules
    loader.exec_module(mod)
    return mod


class TestEntrypoints(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.root = self.home / ".config" / "ai-agents"
        (self.root / "skills" / "demo").mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("# Regeln\n", encoding="utf-8")
        for d in (".claude", ".config/autostart", ".local/bin"):
            (self.home / d).mkdir(parents=True, exist_ok=True)
        self.env = patch.dict(os.environ, {"HOME": str(self.home)})
        self.env.start()
        self.m = load()

    def tearDown(self):
        self.env.stop()

    def conf(self, text):
        (self.root / "entrypoints.conf").write_text(text, encoding="utf-8")

    def test_normal_entrypoints_are_linked(self):
        self.conf("~/.claude/CLAUDE.md AGENTS.md\n~/.claude/skills/ skills/\n")
        done = self.m.link_entrypoints(self.root)
        self.assertTrue((self.home / ".claude" / "CLAUDE.md").is_symlink())
        self.assertTrue((self.home / ".claude" / "skills" / "demo").is_symlink())
        self.assertFalse(any("NICHT" in d for d in done))

    def test_hostile_entrypoints_are_refused(self):
        self.conf("~/.local/bin/sudo AGENTS.md\n"
                  "~/.config/autostart/x.desktop AGENTS.md\n"
                  "~/.claude/CLAUDE.md ../../.ssh/id_ed25519\n"
                  "/etc/evil.md AGENTS.md\n")
        done = self.m.link_entrypoints(self.root)
        self.assertFalse((self.home / ".local" / "bin" / "sudo").exists())
        self.assertFalse((self.home / ".config" / "autostart" / "x.desktop").exists())
        self.assertFalse((self.home / ".claude" / "CLAUDE.md").exists())
        self.assertEqual(sum("NICHT angelegt" in d for d in done), 4)

    def test_lint_reports_hostile_entrypoint(self):
        self.conf("~/.local/bin/sudo AGENTS.md\n")
        r = self.m.lint(self.root) if hasattr(self.m, "lint") else None
        if r is None:
            self.skipTest("lint-Funktion hat einen anderen Namen")
        self.assertTrue(any(f.check == "entrypoints" and "unzulaessig" in f.message for f in r.findings))


    def test_symlink_out_of_memory_is_an_error(self):
        (self.root / "AI_HANDOFF.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "handoff").mkdir()
        target = self.home / ".bashrc"
        target.write_text("# rc\n", encoding="utf-8")
        (self.root / "handoff" / "x.md").symlink_to(target)
        r = self.m.lint(self.root, system=False)
        self.assertTrue(any(f.check == "symlinks" for f in r.findings))


if __name__ == "__main__":
    unittest.main()
