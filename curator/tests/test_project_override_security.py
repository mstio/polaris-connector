"""Projekt-Overrides duerfen keine Befehle, Laufzeiten oder Modelle setzen.

Sicherheitspruefung 2026-11-04: Projektordner liegen oft auf einem
Cloud-Laufwerk, in das auch andere schreiben koennen. Ein
`.polaris/curator-config.yaml` mit `runtime: command` fuehrte frueher
beliebige Befehle als Nutzer aus.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401

from polaris_curator import config, llm


class TestProjectOverrideAllowList(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg_dir = self.tmp / "cfg"
        self.cfg_dir.mkdir()
        (self.cfg_dir / "curator.yaml").write_text("model: global-model\nruntime: codex\n", encoding="utf-8")
        self.project = self.tmp / "Projekt"
        (self.project / ".polaris").mkdir(parents=True)
        self.patches = [patch.object(config, "GLOBAL_CONFIG_DIR", self.cfg_dir),
                        patch.object(config, "GLOBAL_CONFIG_FILE", self.cfg_dir / "curator.yaml")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _override(self, text: str) -> None:
        (self.project / ".polaris" / "curator-config.yaml").write_text(text, encoding="utf-8")

    def test_command_runtime_from_project_is_ignored(self):
        marker = self.tmp / "pwned"
        self._override("runtime: command\n"
                       f"command: [sh, -c, 'touch {marker}; echo {{}}']\n"
                       "provider: evil\nmodel: evil-model\nreviewer_model: evil\n"
                       "claude_fallback_model: evil\ncommand_output_key: x\nlanguage: en\n")
        cfg = config.load_config(self.project)
        self.assertEqual(cfg.runtime, "codex")
        self.assertIsNone(cfg.command)
        self.assertEqual(cfg.model, "global-model")
        self.assertEqual(set(cfg.project_refused_keys),
                         {"runtime", "command", "provider", "model", "reviewer_model",
                          "claude_fallback_model", "command_output_key", "language"})
        self.assertTrue(any("nicht erlaubte Schluessel" in p for p in cfg.config_problems))
        # Und tatsaechlich wird nichts ausgefuehrt: ohne command keine Ausfuehrung.
        with self.assertRaises(llm.LlmUnavailableError):
            llm._run_command("x", "m", cfg)
        self.assertFalse(marker.exists())

    def test_allowed_keys_still_apply(self):
        self._override("budget:\n  max_batches_per_run: 2\ncontext:\n  index_cap: 0\n"
                       "compaction:\n  idle_backoff_max: 8\n")
        cfg = config.load_config(self.project)
        self.assertEqual(cfg.max_batches_per_run, 2)
        self.assertEqual(cfg.index_cap, 0.0)
        self.assertEqual(cfg.idle_backoff_max, 8)  # nur seltener als global (4) erlaubt
        self.assertEqual(cfg.project_refused_keys, ())

    def test_project_may_only_make_runs_cheaper(self):
        (self.cfg_dir / "curator.yaml").write_text(
            "budget:\n  max_llm_calls_per_run: 10\n  max_input_chars_per_batch: 50000\n"
            "compaction:\n  min_interval_days: 7\n", encoding="utf-8")
        self._override("budget:\n  max_llm_calls_per_run: 100000\n  max_input_chars_per_batch: 1000\n"
                       "compaction:\n  min_interval_days: 0\n")
        cfg = config.load_config(self.project)
        self.assertEqual(cfg.max_llm_calls_per_run, 10)          # nicht hoeher als global
        self.assertEqual(cfg.max_input_chars_per_batch, 1000)    # niedriger ist erlaubt
        self.assertEqual(cfg.compact_min_interval_days, 7)       # nicht haeufiger als global

    def test_garbage_values_are_reported_not_fatal(self):
        self._override("budget:\n  max_batches_per_run: {}\n")
        cfg = config.load_config(self.project)
        self.assertTrue(any("unlesbar" in p for p in cfg.config_problems))
        self.assertEqual(cfg.model, "global-model")

    def test_non_mapping_override_is_harmless(self):
        self._override("- runtime: command\n")
        cfg = config.load_config(self.project)
        self.assertEqual(cfg.runtime, "codex")

    def test_global_config_may_still_use_command_runtime(self):
        (self.cfg_dir / "curator.yaml").write_text("runtime: command\ncommand: [my-cli, '{model}']\n",
                                                   encoding="utf-8")
        cfg = config.load_config(self.project)
        self.assertEqual(cfg.runtime, "command")
        self.assertEqual(cfg.command, ["my-cli", "{model}"])

    def test_health_check_reports_refused_keys(self):
        from polaris_curator import systemhealth
        self._override("runtime: command\ncommand: [sh]\n")
        result = systemhealth.check_curation({"Projekt": self.project})
        self.assertEqual(result["level"], "warn")
        self.assertIn("nicht erlaubte Schluessel", str(result))
        self.assertIn("runtime", str(result))

if __name__ == "__main__":
    unittest.main()
