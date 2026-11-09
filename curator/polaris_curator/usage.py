"""Nutzungszaehler (seit 2026-11-05): wie oft laeuft welcher Befehl bzw. welche
Funktion? Grundlage, um ungenutzten Code mit Beleg statt Bauchgefuehl zu
entfernen (Entschlackung; Nutzer: "alten ungenutzten Code entfernen, schon aus
Sicherheitsgruenden").

Nur Name, Anzahl und Zeitpunkt, nie Inhalte, Projekte oder Pfade.
Ablage: ~/.local/state/polaris/usage.json (lokal, nie hochgeladen). Lesen:
`cat ~/.local/state/polaris/usage.json`. Fehler werden verschluckt: der
Zaehler darf nie einen Lauf stoeren.

count(name): ein Aufruf = +1 (Befehle). mark(name): hoechstens +1 je Prozess
(Funktionen innerhalb eines Laufs; zaehlt "Laeufe, in denen X vorkam", ohne
die Datei je Datensatz neu zu schreiben). Seit 2026-11-07 (ADR 003) mit
Dateisperre, weil Bridge, Curator und Widget gleichzeitig zaehlen.
Bridge und Curator haben je eine Kopie dieses Moduls (bewusst unabhaengig,
wie storage.py); Format und Datei sind gleich.
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import time
from pathlib import Path

_MARKED: set[str] = set()


def path() -> Path:
    return Path.home() / ".local" / "state" / "polaris" / "usage.json"


def _bump(names, once_per_day: bool) -> None:
    if os.environ.get("POLARIS_USAGE_OFF"):  # Tests: Statistik nicht verfaelschen
        return
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p.with_name(p.name + ".lock"), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            if not isinstance(data, dict):
                data = {}
            now = time.strftime("%Y-%m-%d")
            changed = False
            for name in names:
                e = data.get(name) if isinstance(data.get(name), dict) else {}
                if once_per_day and e.get("last") == now:
                    continue
                data[name] = {"count": int(e.get("count", 0)) + 1, "first": e.get("first", now), "last": now}
                changed = True
            if not changed:
                return
            tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(tmp, p)
    except Exception:  # noqa: BLE001 - Zaehler darf nie stoeren
        pass


def count(name: str) -> None:
    _bump((name,), False)


def days(names) -> None:
    """Hoechstens +1 je Name und Kalendertag: count = Anzahl Tage, an denen
    der Name vorkam (seit 2026-11-08: Health-Warnungen je Pruefung, um
    Alarmmuedigkeit zu messen). Schreibt nur, wenn sich etwas aendert."""
    _bump(tuple(names), True)


def mark(name: str) -> None:
    if name in _MARKED:
        return
    _MARKED.add(name)
    count(name)


if __name__ == "__main__":  # Shell-Aufrufer (Widget): python3 -m ... usage <name>
    for _n in sys.argv[1:]:
        count(_n)
