"""Tests fuer claude-sitzungen (ohne Netz, ohne fzf; erfundene Sitzungen in einem Temp-Home).

Aufruf: python3 -m unittest discover -s experiments/claude-sitzungen
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent / "claude-sitzungen"
ID_A = "11111111-1111-4111-8111-111111111111"
ID_B = "22222222-2222-4222-8222-222222222222"
ID_C = "33333333-3333-4333-8333-333333333333"
ID_D = "44444444-4444-4444-8444-444444444444"


def lade(home):
    """Skript als Modul laden; Pfade werden beim Import aus HOME/Umgebung gelesen."""
    env = {"HOME": home, "CLAUDE_CONFIG_DIR": os.path.join(home, ".claude"),
           "XDG_CACHE_HOME": os.path.join(home, ".cache")}
    with mock.patch.dict(os.environ, env):
        loader = importlib.machinery.SourceFileLoader("claude_sitzungen", str(SCRIPT))
        spec = importlib.util.spec_from_loader("claude_sitzungen", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    return mod


def zeile(**kw):
    return json.dumps(kw, separators=(",", ":")) + "\n"  # kompakt wie Claude Code


def sitzung(home, sid, cwd, eintraege):
    ordner = Path(home, ".claude", "projects", cwd.replace("/", "-"))
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{sid}.jsonl").write_text("".join(eintraege))


def user(text, cwd, ts="2026-11-01T10:00:00Z", **kw):
    return zeile(type="user", cwd=cwd, timestamp=ts, message={"role": "user", "content": text}, **kw)


def antwort(text, cwd, ts="2026-11-01T10:01:00Z"):
    return zeile(type="assistant", cwd=cwd, timestamp=ts,
                 message={"role": "assistant", "content": [{"type": "text", "text": text}]})


class ClaudeSitzungenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.arbeit = os.path.join(self.home, "Arbeit")
        os.makedirs(self.arbeit)
        a = self.arbeit
        sitzung(self.home, ID_A, a, [
            user("<system-reminder>Gedaechtnis mit Kunde-A</system-reminder>Wie richte ich den Drucker ein?", a),
            antwort("So geht das mit dem Drucker.", a),
            zeile(type="ai-title", aiTitle="Drucker\x1b]0;boese\x07 einrichten"),
            user("Und der Scanner?", a, ts="2026-11-02T09:00:00Z"),
        ])
        # Ordner existiert nicht mehr -> nicht fortsetzbar, nicht gelistet
        sitzung(self.home, ID_B, os.path.join(self.home, "weg"), [
            user("Alte Frage", os.path.join(self.home, "weg"))])
        # nur Slash-Befehl, keine echte Eingabe -> nicht gelistet
        sitzung(self.home, ID_C, a, [user("<command-name>/login</command-name>", a)])
        # Ordner ausserhalb des Home -> nicht gelistet, nicht oeffenbar
        sitzung(self.home, ID_D, "/tmp", [user("Frage in /tmp", "/tmp")])
        self.m = lade(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_filtert_und_wertet_aus(self):
        e = {x["id"]: x for x in self.m.index()}
        self.assertEqual(set(e), {ID_A})
        a = e[ID_A]
        self.assertEqual(a["fragen"], 2)
        self.assertEqual(a["erste"], "Wie richte ich den Drucker ein?")  # system-reminder entfernt
        self.assertEqual(a["letzte"], "Und der Scanner?")
        self.assertEqual(a["cwd"], self.arbeit)

    def test_steuerzeichen_im_titel_werden_entfernt(self):
        z = self.m.zeilen(self.m.index())
        self.assertEqual(len(z), 1)
        self.assertNotIn("\x1b]", z[0])
        self.assertNotIn("\x07", z[0])
        self.assertIn("Drucker]0;boese einrichten", z[0])
        self.assertTrue(z[0].startswith(ID_A + "\t"))

    def test_cache_wird_wiederverwendet(self):
        self.m.index()
        with mock.patch.object(self.m, "auswerten", side_effect=AssertionError("neu ausgewertet")):
            self.assertEqual(len(self.m.index()), 1)

    def test_inhaltssuche_ignoriert_system_reminder(self):
        _, t = self.m.inhaltssuche("Kunde-A")
        self.assertEqual(t, {})
        e, t = self.m.inhaltssuche("drucker")
        self.assertEqual(t, {ID_A: 2})  # Frage + Antwort, Titel zaehlt nicht
        self.assertEqual([x["id"] for x in e], [ID_A])

    def test_oeffnen_nur_mit_gueltiger_id_und_ordner(self):
        with mock.patch.object(self.m.subprocess, "Popen") as popen, \
                mock.patch.object(self.m, "melden") as melden, \
                mock.patch.object(self.m, "offene", return_value={}):
            self.m.oeffnen("../../etc/passwd")
            self.m.oeffnen(ID_D)
            self.m.oeffnen(ID_B)
            popen.assert_not_called()
            self.assertEqual(melden.call_count, 3)
            self.m.oeffnen(ID_A, abzweig=True)
            popen.assert_called_once()
            args, kw = popen.call_args
            self.assertEqual(args[0][-4:], ["claude", "--resume", ID_A, "--fork-session"])
            self.assertEqual(kw["cwd"], self.arbeit)
            self.assertFalse(any(k.startswith("CLAUDE_CODE_") for k in kw["env"]))

    def test_offene_sitzung_wird_fokussiert_statt_doppelt_geoeffnet(self):
        with mock.patch.object(self.m.subprocess, "Popen") as popen, \
                mock.patch.object(self.m, "offene", return_value={ID_A: 4242}), \
                mock.patch.object(self.m, "fenster_zu_pid", return_value="0xabc"), \
                mock.patch.object(self.m.subprocess, "run") as run:
            self.m.oeffnen(ID_A)
            popen.assert_not_called()
            self.assertIn("address:0xabc", run.call_args[0][0][-1])


if __name__ == "__main__":
    unittest.main()
