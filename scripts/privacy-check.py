#!/usr/bin/env python3
"""Sperre gegen private Inhalte im Installationspaket (seit 2026-10-08).

Durchsucht die Dateien eines entpackten Pakets nach Angaben, die nur zu
diesem Rechner bzw. Nutzer gehoeren:
  - der eigene Home-Pfad (z. B. /home/<name>/)
  - die git-E-Mail-Adresse (git config user.email)
  - die Namen der Projektordner unter den Polaris-Wurzeln (polaris roots)
  - weitere Begriffe aus ~/.config/polaris/bundle-deny.txt (eine Zeile je Begriff)
Ausnahmen (z. B. allgemeine Ordnernamen wie "Templates") stehen in
~/.config/polaris/bundle-allow.txt. Beide Listen bleiben lokal und kommen nie
ins Paket. Zeilen mit Urheberangabe (Copyright, "author") sind erlaubt.

Geschuetzte Ordner (seit 2026-11-04): Ordner aus
~/.config/polaris/protected.txt (eine Zeile je Ordner, ~ erlaubt) und jeder
Projektordner unter den Polaris-Wurzeln mit einer Markierungsdatei
.polaris-protected. Fuer sie gilt statt des Ordnernamens als Wort:
  - ihr Pfad (absolut und relativ zum Home, z. B. Projekte/<Name>) ist gesperrt
  - jede markante Textzeile daraus (ab 30 Zeichen, Leerraum und
    Gross-/Kleinschreibung egal, ohne Polaris-Formatzeilen) ist gesperrt; abgeglichen wird ueber
    SHA-256-Fingerabdruecke, die nur im Speicher liegen
  - eine Markierungsdatei im Paket ist ein Treffer
Treffer auf geschuetzte Inhalte nennen nur Datei und Zeile, nie den Text.

Aufruf:  privacy-check.py <Ordner>      Exit 0 = sauber, 1 = Treffer
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

CFG = Path.home() / ".config" / "polaris"
ATTRIBUTION = re.compile(r'Copyright|"author"\s*:')
MARKER = ".polaris-protected"
MIN_LINE = 30                    # kuerzere Zeilen sind zu allgemein ("## Offene Punkte")
MAX_FILE = 5 * 1024 * 1024       # groessere Dateien im geschuetzten Ordner nicht einlesen
# Polaris-eigene Formatzeilen (Curator-Metazeile, polaris-Kommentare) stehen in
# jedem Projekt gleich und sind kein Inhalt; sie bekommen keinen Fingerabdruck.
FORMAT_LINE = re.compile(r"^-?\s*Scope: .+? · Evidenzgrad: .+? · Konfidenz: \S+$|^<!--\s*polaris-[\w-]+:.*-->$")


def _lines(path: Path) -> list[str]:
    try:
        return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


def _project_dirs() -> list[Path]:
    try:
        import yaml
        roots = (yaml.safe_load((CFG / "config.yaml").read_text()) or {}).get("project_roots") or []
    except Exception:  # noqa: BLE001 - ohne Polaris-Konfiguration gibt es keine Projektordner
        return []
    dirs = []
    for root in roots:
        try:
            dirs += [p for p in Path(os.path.expanduser(str(root))).iterdir()
                     if p.is_dir() and not p.name.startswith(".")]
        except OSError:
            pass
    return dirs


def protected_dirs() -> list[Path]:
    """Ordner aus protected.txt (auch fehlende: ihr Pfad bleibt gesperrt) und
    markierte Projektordner."""
    found = {Path(os.path.expanduser(ln)).resolve() for ln in _lines(CFG / "protected.txt")}
    found |= {p.resolve() for p in _project_dirs() if (p / MARKER).is_file()}
    return sorted(found)


def _norm(line: str) -> str:
    return " ".join(line.split()).casefold()


def _digest(line: str) -> bytes | None:
    n = _norm(line)
    if len(n) < MIN_LINE or FORMAT_LINE.match(" ".join(line.split())):
        return None
    return hashlib.sha256(n.encode()).digest()


def fingerprints(dirs: list[Path]) -> set[bytes]:
    fps: set[bytes] = set()
    for d in dirs:
        if not d.is_dir():
            print(f"Hinweis: geschuetzter Ordner fehlt, nur sein Pfad wird gesperrt: {d}", file=sys.stderr)
            continue
        for f in d.rglob("*"):
            try:
                if not f.is_file() or f.name == MARKER or f.stat().st_size > MAX_FILE:
                    continue
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue  # Binaerdateien, keine Rechte
            fps.update(h for h in map(_digest, text.splitlines()) if h)
    return fps


def terms(protected: list[Path] | None = None) -> list[str]:
    protected = protected_dirs() if protected is None else protected
    allow = {t.casefold() for t in _lines(CFG / "bundle-allow.txt")}
    home = Path.home()
    found = [str(home) + "/"]
    try:
        email = subprocess.run(["git", "config", "--global", "user.email"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        if email:
            found.append(email)
    except (OSError, subprocess.SubprocessError):
        pass
    shielded = set(protected)
    found += [p.name for p in _project_dirs() if len(p.name) >= 3 and p.resolve() not in shielded]
    found += _lines(CFG / "bundle-deny.txt")
    terms_ = {t for t in found if t.casefold() not in allow}
    # Pfade geschuetzter Ordner: nie per bundle-allow.txt freizugeben.
    for p in protected:
        terms_.add(str(p))
        if p.is_relative_to(home) and p != home:
            terms_.add(str(p.relative_to(home)))
    return sorted(terms_, key=str.casefold)


def scan(root: Path, words: list[str], fps: set[bytes] | None = None) -> list[str]:
    fps = fps or set()
    pattern = re.compile("|".join(
        (re.escape(w) if not w[0].isalnum() else rf"(?<!\w){re.escape(w)}(?!\w)") for w in words), re.I) \
        if words else None
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if path.name == MARKER:
            hits.append(f"{rel}: Markierungsdatei eines geschuetzten Ordners")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # Binaerdateien (.xpi, Bilder)
        for no, line in enumerate(text.splitlines(), 1):
            if fps and _digest(line) in fps:
                hits.append(f"{rel}:{no}: Inhalt aus geschuetztem Ordner (Text nicht angezeigt)")
                continue
            if pattern is None or ATTRIBUTION.search(line):
                continue
            m = pattern.search(line)
            if m:
                hits.append(f"{rel}:{no}: {m.group(0)!r}: {line.strip()[:120]}")
    return hits


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    protected = protected_dirs()
    words = terms(protected)
    fps = fingerprints(protected)
    hits = scan(Path(sys.argv[1]), words, fps)
    for h in hits:
        print(h)
    print(f"Privatsphaere-Pruefung: {len(words)} Begriffe, {len(protected)} geschuetzte Ordner "
          f"({len(fps)} Zeilen), {len(hits)} Treffer", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
