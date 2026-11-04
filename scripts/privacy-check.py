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
.polaris-protected. Fuer sie gilt statt des Ordnernamens als Wort (Nutzervorgabe: aus einem
geschuetzten Ordner darf keinerlei Inhalt veroeffentlicht werden):
  - ihr Name (exakte Schreibweise, ganzes Wort; auch die Existenz eines
    geschuetzten Ordners wird nicht veroeffentlicht) und ihr Pfad (absolut und
    relativ zum Home) sind gesperrt; bundle-allow.txt hebt das nicht auf
  - jede Datei daraus ist byte-gleich gesperrt (auch PDF, Office, Bilder)
  - jede Textzeile mit Inhalt (ab 4 Buchstaben/Ziffern; Leerraum und
    Gross-/Kleinschreibung egal) ist als ganze Zeile gesperrt, dazu jede
    Folge von 5 Woertern daraus (ab 25 Zeichen) auch mitten in anderem Text
  - ausgenommen sind nur Polaris-Formatzeilen, die in jedem Projekt gleich
    stehen: Curator-Metazeile, polaris-Kommentare, Standard-Ueberschriften,
    JSON-Geruest mit Polaris-Schluesseln und Werten ohne Freitext
  - eine Markierungsdatei im Paket ist ein Treffer
Abgeglichen wird ueber SHA-256-Fingerabdruecke bzw. im Speicher; nichts davon
wird gespeichert.
Treffer auf geschuetzte Inhalte nennen nur Datei und Zeile, nie den Text.

Aufruf:  privacy-check.py <Ordner> [<Ordner> ...]   Exit 0 = sauber, 1 = Treffer
         (mehrere Ordner: geschuetzte Ordner werden nur einmal eingelesen)
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
REPO = Path(__file__).resolve().parents[1]
MIN_ALNUM = 4                    # Zeilen mit weniger Buchstaben/Ziffern ("---", "{", "1.") sind kein Inhalt
SHINGLE_WORDS, SHINGLE_MIN = 5, 25   # Wortfenster fuer eingebettete Bruchstuecke (4 Woerter trafen deutsche Floskeln)
# Fenster nur aus diesen Woertern sind Polaris-Rohdaten-Geruest ("url": "https://chatgpt.com/...")
SHINGLE_NOISE = {"url", "https", "http", "www", "com", "org", "de", "chatgpt", "claude", "ai", "c", "chat"}
MAX_TEXT = 5 * 1024 * 1024       # groessere Dateien nicht zeilenweise einlesen ...
MAX_FILE = 200 * 1024 * 1024     # ... aber bis hierhin byte-gleich sperren
MIN_FILE = 16                    # winzige Dateien ("{}") nicht als ganze Datei sperren
# Polaris-eigene Formatzeilen stehen in jedem Projekt gleich und sind kein
# Inhalt; sie bekommen keinen Fingerabdruck.
FORMAT_LINE = re.compile(
    r"^-?\s*Scope: .+? · Evidenzgrad: .+? · Konfidenz: \S+$"           # Curator-Metazeile
    r"|^<!--\s*polaris-[\w-]+:.*-->$"                                  # polaris-Kommentare
    r"|^-?\s*ID: [KDL]\d+ · (Gültig seit: \d{4}-\d\d-\d\d|offen seit \d{4}-\d\d-\d\d.*)$"  # ID-Zeile
    r"|^\*\*[^*]{1,40}\*\*$"                                           # Feldname in decisions.md
    r"|^[KDL]\d+$|^\d{4}-\d\d-\d\d$"                                    # ID bzw. Datum allein
    r"|^(Aktiv|Abgelöst|Ersetzt|lokal|vorläufig|Pilot/Test|dauerhaft|unternehmensweiter Standard"
    r"|Ja|Nein \(noch nicht (überprüft|bestätigt)\))$")                  # feste Feldwerte
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$")
POLARIS_HEADINGS = {h.casefold() for h in (
    # Abschnitte des Curators (prompts.py "Sektionsnamen", open-loops, decisions)
    "Zielbild", "Aktueller Status", "Architektur / Prozesse", "Stakeholder / Rollen", "Kennzahlen / Fakten",
    "Rahmenbedingungen", "Relevante Erkenntnisse", "Status", "Offen", "Erledigt",
    # Dateititel und feste Abschnitte, die Polaris selbst schreibt
    "Projektwissen", "Polaris Projektwissen", "Entscheidungen", "Weitere Entscheidungen", "Offene Punkte",
    "Dokumente und Mail-Anhänge", "Dokumente und Notizen", "E-Mails", "Wissensarchiv", "Inhalt",
    "Dateien pro Projekt", "So liest man die Einträge", "Zurückgenommene Einträge")}
JSON_LINE = re.compile(r'^"([A-Za-z_]+)":\s*(\{|\[|\{\}|\[\]|true|false|null|-?\d+(?:\.\d+)?|"[a-z_]{1,20}")\s*,?$')
_JSON_KEYS: set[str] | None = None


def polaris_json_keys() -> set[str]:
    """JSON-Schluessel, die Polaris selbst schreibt (aus dem Quelltext von Bridge und Curator)."""
    global _JSON_KEYS
    if _JSON_KEYS is None:
        _JSON_KEYS = set()
        for src in [*(REPO / "bridge" / "polaris").glob("*.py"), *(REPO / "curator" / "polaris_curator").glob("*.py")]:
            try:
                _JSON_KEYS |= set(re.findall(r'"([a-z_]{2,40})"\s*:', src.read_text(encoding="utf-8")))
            except OSError:
                pass
    return _JSON_KEYS


