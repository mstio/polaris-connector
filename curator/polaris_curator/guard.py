"""Ausgabepruefung vor dem Schreiben (Sicherheitspruefung 2026-11-04).

Chats, Mails und Anhaenge sind fremder Inhalt. Eine darin versteckte
Anweisung kann das Modell dazu bringen, sie in `knowledge.md`,
`decisions.md` oder `open-loops.md` zu schreiben. Diese Dateien lesen spaeter
Agenten mit Shell-Zugang und die Chat-Projekte als Kontext ("Injection
zweiter Stufe"); und was dort steht, liegt auf dem Cloud-Laufwerk.

Diese Pruefung haelt eine Modellantwort an, wenn sie
- geheimnisaehnliche Zeichenketten enthaelt (Schluessel, Tokens, der lokale
  Koeder aus `~/.config/polaris/canary`), oder
- wie eine Anweisung an eine KI oder wie ein Shell-Befehl aussieht.

Sie ist eine Erkennungsschicht, keine Garantie: geschickt verschleierter Text
kommt durch. Die eigentlichen Grenzen sind Sandbox und feste Ausgabefelder.
Angehaltene Antworten liegen lokal (nie auf dem Laufwerk) unter
`~/.local/state/polaris/quarantine/` und werden mit
`polaris-curator quarantine` gesichtet, freigegeben oder verworfen.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

QUARANTINE_DIR = Path.home() / ".local" / "state" / "polaris" / "quarantine"
CANARY_FILE = Path.home() / ".config" / "polaris" / "canary"

# Geheimnisse: lieber ein Fehlalarm zu viel. Nur Muster, die in normalem
# Projektwissen praktisch nie vorkommen.
_SECRET_RES = [
    ("privater Schlüssel", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("OpenSSH-Schlüssel", re.compile(r"\bb3BlbnNzaC1rZXktdjE[A-Za-z0-9+/=]{20,}")),
    ("GitHub-Token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("API-Schlüssel", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}")),
    ("AWS-Schlüssel", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("Google-Token", re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}|\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack-Token", re.compile(r"\bxox[abpors]-[A-Za-z0-9-]{10,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("OAuth-Daten", re.compile(r"\"?(?:refresh_token|access_token|client_secret)\"?\s*[:=]\s*\"?[A-Za-z0-9._/+-]{16,}", re.I)),
    ("Passwort-Zuweisung", re.compile(
        r"\b(?:passw(?:or)?d|kennwort|passwort|pw|pin|tresorcode|zugangscode)\s*(?:[:=]|lautet|ist)\s*:?\s*"
        r"(?=\S*[\d!?$%&*#@_+-])\S{6,}", re.I)),
    ("Zugangsdaten", re.compile(
        r"\b(?:zugangsdaten|login|credentials)\s*[:=]\s*\S+\s*(?:/|:)\s*(?=\S*[\d!?$%&*#@_+-])\S{6,}", re.I)),
]

# Anweisungen an eine KI und Shell-Befehle. Deutsch und Englisch.
_INSTRUCTION_RES = [
    ("Anweisung an KI", re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+"
        r"(?:instructions|rules|prompts?)", re.I)),
    ("Anweisung an KI", re.compile(
        r"\b(?:ignorier|vergiss|missacht)\w*\s+(?:alle\s+|die\s+)?(?:vorherigen|bisherigen|obigen|früheren)\s+"
        r"(?:anweisungen|regeln|vorgaben)", re.I)),
    ("Anweisung an KI", re.compile(
        r"\b(?:disregard|ignore)\s+(?:the\s+|everything\s+)?above\b", re.I)),
    ("Anweisung an KI", re.compile(
        r"\b(?:you are now|from now on you|new instructions for|system prompt|as an ai agent|"
        r"du bist (?:jetzt|ab sofort)|neue anweisung(?:en)? (?:an|für) (?:dich|die ki|den assistenten|agenten)|"
        r"systemanweisung|hinweis (?:an|für) (?:die |den |jede |jeden )?(?:ki(?:-\w+)?|assistent(?:en)?|agent(?:en|s)?|"
        r"automatische\w* auswertung\w*))\b",
        re.I)),
    ("Anweisung an KI", re.compile(
        r"\b(?:AGENTS|CLAUDE|GEMINI)\.md\b|~/\.config/ai-agents|\.ssh/|authorized_keys|"
        r"\.credentials\.json|auth\.json|rclone\.conf", re.I)),
    ("Shell-Befehl", re.compile(
        r"(?:\bcurl\b|\bwget\b)[^|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b|\b(?:ba|z)?sh\s+<\(|"
        r"\bbase64\s+(?:-d|--decode)\b|\brm\s+-[a-z]*r[a-z]*f|\bchmod\s+(?:\+x|[0-7]{3,4})\b|"
        r"\b(?:sudo|doas|pkexec)\s+\S|\beval\b\s*[\(\"'$]|\bnc\s+-[el]|/dev/tcp/|\bpython3?\s+-c\s|"
        r"\b(?:ba|z)?sh\s+-c\s|\bmkfifo\b|\bcrontab\s+-|\bssh\s+-[A-Za-z]*\s|\bscp\s+\S|\bgit\s+push\b|"
        r"\b(?:curl|wget)\s+\S+.*&&\s*(?:ba|z)?sh\b")),
    # Bilder laden beim Anzeigen von selbst (Ausleitung ueber die URL); bei
    # Links nur lange/kodierte Parameterwerte, nicht ?id=4711 oder ?usp=sharing.
    ("Link mit Parametern", re.compile(r"!\[[^\]]*\]\(\s*https?://|<img\b[^>]*\bsrc\s*=|"
                                       r"https?://\S+[?&][^=\s&]+=[A-Za-z0-9+/%_=.-]{20,}", re.I)),
]


def canary() -> str | None:
    """Lokaler Koeder: eine zufaellige Zeichenkette, die nirgends auftauchen
    darf. Liegt nur auf diesem Rechner (0600); taucht sie in einer
    Modellantwort auf, hat etwas Daten gelesen, die es nicht sehen durfte."""
    try:
        value = CANARY_FILE.read_text(encoding="utf-8").strip()
        return value or None
    except OSError:
        return None


def ensure_canary() -> str:
    token = canary()
    if token:
        return token
    CANARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    token = "polaris-koeder-" + secrets.token_hex(16)
    fd = os.open(CANARY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    return token


# Ähnlich aussehende Zeichen (kyrillisch/griechisch) auf lateinische falten.
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "ѕ": "s", "і": "i", "ј": "j",
    "ԁ": "d", "һ": "h", "ӏ": "l", "ԛ": "q", "ԝ": "w", "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M",
    "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X", "Ѕ": "S", "І": "I", "Ј": "J",
    "ο": "o", "ν": "v", "α": "a", "ε": "e", "ι": "i", "κ": "k", "ρ": "p", "τ": "t", "υ": "u",
})


def normalize(text: str) -> str:
    """Fuer die Pruefung: Breit-/Sonderformen (NFKC), unsichtbare Zeichen und
    Kombinationszeichen weg, aehnlich aussehende Buchstaben gefaltet - sonst
    reicht ein Nullbreitenzeichen in 'sudo bash', um jedes Muster zu umgehen
    (Zweitmeinung 2026-11-04)."""
    t = unicodedata.normalize("NFKC", text)
    t = "".join(ch for ch in t if unicodedata.category(ch) not in ("Cf", "Mn", "Co", "Cs"))
    return t.translate(_CONFUSABLES)


def strip_invisible(text: str) -> str:
    """Unsichtbare Formatzeichen (z. B. Nullbreite) entfernen, bevor Text
    geschrieben wird; Leser sollen sehen, was dasteht."""
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def scan_text(text: str) -> list[dict]:
    """Befunde in einem einzelnen Text (fuer Indexzeilen, Notizen u. Ae.)."""
    return scan({"text": text})


def _strings(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _strings(v, f"{path}[{i}]")


# Felder, die nie ins Projektwissen geschrieben werden (Selbstpruefung,
# Quellenangaben): dort ist z. B. "auth.json" in einer Begruendung harmlos.
_SKIP_PREFIXES = ("self_review", "irrelevant_sources")


def scan(change: dict) -> list[dict]:
    """Befunde in einer gueltigen Modellantwort: [{field, kind, excerpt}].
    Der Auszug zeigt nur die Fundstelle, gekuerzt."""
    findings: list[dict] = []
    token = canary()
    for path, raw in _strings(change):
        if path.startswith(_SKIP_PREFIXES):
            continue
        text = normalize(raw)
        if token and token in text:
            findings.append({"field": path, "kind": "Köder-Geheimnis", "excerpt": "(Köder)"})
            continue
        # Alle Treffer je Feld (nicht nur den ersten): sonst verdeckt ein
        # bereits akzeptierter Treffer einen neuen dahinter.
        for kind, rx in (*_SECRET_RES, *_INSTRUCTION_RES):
            for m in rx.finditer(text):
                start = max(0, m.start() - 40)
                excerpt = text[start:m.end() + 40].replace("\n", " ")
                for _k, srx in _SECRET_RES:  # kein Geheimnis noch einmal ablegen
                    excerpt = srx.sub("[…]", excerpt)
                if token:
                    excerpt = excerpt.replace(token, "[…]")
                findings.append({"field": path, "kind": kind, "excerpt": excerpt[:200], "_match": m.group(0)})
    return findings


def quarantine(project: Path, label: str, change: dict, findings: list[dict],
               meta: dict | None = None) -> Path:
    """Antwort lokal ablegen (0600, nie auf dem Laufwerk)."""
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(QUARANTINE_DIR, 0o700)
    findings = [{k: v for k, v in f.items() if not k.startswith("_")} for f in findings]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    qid = f"{stamp}-{secrets.token_hex(3)}"
    path = QUARANTINE_DIR / f"{qid}.json"
    record = {"id": qid, "project": str(project), "project_name": project.name, "label": label,
              "created": datetime.now(timezone.utc).isoformat(), "findings": findings,
              "meta": meta or {}, "change": change}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    return path


def entries() -> list[dict]:
    out = []
    for p in sorted(QUARANTINE_DIR.glob("*.json")) if QUARANTINE_DIR.is_dir() else []:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def load(qid: str) -> dict:
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", qid or ""):
        raise ValueError(f"ungültige Quarantäne-Kennung: {qid}")
    return json.loads((QUARANTINE_DIR / f"{qid}.json").read_text(encoding="utf-8"))


def remove(qid: str) -> None:
    load(qid)  # prueft die Kennung
    (QUARANTINE_DIR / f"{qid}.json").unlink()


def stop_if_suspicious(project: Path, label: str, plan: dict, kind: str, error_cls,
                       accepted_text: str = "") -> None:
    """Fuer Verdichtung, Neu-Einordnung und Aufraeumen offener Punkte: Plaene
    des Modells mit Verdachtstext nicht anwenden, sondern lokal ablegen und
    mit error_cls abbrechen (die Aufrufer melden das als Warnung). Sonst
    koennte ein verschleierter Eintrag beim Umformulieren "sauber" werden."""
    findings = scan(plan)
    # Text, der schon in den kuratierten Dateien steht, war bereits einmal
    # sichtbar geschrieben und blockiert nicht dauerhaft; Koeder nie.
    if accepted_text:
        known = normalize(accepted_text)
        findings = [f for f in findings if f["kind"] == "Köder-Geheimnis" or f.get("_match", "") not in known]
    if findings:
        qpath = quarantine(project, label, plan, findings, meta={"kind": kind})
        kinds = ", ".join(sorted({f["kind"] for f in findings}))
        raise error_cls(f"{label}: Modellplan angehalten ({kinds}), nichts geändert – Quarantäne {qpath.stem}")


EMPTY_CHANGE_KEYS = ("knowledge_updates", "decisions_add", "decisions_update", "open_loops_add",
                     "open_loops_close", "conflicts", "irrelevant_sources")


def empty_like(change: dict) -> dict:
    """Gueltige, leere Antwort: der Schritt gilt als erledigt, schreibt aber nichts."""
    out = {k: [] for k in EMPTY_CHANGE_KEYS}
    out["self_review"] = change.get("self_review") or {}
    return out
