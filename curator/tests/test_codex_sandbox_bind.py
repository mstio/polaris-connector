"""Codex-Sandbox gibt nur den Programmordner frei (seit 2026-11-11).

Gremium (Fable, Kopfstand): llm.py band `codex_bin.parent.parent` lesend ein.
Bei `~/.local/bin/codex` war damit ganz `~/.local` sichtbar - samt
`~/.local/share/polaris` (alle erfassten Chats). Liegt der Ordner im oder
ueber dem Home bzw. direkt darunter, wird nur die Datei freigegeben.
"""

import unittest
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401

from polaris_curator import llm


class TestCodexBind(unittest.TestCase):
    def ro(self, binary: str, home: str = "/home/u"):
        with patch.object(Path, "home", return_value=Path(home)), \
                patch.object(Path, "resolve", lambda self, strict=False: Path(str(self).replace("/home/", "/var/home/"))
                             if str(self).startswith("/home/") and home.startswith("/home/s") else self):
            return llm.codex_sandbox_ro(Path(binary))

    def test_pnpm_shim_binds_only_the_file(self):
        # Fable 2026-11-11: ~/.local/share/pnpm/codex -> root ~/.local/share (samt polaris).
        self.assertEqual(self.ro("/home/u/.local/share/pnpm/codex"), [Path("/home/u/.local/share/pnpm/codex")])

    def test_symlinked_home_is_resolved(self):
        # /home/s -> /var/home/s; codex_bin kommt aufgeloest an.
        self.assertEqual(self.ro("/var/home/s/.local/bin/codex", home="/home/s"),
                         [Path("/var/home/s/.local/bin/codex")])

    def test_run_codex_uses_the_helper(self):
        # Mutation (Fable): _run_codex_exec wieder mit parent.parent blieb unbemerkt.
        import inspect
        src = inspect.getsource(llm._run_codex_exec)
        self.assertIn("codex_sandbox_ro(codex_bin)", src)
        self.assertNotIn("codex_bin.parent.parent", src)

    def test_mise_install_dir_is_bound(self):
        b = "/home/u/.local/share/mise/installs/codex/0.167.1/bin/codex"
        self.assertEqual(self.ro(b), [Path("/home/u/.local/share/mise/installs/codex/0.167.1")])

    def test_local_bin_binds_only_the_file(self):
        self.assertEqual(self.ro("/home/u/.local/bin/codex"), [Path("/home/u/.local/bin/codex")])

    def test_home_bin_binds_only_the_file(self):
        self.assertEqual(self.ro("/home/u/bin/codex"), [Path("/home/u/bin/codex")])

    def test_cargo_bin_binds_only_the_file(self):
        self.assertEqual(self.ro("/home/u/.cargo/bin/codex"), [Path("/home/u/.cargo/bin/codex")])

    def test_system_install_keeps_package_dir(self):
        b = "/usr/lib/node_modules/@openai/codex/bin/codex"
        self.assertEqual(self.ro(b), [Path("/usr/lib/node_modules/@openai/codex")])

    def test_usr_bin_binds_only_the_file(self):
        self.assertEqual(self.ro("/usr/bin/codex"), [Path("/usr/bin/codex")])


if __name__ == "__main__":
    unittest.main()
