"""Tests fuer scripts/privacy-check.py und den pre-push-Hook des Spiegels.

Laufen in einem eigenen HOME mit erfundenen Projektnamen, nie gegen das echte Home.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / "scripts" / "privacy-check.py"
HOOK = REPO / "scripts" / "public-pre-push"
SECRET = "Kunde-A plant den Umzug der Zentrale nach Musterstadt im dritten Quartal."


class PrivacyCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "home"
        cfg = self.home / ".config" / "polaris"
        cfg.mkdir(parents=True)
        projekte = self.home / "Projekte"
        (cfg / "config.yaml").write_text(f"project_roots:\n  - {projekte}\n")
        self.offen = projekte / "Kundenprojekt"
        self.geheim = projekte / "Vertraulich"
        for d in (self.offen, self.geheim):
            d.mkdir(parents=True)
        (self.geheim / "notizen.md").write_text(f"# Notizen\n\n{SECRET}\n")
        self.cfg = cfg
        self.env = {**os.environ, "HOME": str(self.home), "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_CONFIG_NOSYSTEM": "1"}
        self.tree = Path(self._tmp.name) / "tree"
        self.tree.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def run_check(self, content: str, name: str = "README.md"):
        (self.tree / name).write_text(content)
        return subprocess.run(["python3", str(CHECK), str(self.tree)], env=self.env,
                              capture_output=True, text=True)

    def protect_by_marker(self):
        (self.geheim / ".polaris-protected").write_text("")

    def test_unprotected_folder_name_is_a_word(self):
        r = self.run_check("Das Wort Vertraulich steht hier.\n")
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_marker_frees_the_plain_word(self):
        self.protect_by_marker()
        r = self.run_check("Dieses Repo bleibt vertraulich, das Wort allein ist harmlos.\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_marker_blocks_copied_content_without_showing_it(self):
        self.protect_by_marker()
        r = self.run_check(f"Einleitung\n  {SECRET.upper()}  \n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("README.md:2: Inhalt aus geschuetztem Ordner", r.stdout)
        self.assertNotIn("musterstadt", r.stdout.casefold())

    def test_marker_keeps_exact_name_blocked(self):
        self.protect_by_marker()
        r = self.run_check("Im Ordner Vertraulich liegt nichts.\n")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Vertraulich", r.stdout)                    # Treffer nennt den Namen nicht
        (self.cfg / "bundle-allow.txt").write_text("Vertraulich\n")
        self.assertEqual(self.run_check("Vertraulich\n").returncode, 1)
        (self.tree / "README.md").unlink()
        r = self.run_check("x\n", name="Vertraulich.md")
        self.assertIn("im Dateipfad", r.stdout)

    def test_marker_blocks_path(self):
        self.protect_by_marker()
        r = self.run_check("Siehe Projekte/Vertraulich/notizen.md\n")
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_allow_list_cannot_free_protected_path(self):
        self.protect_by_marker()
        (self.cfg / "bundle-allow.txt").write_text("Projekte/Vertraulich\nVertraulich\n")
        r = self.run_check("Siehe Projekte/Vertraulich\n")
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_protected_txt_outside_project_roots(self):
        extern = self.home / "Ablage" / "Steuer"
        extern.mkdir(parents=True)
        (extern / "a.txt").write_text(SECRET + "\n")
        (self.cfg / "protected.txt").write_text("# geschuetzt\n~/Ablage/Steuer\n")
        r = self.run_check(SECRET + "\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("1 geschuetzte Ordner", r.stderr)

    def test_short_content_lines_are_blocked(self):
        (self.geheim / "kurz.md").write_text("Max Muster\nTel 0170 123\n---\n## Offen\n")
        self.protect_by_marker()
        self.assertEqual(self.run_check("# Notizen\n").returncode, 1)        # eigene Ueberschrift ist Inhalt
        self.assertEqual(self.run_check("Max Muster\n").returncode, 1)
        self.assertEqual(self.run_check("Tel 0170 123\n").returncode, 1)
        r = self.run_check("---\n## Offen\n")                               # Gerüst und Polaris-Ueberschrift
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_embedded_content_is_blocked(self):
        self.protect_by_marker()
        r = self.run_check(f'x = "{SECRET[:40]}"  # Beispiel\n')
        self.assertEqual(r.returncode, 1, r.stdout)

    def test_binary_file_copy_is_blocked(self):
        (self.geheim / "scan.pdf").write_bytes(b"%PDF-1.7\x00\xff\xfe" + bytes(range(256)))
        self.protect_by_marker()
        (self.tree / "beilage.bin").write_bytes((self.geheim / "scan.pdf").read_bytes())
        r = subprocess.run(["python3", str(CHECK), str(self.tree)], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("byte-gleich", r.stdout)

    def test_polaris_format_lines_are_not_fingerprinted(self):
        meta = "  - Scope: lokal · Evidenzgrad: Einzelbeleg · Konfidenz: hoch"
        (self.geheim / "knowledge.md").write_text(f"{meta}\n<!-- polaris-source: type=chatgpt conversation_id=c1 -->\n")
        self.protect_by_marker()
        r = self.run_check(f"{meta}\n<!-- polaris-source: type=chatgpt conversation_id=c1 -->\n")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_marker_file_in_tree_is_a_hit(self):
        r = self.run_check("", name=".polaris-protected")
        self.assertEqual(r.returncode, 1)

    def test_pre_push_hook_blocks_direct_push(self):
        self.protect_by_marker()
        base = Path(self._tmp.name)
        remote, clone = base / "remote.git", base / "clone"
        git = lambda *a, cwd=None: subprocess.run(["git", *a], cwd=cwd, env=self.env, check=True,
                                                   capture_output=True, text=True)
        git("init", "-q", "--bare", str(remote))
        git("init", "-q", "-b", "main", str(clone))
        git("remote", "add", "origin", str(remote), cwd=clone)
        (clone / ".git" / "hooks" / "pre-push").symlink_to(HOOK)
        ident = ["-c", "user.name=Test", "-c", "user.email=test@example.invalid"]
        (clone / "ok.md").write_text("harmlos\n")
        git("add", "-A", cwd=clone)
        git(*ident, "commit", "-qm", "ok", cwd=clone)
        git("push", "-q", "origin", "main", cwd=clone)
        (clone / "leck.md").write_text(SECRET + "\n")
        git("add", "-A", cwd=clone)
        git(*ident, "commit", "-qm", "leck", cwd=clone)
        r = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=clone, env=self.env,
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Push abgebrochen", r.stderr)

    def test_pre_push_hook_checks_commit_metadata(self):
        (self.cfg / "bundle-deny.txt").write_text("Geheimfirma\n")
        base = Path(self._tmp.name)
        remote, clone = base / "remote.git", base / "clone"
        git = lambda *a, cwd=None: subprocess.run(["git", *a], cwd=cwd, env=self.env, check=True,
                                                   capture_output=True, text=True)
        git("init", "-q", "--bare", str(remote))
        git("init", "-q", "-b", "main", str(clone))
        git("remote", "add", "origin", str(remote), cwd=clone)
        (clone / ".git" / "hooks" / "pre-push").symlink_to(HOOK)
        (clone / "ok.md").write_text("harmlos\n")
        git("add", "-A", cwd=clone)
        git("-c", "user.name=Test", "-c", "user.email=chef@geheimfirma.example", "commit", "-qm", "ok", cwd=clone)
        r = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=clone, env=self.env,
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Autor/Nachricht", r.stderr)


if __name__ == "__main__":
    unittest.main()
