"""Erkennt stille Ausfaelle der ChatGPT-Archivierung.

Anlass (2026-09-25): Die Firefox-Extension erkannte nach einer ChatGPT-
Aenderung 11 Tage lang kein Projekt; nichts wurde archiviert, und nichts hat
es gemeldet. Einzelne Projekte duerfen ruhen - kommt aber in KEINEM Projekt
mehr eine ChatGPT-Nachricht an, ist fast sicher die Kette Extension ->
Native Host/Download -> Bridge unterbrochen. Zusaetzlich werden liegen-
gebliebene Inbox-Dateien, abgelehnte Events und Bridge-Fehler gemeldet.

Nutzt nur Dateimetadaten (mtime), keine Inhalte; kennt die Bridge-Pfade,
importiert die Bridge aber bewusst nicht (lose Kopplung wie in config.py).
"""

from __future__ import annotations

import html
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import layout
from .i18n import t

HOME = Path.home()
BRIDGE_INBOX = HOME / "Downloads" / "polaris-inbox"
BRIDGE_PENDING = HOME / ".local" / "share" / "polaris" / "pending"
# Seit 0.4.0 der Hauptweg: aus Chat-Abbildern zerlegte Turns (bridge config.EXPANDED_DIR).
BRIDGE_EXPANDED = HOME / ".local" / "share" / "polaris" / "expanded"
BRIDGE_FAILED = HOME / ".local" / "share" / "polaris" / "failed"
BRIDGE_LOG = HOME / ".local" / "state" / "polaris" / "polaris.log"
# Register der Bridge fuer Dateien, die nur noch "retry" ergeben (seit 2026-09-29).
BRIDGE_RETRY = HOME / ".local" / "state" / "polaris" / "retry.json"
# Letzter Zustand der Schnittstellen-Erfassung der Extension (Native Host).
CAPTURE_STATUS = HOME / ".local" / "state" / "polaris" / "capture-status.json"
# Chats mit zurueckgehaltener letzter Antwort (Bridge, seit Review Runde 5).
HELD_BACK = HOME / ".local" / "state" / "polaris" / "held-back.json"
RETRY_STALE_AFTER = timedelta(hours=1)
NOTIFY_STAMP = HOME / ".local" / "state" / "polaris" / "curator-health-notified.json"

INBOX_STALE_AFTER = timedelta(hours=1)
FAILED_RECENT = timedelta(days=7)
LOG_ERRORS_RECENT = timedelta(hours=24)


def _latest_mtime(directory: Path) -> float | None:
    latest = None
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if entry.name.endswith(".json") and entry.is_file():
                    m = entry.stat().st_mtime
                    latest = m if latest is None or m > latest else latest
    except OSError:
        return None
    return latest


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None


def _count_files(directory: Path, pattern: str, newer_than: float | None = None,
                 older_than: float | None = None) -> int:
    n = 0
    for p in directory.glob(pattern):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if newer_than is not None and m < newer_than:
            continue
        if older_than is not None and m > older_than:
            continue
        n += 1
    return n


_FAILED_LINE_RE = re.compile(r" ERROR failed file=(\S+) reason=(\S+)")
_CONFLICT_LINE_RE = re.compile(r" ERROR conflict file=(\S+)")
BRIDGE_CONFLICTS = HOME / ".local" / "share" / "polaris" / "conflicts"


def _recent_log_errors(since: datetime) -> int:
    """ERROR-Zeilen seit since. Zeilen zu abgelehnten Dateien zaehlen nur,
    solange die Datei noch in failed/ liegt - nach dem Aufraeumen soll der
    Health Check sofort wieder gruen sein (seit 2026-09-29)."""
    if not BRIDGE_LOG.is_file():
        return 0
    cutoff = since.strftime("%Y-%m-%d %H:%M:%S")
    n = 0
    try:
        with BRIDGE_LOG.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if " ERROR " not in line or line[:19] < cutoff:
                    continue
                m = _FAILED_LINE_RE.search(line)
                if m and not (BRIDGE_FAILED / m.group(1)).exists():
                    continue
                # Geklaerte Konflikte zaehlen nicht mehr (polaris conflicts --resolve).
                c = _CONFLICT_LINE_RE.search(line)
                if c and not (BRIDGE_CONFLICTS / c.group(1)).exists():
                    continue
                n += 1
    except OSError:
        return 0
    return n


