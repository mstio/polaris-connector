import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import conftest_helpers  # noqa: F401

from polaris_curator import config


class TestChatSources(unittest.TestCase):
    def test_explicit_sources_are_independent_of_runtime(self):
        cfg = config.CuratorConfig(runtime="command").merged_with({"monitoring": {"chat_sources": []}})
        self.assertEqual(cfg.chat_sources, ())
        self.assertEqual(cfg.runtime, "command")
        self.assertEqual(config.CuratorConfig().merged_with(
            {"monitoring": {"chat_sources": ["claude"]}}).chat_sources, ("claude",))

    def test_unknown_source_is_reported_not_fatal(self):
        cfg = config.CuratorConfig().merged_with({"monitoring": {"chat_sources": ["grok", "claude"]}})
        self.assertEqual(cfg.chat_sources, ("claude",))
        self.assertTrue(cfg.chat_sources_explicit)
        self.assertEqual(len(cfg.config_problems), 1)
        self.assertIn("grok", cfg.config_problems[0])

    def test_case_and_duplicates_are_tolerated(self):
        cfg = config.CuratorConfig().merged_with({"monitoring": {"chat_sources": [" ChatGPT", "chatgpt", "Claude"]}})
        self.assertEqual(cfg.chat_sources, ("chatgpt", "claude"))
        self.assertEqual(cfg.config_problems, ())

    def test_non_list_falls_back_to_both_with_problem(self):
        cfg = config.CuratorConfig().merged_with({"monitoring": {"chat_sources": "claude"}})
        self.assertEqual(cfg.chat_sources, ("chatgpt", "claude"))
        self.assertEqual(len(cfg.config_problems), 1)

    def test_without_key_sources_are_implicit(self):
        cfg = config.CuratorConfig().merged_with({"monitoring": {"max_days_without_claude": 7}})
        self.assertFalse(cfg.chat_sources_explicit)
        self.assertEqual(cfg.chat_sources, ("chatgpt", "claude"))


class TestKnownProjectsDedup(unittest.TestCase):
    def test_one_entry_per_folder_chatgpt_id_preferred(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "MusterFirma").mkdir()
        (tmp / "Falke").mkdir()
        f = tmp / "projects.yaml"
        f.write_text(yaml.safe_dump({"projects": {
            "claude-p-coo": {"local_path": str(tmp / "MusterFirma"), "status": "ok"},
            "g-p-muster": {"local_path": str(tmp / "MusterFirma"), "status": "ok"},
            "claude-p-verw": {"local_path": str(tmp / "MusterFirma"), "status": "ok"},
            "g-p-falke": {"local_path": str(tmp / "Falke"), "status": "ok"},
            "g-p-weg": {"local_path": str(tmp / "Gibtsnicht"), "status": "ok"},
        }}))
        with patch.object(config, "PROJECTS_FILE", f):
            known = config.list_known_projects()
        self.assertEqual(sorted(known), ["g-p-falke", "g-p-muster"])


if __name__ == "__main__":
    unittest.main()