def is_format_line(line: str) -> bool:
    s = " ".join(line.split())
    if FORMAT_LINE.match(s):
        return True
    m = HEADING.match(s)
    if m and m[1].casefold() in POLARIS_HEADINGS:
        return True
    m = JSON_LINE.match(s)
    return bool(m and m[1] in polaris_json_keys())


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


def _content(line: str) -> str | None:
    """Normalisierte Zeile, wenn sie Inhalt ist, sonst None."""
    n = _norm(line)
    if sum(c.isalnum() for c in n) < MIN_ALNUM or is_format_line(line):
        return None
    return n


def _shingles(n: str) -> set[str]:
    w = re.findall(r"\w+", n)
    out = set()
    for i in range(len(w) - SHINGLE_WORDS + 1):
        part = w[i:i + SHINGLE_WORDS]
        s = " ".join(part)
        if len(s) >= SHINGLE_MIN and not set(part) <= SHINGLE_NOISE:
            out.add(s)
    return out


def _file_digest(path: Path) -> bytes:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.digest()


class Protected:
    """Fingerabdruecke der geschuetzten Ordner (nur im Speicher)."""

    def __init__(self, dirs: list[Path]):
        self.lines: set[bytes] = set()
        self.files: set[bytes] = set()
        self.shingles: set[bytes] = set()
        for d in dirs:
            if not d.is_dir():
                print(f"Hinweis: geschuetzter Ordner fehlt, nur sein Pfad wird gesperrt: {d}", file=sys.stderr)
                continue
            for f in d.rglob("*"):
                try:
                    if not f.is_file() or f.name == MARKER:
                        continue
                    size = f.stat().st_size
                    if not MIN_FILE <= size <= MAX_FILE:
                        continue
                    digest = _file_digest(f)
                    text = f.read_text(encoding="utf-8") if size <= MAX_TEXT else None
                except UnicodeDecodeError:
                    self.files.add(digest)       # Binaerdatei: byte-gleich gesperrt
                    continue
                except OSError:
                    continue
                if text is None:
                    self.files.add(digest)
                    continue
                contents = [n for n in map(_content, text.splitlines()) if n]
                if contents:                     # Datei nur aus Polaris-Geruest ist kein Inhalt
                    self.files.add(digest)
                for n in contents:
                    self.lines.add(hashlib.sha256(n.encode()).digest())
                    self.shingles |= {hashlib.sha256(s.encode()).digest() for s in _shingles(n)}

    def hit(self, line: str) -> bool:
        n = _norm(line)
        if hashlib.sha256(n.encode()).digest() in self.lines and _content(line):
            return True
        return any(hashlib.sha256(s.encode()).digest() in self.shingles for s in _shingles(n))

    def __len__(self) -> int:
        return len(self.lines)


def fingerprints(dirs: list[Path]) -> Protected:
    return Protected(dirs)


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


def exact_names(protected: list[Path]) -> list[str]:
    """Namen geschuetzter Ordner: exakte Schreibweise, ganzes Wort, nie freizugeben.
    (Ein allgemeines kleingeschriebenes Wort gleichen Inhalts bleibt erlaubt.)"""
    return sorted({p.name for p in protected if p.name})


def scan(root: Path, words: list[str], fps: Protected | None = None,
         names: list[str] | None = None) -> list[str]:
    pattern = re.compile("|".join(
        (re.escape(w) if not w[0].isalnum() else rf"(?<!\w){re.escape(w)}(?!\w)") for w in words), re.I) \
        if words else None
    exact = re.compile("|".join(rf"(?<!\w){re.escape(n)}(?!\w)" for n in names)) if names else None
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if exact and exact.search(str(rel)):
            hits.append(f"{rel}: Name eines geschuetzten Ordners im Dateipfad")
            continue
        if path.name == MARKER:
            hits.append(f"{rel}: Markierungsdatei eines geschuetzten Ordners")
            continue
        try:
            if fps and fps.files and MIN_FILE <= path.stat().st_size <= MAX_FILE and _file_digest(path) in fps.files:
                hits.append(f"{rel}: Datei aus geschuetztem Ordner (byte-gleich)")
                continue
        except OSError:
            pass
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # Binaerdateien (.xpi, Bilder)
        for no, line in enumerate(text.splitlines(), 1):
            if fps and fps.hit(line):
                hits.append(f"{rel}:{no}: Inhalt aus geschuetztem Ordner (Text nicht angezeigt)")
                continue
            if exact and exact.search(line):
                hits.append(f"{rel}:{no}: Name eines geschuetzten Ordners (Text nicht angezeigt)")
                continue
            if pattern is None or ATTRIBUTION.search(line):
                continue
            m = pattern.search(line)
            if m:
                hits.append(f"{rel}:{no}: {m.group(0)!r}: {line.strip()[:120]}")
    return hits


def main() -> int:
    if len(sys.argv) < 2:
        print("Aufruf: privacy-check.py <Ordner> [<Ordner> ...]", file=sys.stderr)
        return 2
    protected = protected_dirs()
    words = terms(protected)
    fps = fingerprints(protected)
    names = exact_names(protected)
    roots = [Path(a) for a in sys.argv[1:]]
    hits = []
    for root in roots:
        found = scan(root, words, fps, names)
        hits += [f"{root.name}/{h}" for h in found] if len(roots) > 1 else found
    for h in hits:
        print(h)
    print(f"Privatsphaere-Pruefung: {len(words)} Begriffe, {len(protected)} geschuetzte Ordner "
          f"({len(fps)} Zeilen), {len(hits)} Treffer", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
