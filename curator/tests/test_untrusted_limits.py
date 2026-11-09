"""Grenzen fuer Fremdinhalt (ADR 004, Schritt 0, 2026-11-07): Zip-Bomben in
Office-Dateien, uebergrosse Dateien/Anhaenge, verwaiste Zwischendateien."""
import io
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401
from polaris_curator import documents_source, office_extract
from polaris_curator import systemhealth as sh


def docx_with(member: str, payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, payload)
    return buf.getvalue()


class TestOfficeLimits(unittest.TestCase):
    def test_normal_docx_still_works(self):
        xml = (b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               b'<w:body><w:p><w:r><w:t>Hallo</w:t></w:r></w:p></w:body></w:document>')
        self.assertIn("Hallo", office_extract.extract_docx(docx_with("word/document.xml", xml)))

    def test_oversized_member_is_refused_without_unpacking(self):
        bomb = docx_with("word/document.xml", b"<a>" + b"x" * (3 * 2**20) + b"</a>")   # klein gepackt
        with patch.object(office_extract, "MAX_XML_MEMBER", 2**20), \
                patch.object(office_extract.ET, "fromstring", side_effect=AssertionError("entpackt")):
            with self.assertRaises(ValueError):
                office_extract.extract_docx(bomb)

    def test_oversized_archive_total_is_refused(self):
        bomb = docx_with("word/document.xml", b"x" * (3 * 2**20))
        with patch.object(office_extract, "MAX_TOTAL_UNCOMPRESSED", 2**20):
            with self.assertRaises(ValueError):
                office_extract.extract_docx(bomb)


class TestDocumentSize(unittest.TestCase):
    def test_oversized_file_or_attachment_is_refused(self):
        with patch.object(documents_source, "MAX_DOCUMENT_BYTES", 10):
            with self.assertRaises(ValueError):
                documents_source.text_from_bytes("a.txt", b"x" * 11)
        self.assertEqual(documents_source.text_from_bytes("a.txt", b"klein"), "klein")


class TestStaleTmp(unittest.TestCase):
    def test_old_unique_tmp_is_reported_fresh_and_foreign_are_not(self):
        p = Path(tempfile.mkdtemp())
        (p / ".polaris").mkdir()
        old = p / ".knowledge.md.123.abcdef01.tmp"
        old.write_text("x")
        past = time.time() - 3 * 24 * 3600
        os.utime(old, (past, past))
        (p / ".polaris" / ".state.json.9.0123abcd.tmp").write_text("frisch")
        (p / "knowledge.md.tmp").write_text("alter fester Name, fremd")
        os.utime(p / "knowledge.md.tmp", (past, past))
        found = sh._stale_tmp_files({"x": p}, time.time())
        self.assertEqual(found, [f"{p.name}/.knowledge.md.123.abcdef01.tmp"])
        c = sh.check_journals({"x": p})
        self.assertEqual(c["level"], "warn")
        self.assertIn("verwaiste Zwischendatei", c["detail"])


if __name__ == "__main__":
    unittest.main()
