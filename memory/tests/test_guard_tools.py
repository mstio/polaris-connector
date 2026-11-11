"""Tests fuer memory/tools/claude-guard-hook.py und claude-guard-einschalten.sh (seit 2026-11-05)."""

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
HOOK = TOOLS / "claude-guard-hook.py"
ENABLE = TOOLS / "claude-guard-einschalten.sh"
SNAP = TOOLS / "home-snapshots-einrichten.sh"


class TestGuardHook(unittest.TestCase):
    def setUp(self):
        # Nicht unter /tmp: /tmp ist selbst Fremdinhalt und wuerde jeden Fall tainten (Fable 2026-11-05).
        base = Path.home() / ".cache"
        base.mkdir(exist_ok=True)
        self.home = Path(tempfile.mkdtemp(dir=base, prefix="guard-test-"))
        self.addCleanup(shutil.rmtree, self.home, True)
        (self.home / ".config" / "polaris").mkdir(parents=True)
        self.root = self.home / "Kunden"
        (self.home / ".config" / "polaris" / "config.yaml").write_text(f"project_roots: ['{self.root}']\n")

    def hook(self, event, tool, ti=None, level="streng", sid="s1", extra_env=None, cwd=None):
        data = {"hook_event_name": event, "session_id": sid, "tool_name": tool, "tool_input": ti or {}}
        if cwd:
            data["cwd"] = cwd
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_GUARD_UNTRUSTED"}
        env.update({"HOME": str(self.home), "CLAUDE_GUARD_LEVEL": level, **(extra_env or {})})
        r = subprocess.run(["python3", "-I", str(HOOK)], input=json.dumps(data), env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] if r.stdout.strip() else None

    def test_fachsystem_write_always_asks(self):
        self.assertEqual(self.hook("PreToolUse", "mcp__x__mail_schreiben", level="standard"), "ask")
        self.assertEqual(self.hook("PreToolUse", "mcp__x__vorgaenge", {"aktion": "aendern"}, level="standard"), "ask")
        self.assertIsNone(self.hook("PreToolUse", "mcp__x__vorgaenge", {"aktion": "suchen"}, level="standard"))

    def test_taint_from_polaris_root_then_ask(self):
        self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": "ls"}))
        self.hook("PostToolUse", "Read", {"file_path": str(self.root / "a" / "mail.md")})
        self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}), "ask")
        self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": "ls"}, sid="andere"))

    def test_taint_tilde_path_in_bash(self):
        self.hook("PostToolUse", "Bash", {"command": "cat ~/Kunden/x/mail.eml"})
        self.assertEqual(self.hook("PreToolUse", "Write", {"file_path": "/x"}), "ask")

    def test_standard_level_does_not_ask_after_taint(self):
        self.hook("PostToolUse", "WebFetch", {"url": "https://example.org"})
        self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": "ls"}, level="standard"))

    def test_extra_untrusted_paths(self):
        self.hook("PostToolUse", "Read", {"file_path": "/srv/inbox/x"}, extra_env={"CLAUDE_GUARD_UNTRUSTED": "/srv/inbox"})
        self.assertEqual(self.hook("PreToolUse", "Edit", {"file_path": "/y"}), "ask")

    def test_audit_log_private_and_garbage_input_fails_open(self):
        self.hook("PreToolUse", "Bash", {"command": "echo hi"})
        log = self.home / ".claude" / "guard" / "audit.jsonl"
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        self.assertIn("echo hi", log.read_text())
        r = subprocess.run(["python3", str(HOOK)], input="kein json", capture_output=True, text=True,
                           env={**os.environ, "HOME": str(self.home)})
        self.assertEqual(r.returncode, 0)
        # fail-closed: kaputte Eingabe -> Rueckfrage statt still durchlassen
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_guard_dir_replaced_by_file_asks(self):
        guard = self.home / ".claude" / "guard"
        guard.parent.mkdir(parents=True, exist_ok=True)
        guard.write_text("kein Ordner")
        self.assertEqual(self.hook("PreToolUse", "mcp__x__mail_schreiben", level="standard"), "ask")
        self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}, level="standard"), "ask")

    def test_self_protection_always_asks(self):
        for tool, ti in [("Edit", {"file_path": str(self.home / ".claude" / "settings.json")}),
                         ("Write", {"file_path": str(self.home / ".config/ai-agents/tools/claude-guard-hook.py")}),
                         ("Write", {"file_path": str(self.home / ".config/polaris/config.yaml")}),
                         ("Edit", {"file_path": str(self.home / ".config/polaris/radar.yaml")}),
                         ("Bash", {"command": "echo x >> ~/.config/polaris/radar.yaml"}),
                         ("Bash", {"command": "cd ~/.config/polaris && echo x >> radar.yaml"}),
                         # Vertrauensanker fuer Updates (Fable 2026-11-11)
                         ("Write", {"file_path": str(self.home / ".config/polaris/allowed_signers")}),
                         ("Bash", {"command": "cp keys/allowed_signers ~/.config/polaris/allowed_signers"}),
                         ("Bash", {"command": "cd ~/.config/polaris && cp /tmp/k allowed_signers"}),
                         ("Bash", {"command": "rm -rf ~/.claude/guard"}),
                         ("Bash", {"command": "sed -i s/x/y/ ~/.claude/settings.local.json"})]:
            self.assertEqual(self.hook("PreToolUse", tool, ti, level="standard"), "ask", (tool, ti))
        self.assertIsNone(self.hook("PreToolUse", "Edit", {"file_path": "/x/y.py"}, level="standard"))

    def test_taint_sources_found_by_fable(self):
        cases = [("Bash", {"command": "cat $HOME/Downloads/x"}, None),
                 ("Bash", {"command": "gh pr view 1"}, None),
                 ("Bash", {"command": "git pull"}, None),
                 ("Grep", {"pattern": "x"}, str(self.root / "p")),
                 ("Read", {"file_path": "mail.md"}, str(self.root / "p")),
                 ("mcp__x__vorgaenge", {"aktion": "suchen"}, None),
                 ("Monitor", {"command": "tail -f x"}, None)]
        for i, (tool, ti, cwd) in enumerate(cases):
            sid = f"t{i}"
            self.hook("PostToolUse", tool, ti, sid=sid, cwd=cwd)
            self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}, sid=sid), "ask", (tool, ti))
        self.hook("PostToolUse", "mcp__x__vorgaenge", {}, sid="tr",
                  extra_env={"CLAUDE_GUARD_TRUSTED_MCP": "__vorgaenge$"})
        self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": "ls"}, sid="tr"))

    def test_exfil_tools_ask_after_taint(self):
        self.hook("PostToolUse", "WebFetch", {"url": "https://example.org"})
        for tool in ("WebSearch", "Monitor", "Artifact", "SendMessage"):
            self.assertEqual(self.hook("PreToolUse", tool, {}), "ask", tool)
        self.assertIsNone(self.hook("PreToolUse", "Read", {"file_path": "/x"}))

    def test_polaris_own_foreign_text_taints(self):
        # Gremium 2026-11-11 (Fable): Polaris' eigene Ablagen fuer Fremdtext
        # (Quarantaene, abgelehnte/verarbeitete Chats, Radar) galten als sauber.
        cases = [".local/share/polaris/quarantine/q.json", ".local/share/polaris/processed/a.json",
                 ".local/share/polaris/failed/b.json", ".local/share/polaris/conflicts/c.json",
                 ".config/ai-agents/handoff/omarchy-radar.md", ".local/state/polaris/radar.json"]
        for i, rel in enumerate(cases):
            sid = f"p{i}"
            self.hook("PostToolUse", "Read", {"file_path": str(self.home / rel)}, sid=sid)
            self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}, sid=sid), "ask", rel)

    def test_polaris_program_code_does_not_taint(self):
        self.hook("PostToolUse", "Read", {"file_path": str(self.home / ".local/share/polaris/app/update.sh")})
        self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": "ls"}))

    def test_unreadable_polaris_config_fails_closed(self):
        # Fable 2026-11-11: kaputte config.yaml ergab still "keine Projektwurzeln".
        (self.home / ".config" / "polaris" / "config.yaml").write_text("project_roots: [unbalanced\n")
        self.hook("PostToolUse", "Read", {"file_path": str(self.home / "Irgendwo" / "kunde.md")})
        self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}), "ask")

    def test_more_polaris_settings_are_protected(self):
        for rel in (".config/polaris/curator.yaml", ".config/polaris/projects.yaml", ".config/polaris/canary",
                    ".config/systemd/user/polaris-curator.service.d/x.conf", ".config/omarchy/defaults/agent"):
            self.assertEqual(self.hook("PreToolUse", "Write", {"file_path": str(self.home / rel)}, level="standard"),
                             "ask", rel)
        self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "cd ~/.config/polaris && sed -i s/a/b/ curator.yaml"},
                                   level="standard"), "ask")
        self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "systemctl --user edit polaris-curator"},
                                   level="standard"), "ask")

    def test_unit_and_environment_gaps_found_by_fable(self):
        # Gremium 2026-11-11 (Fable, 2. Runde, M5)
        asks = [("Bash", {"command": "systemctl --user stop polaris-curator.timer"}),
                ("Bash", {"command": "systemctl --user kill polaris-bridge.service"}),
                ("Write", {"file_path": str(self.home / ".config/environment.d/x.conf"), "content": "A=1"}),
                ("Write", {"file_path": str(self.home / ".config/systemd/user/service.d/x.conf"), "content": "A=1"}),
                ("Write", {"file_path": "/irgendwo/x.conf", "content": "Environment=POLARIS_NO_SANDBOX=1"}),
                ("Edit", {"file_path": "/irgendwo/x.conf", "new_string": "POLARIS_NO_SANDBOX=1"}),
                ("Write", {"file_path": str(self.home / ".local/bin/bwrap"), "content": "x"}),
                ("Write", {"file_path": str(self.home / ".local/share/polaris/app/curator/x.py"), "content": "x"}),
                ("Bash", {"command": "rm ~/.local/state/polaris/sandbox-last-run.json"}),
                ("Bash", {"command": "systemctl --user set-environment POLARIS_NO_SANDBOX=1"}),
                ("Bash", {"command": "cd ~/.config/systemd/user && echo x > polaris-curator.service.d/x.conf"})]
        for tool, ti in asks:
            self.assertEqual(self.hook("PreToolUse", tool, ti, level="standard"), "ask", (tool, ti))

    def test_round_two_findings(self):
        # Fable 2026-11-11, 2. Nachpruefung (R1, R2, R4, R5, R6)
        asks = ["echo 'export POLARIS_NO_SANDBOX=1' >> ~/.bashrc",
                "dbus-update-activation-environment --systemd POLARIS_NO_SANDBOX=1",
                "systemctl --user \\\nstop polaris-radar.timer",
                "cd ~/.config/systemd/user && rm polaris-radar.timer",
                "cp /x/y ~/.local/share/polaris/app/update.sh"]
        for cmd in asks:
            self.assertEqual(self.hook("PreToolUse", "Bash", {"command": cmd}, level="standard"), "ask", cmd)
        quiet = ["cat ~/.local/share/polaris/app/docs/AGENTEN-LEITFADEN.md",
                 "git -C ~/.local/share/polaris/app log -3",
                 "ls ~/.config/systemd/user 2>/dev/null", "systemctl --user status polaris-radar.timer"]
        for cmd in quiet:
            self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": cmd}, level="standard"), cmd)
        self.assertIsNone(self.hook("PreToolUse", "Edit", {"file_path": "/repo/curator/polaris_curator/sandbox.py",
                                                           "new_string": "POLARIS_NO_SANDBOX"}, level="standard"))
        self.assertEqual(self.hook("PreToolUse", "Edit", {"file_path": str(self.home / ".bashrc"),
                                                          "new_string": "export POLARIS_NO_SANDBOX=1"},
                                   level="standard"), "ask")
        self.hook("PostToolUse", "Bash", {"command": "grep -rn foo $HOME/.config/ai-agents/"}, sid="r6")
        self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}, sid="r6"), "ask")
        self.hook("PostToolUse", "Bash", {"command": "grep -n polaris-radar README.md"}, sid="r2")
        self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": "ls"}, sid="r2"))

    def test_fewer_false_alarms(self):
        # Fable 2026-11-11 (M7): harmlose Befehle im Repo fragten nach.
        repo = "/home/u/Projects/polaris-chatgpt-connector"
        for cmd in ("grep -rn POLARIS_NO_SANDBOX curator/", "POLARIS_NO_SANDBOX=1 python3 -m unittest tests.test_e2e",
                    f"cd {repo} && grep -n config.yaml README.md", f"grep -n canary {repo}/docs/x.md",
                    "systemctl --user status polaris-curator.timer"):
            self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": cmd}, level="standard"), cmd)

    def test_taint_via_parent_dirs_and_tools(self):
        # Fable 2026-11-11 (M6)
        cases = [("Bash", {"command": "grep -rn foo ~/.config/ai-agents/handoff/"}, None),
                 ("Grep", {"pattern": "x", "path": str(self.home / ".local/share/polaris")}, None),
                 ("Bash", {"command": "polaris-radar --show"}, None),
                 ("Bash", {"command": "polaris-curator quarantine show 1"}, None),
                 ("Read", {"file_path": str(self.home / ".local/state/polaris/journals/j.json")}, None)]
        for i, (tool, ti, cwd) in enumerate(cases):
            sid = f"m{i}"
            self.hook("PostToolUse", tool, ti, sid=sid, cwd=cwd)
            self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}, sid=sid), "ask", (tool, ti))

    def test_read_outside_untrusted_does_not_taint(self):
        self.hook("PostToolUse", "Read", {"file_path": str(self.home / "eigenes" / "notiz.md")})
        self.assertIsNone(self.hook("PreToolUse", "Bash", {"command": "ls"}))

    def test_wiping_claude_dir_asks(self):
        for cmd in ("rm -rf ~/.claude", "mv ~/.claude /x", "find ~/.claude -delete"):
            self.assertEqual(self.hook("PreToolUse", "Bash", {"command": cmd}, level="standard"), "ask", cmd)

    def test_dangling_symlink_guard_dir_reported_as_tampering(self):
        g = self.home / ".claude" / "guard"
        g.parent.mkdir(parents=True, exist_ok=True)
        g.symlink_to(self.home / "nirgends")
        r = subprocess.run(["python3", "-I", str(HOOK)], capture_output=True, text=True,
                           input=json.dumps({"hook_event_name": "PreToolUse", "session_id": "s", "tool_name": "Bash",
                                             "tool_input": {"command": "ls"}}), env={**os.environ, "HOME": str(self.home)})
        self.assertIn("manipuliert", r.stdout)

    def test_invalid_trusted_regex_is_reported(self):
        self.assertEqual(self.hook("PreToolUse", "Bash", {"command": "ls"}, level="standard",
                                   extra_env={"CLAUDE_GUARD_TRUSTED_MCP": "("}), "ask")

    def test_old_markers_pruned(self):
        guard = self.home / ".claude" / "guard"
        guard.mkdir(parents=True)
        old = guard / "alt.tainted"
        old.write_text("x")
        os.utime(old, (1, 1))
        self.hook("PostToolUse", "WebFetch", {"url": "https://example.org"}, sid="neu")
        self.assertFalse(old.exists())
        self.assertTrue((guard / "neu.tainted").exists())


