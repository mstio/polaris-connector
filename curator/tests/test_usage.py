"""Tests fuer polaris_curator/usage.py (Nutzungszaehler, seit 2026-11-05)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401 - setzt POLARIS_USAGE_OFF
from polaris_curator import usage


class TestUsage(unittest.TestCase):
    def test_counts_names_only_and_is_off_in_tests(self):
        home = Path(tempfile.mkdtemp())
        with patch.object(Path, "home", return_value=home):
            usage.count("x")
            self.assertFalse(usage.path().exists())  # in Tests abgeschaltet
            with patch.dict(os.environ, {"POLARIS_USAGE_OFF": ""}):
                usage.count("cli:run")
                usage.count("cli:run")
                usage.path().write_text(usage.path().read_text())  # bleibt lesbar
                d = json.loads(usage.path().read_text())
                self.assertEqual(d["cli:run"]["count"], 2)
                self.assertEqual(set(d["cli:run"]), {"count", "first", "last"})
                usage.path().write_text("kaputt")
                usage.count("y")  # darf nicht werfen, faengt neu an
                self.assertEqual(json.loads(usage.path().read_text())["y"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