def _held_back(now: datetime) -> list[str]:
    try:
        data = json.loads(HELD_BACK.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for key, entry in (data or {}).items():
        try:
            since = datetime.fromisoformat(str(entry.get("since", "")).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if now - since > timedelta(hours=1):
            out.append(str(entry.get("title") or key))
    return out


CAPTURE_ERROR_FRESH = timedelta(hours=3)
# Voruebergehende Fehler (429, 5xx, Netz) behandelt die Extension seit 0.4.1
# selbst: sie wartet (30 s, verdoppelnd bis 10 min) und ruft erneut ab, ohne
# aus der Seite zu lesen (extension/content.js, isTransientApiError). Jeder
# weitere Fehlversuch erneuert den Zeitstempel, ein anhaltender Ausfall bleibt
# also sichtbar, solange ein synchronisierter Chat offen ist. Ein einzelner 429
# meldete sonst 3 h lang faelschlich "liest ersatzweise aus der Seite"
# (2026-11-09): Erfolg meldet die Extension nur nach einem geaenderten Chat.
# Am Anfang verankert (Zweitpruefung 2026-11-09): nur die Form der Abruffehler
# (chatgpt_api.js bzw. fetch selbst). Lehnt die Bridge ein Abbild ab
# ("error: TypeError: ..."), liest die Extension sehr wohl aus der Seite.
# Nur Netzfehler von fetch zaehlen als voruebergehend, nicht jeder TypeError
# (Gremium 2026-11-10): ein Programmierfehler der Extension ("TypeError:
# Cannot read properties of undefined") soll 3 h sichtbar bleiben. Die
# Extension 0.4.5 wertet noch jeden TypeError als voruebergehend; das naechste
# Release zieht content.js (isTransientApiError) nach.
# Offen: Beginn einer Fehlerserie kennt die Statusdatei nicht (native_host.py).
CAPTURE_TRANSIENT_FRESH = timedelta(minutes=30)
_TRANSIENT_ERROR = re.compile(
    r"^(?:Error: (?:Unterhaltung|Sitzung): HTTP (?:429|5\d\d)\b"
    r"|TypeError: (?:NetworkError|Failed to fetch|network error|Error in body stream|Load failed)"
    r"|AbortError\b)")
# Sonstiger TypeError: vermutlich Programmierfehler der Extension. 0.4.5
# wartet dann und liest nicht aus der Seite; deshalb neutraler Text.
_EXTENSION_ERROR = re.compile(r"^TypeError: ")


def _capture_problem(now: datetime) -> str | None:
    """Warnung, wenn die ChatGPT-Schnittstelle zuletzt nur Fehler lieferte
    (die Extension liest dann aus der Seite - weniger robust)."""
    try:
        data = json.loads(CAPTURE_STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    err = data.get("last_error") or {}
    try:
        err_at = datetime.fromisoformat(err.get("at", ""))
    except ValueError:
        return None
    last_ok = data.get("last_ok")
    try:
        ok_at = datetime.fromisoformat(last_ok) if last_ok else None
    except ValueError:
        ok_at = None
    # Nur ein frischer Fehler zaehlt (seit 2026-10-08, vorher 2 Tage): Jeder
    # weitere Abruf erneuert den Zeitstempel, ein echter Ausfall bleibt also
    # sichtbar, solange ChatGPT benutzt wird. Ein einzelner alter Fehler ohne
    # spaeteren Versuch (z. B. kurzer Netzaussetzer, danach nur unveraenderte
    # oder nicht zugeordnete Chats) loeste sonst noch Stunden spaeter eine
    # Desktop-Meldung aus.
    if ok_at is not None and ok_at >= err_at:
        return None
    error = str(err.get("error", ""))[:100]
    local = err_at.astimezone().strftime("%H:%M")
    if _TRANSIENT_ERROR.search(error):
        if now - err_at < CAPTURE_TRANSIENT_FRESH:
            return t("ChatGPT-Schnittstelle um {local} gedrosselt oder nicht erreichbar ({error}) - "
                     "die Erweiterung wiederholt den Abruf selbst; hält das an, wird nichts erfasst.",
                     local=local, error=error)
        return None
    if now - err_at < CAPTURE_ERROR_FRESH:
        if _EXTENSION_ERROR.search(error):
            return t("ChatGPT-Schnittstelle um {local} nicht nutzbar ({error}) - "
                     "vermutlich Fehler in der Erweiterung; Erfassung dieses Chats prüfen.",
                     local=local, error=error)
        return t("ChatGPT-Schnittstelle um {local} nicht nutzbar ({error}) - "
                 "Erfassung liest ersatzweise aus der Seite.", local=local, error=error)
    return None


def _stuck_retries(now: datetime) -> list[tuple[str, str]]:
    try:
        data = json.loads(BRIDGE_RETRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for name, entry in (data or {}).items():
        try:
            first = datetime.fromisoformat(entry.get("first", ""))
        except (ValueError, AttributeError):
            continue
        # Nur Dateien, die es noch gibt (Inbox oder Pending).
        if (not (BRIDGE_INBOX / name).exists() and not (BRIDGE_EXPANDED / name).exists()
                and not list(BRIDGE_PENDING.glob(f"*/{name}"))):
            continue
        if now - first > RETRY_STALE_AFTER:
            out.append((name, str(entry.get("last_error", ""))[:120]))
    return out


# Ohne ausdrueckliche Quellenliste weiss ein Agent sonst nicht, dass der
# ChatGPT-Alarm auf Claude-only-Systemen per Konfiguration verschwindet.
SOURCES_HINT = ("Falls ChatGPT hier nicht genutzt wird: in ~/.config/polaris/curator.yaml "
                "monitoring.chat_sources setzen, z. B. [claude] (siehe CHANGELOG).")


def _sources_hint(sources_explicit: bool) -> str:
    return "" if sources_explicit else " " + t(SOURCES_HINT)


def collect(projects: dict[str, Path], max_days_without_chatgpt: int, now: datetime | None = None,
            chat_sources: tuple[str, ...] = ("chatgpt", "claude"), sources_explicit: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    per_project: dict[str, str | None] = {}
    latest = None
    if "chatgpt" in chat_sources:
        for path in sorted({p.resolve() for p in projects.values()}):
            m = _latest_mtime(layout.messages_dir(path))
            per_project[path.name] = _iso(m)
            if m is not None and (latest is None or m > latest):
                latest = m

    warnings: list[str] = []
    # Gesondert statt per Textsuche in den (uebersetzten) Warnungen: keine
    # ChatGPT-Nachricht seit der Frist -> systemhealth zeigt rot.
    silent = False
    days_since = None
    # 0 schaltet nur die Zeitpruefung aus, nicht die Quelle oder Bridge-Fehler.
    if projects and "chatgpt" in chat_sources and max_days_without_chatgpt > 0:
        if latest is None:
            silent = True
            warnings.append(t("Noch keine ChatGPT-Nachricht archiviert.") + _sources_hint(sources_explicit))
        else:
            days_since = (now.timestamp() - latest) / 86400
            if days_since > max_days_without_chatgpt:
                silent = True
                warnings.append(
                    t("Seit {days} Tagen keine ChatGPT-Nachricht mehr archiviert "
                      "(in keinem Projekt) - Firefox-Erweiterung, Berechtigung für chatgpt.com "
                      "und Native Host prüfen.", days=int(days_since)) + _sources_hint(sources_explicit)
                )

    inbox_stale = 0
    pending = 0
    failed_recent = 0
    log_errors = 0
    if chat_sources:
        inbox_stale = _count_files(BRIDGE_INBOX, "*.json", older_than=(now - INBOX_STALE_AFTER).timestamp()) + \
            _count_files(BRIDGE_EXPANDED, "*.json", older_than=(now - INBOX_STALE_AFTER).timestamp())
        pending = _count_files(BRIDGE_PENDING, "*/*.json")
        failed_recent = _count_files(BRIDGE_FAILED, "*.json")
        log_errors = _recent_log_errors((now - LOG_ERRORS_RECENT).astimezone())
    # Solange etwas in failed/ liegt, sichtbar - unabhaengig vom Alter (die
    # Datei behaelt die mtime aus der Inbox und war sonst evtl. sofort "zu alt";
    # Review Runde 3).
    if inbox_stale:
        warnings.append(t("{n} Datei(en) liegen seit über einer Stunde unverarbeitet in der Bridge-Inbox.",
                          n=inbox_stale))
    if pending:
        warnings.append(t("{n} Nachricht(en) warten auf eine Projektzuordnung (polaris pending).", n=pending))
    if failed_recent:
        warnings.append(t("{n} Datei(en) hat die Bridge abgelehnt (~/.local/share/polaris/failed/) - "
                          "Grund im Bridge-Protokoll.", n=failed_recent))
    if log_errors:
        warnings.append(t("{n} Fehler im Bridge-Protokoll in den letzten 24 Stunden.", n=log_errors))
    held = _held_back(now) if "chatgpt" in chat_sources else []
    if held:
        names = ", ".join(f"„{t}“" for t in held[:3]) + (" …" if len(held) > 3 else "")
        warnings.append(t(
            "{n} Chat(s) mit noch nicht übernommener letzter Antwort seit über 1 h: {names} – "
            "Chat öffnen oder im Popup „Sync now“ (gelöschter Chat: `polaris held-back --clear …`).",
            n=len(held), names=names))
    capture = _capture_problem(now) if "chatgpt" in chat_sources else None
    if capture:
        warnings.append(capture)
    stuck = _stuck_retries(now) if chat_sources else []
    if stuck:
        example = stuck[0]
        warnings.append(t(
            "{n} Datei(en) lassen sich seit über einer Stunde nicht ablegen "
            "(z. B. {name}: {error}) - Projektordner/Mount prüfen.",
            n=len(stuck), name=example[0], error=example[1]))

    return {
        "last_chatgpt_message_at": _iso(latest),
        "days_since_chatgpt_message": round(days_since, 1) if days_since is not None else None,
        "max_days_without_chatgpt": max_days_without_chatgpt,
        "projects_last_chatgpt_message_at": per_project,
        "bridge": {
            "inbox_stale": inbox_stale,
            "pending": pending,
            "failed_last_7_days": failed_recent,
            "log_errors_last_24h": log_errors,
        },
        "warnings": warnings,
        "chatgpt_silent": silent,
    }


def notify_once_per_day(health: dict, now: datetime | None = None) -> bool:
    """Desktop-Benachrichtigung, hoechstens einmal pro Tag und Befund."""
    warnings = health.get("warnings") or []
    if os.environ.get("POLARIS_NO_NOTIFY") or not warnings or not shutil.which("notify-send"):
        return False
    now = now or datetime.now(timezone.utc)
    digest = hashlib.sha256("\n".join(warnings).encode()).hexdigest()[:16]
    today = now.astimezone().date().isoformat()
    try:
        stamp = json.loads(NOTIFY_STAMP.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stamp = {}
    if stamp.get("date") == today and stamp.get("digest") == digest:
        return False
    try:
        subprocess.run(
            ["notify-send", "-u", "critical", "-a", "Polaris Curator", t("Polaris: Archivierung prüfen"),
             html.escape("\n".join(warnings), quote=False)],
            check=False, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    NOTIFY_STAMP.parent.mkdir(parents=True, exist_ok=True)
    NOTIFY_STAMP.write_text(json.dumps({"date": today, "digest": digest}), encoding="utf-8")
    return True
