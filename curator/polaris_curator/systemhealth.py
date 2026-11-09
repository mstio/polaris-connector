"""Health-Check fuer die selbst gebauten Bausteine auf dem Entwicklungsrechner (seit 2026-09-25).

Speist das Omarchy-Bar-Widget (vorher reines Curator-Widget). Liest nur
Zustandsdateien, Metadaten und systemd-Zustaende - keine teuren Pruefungen
(z. B. kein `omarchy-backup status`, das jede gesicherte Datei hasht; die
Drift zeigt das Backup-Widget selbst). Jede Komponente liefert
{id, label, level: ok|warn|error, detail}; level "error" nur fuer Dinge, bei
denen tatsaechlich etwas verloren gehen oder ausfallen kann.
"""

from __future__ import annotations

import hashlib
import time
import json
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import health as archive_health
from . import integrity, layout
from .i18n import language, t

HOME = Path.home()
EXTENSION_ID = "polaris-chatgpt-connector@mstarchy.local"
NATIVE_MANIFEST = HOME / ".mozilla" / "native-messaging-hosts" / "polaris_bridge.json"
FIREFOX_DIR = HOME / ".config" / "mozilla" / "firefox"
BACKUP_DATA = HOME / ".local" / "share" / "omarchy-backup"
BACKUP_STATE = BACKUP_DATA / "state.json"
# Ergebnis der letzten Zielpruefung von omarchy-backup (integrity check,
# doctor, push); liegt lokal, wird nie hochgeladen.
BACKUP_INTEGRITY = BACKUP_DATA / "integrity-status.json"
BACKUP_SNAPSHOTS = BACKUP_DATA / "snapshots"
POLARIS_CONFIG_DIR = HOME / ".config" / "polaris"
# memlint aus dem Polaris-Programm, nicht aus ~/.config/ai-agents/tools:
# Der Health Check fuehrt es alle 10 min aus, und das Gedaechtnis kann aus
# einem fremdbeschreibbaren Spiegel stammen (Sicherheitspruefung 2026-11-04).
_REPO_MEMLINT = Path(__file__).resolve().parents[2] / "memory" / "tools" / "memlint.py"
MEM_ROOT = HOME / ".config" / "ai-agents"
MEMLINT = _REPO_MEMLINT if _REPO_MEMLINT.is_file() else MEM_ROOT / "tools" / "memlint.py"
MEMORY_MIRROR_STATE = HOME / ".local" / "state" / "polaris" / "memory-mirror.json"
MEMORY_MIRROR_MAX_DAYS = 2
# Sicherheitsabgleich von polaris-radar (seit 2026-11-02; Timer taeglich).
SECURITY_STATE = HOME / ".local" / "state" / "polaris" / "security.json"
SECURITY_MAX_DAYS = 3
# memlint-Befunde, bei denen Wissen verloren gehen oder nach aussen gelangen
# kann -> rot; alles andere (kaputter Verweis, fehlender Tag, Rueckkopie) gelb.
MEMLINT_SEVERE = {"backup", "entrypoints", "secrets", "symlinks"}
MIN_EXTENSION_VERSION = (0, 1, 2)
# Omarchy lehnt symlinkte Plugin-Ordner ab, aktiv ist eine Kopie (install.sh).
WIDGET_ID = "mst.polaris-curator"
WIDGET_SRC = Path(__file__).resolve().parents[2] / "omarchy-plugin" / WIDGET_ID
WIDGET_ACTIVE = HOME / ".config" / "omarchy" / "plugins" / WIDGET_ID
WIDGET_SYNC_HINT = "./install.sh --yes --no-units --no-backup --no-memory, dann omarchy restart shell"

_LEVELS = {"ok": 0, "warn": 1, "error": 2}


def _c(cid: str, label: str, level: str, detail: str, command: str | None = None) -> dict:
    """command (seit 2026-11-05): fertiger Befehl zum Kopieren im Widget.
    Teile aus Dateien/Pfaden immer mit _sh() quoten (Fremdtext)."""
    c = {"id": cid, "label": label, "level": level, "detail": detail}
    if command:
        c["command"] = command
    return c


def _sh(path: Path | str) -> str:
    """Pfad fuer einen kopierbaren Befehl: unter HOME als ~/<gequotet>, damit
    er lesbar bleibt und trotzdem jeder Dateiname sicher ist."""
    p = Path(path)
    try:
        return "~/" + shlex.quote(str(p.relative_to(HOME)))
    except ValueError:
        return shlex.quote(str(p))


