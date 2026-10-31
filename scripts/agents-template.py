#!/usr/bin/env python3
"""Erzeugt memory/template/AGENTS.md aus der Live-Fassung (seit 2026-10-31).

Die Live-Datei ~/.config/ai-agents/AGENTS.md enthaelt allgemeine Regeln und
Angaben zu diesem Rechner nebeneinander. In die Vorlage des Pakets kommt nur,
was ausdruecklich geteilt werden soll:
  - Abschnitte (## …) mit <!-- allgemein --> in der Ueberschrift,
  - darin ohne die Punkte mit <!-- privat --> am Zeilenende (samt ihren
    eingerueckten Folgezeilen).
Abschnitte ohne Kennzeichnung gelten als privat (sicherer Standard: eine neue
Regel wird nie aus Versehen geteilt). Die Privatsphaere-Pruefung des Pakets
laeuft danach zusaetzlich.

  scripts/agents-template.py --check   # Exit 1, wenn die Vorlage veraltet ist
  scripts/agents-template.py --write   # Vorlage neu schreiben
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIVE = Path.home() / ".config" / "ai-agents" / "AGENTS.md"
TEMPLATE = REPO / "memory" / "template" / "AGENTS.md"
HEADER = ("# Gemeinsamer Kontext für lokale AI-Agenten\n\n"
          "<!-- Vorlage aus dem Polaris-Installationspaket. An den eigenen Rechner anpassen. -->\n")
ALLGEMEIN = re.compile(r"\s*<!--\s*allgemein\s*-->\s*$")
PRIVAT = re.compile(r"\s*<!--\s*privat\s*-->\s*$")


def render(live_text: str) -> tuple[str, list[str]]:
    """Liefert (Vorlage, Namen der nicht geteilten Abschnitte)."""
    sections: list[tuple[str, list[str]]] = []
    for line in live_text.splitlines():
        if line.startswith("## "):
            sections.append((line, []))
        elif sections:
            sections[-1][1].append(line)
    out = [HEADER]
    skipped = []
    for heading, body in sections:
        if not ALLGEMEIN.search(heading):
            skipped.append(heading[3:].strip())
            continue
        kept: list[str] = []
        dropping = False
        for line in body:
            if line.startswith("- ") and PRIVAT.search(line):
                dropping = True
                continue
            if dropping and line[:1] in (" ", "\t"):
                continue  # Folgezeile eines privaten Punkts
            dropping = False
            if PRIVAT.search(line) or ALLGEMEIN.search(line):
                raise ValueError(f"Kennzeichnung an unerwarteter Stelle: {line[:80]}")
            kept.append(line)
        while kept and not kept[-1].strip():
            kept.pop()
        out.append("\n" + ALLGEMEIN.sub("", heading) + "\n" + "\n".join(kept) + "\n")
    return "".join(out), skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    ap.add_argument("--live", type=Path, default=LIVE)
    args = ap.parse_args()
    if not args.live.exists():
        print(f"agents-template: {args.live} fehlt - Vorlage bleibt unveraendert", file=sys.stderr)
        return 0 if args.check else 1
    text, skipped = render(args.live.read_text(encoding="utf-8"))
    if args.write:
        TEMPLATE.write_text(text, encoding="utf-8")
        print(f"agents-template: {TEMPLATE.relative_to(REPO)} geschrieben; nicht geteilt: {', '.join(skipped) or '-'}")
        return 0
    current = TEMPLATE.read_text(encoding="utf-8") if TEMPLATE.exists() else ""
    if current == text:
        return 0
    sys.stdout.writelines(difflib.unified_diff(current.splitlines(True), text.splitlines(True),
                                               "Vorlage (Repo)", "aus Live-AGENTS.md", n=1))
    print("\nagents-template: Vorlage ist veraltet - scripts/agents-template.py --write, pruefen, committen.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
