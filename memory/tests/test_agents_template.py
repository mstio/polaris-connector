"""Tests fuer scripts/agents-template.py (Vorlage aus der Live-AGENTS.md)."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "agents-template.py"
spec = importlib.util.spec_from_file_location("agents_template", SCRIPT)
at = importlib.util.module_from_spec(spec)
spec.loader.exec_module(at)

LIVE = """# Titel

<!-- Hinweis -->

## Geteilt <!-- allgemein -->
- Regel A
- Intern X <!-- privat -->
  - Folgezeile von X
- Regel B
  - Unterpunkt von B

## Ohne Kennzeichnung
- geheim

## Auch geteilt <!-- allgemein -->
- Regel C
"""


class TestRender(unittest.TestCase):
    def test_only_marked_sections_without_private_items(self):
        text, skipped = at.render(LIVE)
        self.assertIn("## Geteilt\n- Regel A\n- Regel B\n  - Unterpunkt von B\n", text)
        self.assertIn("## Auch geteilt\n- Regel C\n", text)
        for secret in ("Intern X", "Folgezeile", "geheim", "Ohne Kennzeichnung", "<!--  allgemein", "Hinweis"):
            self.assertNotIn(secret, text)
        self.assertEqual(skipped, ["Ohne Kennzeichnung"])
        self.assertTrue(text.startswith(at.HEADER))

    def test_marker_in_wrong_place_is_rejected(self):
        with self.assertRaises(ValueError):
            at.render("## A <!-- allgemein -->\nText mitten im Absatz <!-- privat -->\n")


if __name__ == "__main__":
    unittest.main()
