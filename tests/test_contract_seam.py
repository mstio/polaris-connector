"""Nahtstelle Bridge -> Curator (ADR 003, Stufe 1, Schritt 6).

Bridge- und Curator-Tests schrieben ihre Testdaten bisher je von Hand; eine
Abweichung im Format zwischen beiden blieb unsichtbar. Hier läuft jede
Beispieldatei aus tests/contracts/ durch die echte Bridge (Prüfung, Ablage
unter raw/) und wird mit dem echten Curator-Leser wieder gelesen.
"""
import json
import sys
import unittest
from pathlib import Path

from conftest_helpers import TempHome
from polaris import config, mapping, pipeline
from polaris.schema import validate_and_normalize

CURATOR_ROOT = Path(__file__).resolve().parents[1] / "curator"
if str(CURATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(CURATOR_ROOT))
from polaris_curator import chatgpt_source, state as state_mod  # noqa: E402

CONTRACTS = Path(__file__).resolve().parent / "contracts"
FIXTURES = sorted(CONTRACTS.glob("bridge-event-*.json"))


class TestBridgeCuratorSeam(unittest.TestCase):
    def test_fixtures_exist_for_every_source(self):
        sources = {json.loads(f.read_text(encoding="utf-8"))["source"] for f in FIXTURES}
        self.assertEqual(sources, {"chatgpt", "claude"})

    def test_bridge_accepts_fixture_unchanged_in_substance(self):
        for f in FIXTURES:
            event = json.loads(f.read_text(encoding="utf-8"))
            norm = validate_and_normalize(json.loads(f.read_text(encoding="utf-8")))
            with self.subTest(f.name):
                self.assertEqual(norm["message"]["id"], event["message"]["id"])
                self.assertEqual(norm["message"]["content"], event["message"]["content"])
                self.assertEqual(norm["source"], event["source"])

    def test_curator_reads_what_the_bridge_wrote(self):
        for f in FIXTURES:
            event = json.loads(f.read_text(encoding="utf-8"))
            with self.subTest(f.name), TempHome() as h:
                h.make_project_root(event["project"]["name"])
                (config.INBOX_DIR / "e.json").write_text(json.dumps(event), encoding="utf-8")
                counts = pipeline.process_inbox()
                self.assertEqual(counts["processed"], 1, counts)
                project = Path(mapping.load_store().get(event["project"]["id"]).local_path)
                msgs = chatgpt_source.load_new_messages(
                    project, state_mod.load_state(project), allowed_pids={event["project"]["id"]})
                self.assertEqual(len(msgs), 1)
                m = msgs[0]
                self.assertEqual(m.source, event["source"])
                self.assertIn(event["message"]["content"], m.content)
                self.assertEqual(m.conversation_id, event["conversation"]["id"])


if __name__ == "__main__":
    unittest.main()
