import os
import tempfile
import time
import unittest
from pathlib import Path

import conftest_helpers  # noqa: F401 - sys.path

from polaris_curator import storage


class TestAtomicWriteSetsMtime(unittest.TestCase):
    def test_replaced_file_gets_current_mtime(self):
        p = Path(tempfile.mkdtemp()) / "knowledge.md"
        p.write_text("alt")
        old = time.time() - 4 * 86400
        os.utime(p, (old, old))
        storage.atomic_write_text(p, "neu")
        self.assertEqual(p.read_text(), "neu")
        self.assertGreater(p.stat().st_mtime, time.time() - 60)


class TestAtomicWriteTmpNames(unittest.TestCase):
    """Eindeutige Zwischendateien (ADR 003): keine Reste, kein fester .tmp-Name."""

    def test_no_leftovers_and_no_fixed_tmp(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from polaris_curator import storage
        d = Path(tempfile.mkdtemp())
        target = d / "knowledge.md"
        (d / "knowledge.md.tmp").write_text("fremd")      # alter fester Name bleibt unberuehrt
        storage.atomic_write_text(target, "neu")
        self.assertEqual(target.read_text(), "neu")
        self.assertEqual((d / "knowledge.md.tmp").read_text(), "fremd")
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["knowledge.md", "knowledge.md.tmp"])
        with patch.object(storage.os, "replace", side_effect=OSError("Laufwerk weg")):
            with self.assertRaises(OSError):
                storage.atomic_write_text(target, "zwei")
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["knowledge.md", "knowledge.md.tmp"])


if __name__ == "__main__":
    unittest.main()