def _systemctl_user(*args: str) -> str:
    try:
        return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _age_days(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return (now - dt).total_seconds() / 86400


def _fmt_age(days: float | None) -> str:
    if days is None:
        return t("nie")
    if days < 1 / 24:
        return t("gerade eben")
    if days < 1:
        return t("vor {n} h", n=int(days * 24))
    return t("vor {n} Tag(en)", n=int(days))


def check_archive(projects: dict, max_days: int, sources_explicit: bool = True) -> dict:
    h = archive_health.collect(projects, max_days, chat_sources=("chatgpt",), sources_explicit=sources_explicit)
    label = t("ChatGPT-Archivierung")
    if h["warnings"]:
        level = "error" if h.get("chatgpt_silent") else "warn"
        return _c("chatgpt-archive", label, level, " ".join(h["warnings"]))
    last = h["last_chatgpt_message_at"]
    if last is None:
        return _c("chatgpt-archive", label, "ok", t("noch keine ChatGPT-Nachricht archiviert"))
    days = _age_days(last, datetime.now(timezone.utc))
    return _c("chatgpt-archive", label, "ok", t("letzte Nachricht {age}", age=_fmt_age(days)))


def check_bridge_without_chatgpt(projects: dict) -> dict:
    """Bridge-Fehler auch bei reiner Claude-Erfassung sichtbar halten."""
    h = archive_health.collect(projects, 0, chat_sources=("claude",))
    if h["warnings"]:
        return _c("bridge", "Bridge", "warn", " ".join(h["warnings"]))
    return _c("bridge", "Bridge", "ok", t("keine Auffälligkeiten"))


def check_claude_archive(projects: dict, max_days: int, now: datetime, required: bool = False) -> dict:
    """Eigene Zeile fuer Claude (seit Extension 0.2.0): laengere Frist als bei
    ChatGPT und hoechstens gelb, weil Claude unregelmaessiger genutzt wird.
    Noch nie eine Claude-Nachricht: neutral, wenn Claude nur per Voreinstellung
    geprueft wird; rot, wenn monitoring.chat_sources Claude ausdruecklich nennt
    (required) - sonst bliebe eine nie funktionierende Erfassung unbemerkt."""
    latest = None
    count = 0
    # Mehrere Zuordnungen (ChatGPT + Claude-Projekte) koennen auf denselben
    # Ordner zeigen - Ordner zaehlen, nicht Zuordnungen.
    for path in sorted({p.resolve() for p in projects.values()}):
        d = path / "raw" / "claude" / "messages"
        m = archive_health._latest_mtime(d)
        if m is not None:
            count += 1
            latest = m if latest is None or m > latest else latest
    label = t("Claude-Archivierung")
    if latest is None:
        if required and projects:
            return _c("claude-archive", label, "error",
                      t("noch keine Claude-Nachricht archiviert – Erweiterung, Zugriff auf claude.ai und "
                        "Projektzuordnung prüfen (oder claude aus monitoring.chat_sources entfernen)"))
        return _c("claude-archive", label, "ok", t("noch keine Claude-Nachricht archiviert"))
    days = (now.timestamp() - latest) / 86400
    detail = t("letzte Nachricht {age} ({n} Projekt(e) mit Claude-Quelle)", age=_fmt_age(days), n=count)
    if days > max_days:
        return _c("claude-archive", label, "warn",
                  t("seit {days} Tagen keine Claude-Nachricht – falls du Claude genutzt hast: "
                    "Erweiterung/Berechtigung für claude.ai und Sync im Popup prüfen", days=int(days)))
    return _c("claude-archive", label, "ok", detail)


def check_journals(projects: dict) -> dict:
    """Unterbrochene Kurationsschritte (journal.py): offen laenger als 1 h oder
    beschaedigt -> rot, das Projekt wird dann nicht (vollstaendig) kuratiert."""
    from . import journal

    label = t("Kurationsschritte")
    stuck = []
    now = datetime.now(timezone.utc).timestamp()
    for path in sorted({p.resolve() for p in projects.values()}):
        jp = journal.existing_path(path)
        if jp is None:
            continue
        try:
            journal.pending(path)
            age = now - jp.stat().st_mtime
            if age > 3600:
                stuck.append(t("{name} (offen seit {h} h)", name=path.name, h=int(age // 3600)))
        except (journal.JournalConflict, OSError) as exc:
            stuck.append(f"{path.name} ({exc})")
    if stuck:
        return _c("journal", label, "error",
                  t("unterbrochen: {items} – `polaris-curator journal <Projekt>`", items=", ".join(stuck)))
    leftovers = _stale_tmp_files(projects, now)
    if leftovers:
        return _c("journal", label, "warn",
                  t("keiner offen; {n} verwaiste Zwischendatei(en), z. B. {item} – nach Prüfung löschen",
                    n=len(leftovers), item=leftovers[0]))
    return _c("journal", label, "ok", t("keiner offen"))


# Eindeutige Zwischendateien von storage.atomic_write_text (".<name>.<pid>.<hex>.tmp",
# seit 2026-11-07): bleiben nur nach Absturz/Stromausfall liegen und wuerden nie
# mehr ueberschrieben. Nur Verzeichniseintraege, keine Inhalte (ADR 004, Schritt 0).
_TMP_RE = re.compile(r"^\..+\.\d+\.[0-9a-f]{8}\.tmp$")
TMP_STALE_S = 24 * 3600


def _stale_tmp_files(projects: dict, now: float) -> list[str]:
    found = []
    for path in sorted({p.resolve() for p in projects.values()}):
        for d in (path, path / ".polaris"):
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if _TMP_RE.match(e.name) and now - e.stat(follow_symlinks=False).st_mtime > TMP_STALE_S:
                                found.append(f"{path.name}/{d.name + '/' if d != path else ''}{e.name}")
                        except OSError:
                            continue
            except OSError:
                continue
    return found


PENDING_STALE_DAYS = 7


def check_curation(projects: dict, now: datetime | None = None) -> dict:
    """Ergebnis der letzten Laeufe je Projekt (.polaris/last-run.json, seit
    2026-09-29): gelb bei Fehlern, wichtigen Warnungen (Dokument bleibt
    liegen/gekuerzt, Kontextgrenze, nicht zugeordnete Nachrichten),
    wiederholt scheiternden Einheiten oder Rueckstand aelter als 7 Tage.
    Vorher meldete das Widget nur den Exit-Code des Timer-Dienstes."""
    from datetime import date

    from . import state as state_mod

    label = t("Kuration")
    today = (now or datetime.now(timezone.utc)).astimezone().date()
    problems: list[str] = []
    for path in sorted({p.resolve() for p in projects.values()}):
        lr = path / ".polaris" / "last-run.json"
        try:
            rec = json.loads(lr.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rec = None
        if rec:
            if rec.get("aborted_reason") == "integrity":
                pass  # meldet schon die Zeile "Projekttrennung"
            elif rec.get("errors") or rec.get("aborted_reason"):
                first = (rec.get("errors") or [rec.get("aborted_reason")])[0]
                problems.append(t("{name}: letzter Lauf mit Fehler ({error})", name=path.name, error=str(first)[:90]))
            for w in rec.get("warnings") or []:
                problems.append(f"{path.name}: {w[:110]}")
            oldest = rec.get("oldest_pending_day")
            if oldest:
                try:
                    age = (today - date.fromisoformat(oldest)).days
                except ValueError:
                    age = 0
                if age > PENDING_STALE_DAYS:
                    problems.append(t("{name}: Rückstand seit {age} Tagen ({n} Tages-Batches)",
                                      name=path.name, age=age, n=rec.get("pending_chat_batches")))
        try:
            from . import config as config_mod, context as context_mod

            pcfg = config_mod.load_config(path)
            # Abgewiesene oder unlesbare Projekt-Overrides vorn einreihen:
            # moeglicher Angriff ueber das Cloud-Laufwerk.
            for prob in reversed([p for p in getattr(pcfg, "config_problems", ()) if "curator-config.yaml" in p]):
                problems.insert(0, prob)
            full = getattr(pcfg, "full_context_chars", 0)
            cap = getattr(pcfg, "index_cap", context_mod.INDEX_CAP)
            for fname, is_dec in (("knowledge.md", False), ("open-loops.md", False), ("decisions.md", True)):
                fp = path / fname
                if full and fp.is_file():
                    share = context_mod.index_share(fp.read_text(encoding="utf-8"), full, is_dec, cap)
                    if share > 0.5:
                        problems.append(t("{name}/{file}: Verzeichnis belegt {pct} % des Kontext-Budgets – "
                                          "aufräumen (compact / review-loops) oder full_context_chars erhöhen",
                                          name=path.name, file=fname, pct=int(share * 100)))
        except Exception:  # noqa: BLE001 - nur Anzeige
            pass
        try:
            st = state_mod.load_state(path)
            repeated = [k for k, f in (st.failures or {}).items() if (f or {}).get("count", 0) >= 2]
        except Exception:  # noqa: BLE001 - nur Anzeige
            repeated = []
        if repeated:
            problems.append(t("{name}: {n} Einheit(en) scheitern wiederholt", name=path.name, n=len(repeated)))
    try:
        from . import guard
        nq = len(guard.entries())
    except Exception:  # noqa: BLE001 - nur Anzeige
        nq = 0
    if nq:
        problems.insert(0, t("{n} Antwort(en) in Quarantäne – polaris-curator quarantine list", n=nq))
    if problems:
        uniq = list(dict.fromkeys(problems))
        return _c("curation", label, "warn", " · ".join(uniq[:3]) + (f" (+{len(uniq) - 3})" if len(uniq) > 3 else ""))
    return _c("curation", label, "ok", t("keine Auffälligkeiten"))


def check_separation(mappings: dict | None = None) -> dict:
    """Projekttrennung (seit 2026-09-29, Vorfall zweier vermischter Kundenprojekte): rot, wenn im
    Rohbestand Nachrichten liegen, die zu einem anderen Projekt/Chat gehoeren
    (der Curator laesst betroffene Projekte dann aus); gelb, wenn die Bridge
    einen solchen Versuch abgewehrt hat oder ein Chat-Verzeichnis fremde IDs
    fuehrt."""
    label = t("Projekttrennung")
    try:
        findings = integrity.scan(mappings)
    except OSError as exc:
        return {**_c("separation", label, "warn", t("Prüfung fehlgeschlagen: {exc}", exc=exc)), "transient": True}
    blocking = [f for f in findings if f.blocking]
    if blocking:
        projects = sorted({p for f in blocking for p in f.projects})
        return _c("separation", label, "error",
                  t("{n} Nachricht(en) im falschen Projekt/Chat ({projects}) – "
                    "betroffene Projekte werden nicht kuratiert; z. B. {example}",
                    n=len(blocking), projects=", ".join(projects), example=blocking[0].summary()))
    notes = []
    for kind, text in (
        ("index_mismatch", t("Chat-Verzeichnis(se) mit fremden IDs")),
        ("unreadable", t("unlesbare Nachrichtendatei(en)")),
        ("unknown_project", t("Nachricht(en) ohne zugeordnete Projekt-ID (werden nicht kuratiert)")),
    ):
        hits = [f for f in findings if f.kind == kind]
        if hits:
            notes.append(f"{len(hits)} {text} ({', '.join(sorted({p for f in hits for p in f.projects}))})")
    if notes:
        return _c("separation", label, "warn", "; ".join(notes))
    return _c("separation", label, "ok", t("keine Nachricht im falschen Projekt"))


def _firefox_profiles() -> list[Path]:
    return [p for p in FIREFOX_DIR.glob("*") if (p / "extensions.json").is_file()]


def _version_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except ValueError:
        return (0,)


def check_extension(chat_sources: tuple[str, ...] = ("chatgpt", "claude"), claude_required: bool = False) -> dict:
    label = t("Firefox-Erweiterung")
    for profile in _firefox_profiles():
        try:
            addons = json.loads((profile / "extensions.json").read_text(encoding="utf-8")).get("addons", [])
        except (OSError, ValueError):
            continue
        for a in addons:
            if a.get("id") != EXTENSION_ID:
                continue
            version = a.get("version") or "?"
            origins = list((a.get("userPermissions") or {}).get("origins") or [])
            # Nachtraeglich erteilte (optionale) Seitenzugriffe speichert Firefox
            # nicht in extensions.json, sondern in extension-preferences.json.
            try:
                prefs = json.loads((profile / "extension-preferences.json").read_text(encoding="utf-8"))
                origins += (prefs.get(EXTENSION_ID) or {}).get("origins") or []
            except (OSError, ValueError):
                pass
            if a.get("userDisabled") or a.get("appDisabled"):
                return _c("extension", label, "error", t("v{version} ist deaktiviert", version=version))
            if not a.get("active", True) and not a.get("visible", True):
                # Von einer temporaer (about:debugging) geladenen Version mit
                # derselben ID ueberlagert; deren Rechte stehen nicht hier.
                return _c("extension", label, "warn",
                          t("läuft als temporär geladene Version (installiert: v{version}) – fällt nach "
                            "einem Firefox-Neustart weg; neue Version signieren lassen und installieren",
                            version=version))
            if "chatgpt" in chat_sources and not any("chatgpt.com" in o for o in origins):
                return _c("extension", label, "error",
                          t("v{version}: Zugriff auf chatgpt.com nicht erteilt – exportiert nur nach Klick "
                            "(about:addons → Polaris → Berechtigungen)", version=version))
            if _version_tuple(version) < MIN_EXTENSION_VERSION:
                return _c("extension", label, "warn",
                          t("installiert ist v{version}; eine neuere Version läuft höchstens temporär "
                            "und fällt nach einem Firefox-Neustart weg (signieren lassen)", version=version))
            if "claude" in chat_sources and _version_tuple(version) < (0, 2, 0):
                return _c("extension", label, "error",
                          t("v{version} unterstützt Claude-Erfassung noch nicht", version=version))
            if "claude" in chat_sources and not any("claude.ai" in o for o in origins):
                return _c("extension", label, "error" if claude_required else "warn",
                          t("v{version}: Zugriff auf claude.ai nicht erteilt – Claude-Export ruht "
                            "(Polaris-Symbol auf claude.ai anklicken → Zugriff erlauben)", version=version))
            granted = t(" und ").join(domain for source, domain in
                                   (("chatgpt", "chatgpt.com"), ("claude", "claude.ai"))
                                   if source in chat_sources and any(domain in o for o in origins))
            return _c("extension", label, "ok", t("v{version}, Zugriff auf {granted} erteilt", version=version, granted=granted))
    return _c("extension", label, "error", t("nicht installiert"))


def check_native_host() -> dict:
    try:
        manifest = json.loads(NATIVE_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _c("native-host", "Native Host", "warn",
                  t("nicht registriert – Erweiterung nutzt Downloads (bridge/install-native-host.sh)"))
    path = Path(manifest.get("path", ""))
    if not (path.is_file() and os.access(path, os.X_OK)):
        return _c("native-host", "Native Host", "warn", t("registriert, aber {path} fehlt/nicht ausführbar", path=path))
    return _c("native-host", "Native Host", "ok", t("registriert"))


# Nur fuer die Doku des Plugin-Repos; eine abweichende Kopie aendert nichts an
# der Funktion und ist keine Warnung wert (seit 2026-11-04).
WIDGET_DOC_FILES = {"README.md", "LICENSE", "preview.png"}


def _tree(root: Path) -> dict[str, bytes]:
    return {str(f.relative_to(root)): f.read_bytes() for f in sorted(root.rglob("*"))
            if f.is_file() and str(f.relative_to(root)) not in WIDGET_DOC_FILES}


def check_widget(src: Path | None = None, active: Path | None = None) -> dict | None:
    """Ist die aktive Widget-Kopie auf dem Stand des Programmordners? Ohne
    installiertes Widget (--no-widget) keine Zeile. Liest nur ein paar kleine
    Dateien."""
    src = src or WIDGET_SRC
    active = active or WIDGET_ACTIVE
    if not active.is_dir() or not src.is_dir():
        return None
    # Aus dem Marktplatz bzw. per `omarchy plugin add` (seit 2026-11-04):
    # aktualisiert `omarchy plugin update`, keine Kopie zu vergleichen.
    if (active / ".git").exists():
        return _c("widget", "Widget", "ok", t("git-Checkout, aktualisiert per omarchy plugin update"))
    try:
        want, have = _tree(src), _tree(active)
    except OSError as exc:
        return _c("widget", "Widget", "warn", t("Kopie nicht lesbar: {exc}", exc=exc))
    differ = sorted(n for n in want.keys() | have.keys() if want.get(n) != have.get(n))
    if differ:
        names = ", ".join(differ[:3]) + (" …" if len(differ) > 3 else "")
        repo = src.parents[1]
        return _c("widget", "Widget", "warn", t("Kopie veraltet ({names}) – {hint}", names=names, hint=t(WIDGET_SYNC_HINT)),
                  command=f"{_sh(repo / 'install.sh')} --yes --no-units --no-backup --no-memory && omarchy restart shell")
    return _c("widget", "Widget", "ok", t("Kopie aktuell"))


UPDATE_STATE = HOME / ".local" / "state" / "polaris" / "update-check.json"
UPDATE_SCRIPT = Path(__file__).resolve().parents[2] / "update.sh"
UPDATE_MAX_AGE_H = 24
UPDATE_ATTEMPT = HOME / ".local" / "state" / "polaris" / "update-check.attempt"
UPDATE_RETRY_S = 3600


def check_update(now: datetime) -> dict | None:
    """Gibt es einen neueren Polaris-Stand (git-Checkout, seit 2026-10-23)?
    Ausnahme vom Grundsatz "nur Zustandsdateien": hoechstens einmal am Tag ein
    `git fetch` ueber `update.sh --check`, sonst nur die Zustandsdatei. Ohne
    git-Checkout (Installationspaket) keine Zeile."""
    if not (UPDATE_SCRIPT.parent / ".git").exists():
        return None
    state: dict = {}
    try:
        state = json.loads(UPDATE_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    age = _age_days(state.get("checked_at"), now)
    if age is None or age * 24 >= UPDATE_MAX_AGE_H:
        # Seit 2026-11-07 (ADR 003) losgeloest im Hintergrund: der Health Check
        # wartet nie auf das Netz (vorher bis 70 s im Widget-Aufruf). Der neue
        # Zustand erscheint beim naechsten Aufruf. Ohne Netz schreibt update.sh
        # keinen Zustand; der Versuchsmarker begrenzt dann auf einen je Stunde.
        try:
            last_try = UPDATE_ATTEMPT.stat().st_mtime
        except OSError:
            last_try = 0.0
        if time.time() - last_try >= UPDATE_RETRY_S:
            try:
                UPDATE_ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
                UPDATE_ATTEMPT.touch()
                subprocess.Popen([str(UPDATE_SCRIPT), "--check"], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            except OSError:
                pass
        if age is None:
            return _c("update", "Update", "ok", t("Prüfung läuft bzw. nicht möglich (offline?) – polaris update --check"))
    # Scheitert die Pruefung dauerhaft, bleibt der Zustand alt: sichtbar machen.
    stale = t(", zuletzt geprüft {age}", age=_fmt_age(age)) if age is not None and age > 1 else ""
    # Gelb schon nach 3 Tagen ohne erfolgreiche Pruefung (Gutachten agy 2026-11-07;
    # vorher 14): eine dauerhaft scheiternde Pruefung soll bald auffallen.
    if age is not None and age > 3 and int(state.get("behind") or 0) == 0:
        return _c("update", "Update", "warn",
                  t("zuletzt geprüft {age} – polaris update --check", age=_fmt_age(age)),
                  command="polaris update --check")
    if int(state.get("behind") or 0) > 0:
        return _c("update", "Update", "warn",
                  t("verfügbar: {local} → {remote} – polaris update",
                    local=state.get("local", "?"), remote=state.get("remote", "?")), command="polaris update")
    return _c("update", "Update", "ok", t("aktuell ({local})", local=state.get("local", "?")) + stale)


def check_curator_timer() -> dict:
    result = _systemctl_user("show", "polaris-curator.service", "--property=Result", "--value")
    enabled = _systemctl_user("is-enabled", "polaris-curator.timer")
    if enabled != "enabled":
        return _c("curator", "Curator", "error", t("Timer nicht aktiviert"))
    if result and result != "success":
        return _c("curator", "Curator", "warn", t("letzter Timer-Lauf: {result}", result=result))
    return _c("curator", "Curator", "ok", t("Timer aktiv, letzter Lauf erfolgreich"))


def check_llm() -> dict:
    """Sind die CLIs der konfigurierten Modell-Runtime da? Nur `which`, kein
    Aufruf (kostet nichts); Anmeldung prueft `polaris-curator llm-check --call`."""
    from . import config as config_mod, llm

    label = t("Modell")
    try:
        cfg = config_mod.load_config()
    except Exception as e:  # noqa: BLE001 - kaputte curator.yaml
        return _c("llm", label, "error", t("curator.yaml unlesbar: {e}", e=e))
    if cfg.runtime not in llm.RUNTIMES:
        return _c("llm", label, "error", t("unbekannte runtime {runtime!r}", runtime=cfg.runtime))
    bins = llm.runtime_binaries(cfg)
    missing = [b for b, path in bins.items() if path is None]
    main = llm.main_binary(cfg)
    if main in missing:
        return _c("llm", label, "error", t("{main} fehlt – polaris-curator llm-check", main=main))
    # Fremdinhalte (Chats, Anhaenge) laufen in bubblewrap; ohne Sandbox laut melden.
    from . import sandbox
    notes = []
    if missing:
        notes.append(t("{missing} (Ersatz/Prüfer) fehlt", missing=", ".join(missing)))
    # Abgelehnte Uebernahme einer erneuerten Anmeldung (llm._sync_back_codex_auth):
    # ohne Hinweis verloere der Nutzer Stunden spaeter still die Anmeldung.
    try:
        cs = json.loads(llm.CRED_SYNC_STATE.read_text(encoding="utf-8"))
        if cs.get("refused") and time.time() - float(cs.get("at", 0)) < 7 * 86400:
            notes.append(t("erneuerte Anmeldung nicht übernommen ({file}: {fields}) – ggf. neu anmelden",
                           file=Path(str(cs.get("file", "?"))).name,
                           fields=", ".join(str(f) for f in cs["refused"][:4])))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    problem = sandbox.status()
    if problem and os.environ.get("POLARIS_NO_SANDBOX") != "1":
        # Seit 2026-11-07 fail-closed: ohne Sandbox laeuft keine Kuratierung.
        return _c("llm", label, "error",
                  t("Sandbox nicht nutzbar – Kuratierung ausgesetzt: {problem}", problem=problem))
    if problem:
        notes.append(t("ohne Sandbox: {problem}", problem=problem))
    if notes:
        return _c("llm", label, "warn", f"{cfg.runtime} {cfg.model}; " + "; ".join(notes))
    return _c("llm", label, "ok", f"{cfg.runtime} {cfg.model}")


def check_backup(now: datetime) -> dict:
    if not BACKUP_STATE.exists():
        # Optionaler Baustein (seit 2026-10-07): auf Rechnern ohne
        # omarchy-backup kein Fehler, sondern ein klarer Hinweis.
        if shutil.which("omarchy-backup") is None:
            return _c("backup", "omarchy-backup", "ok", t("nicht eingerichtet (optional)"))
        return _c("backup", "omarchy-backup", "warn", t("installiert, aber noch kein Snapshot"))
    try:
        state = json.loads(BACKUP_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _c("backup", "omarchy-backup", "error", t("Zustandsdatei unlesbar"))
    snaps = state.get("snapshots") or []
    last = max((s.get("created_at", "") for s in snaps), default="")
    pushed = max((s.get("created_at", "") for s in snaps if s.get("remote_pushed")), default="")
    last_days, pushed_days = _age_days(last or None, now), _age_days(pushed or None, now)
    doctor = state.get("last_doctor_status") or "?"
    result = _systemctl_user("show", "omarchy-backup-snapshot.service", "--property=Result", "--value")
    detail = t("Snapshot {last}, hochgeladen {pushed}, doctor {doctor}",
               last=_fmt_age(last_days), pushed=_fmt_age(pushed_days), doctor=doctor)
    if doctor not in ("HEALTHY", "?"):
        return _c("backup", "omarchy-backup", "error", detail, command="omarchy-backup doctor")
    if pushed_days is None or pushed_days > 7:
        return _c("backup", "omarchy-backup", "error", detail)
    if (last_days or 99) > 2 or (pushed_days or 99) > 2 or (result and result != "success"):
        suffix = t(", letzter Lauf: {result}", result=result) if result and result != "success" else ""
        return _c("backup", "omarchy-backup", "warn", detail + suffix)
    return _c("backup", "omarchy-backup", "ok", detail)


def check_backup_integrity() -> dict | None:
    """Zielpruefung von omarchy-backup (seit 2026-11-05): Befunde sofort
    zeigen, nicht erst nach dem naechsten doctor-Lauf. Fehlt die Datei
    (aelteres omarchy-backup, nie geprueft): keine Zeile."""
    try:
        status = json.loads(BACKUP_INTEGRITY.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return _c("backup-integrity", t("Backup-Ziel"), "warn", t("Prüfergebnis unlesbar"))
    problems = [str(p) for p in status.get("problems") or []]
    unrecorded = [str(u) for u in status.get("unrecorded") or []]
    if problems:
        return _c("backup-integrity", t("Backup-Ziel"), "error",
                  t("außerhalb dieses Rechners verändert: {items} – omarchy-backup doctor",
                    items=", ".join(problems[:3]) + (" …" if len(problems) > 3 else "")),
                  command="omarchy-backup doctor")
    if unrecorded:
        return _c("backup-integrity", t("Backup-Ziel"), "warn",
                  t("ungeprüfte ältere Uploads: {items} – omarchy-backup doctor", items=", ".join(unrecorded[:3])),
                  command="omarchy-backup doctor")
    return _c("backup-integrity", t("Backup-Ziel"), "ok", t("unverändert"))


def _untracked_now(repo: Path) -> list[str] | None:
    """Aktuell nicht versionierte Dateien eines Repos (None: nicht pruefbar).
    Nur fuer Repos, die das Manifest meldet; Pfad nur unterhalb von HOME."""
    try:
        if not repo.resolve().is_relative_to(HOME.resolve()) or not (repo / ".git").exists():
            return None
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard", "-z"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if out.returncode != 0:
        return None
    return [f for f in out.stdout.split("\0") if f]


def _home_rel(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(HOME))
    except ValueError:
        return str(path)


def check_repos() -> dict | None:
    """Was in gesicherten git-Repos nicht im Backup landet (seit 2026-11-05):
    neue, nicht versionierte Dateien und verschwundene Repos. Grundlage ist
    das Manifest des neuesten lokalen Snapshots; nur fuer dort gemeldete Repos
    fragt der Check git direkt (Dateinamen, und ob es inzwischen erledigt ist)."""
    try:
        state = json.loads(BACKUP_STATE.read_text(encoding="utf-8"))
        newest = max(state.get("snapshots") or [], key=lambda s: s.get("created_at", ""))
        manifest = json.loads((BACKUP_SNAPSHOTS / str(newest["name"]) / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    missing, files, resolved, commands = [], [], 0, []
    for repo in manifest.get("repos") or []:
        path = HOME / str(repo.get("path", ""))
        if repo.get("missing"):
            missing.append(_home_rel(path))
        elif int(repo.get("untracked") or 0) > 0:
            now = _untracked_now(path)
            if now is None:
                files.append(t("{repo} ({n} Datei(en))", repo=_home_rel(path), n=int(repo["untracked"])))
            elif now:
                files += [f"{_home_rel(path)}/{f}" for f in now]
                repo_q = _sh(path)
                names = " ".join(shlex.quote(f) for f in now)
                msg = shlex.quote(t("Neue Dateien sichern: {names}", names=", ".join(now[:3]) + (" …" if len(now) > 3 else "")))
                commands.append(f"git -C {repo_q} add -- {names} && git -C {repo_q} commit -m {msg}")
            else:
                resolved += 1
    if missing:
        return _c("repos", t("Repos"), "warn",
                  t("gesichertes Repo fehlt: {items} – verschoben? Pfad in ~/.config/omarchy-backup/paths.conf anpassen",
                    items=", ".join(missing[:3])))
    if files:
        shown = ", ".join(files[:3]) + (t(" und {n} weitere", n=len(files) - 3) if len(files) > 3 else "")
        return _c("repos", t("Repos"), "warn",
                  t("wird nicht gesichert: {items} – neue Datei in einem git-Repo; wichtig: committen, "
                    "sonst in .gitignore eintragen", items=shown),
                  command=" && ".join(commands) or None)
    if resolved:
        return _c("repos", t("Repos"), "ok", t("erledigt – der nächste Snapshot sichert es"))
    return _c("repos", t("Repos"), "ok", t("alles im Backup"))


RCLONE_VFS_META = HOME / ".cache" / "rclone" / "vfsMeta"
UPLOAD_STALE_SECONDS = 3600


def _upload_backlog() -> tuple[int, int] | None:
    """(Anzahl, Alter der aeltesten in h) lokal geaenderter, noch nicht
    hochgeladener Dateien (rclone --vfs-cache-mode full, Dirty=true) aelter als
    1 h. Schreiben gelingt lokal auch ohne Upload - ein Upload-Stau war sonst
    unsichtbar (Review Runde 3)."""
    if not RCLONE_VFS_META.is_dir():
        return None
    now = datetime.now().timestamp()
    stale = []
    for meta in RCLONE_VFS_META.rglob("*"):
        try:
            if not meta.is_file() or now - meta.stat().st_mtime < UPLOAD_STALE_SECONDS:
                continue
            if b'"Dirty": true' in meta.read_bytes()[:2000]:
                stale.append(now - meta.stat().st_mtime)
        except OSError:
            continue
    if not stale:
        return None
    return len(stale), int(max(stale) // 3600)


def _fstype(path: Path) -> str:
    try:
        return subprocess.run(["findmnt", "-n", "-o", "FSTYPE", "--target", str(path)],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _read_polaris_yaml(name: str) -> dict:
    try:
        import yaml

        return yaml.safe_load((POLARIS_CONFIG_DIR / name).read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 - fehlend/kaputt: wie leer behandeln
        return {}


def check_mount() -> dict:
    """Projektordner-Speicher (seit 2026-10-07 nicht mehr fest ~/Projekte als
    Google-Drive-Mount): prueft jeden project_root aus der Bridge-Konfiguration.
    Fehler, wenn ein Root fehlt oder zugeordnete Projektordner darunter fehlen
    (so faellt auch ein abgefallener Mount auf, dessen leerer Mountpunkt noch
    existiert). Bei rclone-Mounts zusaetzlich der Upload-Stau."""
    roots = [Path(str(r)).expanduser() for r in (_read_polaris_yaml("config.yaml").get("project_roots") or [])]
    if not roots:
        return _c("mount", t("Projektordner"), "warn",
                  t("keine project_roots konfiguriert – polaris roots add <Ordner>"))
    label = t("Projektordner ({roots})", roots=", ".join(str(r).replace(str(HOME), "~", 1) for r in roots))
    mapped = [Path(str(e.get("local_path"))).expanduser()
              for e in (_read_polaris_yaml("projects.yaml").get("projects") or {}).values()
              if isinstance(e, dict) and e.get("status") == "ok" and e.get("local_path")]
    kinds = []
    for root in roots:
        short = str(root).replace(str(HOME), "~", 1)
        fstype = _fstype(root) if root.is_dir() else ""
        rclone = fstype.startswith("fuse.rclone")
        hint = t("Laufwerk eingehängt?")
        if not root.is_dir():
            return _c("mount", label, "error", t("{short} fehlt – {hint}", short=short, hint=hint))
        missing = [m for m in mapped if m.parent == root and not m.is_dir()]
        if missing:
            return _c("mount", label, "error",
                      t("{n} zugeordnete(r) Projektordner unter {short} fehlt – {hint}",
                        n=len(missing), short=short, hint=hint))
        if rclone:
            pending = _upload_backlog()
            if pending:
                n, oldest_h = pending
                level = "error" if oldest_h >= 24 else "warn"
                return _c("mount", label, level,
                          t("eingehängt, aber {n} Datei(en) seit {h} h nicht hochgeladen – rclone-Log prüfen",
                            n=n, h=oldest_h))
            kinds.append(t("rclone eingehängt"))
        else:
            kinds.append(t("erreichbar"))
    return _c("mount", label, "ok", ", ".join(dict.fromkeys(kinds)))


# --- Zwischenspeicher fuer teure Pruefungen (ADR 003, 2026-11-07) ----------
# Das Widget ruft `health` alle 10 min auf. check_separation las dabei jedes
# Mal alle Rohdaten-JSONs vom Cloud-Laufwerk, check_memory startete memlint.
# Beide rechnen nur neu, wenn sich ihr Fingerabdruck aendert (nur
# Verzeichniseintraege bzw. Datei-Metadaten, keine Inhalte), spaetestens
# nach HEALTH_CACHE_MAX_AGE. POLARIS_HEALTH_NO_CACHE=1 schaltet ab (Tests).
HEALTH_CACHE = HOME / ".local" / "state" / "polaris" / "health-cache.json"
HEALTH_CACHE_MAX_AGE = 6 * 3600


def _dir_entries(directory: Path) -> list:
    out = []
    try:
        with os.scandir(directory) as it:
            for e in it:
                try:
                    st = e.stat(follow_symlinks=False)
                    out.append((e.name, st.st_size, st.st_mtime_ns))
                except OSError:
                    continue
    except OSError:
        return [("<fehlt>",)]
    return sorted(out)


def _lentry(p: Path) -> tuple:
    """Metadaten ohne Symlinks zu folgen; Ziel eines Symlinks gehoert dazu."""
    try:
        st = p.lstat()
        link = os.readlink(p) if p.is_symlink() else ""
        return (str(p), st.st_mode, st.st_size, st.st_mtime_ns, link, p.exists())
    except OSError:
        return (str(p), "<fehlt>")


def _separation_fingerprint() -> list:
    mappings = integrity.load_mappings()
    parts: list = [datetime.now().date().isoformat(), language(), _dir_entries(integrity.CONFLICTS_DIR)]
    try:
        parts.append(sorted((k, str(v)) for k, v in mappings.items()))
    except AttributeError:
        parts.append(repr(mappings))
    for folder in integrity._project_folders(mappings, []):
        for _src, d in layout.chat_messages_dirs(folder):
            parts.append((str(d), _dir_entries(d), _dir_entries(d.parent / "conversations")))
    return parts


def _memory_fingerprint() -> list:
    """Alle Eingaben von memlint: der Baum (auch Symlinks, kaputte Links,
    Ordner) und die Systempruefungen ausserhalb - Agenten-Einstiege, Skill-
    Ordner, Eintraege aus entrypoints.conf, omarchy-backup-Pfadregeln."""
    parts: list = [language(), _lentry(MEMLINT)]
    try:
        tree = sorted(MEM_ROOT.rglob("*"))
    except OSError:
        tree = []
    parts += [_lentry(p) for p in tree if ".git" not in p.parts]
    outside = [HOME / ".claude" / "CLAUDE.md", HOME / ".codex" / "AGENTS.md", HOME / ".gemini" / "GEMINI.md",
               HOME / ".agents" / "skills", HOME / ".claude" / "skills", HOME / ".codex" / "skills",
               HOME / ".config" / "omarchy-backup" / "paths.conf"]
    try:
        for line in (MEM_ROOT / "entrypoints.conf").read_text(encoding="utf-8").splitlines():
            field = line.split("#", 1)[0].split()
            if field:
                outside.append(Path(os.path.expanduser(field[0])))
    except OSError:
        pass
    parts += [_lentry(p) for p in outside]
    parts.append(_dir_entries(HOME / ".config" / "omarchy-backup" / "paths.d"))
    for d in (HOME / ".agents" / "skills", HOME / ".claude" / "skills", HOME / ".codex" / "skills"):
        parts.append(_dir_entries(d))
    return parts


def _cached(name: str, fingerprint, compute, max_age: float | None = None) -> dict:
    if os.environ.get("POLARIS_HEALTH_NO_CACHE") == "1":
        return compute()
    try:
        fp = hashlib.sha256(json.dumps(fingerprint(), default=str).encode()).hexdigest()
    except Exception:  # noqa: BLE001 - ohne Fingerabdruck einfach rechnen
        return compute()
    try:
        cache = json.loads(HEALTH_CACHE.read_text(encoding="utf-8"))
        cache = cache if isinstance(cache, dict) else {}
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(name)
    now = time.time()
    try:  # Zwischenspeicher ist Eingabe wie jede andere: pruefen, nicht vertrauen
        fresh = (isinstance(hit, dict) and hit.get("fp") == fp
                 and 0 <= now - float(hit.get("at", 0)) < (HEALTH_CACHE_MAX_AGE if max_age is None else max_age))
    except (TypeError, ValueError):
        fresh = False
    check = hit.get("check") if fresh else None
    if isinstance(check, dict) and check.get("id") == name and check.get("level") in ("ok", "warn", "error"):
        return check
    result = compute()
    if result.get("transient"):  # voruebergehender Fehler: beim naechsten Mal neu
        return {k: v for k, v in result.items() if k != "transient"}
    cache[name] = {"fp": fp, "at": now, "check": result}
    try:
        HEALTH_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HEALTH_CACHE.with_name(HEALTH_CACHE.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, HEALTH_CACHE)
    except OSError:
        pass  # Zwischenspeicher ist entbehrlich
    return result


def check_memory() -> dict:
    """Maschinengedaechtnis: memlint-Ergebnis (zwischengespeichert, solange
    sich keine seiner Eingaben aendert) plus Zustand des Spiegels (immer frisch)."""
    return _with_mirror(_cached("memory", _memory_fingerprint, _memlint_check))


def _with_mirror(c: dict) -> dict:
    """Spiegelzustand nie aus dem Zwischenspeicher: "Spiegel neuer als lokal"
    (moegliche Manipulation) und das Alter muessen sofort sichtbar sein."""
    if not c.get("mirror"):
        return c
    level, mirror = mirror_status()
    out = {k: v for k, v in c.items() if k != "mirror"}
    # immer die schlechtere Stufe (Gutachten Codex 2026-11-07: ein Spiegel darf
    # einen memlint-Befund nie ueberdecken, auch nach kuenftigen Umbauten)
    out["level"] = max((c.get("level", "ok"), level), key=lambda lv: _LEVELS.get(lv, 0))
    out["detail"] = c["detail"] + (f", {mirror}" if mirror else "")
    return out


def _memlint_check() -> dict:
    """Maschinengedaechtnis ~/.config/ai-agents per memlint (deterministisch, stdlib)."""
    label = t("Maschinengedächtnis")
    if not MEM_ROOT.is_dir():
        return _c("memory", label, "ok", t("nicht eingerichtet (optional)"))
    if not MEMLINT.is_file():
        return _c("memory", label, "warn", t("{path} fehlt", path=MEMLINT))
    try:
        proc = subprocess.run(["python3", str(MEMLINT), "--json", "--root", str(MEM_ROOT)],
                              capture_output=True, text=True, timeout=30,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        report = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        # transient: nicht zwischenspeichern (z. B. Zeitlimit unter Last)
        return {**_c("memory", label, "warn", t("memlint konnte nicht ausgeführt werden")), "transient": True}
    findings = report.get("findings") or []
    errors = [f for f in findings if f.get("level") == "error"]
    warnings = [f for f in findings if f.get("level") != "error"]
    if errors:
        first = errors[0]
        level = "error" if any(f.get("check") in MEMLINT_SEVERE for f in errors) else "warn"
        return _c("memory", label, level,
                  t("{n} Fehler (z. B. {check}: {file}) – memlint.py ausführen",
                    n=len(errors), check=first.get("check"), file=first.get("file")))
    # Groessenhinweise halten die Handoffs schlank, sind aber kein Ausfall.
    note = t(", {n} Hinweis(e)", n=len(warnings)) if warnings else ""
    detail = t("konsistent, {n} Einträge", n=report.get("stats", {}).get("tags", 0)) + note
    return {**_c("memory", label, "ok", detail), "mirror": True}


def check_security(now: datetime) -> dict:
    """Ergebnis des letzten Sicherheitsabgleichs (polaris-radar). Liest nur die
    Zustandsdatei, kein Netz. Gelb, nie rot: Die Befunde brauchen eine
    Bewertung (Fix-Stand, Betroffenheit), sie sind kein Ausfall."""
    label = t("Sicherheit")
    try:
        state = json.loads(SECURITY_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _c("security", label, "warn", t("noch nicht geprüft – polaris-radar"))
    age = _age_days(state.get("checked_at"), now)
    finds = state.get("findings") or []
    if finds:
        more = t(" (+{n} weitere)", n=len(finds) - 1) if len(finds) > 1 else ""
        return _c("security", label, "warn",
                  f"{finds[0].get('text', '?')}{more} – handoff/omarchy-radar.md")
    if age is None or age > SECURITY_MAX_DAYS:
        return _c("security", label, "warn", t("zuletzt geprüft {age} – polaris-radar", age=_fmt_age(age)))
    if state.get("error"):
        return _c("security", label, "warn", t("Abgleich unvollständig ({error}) – polaris-radar", error=state["error"]))
    return _c("security", label, "ok", t("keine Befunde (geprüft {age})", age=_fmt_age(age)))


def _polaris_config_value(key: str):
    return _read_polaris_yaml("config.yaml").get(key)


def mirror_status(now: datetime | None = None) -> tuple[str, str]:
    """Spiegel des Gedaechtnisses (memory-mirror, seit 2026-10-08). Nur gelb:
    Die lokale Fassung ist die Arbeitskopie, ein fehlender Spiegel legt nichts lahm."""
    if not _polaris_config_value("memory_mirror"):
        return "ok", ""
    now = now or datetime.now(timezone.utc)
    try:
        state = json.loads(MEMORY_MIRROR_STATE.read_text())
    except (OSError, ValueError):
        return "warn", t("Spiegel noch nie gelaufen – polaris-memory-mirror")
    if state.get("last_result") == "hold":
        return "warn", t("Spiegel gesperrt: bei der Installation nicht zurückgeholt – entscheiden (polaris-memory-mirror)")
    if state.get("last_result") == "mirror_newer":
        return "warn", t("Spiegel neuer als lokal – Unterschiede prüfen, nur nach Entscheidung zurückholen (polaris-memory-mirror)")
    days = _age_days(state.get("last_success"), now)
    if days is None or days > MEMORY_MIRROR_MAX_DAYS:
        why = f" ({state.get('detail')})" if state.get("last_result") != "ok" and state.get("detail") else ""
        return "warn", t("Spiegel {age}", age=_fmt_age(days)) + why
    return "ok", t("gespiegelt {age}", age=_fmt_age(days))


# Typische Platzfresser, die sich gefahrlos verkleinern lassen (Idee aus
# omasweep, 2026-10-08). Nur gemessen und genannt, nie geloescht. Nicht dabei:
# ~/.cache/rclone (VFS-Cache von ~/Projekte, kann noch nicht hochgeladene
# Dateien enthalten).
RECLAIM_CANDIDATES = [
    ("pacman-Cache", Path("/var/cache/pacman/pkg"), "paccache -rk2"),
    ("Papierkorb", HOME / ".local" / "share" / "Trash", ""),
    ("yay-Cache", HOME / ".cache" / "yay", ""),
    ("paru-Cache", HOME / ".cache" / "paru", ""),
    ("Journal", Path("/var/log/journal"), "journalctl --vacuum-time=4weeks"),
    ("Coredumps", Path("/var/lib/systemd/coredump"), ""),
]
RECLAIM_MIN_BYTES = 512 * 2**20
COREDUMP_DIR = Path("/var/lib/systemd/coredump")
CRASH_WINDOW_HOURS = 24


def _du_bytes(path: Path) -> int | None:
    """Groesse per du; Teilfehler (z. B. root-eigene Unterordner im yay-Cache)
    liefern trotzdem die lesbare Summe."""
    try:
        out = subprocess.run(["du", "-sb", "--one-file-system", str(path)],
                             capture_output=True, text=True, timeout=30).stdout
        return int(out.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def _fmt_size(n: int) -> str:
    gb = n / 2**30
    if gb >= 10:
        return f"{gb:.0f} GB"
    return f"{gb:.1f} GB" if language() == "en" else f"{gb:.1f} GB".replace(".", ",")


MOUNTINFO = Path("/proc/self/mountinfo")


def _backing_device(path: str | Path) -> str | None:
    """Quellgeraet des Mounts, auf dem path liegt. Nicht st_dev: auf Btrfs hat
    jedes Subvolume (@, @pkg, @log ...) ein eigenes st_dev, teilt aber den Platz."""
    try:
        target = os.path.realpath(path)
        lines = MOUNTINFO.read_text().splitlines()
    except OSError:
        return None
    best, source = "", None
    for line in lines:
        pre, sep, post = line.partition(" - ")
        fields, tail = pre.split(), post.split()
        if not sep or len(fields) < 5 or len(tail) < 2:
            continue
        mnt = fields[4].replace("\\040", " ")
        if (target == mnt or target.startswith(mnt.rstrip("/") + "/")) and len(mnt) >= len(best):
            best, source = mnt, tail[1]
    return source


def reclaimable(mount: str) -> list[tuple[str, int, str]]:
    """Groesste Kandidaten auf demselben Geraet wie mount, absteigend."""
    dev = _backing_device(mount)
    if not dev:
        return []
    found = []
    for label, path, hint in RECLAIM_CANDIDATES:
        try:
            if not path.is_dir() or path.is_symlink() or _backing_device(path) != dev:
                continue
        except OSError:
            continue
        size = _du_bytes(path)
        if size and size >= RECLAIM_MIN_BYTES:
            found.append((label, size, hint))
    return sorted(found, key=lambda x: -x[1])


def _parse_coredump_name(name: str) -> tuple[str, datetime] | None:
    """core.<comm>.<uid>.<boot-id>.<pid>.<usec>[.zst|.lz4|.xz]; comm kann Punkte enthalten."""
    if not name.startswith("core."):
        return None
    base = name[5:]
    for ext in (".zst", ".lz4", ".xz"):
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    parts = base.rsplit(".", 4)
    if len(parts) != 5 or not parts[4].isdigit():
        return None
    comm = parts[0].replace("\\x20", " ")
    return comm, datetime.fromtimestamp(int(parts[4]) / 1e6, timezone.utc)


def check_crashes(now: datetime | None = None, window_hours: int = CRASH_WINDOW_HOURS) -> dict | None:
    """Neue Coredumps (Idee aus omasweep): gelb, solange ein Absturz juenger als
    window_hours ist. Liest nur die Dateinamen, keine Inhalte."""
    now = now or datetime.now(timezone.utc)
    try:
        names = [e.name for e in os.scandir(COREDUMP_DIR)]
    except OSError:
        return None
    dumps = [d for d in map(_parse_coredump_name, names) if d]
    recent = [comm for comm, ts in dumps if (now - ts).total_seconds() < window_hours * 3600]
    if recent:
        counts: dict[str, int] = {}
        for comm in recent:
            counts[comm] = counts.get(comm, 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])
        listed = ", ".join(f"{c} ({n}×)" if n > 1 else c for c, n in top[:3])
        more = t(" u. a.") if len(top) > 3 else ""
        return _c("crashes", t("Abstürze"), "warn",
                  t("{n} seit {h} h: {listed}{more} – coredumpctl list",
                    n=len(recent), h=window_hours, listed=listed, more=more))
    if dumps:
        last = max(dumps, key=lambda d: d[1])
        return _c("crashes", t("Abstürze"), "ok", t("keine neuen (zuletzt {name}, {age})", name=last[0],
                                                    age=_fmt_age(_age_days(last[1].isoformat(), now))))
    return _c("crashes", t("Abstürze"), "ok", t("keine"))


MODULES_DIR = Path("/usr/lib/modules")
BTRFS_SYSFS = Path("/sys/fs/btrfs")


def check_reboot() -> dict | None:
    """Kernel aktualisiert, aber nicht neu gestartet (seit 2026-11-05): Die
    Module des laufenden Kernels fehlen dann; neue Treiber (USB-Stick,
    Dateisysteme) lassen sich nicht mehr laden."""
    if not MODULES_DIR.is_dir():
        return None
    if (MODULES_DIR / os.uname().release).is_dir():
        return None
    return _c("reboot", t("Neustart"), "warn", t("Kernel aktualisiert – bitte neu starten"))


def check_disk_errors() -> list[dict]:
    """Fehlerzaehler von btrfs (seit 2026-11-05; sysfs, ohne root): jeder
    Lese-, Schreib- oder Pruefsummenfehler ist ein frueher Hinweis auf eine
    sterbende SSD oder Kabelprobleme."""
    bad = []
    for stats in sorted(BTRFS_SYSFS.glob("*/devinfo/*/error_stats")):
        try:
            pairs = dict(line.split() for line in stats.read_text().splitlines() if line.strip())
        except (OSError, ValueError):
            continue
        errs = {k: int(v) for k, v in pairs.items() if v.isdigit() and int(v) > 0}
        if errs:
            fs = stats.parts[-4][:8]
            bad.append(f"{fs}: " + ", ".join(f"{k} {v}" for k, v in sorted(errs.items())))
    if not bad:
        return [] if not any(BTRFS_SYSFS.glob("*/devinfo")) else [_c("disk-errors", t("Plattenfehler"), "ok", t("keine"))]
    return [_c("disk-errors", t("Plattenfehler"), "error",
               t("btrfs meldet Fehler: {items} – Daten sichern, sudo btrfs device stats prüfen", items="; ".join(bad)),
               command="sudo btrfs device stats /")]


def check_system(now: datetime | None = None) -> list[dict]:
    items = []
    seen_devs: set[str | None] = set()
    for mount in ("/", "/home"):
        try:
            usage = shutil.disk_usage(mount)
        except OSError:
            continue
        pct = usage.used * 100 / usage.total
        level = "error" if pct > 95 else "warn" if pct > 85 else "ok"
        detail = t("{pct:.0f} % belegt, {free:.0f} GB frei", pct=pct, free=usage.free / 2**30)
        dev = _backing_device(mount)
        if level != "ok" and dev not in seen_devs:
            big = reclaimable(mount)[:4]
            if big:
                detail += t(" – größte Posten: ") + ", ".join(
                    f"{t(label)} {_fmt_size(size)}" + (f" ({hint})" if hint else "") for label, size, hint in big)
        seen_devs.add(dev)
        items.append(_c(f"disk{mount}", t("Platte {mount}", mount=mount), level, detail))
    failed = []
    for scope in (["systemctl"], ["systemctl", "--user"]):
        try:
            out = subprocess.run([*scope, "--failed", "--no-legend", "--plain"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        failed += [line.split()[0] for line in out.splitlines() if line.strip()]
    items.append(_c("units", "systemd-Units", "warn" if failed else "ok",
                    t("fehlgeschlagen: {units}", units=", ".join(failed[:5])) if failed else t("keine fehlgeschlagen")))
    for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            cap = int((bat / "capacity").read_text().strip())
            status = (bat / "status").read_text().strip()
        except (OSError, ValueError):
            continue
        items.append(_c("battery", t("Akku"), "warn" if cap < 15 and status == "Discharging" else "ok", f"{cap} % ({status})"))
        break
    reboot = check_reboot()
    if reboot:
        items.append(reboot)
    items.extend(check_disk_errors())
    crashes = check_crashes(now)
    if crashes:
        items.append(crashes)
    return items


# Gruppen fuer die Anzeige (seit 2026-09-29, Nutzerwunsch: weniger Zeilen).
# (id, Anzeigename, [(Kurzname, Teil-ID)], Teil-ID fuer die OK-Zusammenfassung)
GROUPS = [
    ("capture", "Erfassung", [("ChatGPT", "chatgpt-archive"), ("Claude", "claude-archive"), ("Bridge", "bridge"),
                              ("Konfiguration", "chat-sources"), ("Erweiterung", "extension"), ("Native Host", "native-host")], "chatgpt-archive"),
    ("separation", "Projekttrennung", [("Projekttrennung", "separation")], "separation"),
    ("curator", "Curator", [("Timer", "curator"), ("Kurationsschritte", "journal"), ("Kuration", "curation"),
                                         ("Modell", "llm"), ("Widget", "widget")],
     "curator"),
    ("storage", "Speicher & Sicherung", [("Projektordner", "mount"), ("Backup", "backup"),
                                         ("Backup-Ziel", "backup-integrity"), ("Repos", "repos")], "backup"),
    ("memory", "Maschinengedächtnis", [("Maschinengedächtnis", "memory")], "memory"),
    ("security", "Sicherheit", [("Sicherheit", "security")], "security"),
]


def _group(gid: str, label: str, members: list[tuple[str, dict]], primary: dict | None) -> dict:
    """Eine Zeile je Gruppe: schlechtester Zustand der Teile; im Text nur die
    auffaelligen Teile, sonst eine kurze Zusammenfassung. Die Teile bleiben in
    "parts" (polaris-curator health --all)."""
    worst = max((_LEVELS[c["level"]] for _n, c in members), default=0)
    level = {0: "ok", 1: "warn", 2: "error"}[worst]
    if level == "ok":
        names = ", ".join(n for n, _c in members)
        if len(members) == 1:
            detail = members[0][1]["detail"]
        else:
            detail = t("{names} in Ordnung", names=names) + (f" – {primary['detail']}" if primary else "")
    else:
        bad = sorted(((n, c) for n, c in members if c["level"] != "ok"), key=lambda nc: -_LEVELS[nc[1]["level"]])
        prefix = len(members) > 1
        detail = " · ".join((f"{n}: " if prefix else "") + c["detail"] for n, c in bad)
    group = {"id": gid, "label": label, "level": level, "detail": detail, "parts": [c for _n, c in members]}
    # Befehl zum Kopieren: der des schlimmsten auffaelligen Teils.
    if level != "ok":
        command = next((c["command"] for _n, c in bad if c.get("command")), None)
        if command:
            group["command"] = command
    return group


def group_components(checks: list[dict]) -> list[dict]:
    by_id = {c["id"]: c for c in checks}
    used: set[str] = set()
    out = []
    for gid, label, parts, primary_id in GROUPS:
        # Namen aus GROUPS sind deutsche Literale; Uebersetzung erst hier.
        members = [(t(name), by_id[pid]) for name, pid in parts if pid in by_id]
        if not members:
            continue
        used.update(pid for _n, pid in parts)
        out.append(_group(gid, t(label), members, by_id.get(primary_id)))
    # Unbekannte (neu hinzugekommene) Pruefungen nie verschlucken.
    out.extend(c for c in checks if c["id"] not in used)
    return out


def check_config(problems: tuple[str, ...]) -> dict | None:
    if not problems:
        return None
    return _c("chat-sources", t("Chatquellen-Konfiguration"), "error", " ".join(problems))


def _count_alarm_days(checks: list[dict]) -> None:
    """Alarmmuedigkeit messen (2026-11-08, Perspektivwechsel/Kopfstand): je
    Pruefung die Tage mit warn/error, dazu die Tage mit Health-Lauf als Nenner.
    Bleibt eine Zeile wochenlang gelb, ohne dass jemand handelt, ist sie
    Rauschen oder ein ignoriertes Problem (Auswertung ~05.12., ADR 004).
    Nur Pruef-IDs, nie Texte; hoechstens ein Schreibvorgang je Tag und Name."""
    from . import usage
    usage.days(["health:day"] + [f"health-{c['level']}:{c['id']}" for c in checks
                                 if c.get("level") in ("warn", "error") and c.get("id")])


def collect(projects: dict, max_days_without_chatgpt: int, max_days_without_claude: int = 7,
            chat_sources: tuple[str, ...] = ("chatgpt", "claude"), sources_explicit: bool = False,
            config_problems: tuple[str, ...] = ()) -> dict:
    now = datetime.now(timezone.utc)
    claude_required = sources_explicit and "claude" in chat_sources
    checks = [
        check_config(config_problems),
        check_archive(projects, max_days_without_chatgpt, sources_explicit) if "chatgpt" in chat_sources else None,
        check_bridge_without_chatgpt(projects) if chat_sources and "chatgpt" not in chat_sources else None,
        check_claude_archive(projects, max_days_without_claude, now, claude_required)
        if "claude" in chat_sources else None,
        _cached("separation", _separation_fingerprint, check_separation),
        check_journals(projects),
        check_curation(projects, now),
        check_extension(chat_sources, claude_required) if chat_sources else None,
        check_native_host() if chat_sources else None,
        check_curator_timer(),
        check_llm(),
        check_backup(now),
        check_backup_integrity(),
        check_repos(),
        check_mount(),
        check_memory(),
        check_security(now),
        check_widget(),
        check_update(now),
    ]
    checks = [c for c in checks if c is not None]
    system = check_system(now)
    worst = max((_LEVELS[c["level"]] for c in checks + system), default=0)
    _count_alarm_days(checks + system)
    return {
        "generated_at": now.isoformat(),
        # Fuer das Widget, das seine festen Texte selbst uebersetzt.
        "language": language(),
        "level": {0: "ok", 1: "warn", 2: "error"}[worst],
        "components": group_components(checks),
        "checks": checks,
        "system": system,
    }
