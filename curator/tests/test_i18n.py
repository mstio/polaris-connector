"""Zweisprachiger Health Check (i18n.py, seit 2026-11-04)."""

import ast
import os
import string
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import conftest_helpers  # noqa: F401 - sys.path, POLARIS_LANG=de

import yaml

from polaris_curator import config, i18n, systemhealth as sh

PKG = Path(__file__).resolve().parents[1] / "polaris_curator"


def _t_literals(path: Path) -> list[str]:
    """Erste Argumente aller t()-Aufrufe (bzw. zweite bei t_lang): Literale
    oder Modulkonstanten. Andere Argumente (Variablen) werden gesondert
    geprueft (GROUPS, RECLAIM_CANDIDATES)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    consts = {tg.id: node.value.value for node in tree.body if isinstance(node, ast.Assign)
              and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
              for tg in node.targets if isinstance(tg, ast.Name)}
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        idx = {"t": 0, "t_lang": 1}.get(name)
        if idx is None or len(node.args) <= idx:
            continue
        arg = node.args[idx]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append(arg.value)
        elif isinstance(arg, ast.Name) and arg.id in consts:
            found.append(consts[arg.id])
    return found


def _fields(s: str) -> list[str]:
    return sorted(f for _lit, f, _spec, _conv in string.Formatter().parse(s) if f)


class TestLanguageSelection(unittest.TestCase):
    def setUp(self):
        i18n.reset_cache()
        self.addCleanup(i18n.reset_cache)
        self.dir = Path(tempfile.mkdtemp())
        self.cfg_file = self.dir / "curator.yaml"
        for name, value in (("GLOBAL_CONFIG_DIR", self.dir), ("GLOBAL_CONFIG_FILE", self.cfg_file)):
            p = patch.object(config, name, value)
            p.start()
            self.addCleanup(p.stop)

    def _without_env(self):
        env = {k: v for k, v in os.environ.items() if k != "POLARIS_LANG"}
        return patch.dict(os.environ, env, clear=True)

    def test_missing_key_means_german(self):
        self.cfg_file.write_text("model: x\n", encoding="utf-8")
        with self._without_env():
            self.assertEqual(i18n.language(), "de")
            self.assertEqual(config.load_config().config_problems, ())

    def test_config_value_en(self):
        self.cfg_file.write_text("language: EN\n", encoding="utf-8")
        with self._without_env():
            self.assertEqual(i18n.language(), "en")

    def test_env_wins_over_config(self):
        self.cfg_file.write_text("language: en\n", encoding="utf-8")
        with patch.dict(os.environ, {"POLARIS_LANG": "de"}):
            self.assertEqual(i18n.language(), "de")

    def test_invalid_value_is_german_plus_problem(self):
        self.cfg_file.write_text("language: fr\n", encoding="utf-8")
        with self._without_env():
            cfg = config.load_config()
            self.assertEqual(cfg.language, "de")
            self.assertEqual(len(cfg.config_problems), 1)
            self.assertIn("language", cfg.config_problems[0])
            self.assertIn("fr", cfg.config_problems[0])
            self.assertEqual(i18n.language(), "de")

    def test_invalid_language_survives_chat_sources_problem(self):
        self.cfg_file.write_text("language: fr\nmonitoring:\n  chat_sources: [grok]\n", encoding="utf-8")
        with self._without_env():
            cfg = config.load_config()
        self.assertEqual(len(cfg.config_problems), 2)
        self.assertIn("language", cfg.config_problems[0])
        self.assertIn("grok", cfg.config_problems[1])

    def test_problem_shown_by_health_check(self):
        self.cfg_file.write_text("language: 42\n", encoding="utf-8")
        with self._without_env():
            c = sh.check_config(config.load_config().config_problems)
        self.assertEqual(c["level"], "error")
        self.assertIn("language", c["detail"])

    def test_new_default_config_is_english(self):
        config.ensure_global_config()
        text = self.cfg_file.read_text(encoding="utf-8")
        self.assertIn("# Language of the widget and health check: en or de", text)
        self.assertEqual(yaml.safe_load(text)["language"], "en")
        self.assertEqual(yaml.safe_load(text)["model"], config.DEFAULT_MODEL)
        with self._without_env():
            self.assertEqual(i18n.language(), "en")

    def test_existing_config_not_rewritten(self):
        self.cfg_file.write_text("model: x\n", encoding="utf-8")
        config.ensure_global_config()
        self.assertEqual(self.cfg_file.read_text(encoding="utf-8"), "model: x\n")


class TestTranslation(unittest.TestCase):
    def setUp(self):
        i18n.reset_cache()
        self.addCleanup(i18n.reset_cache)

    def test_german_default_unchanged(self):
        self.assertEqual(sh._fmt_age(None), "nie")
        self.assertEqual(sh._fmt_age(3.2), "vor 3 Tag(en)")
        self.assertEqual(sh._fmt_size(int(1.5 * 2**30)), "1,5 GB")
        self.assertEqual(sh.check_config(("x",))["label"], "Chatquellen-Konfiguration")
        groups = sh.group_components([sh._c("memory", "Maschinengedächtnis", "ok", "konsistent")])
        self.assertEqual(groups[0]["label"], "Maschinengedächtnis")

    def test_english_labels(self):
        with patch.dict(os.environ, {"POLARIS_LANG": "en"}):
            self.assertEqual(sh._fmt_age(3.2), "3 day(s) ago")
            self.assertEqual(sh._fmt_size(int(1.5 * 2**30)), "1.5 GB")
            self.assertEqual(sh.check_config(("x",))["label"], "Chat source configuration")
            checks = [sh._c("curator", "Curator", "ok", "a"), sh._c("llm", sh.t("Modell"), "ok", "b")]
            group = sh.group_components(checks)[0]
            self.assertEqual(group["detail"], "Timer, Model OK – a")
            with patch.object(sh, "SECURITY_STATE", Path(tempfile.mkdtemp()) / "missing.json"):
                c = sh.check_security(sh.datetime.now(sh.timezone.utc))
            self.assertEqual((c["label"], c["detail"]), ("Security", "not checked yet – polaris-radar"))

    def test_collect_carries_language(self):
        stub = sh._c("x", "X", "ok", "")
        patches = [patch.object(sh, name, return_value=dict(stub, id=cid)) for name, cid in (
            ("check_separation", "separation"), ("check_curator_timer", "curator"), ("check_llm", "llm"),
            ("check_backup", "backup"), ("check_mount", "mount"), ("check_memory", "memory"))]
        patches += [patch.object(sh, "check_update", return_value=None),
                    patch.object(sh, "check_widget", return_value=None),
                    patch.object(sh, "check_system", return_value=[]),
                    patch.object(sh, "SECURITY_STATE", Path(tempfile.mkdtemp()) / "missing.json"),
                    patch.dict(os.environ, {"POLARIS_LANG": "en"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        data = sh.collect({}, 3, chat_sources=())
        self.assertEqual(data["language"], "en")
        self.assertIn("Security", [c["label"] for c in data["components"]])

    def test_missing_translation_falls_back_to_german(self):
        self.assertEqual(i18n.t_lang("en", "gibt es nicht {n}", n=1), "gibt es nicht 1")

    def test_every_german_string_has_english_entry(self):
        missing = []
        for name in ("systemhealth.py", "health.py", "cli.py", "config.py"):
            missing += [(name, s) for s in _t_literals(PKG / name) if s not in i18n.EN]
        # Werte, die erst zur Laufzeit an t() gehen.
        for _gid, label, parts, _p in sh.GROUPS:
            missing += [("GROUPS", s) for s in [label, *(n for n, _ in parts)] if s not in i18n.EN]
        missing += [("RECLAIM", label) for label, _p, _h in sh.RECLAIM_CANDIDATES if label not in i18n.EN]
        self.assertEqual(missing, [])

    def test_placeholders_match(self):
        bad = [(de, en) for de, en in i18n.EN.items() if _fields(de) != _fields(en)]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
