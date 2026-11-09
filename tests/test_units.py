"""systemd-Units: Eine durch polaris-awake bedingte Unit wird uebersprungen,
solange der Bildschirm gesperrt ist. Laeuft ihr Timer nur einmal am Tag
(nachts, Rechner gesperrt), faellt sie dauerhaft aus – so lief der
Sicherheitsabgleich des Radars vom 05.11. bis 08.11.2026 nie (Health gelb
„zuletzt geprueft vor 3 Tagen“). Bedingte Units brauchen einen Timer, der
bald erneut versucht."""
import re
import unittest
from pathlib import Path

UNITS = Path(__file__).resolve().parents[1] / "systemd"


GATE = re.compile(r"^ExecCondition=.*polaris-awake", re.M)


class TestAwakeGatedUnits(unittest.TestCase):
    def test_gated_units_retry_soon(self):
        gated = [s for s in UNITS.glob("*.service") if GATE.search(s.read_text())]
        self.assertTrue(gated)  # Bridge und Spiegel sind bedingt
        for service in gated:
            timer = service.with_suffix(".timer")
            if not timer.exists():
                continue  # nur per .path oder von Hand gestartet
            self.assertRegex(timer.read_text(), re.compile(r"^OnUnit(In)?[Aa]ctiveSec=", re.M),
                             f"{service.name}: bedingt, aber {timer.name} versucht nicht bald erneut")

    def test_radar_touches_no_cloud_drive_and_is_not_gated(self):
        # polaris-awake schuetzt vor haengenden FUSE-Zugriffen beim Einschlafen;
        # der Radar liest nur lokale Dateien und das Netz.
        self.assertNotRegex((UNITS / "polaris-radar.service").read_text(), GATE)


if __name__ == "__main__":
    unittest.main()
