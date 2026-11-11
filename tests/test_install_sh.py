"""Tests fuer install.sh: Begleit-Widgets per git, Update richtet nichts Neues ein.

Laufen in einem eigenen HOME mit Platzhaltern fuer omarchy, omarchy-shell und
systemctl; 'omarchy plugin add' legt nur einen Ordner an (kein Netz).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[1]

OMARCHY_STUB = r"""#!/usr/bin/env bash
P="$HOME/.config/omarchy/plugins"; E="$HOME/.omarchy-enabled"; L="$HOME/.omarchy-calls"; touch "$E"
echo "$*" >> "$L"
case "$1 $2" in
  "plugin list") python3 - "$P" "$E" <<'PY'
import json,os,sys
p,e=sys.argv[1:3]; en=set(open(e).read().split())
print(json.dumps([{"id":d,"enabled":d in en} for d in (os.listdir(p) if os.path.isdir(p) else [])]))
PY
  ;;
  "plugin add") id=$(basename "$3" .git); mkdir -p "$P/$id/.git" && echo "$id" >> "$E";;
  "plugin enable") echo "$3" >> "$E";;
  *) :;;
esac
"""

BASE_ARGS = ["--yes", "--no-backup", "--no-memory", "--no-units", "--no-restart"]


class InstallShTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.home = base / "home"
        (self.home / "Projekte" / "Kunde-A").mkdir(parents=True)
        stub = base / "stub"
        stub.mkdir()
        (stub / "omarchy").write_text(OMARCHY_STUB)
        for name in ("systemctl", "omarchy-shell"):
            (stub / name).write_text("#!/bin/sh\nexit 0\n")
        (stub / "omarchy-default-agent").write_text(
            '#!/bin/sh\ncat "$HOME/.config/omarchy/defaults/agent" 2>/dev/null || true\n')
        for f in stub.iterdir():
            f.chmod(0o755)
        self.base = base
        self.env = {"HOME": str(self.home), "PATH": f"{stub}:/usr/bin:/bin", "USER": "test",
                    "GIT_CONFIG_GLOBAL": os.devnull, "POLARIS_NO_NOTIFY": "1", "LANG": "C.UTF-8"}
        self.plugins = self.home / ".config" / "omarchy" / "plugins"

    def tearDown(self):
        self._tmp.cleanup()

    def install(self, *args, via=None):
        cmd = [str(REPO / "install.sh"), *args]
        if via:  # Aufruf ueber ein Skript dieses Namens (Elternprozess wie bei update.sh)
            wrapper = self.base / via
            wrapper.write_text(f'#!/usr/bin/env bash\n"{REPO / "install.sh"}" "$@"\n')
            wrapper.chmod(0o755)
            cmd = [str(wrapper), *args]
        return subprocess.run(cmd, env=self.env, capture_output=True, text=True, timeout=300)

    def enabled(self) -> set[str]:
        f = self.home / ".omarchy-enabled"
        return set(f.read_text().split()) if f.exists() else set()

    def test_fresh_install_adds_companion_widgets(self):
        r = self.install(*BASE_ARGS, "--projects", str(self.home / "Projekte"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(yaml.safe_load((self.home / ".config/polaris/curator.yaml").read_text())["runtime"],
                         "default")
        for pid in ("mst.polaris-curator", "mst.agent-launchers", "omadock"):
            self.assertTrue((self.plugins / pid).is_dir(), pid)
            self.assertIn(pid, self.enabled())

    def test_default_curator_agent_is_checked_during_install(self):
        selected = self.home / ".config/omarchy/defaults/agent"
        selected.parent.mkdir(parents=True)
        selected.write_text("claude\n")
        stub = Path(self.env["PATH"].split(":", 1)[0])
        (stub / "claude").write_text("#!/bin/sh\nexit 0\n")
        (stub / "claude").chmod(0o755)
        r = self.install(*BASE_ARGS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Kein von Polaris unterstützter Omarchy-Standardagent", r.stdout)
        self.assertNotIn("ist nicht installiert", r.stdout)

    def test_existing_disabled_plugin_gets_enabled(self):
        (self.plugins / "omadock" / ".git").mkdir(parents=True)   # geklont, nie aktiviert
        r = self.install(*BASE_ARGS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("omadock", self.enabled())

    def test_update_parent_adds_nothing_new(self):
        self.install(*BASE_ARGS)
        (self.home / ".omarchy-enabled").write_text("mst.polaris-curator\nomadock\n")
        subprocess.run(["rm", "-rf", str(self.plugins / "mst.agent-launchers")], check=True)
        r = self.install(*BASE_ARGS, via="update.sh")          # wie ein aelteres update.sh
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.plugins / "mst.agent-launchers").exists())
        self.assertIn("nicht eingerichtet, bleibt so", r.stdout)

    def test_mere_mention_of_update_sh_is_not_an_update(self):
        self.install(*BASE_ARGS)
        subprocess.run(["rm", "-rf", str(self.plugins / "mst.agent-launchers")], check=True)
        script = f'echo update.sh >/dev/null; "{REPO / "install.sh"}" ' + " ".join(BASE_ARGS)
        r = subprocess.run(["bash", "-c", script], env=self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.plugins / "mst.agent-launchers").is_dir())

    def test_long_update_news_do_not_abort_install(self):
        # >40 Zeilen Neuigkeiten: head -40 + pipefail beendete install.sh vorzeitig.
        state = self.home / ".local/state/polaris"
        state.mkdir(parents=True)
        (state / "neu-seit-update.md").write_text(
            "# Neu\n\n## Update vom 2026-01-01 00:00\n\n" + "".join(f"- Punkt {i} " + "x" * 100 + "\n" for i in range(3000)))  # > 64-KB-Puffer
        (state / "changelog-gesehen.md").write_text((REPO / "CHANGELOG.md").read_text())
        r = self.install(*BASE_ARGS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Punkt 37", r.stdout)
        self.assertNotIn("Punkt 41", r.stdout)

    def test_private_dirs_are_0700(self):
        # Marktplatz #13877 (HANCORE-linux): auch bestehende 0755-Ordner werden enger.
        dirs = (".config/polaris", ".local/share/polaris", ".local/state/polaris", "Downloads/polaris-inbox")
        for d in dirs:
            (self.home / d).mkdir(parents=True)
            (self.home / d).chmod(0o755)
        r = self.install(*BASE_ARGS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for d in dirs:
            self.assertEqual((self.home / d).stat().st_mode & 0o777, 0o700, d)

    def test_private_dir_symlink_is_left_alone_with_warning(self):
        target = self.base / "geteilt"
        target.mkdir()
        target.chmod(0o755)
        (self.home / ".local/state").mkdir(parents=True)
        (self.home / ".local/state/polaris").symlink_to(target)
        r = self.install(*BASE_ARGS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)
        self.assertIn("ist ein Symlink", r.stdout)

    def test_only_existing_adds_nothing_new(self):
        self.install(*BASE_ARGS)
        subprocess.run(["rm", "-rf", str(self.plugins / "omadock")], check=True)
        r = self.install(*BASE_ARGS, "--only-existing")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.plugins / "omadock").exists())

    def test_manual_rerun_completes_missing_widget(self):
        self.install(*BASE_ARGS)
        subprocess.run(["rm", "-rf", str(self.plugins / "mst.agent-launchers")], check=True)
        r = self.install(*BASE_ARGS)                             # z. B. nach Netzausfall beim ersten Lauf
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.plugins / "mst.agent-launchers").is_dir())

    def test_copy_widget_gets_migration_hint(self):
        (self.plugins / "mst.agent-launchers").mkdir(parents=True)  # Kopie aus dem alten Paket
        r = self.install(*BASE_ARGS)
        self.assertIn("omarchy plugin remove mst.agent-launchers", r.stdout)

    def test_existing_memory_gets_radar_placeholder_and_index_entry(self):
        mem = self.home / ".config" / "ai-agents"
        (mem / "handoff").mkdir(parents=True)
        (mem / "AGENTS.md").write_text("# Regeln\n\n- Radar: `handoff/omarchy-radar.md` lesen.\n")
        (mem / "AI_HANDOFF.md").write_text("# Index\n\n| Datei | Thema | Status |\n|---|---|---|\n")
        args = [a for a in BASE_ARGS if a != "--no-memory"]
        r = self.install(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((mem / "handoff" / "omarchy-radar.md").is_file())
        self.assertIn("| `handoff/omarchy-radar.md` |", (mem / "AI_HANDOFF.md").read_text())

    def _mirror(self):
        mirror = self.base / "drive" / "Maschinengedaechtnis"
        (mirror / "tools").mkdir(parents=True)
        (mirror / "AGENTS.md").write_text("# Regeln aus dem Spiegel\n")
        (mirror / "tools" / "memlint.py").write_text("raise SystemExit('fremdes memlint')\n")
        return mirror

    def test_mirror_is_not_restored_without_explicit_decision(self):
        # Sicherheitspruefung 2026-11-04: Der Spiegel liegt auf einem
        # Cloud-Laufwerk; AGENTS.md steuert alle Agenten.
        mirror = self._mirror()
        args = [a for a in BASE_ARGS if a != "--no-memory"] + ["--memory-mirror", str(mirror)]
        r = self.install(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        mem = self.home / ".config" / "ai-agents"
        self.assertNotIn("aus dem Spiegel", (mem / "AGENTS.md").read_text())
        self.assertIn("--memory-from-mirror", r.stdout)
        # Und der echte Spiegel wird nicht mit der frischen Vorlage ueberschrieben.
        self.assertTrue((mem / ".mirror-hold").exists())
        m = subprocess.run([str(REPO / "memory" / "tools" / "memory-mirror")], env=self.env,
                           capture_output=True, text=True, timeout=60)
        self.assertNotEqual(m.returncode, 0)
        self.assertIn("gesperrt", m.stderr)
        self.assertIn("Regeln aus dem Spiegel", (mirror / "AGENTS.md").read_text())

    def test_mirror_restore_never_brings_tools(self):
        mirror = self._mirror()
        args = [a for a in BASE_ARGS if a != "--no-memory"] + ["--memory-mirror", str(mirror), "--memory-from-mirror"]
        r = self.install(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        mem = self.home / ".config" / "ai-agents"
        self.assertIn("aus dem Spiegel", (mem / "AGENTS.md").read_text())
        self.assertEqual((mem / "tools" / "memlint.py").read_bytes(),
                         (REPO / "memory" / "tools" / "memlint.py").read_bytes())

    def _new_curator_yaml(self, *extra, lang="C.UTF-8"):
        self.env["LANG"] = lang
        args = [a for a in BASE_ARGS] + list(extra)
        r = self.install(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return (self.home / ".config" / "polaris" / "curator.yaml").read_text()

    def test_new_curator_yaml_language_from_system(self):
        self.assertIn("\nlanguage: en\n", self._new_curator_yaml())

    def test_new_curator_yaml_german_system_language(self):
        self.assertIn("\nlanguage: de\n", self._new_curator_yaml(lang="de_DE.UTF-8"))

    def test_language_option_wins(self):
        self.assertIn("\nlanguage: de\n", self._new_curator_yaml("--language", "de"))

    def test_existing_curator_yaml_untouched(self):
        cfg = self.home / ".config" / "polaris"
        cfg.mkdir(parents=True)
        (cfg / "curator.yaml").write_text("runtime: claude\n")
        r = self.install(*BASE_ARGS, "--language", "en")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((cfg / "curator.yaml").read_text(), "runtime: claude\n")

    def test_invalid_language_rejected(self):
        r = self.install(*BASE_ARGS, "--language", "fr")
        self.assertEqual(r.returncode, 2)


    # Vertrauensanker fuer polaris update (seit 2026-11-11, nach dem Vorschlag eines Nutzers)
    def test_trust_anchor_created_from_repo(self):
        r = self.install(*BASE_ARGS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        anchor = self.home / ".config/polaris/allowed_signers"
        self.assertEqual(anchor.read_text(), (REPO / "keys/allowed_signers").read_text())
        self.assertIn("SHA256:", r.stdout)

    def test_trust_anchor_never_replaced(self):
        anchor = self.home / ".config/polaris/allowed_signers"
        anchor.parent.mkdir(parents=True)
        anchor.write_text("eigener Anker\n")
        r = self.install(*BASE_ARGS, "--only-existing")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(anchor.read_text(), "eigener Anker\n")
        self.assertIn("NICHT ersetzt", r.stdout)

    def test_empty_trust_anchor_is_filled(self):
        # Fable 2026-11-11: leerer Anker war eine Sackgasse (update.sh: "fehlt",
        # install.sh: "weicht ab").
        anchor = self.home / ".config/polaris/allowed_signers"
        anchor.parent.mkdir(parents=True)
        anchor.write_text("")
        r = self.install(*BASE_ARGS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(anchor.read_text(), (REPO / "keys/allowed_signers").read_text())

    def test_repo_anchor_matches_documented_fingerprint(self):
        out = subprocess.run(["ssh-keygen", "-lf", "-"], input=" ".join(
            (REPO / "keys/allowed_signers").read_text().split()[2:4]), capture_output=True, text=True).stdout
        self.assertIn(out.split()[1], (REPO / "docs/install.md").read_text())


if __name__ == "__main__":
    unittest.main()
