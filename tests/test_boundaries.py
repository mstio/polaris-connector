"""Grenzen und Schutzregel ausführbar (ADR 003, Stufe 1, Schritt 5).

- Importrichtung: Bridge und Curator importieren einander nie (sie reden nur
  über Dateien); der Kern des Curators importiert weder Health Check noch CLI.
- Die Liste der Schutzdateien in AGENTS.md stimmt mit dem Repo überein.
"""
import ast
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CURATOR = REPO / "curator" / "polaris_curator"
BRIDGE = REPO / "bridge" / "polaris"
# Was nicht zum Kern gehört: Oberflächen und Health Check.
NOT_CORE = {"cli", "systemhealth", "healthagent"}


def imports(path: Path) -> set[str]:
    """Importierte Module, relative als '.<name>'."""
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = ("." * node.level) + (node.module or "")
            out.add(base)
            if node.level and not node.module:
                out.update("." + a.name for a in node.names)
    return out


class TestBoundaries(unittest.TestCase):
    def test_bridge_never_imports_curator(self):
        for f in BRIDGE.glob("*.py"):
            bad = {m for m in imports(f) if m.split(".")[0] == "polaris_curator"}
            self.assertFalse(bad, f"{f.name} importiert den Curator: {bad}")

    def test_curator_never_imports_bridge(self):
        for f in CURATOR.glob("*.py"):
            bad = {m for m in imports(f) if m == "polaris" or m.startswith("polaris.")}
            self.assertFalse(bad, f"{f.name} importiert die Bridge: {bad}")

    def test_core_never_imports_interfaces_or_health(self):
        for f in CURATOR.glob("*.py"):
            if f.stem in NOT_CORE:
                continue
            mods = imports(f)
            bad = {m for m in mods for n in NOT_CORE
                   if m in (f".{n}", f"polaris_curator.{n}") or m.endswith(f".{n}")}
            self.assertFalse(bad, f"{f.name} (Kern) importiert {bad}")


class TestProtectedFiles(unittest.TestCase):
    def listed(self) -> list[str]:
        text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        block = re.search(r"<!-- schutzdateien:start -->(.*?)<!-- schutzdateien:end -->", text, re.S)
        self.assertIsNotNone(block, "Schutzdatei-Liste fehlt in AGENTS.md")
        return re.findall(r"^- `([^`]+)`", block.group(1), re.M)

    def test_listed_files_exist(self):
        files = self.listed()
        self.assertGreaterEqual(len(files), 5)
        for rel in files:
            self.assertTrue((REPO / rel).is_file(), f"Schutzdatei fehlt: {rel}")

    def test_core_protection_is_listed(self):
        must = {"curator/polaris_curator/sandbox.py", "curator/polaris_curator/guard.py",
                "memory/tools/claude-guard-hook.py", "scripts/privacy-check.py"}
        self.assertTrue(must <= set(self.listed()), must - set(self.listed()))


if __name__ == "__main__":
    unittest.main()