class TestGuardEnable(unittest.TestCase):
    def test_enable_strict_off_roundtrip(self):
        home = Path(tempfile.mkdtemp())
        (home / ".claude").mkdir()
        orig = {"theme": "dark", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}}
        f = home / ".claude" / "settings.json"
        f.write_text(json.dumps(orig))
        env = {**os.environ, "HOME": str(home)}
        for level in ("standard", "streng"):
            time.sleep(1.05)  # Sicherung je Sekunde, zweite in derselben Sekunde wird abgelehnt
            subprocess.run([str(ENABLE), level], env=env, check=True, capture_output=True)
            d = json.loads(f.read_text())
            pre = d["hooks"]["PreToolUse"]
            self.assertEqual(len(pre), 1)
            self.assertIn(f"CLAUDE_GUARD_LEVEL={level} python3 -I ", pre[0]["hooks"][0]["command"])
            self.assertEqual(pre[0]["hooks"][0]["onFailure"], "block")
            self.assertNotIn("onFailure", d["hooks"]["PostToolUse"][0]["hooks"][0])
            self.assertIn("PostToolUse", d["hooks"])
        time.sleep(1.05)
        subprocess.run([str(ENABLE), "aus"], env=env, check=True, capture_output=True)
        self.assertEqual(json.loads(f.read_text()), orig)
        self.assertTrue(list((home / ".claude").glob("settings.json.bak-*")))
        r = subprocess.run([str(ENABLE), "quatsch"], env=env, capture_output=True)
        self.assertEqual(r.returncode, 2)


class TestSnapshotScript(unittest.TestCase):
    def test_syntax_and_no_fixed_private_units(self):
        subprocess.run(["bash", "-n", str(SNAP)], check=True)
        text = SNAP.read_text()
        self.assertNotIn("rclone-projekte", text)
        self.assertIn("mv -T --exchange", text)

    def test_root_steps_single_call_and_pkexec(self):
        # Alle root-Schritte in einem Aufruf; --pkexec statt sudo (Rueckmeldung von bernhard2804, 2026-11-05).
        text = SNAP.read_text()
        self.assertNotIn("run sudo ", text)
        self.assertIn('"$ROOT" /usr/bin/bash -c "$ROOT_STEPS"', text)
        r = subprocess.run(["bash", str(SNAP), "--unbekannt"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--pkexec", r.stderr)


if __name__ == "__main__":
    unittest.main()
