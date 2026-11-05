"""Nutzungszaehler (seit 2026-11-05): wie oft laeuft welcher Befehl bzw. welche
Funktion? Grundlage, um ungenutzten Code mit Beleg statt Bauchgefuehl zu
entfernen (Entschlackung; Nutzer: "alten ungenutzten Code entfernen, schon aus
Sicherheitsgruenden").

Nur Name, Anzahl und Zeitpunkt, nie Inhalte, Projekte oder Pfade.
Ablage: ~/.local/state/polaris/usage.json (lokal, nie hochgeladen). Lesen:
`cat ~/.local/state/polaris/usage.json`. Fehler werden verschluckt: der
Zaehler darf nie einen Lauf stoeren.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def path() -> Path:
    return Path.home() / ".local" / "state" / "polaris" / "usage.json"


def count(name: str) -> None:
    if os.environ.get("POLARIS_USAGE_OFF"):  # Tests: Statistik nicht verfaelschen
        return
    try:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        now = time.strftime("%Y-%m-%d")
        e = data.get(name) if isinstance(data.get(name), dict) else {}
        data[name] = {"count": int(e.get("count", 0)) + 1, "first": e.get("first", now), "last": now}
        tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, p)
    except Exception:  # noqa: BLE001 - Zaehler darf nie stoeren
        pass
