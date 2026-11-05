#!/usr/bin/env python3
"""Claude-Code-Hook gegen Prompt-Injection (seit 2026-11-04, Teil von Polaris).

Wird nie automatisch eingeschaltet; einbinden mit
tools/claude-guard-einschalten.sh [standard|streng|aus] (wirkt sofort, auch in
laufenden Sitzungen).

Grundsatz "never trust your input": Hat eine Sitzung Fremdinhalt gelesen
(Mail, Web, Downloads, Projektordner auf dem Cloud-Laufwerk, MCP-Konnektoren),
koennte darin eine versteckte Anweisung stecken. Dann fragen Aktionen nach
aussen oder mit Folgen beim Nutzer nach, egal wie sie formuliert sind
(Sperrlisten fuer Befehle wirken nicht, die Rueckfrage schon).

Aufruf durch Claude Code mit JSON auf stdin:
  PostToolUse  -> markiert die Sitzung als "hat Fremdinhalt gelesen"
  PreToolUse   -> protokolliert jede Aktion; fragt nach bei
                  * Schreibvorgaengen in Fachsystemen ueber MCP (immer),
                  * Aenderungen am Schutz selbst: ~/.claude/settings*,
                    ~/.claude/guard, claude-guard-*, ~/.config/polaris/config.yaml (immer),
                  * nach Fremdinhalt: Bash, Schreiben, MCP, WebFetch, WebSearch,
                    Monitor, Artifact, SendMessage - Stufe "streng"
Stufe ueber CLAUDE_GUARD_LEVEL=standard|streng (Standard: streng).
Fremdinhalt: Web/Monitor, jedes MCP-Werkzeug ausser Schreibwerkzeugen und
CLAUDE_GUARD_TRUSTED_MCP (Regex), Netzbefehle in Bash (curl, wget, gh, git
pull/fetch/clone, ssh, scp, rsync, pip, npm, URLs) sowie Lesen in ~/Downloads,
/tmp, den Polaris-Projektwurzeln (project_roots in ~/.config/polaris/config.yaml)
und CLAUDE_GUARD_UNTRUSTED (Pfade mit ":"), auch ueber das Arbeitsverzeichnis.
Protokoll: ~/.claude/guard/audit.jsonl (0600, ab 5 MB eine Vorgaengerdatei;
enthaelt Befehle, ggf. auch darin stehende Geheimnisse), Markierungen
~/.claude/guard/<session>.tainted (nach 30 Tagen geloescht).
Fehler: Bei PreToolUse fragt der Hook nach, statt still durchzulassen
(fail-closed); Absturz/Zeitueberschreitung faengt "onFailure": "block" ab.
Grenze: verschleierte Bash-Befehle umgehen die Textpruefung auf Stufe
"standard"; Rueckhalt sind Snapshots und das Protokoll.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

HOME = Path.home()
GUARD = HOME / ".claude" / "guard"
LEVEL = os.environ.get("CLAUDE_GUARD_LEVEL", "streng")

# Nicht-MCP-Werkzeuge, die Fremdinhalt in die Sitzung bringen.
UNTRUSTED_TOOLS = re.compile(r"^(WebFetch|WebSearch|Monitor|mcp__claude_in_chrome__.*)$")
NET_CMD = re.compile(r"\b(curl|wget|gh|ssh|scp|rsync|pip|pip3|npm|npx|git\s+(pull|fetch|clone))\b|https?://")

# Immer nachfragen: Schreibvorgaenge in Fachsystemen (Mail senden, Vorgaenge aendern ...).
ALWAYS_ASK_TOOLS = re.compile(r"^mcp__.*(_schreiben|_anlegen|send|create|update|delete).*$", re.I)
ALWAYS_ASK_ACTIONS = re.compile(
    r"(senden|send|antworten|schreiben|anlegen|loeschen|löschen|aendern|ändern|erstellen|update)", re.I)

# Immer nachfragen: Aenderungen am Schutz selbst.
PROTECTED = (".claude/settings", ".claude/guard", "claude-guard", ".config/polaris/config.yaml")
DESTRUCTIVE = re.compile(r"\b(rm|mv|chmod|chattr|ln|truncate|rsync|find)\b")

# Nach Fremdinhalt nachfragen (Stufe "streng"): alles, was Folgen haben oder ausleiten kann.
AFTER_TAINT_TOOLS = re.compile(
    r"^(Bash|Write|Edit|NotebookEdit|WebFetch|WebSearch|Monitor|Artifact|SendMessage|mcp__.*)$")

EVENT = None


def _polaris_roots() -> list[str]:
    try:
        import yaml  # Polaris setzt PyYAML voraus
        raw = yaml.safe_load((HOME / ".config" / "polaris" / "config.yaml").read_text()) or {}
        return [str(Path(str(r)).expanduser()) for r in raw.get("project_roots") or [] if r]
    except Exception:  # noqa: BLE001 - ohne Polaris-Konfiguration nur die Standardordner
        return []


def untrusted_paths() -> tuple[str, ...]:
    paths = [str(HOME / "Downloads"), "/tmp", *_polaris_roots()]
    paths += [str(Path(p).expanduser()) for p in os.environ.get("CLAUDE_GUARD_UNTRUSTED", "").split(":") if p]
    return tuple(p.rstrip("/") for p in paths if p.strip("/"))


def _mentions(text: str, paths) -> bool:
    """Pfad absolut, als ~/... oder $HOME/... im Text."""
    home = str(HOME)
    for p in paths:
        if p in text:
            return True
        if p.startswith(home + "/"):
            rel = p[len(home) + 1:]
            if any(f"{pre}{rel}" in text for pre in ("~/", "$HOME/", "${HOME}/")):
                return True
    return False


def _under(path: str, paths) -> bool:
    try:
        real = os.path.realpath(os.path.expanduser(path))
    except Exception:  # noqa: BLE001
        real = path
    return any(real == p or real.startswith(p + "/") or path.startswith(p) for p in paths)


def _session_file(data: dict) -> Path:
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id") or "unbekannt"))[:80]
    return GUARD / f"{sid}.tainted"


def _guard_dir_ok() -> bool:
    return not GUARD.is_symlink() and (not GUARD.exists() or GUARD.is_dir())


def _write(path: Path, line: str) -> None:
    GUARD.mkdir(parents=True, exist_ok=True)
    os.chmod(GUARD, 0o700)
    try:  # Protokoll begrenzen: ab 5 MB eine Vorgaengerdatei behalten
        if path.stat().st_size > 5_000_000:
            os.replace(path, path.with_name(path.name + ".1"))
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write(line)


def _prune_markers() -> None:
    cutoff = time.time() - 30 * 86400
    for m in GUARD.glob("*.tainted"):
        try:
            if m.stat().st_mtime < cutoff:
                m.unlink()
        except OSError:
            pass


def _trusted_mcp():
    raw = os.environ.get("CLAUDE_GUARD_TRUSTED_MCP", "")
    return re.compile(raw) if raw else None  # ungueltig -> re.error (PreToolUse fragt dann nach)


def _is_untrusted_read(data: dict) -> bool:
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") or {}
    if UNTRUSTED_TOOLS.match(tool):
        return True
    if tool.startswith("mcp__"):
        trusted = _trusted_mcp()
        if trusted and trusted.search(tool):
            return False
        return not ALWAYS_ASK_TOOLS.match(tool)
    paths = untrusted_paths()
    cwd = str(data.get("cwd") or "")
    in_untrusted_cwd = bool(cwd) and _under(cwd, paths)
    if tool in ("Read", "Grep", "Glob"):
        target = str(ti.get("file_path") or ti.get("path") or "")
        if not target:
            return in_untrusted_cwd
        if not target.startswith(("/", "~", "$")) and in_untrusted_cwd:
            return True
        return _under(target, paths) or _mentions(target, paths)
    if tool == "Bash":
        cmd = str(ti.get("command") or "")
        return in_untrusted_cwd or _mentions(cmd, paths) or bool(NET_CMD.search(cmd))
    return False


def _touches_protection(tool: str, ti: dict) -> bool:
    if tool in ("Write", "Edit", "NotebookEdit"):
        raw = str(ti.get("file_path") or ti.get("notebook_path") or "")
        target = os.path.realpath(os.path.expanduser(raw))
        return any(p in target or p in raw for p in PROTECTED)
    if tool in ("Bash", "Monitor"):
        cmd = str(ti.get("command") or "")
        return (any(p in cmd for p in PROTECTED) or (".claude" in cmd and "settings" in cmd)
                or (".claude" in cmd and bool(DESTRUCTIVE.search(cmd))))
    return False


def _ask(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                             "permissionDecisionReason": reason}}, ensure_ascii=False))


def decide(data: dict, tainted: bool) -> str | None:
    """Grund fuer eine Rueckfrage oder None."""
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input") or {}
    aktion = str(ti.get("aktion") or "")
    if ALWAYS_ASK_TOOLS.match(tool) or (tool.startswith("mcp__") and ALWAYS_ASK_ACTIONS.search(aktion)):
        return f"Schreibvorgang in einem Fachsystem ({tool} {aktion}) – bitte bestätigen."
    if _touches_protection(tool, ti):
        return "Änderung am Agenten-Schutz (Einstellungen, Guard-Hook, Polaris-Konfiguration) – bitte bestätigen."
    if LEVEL == "streng" and tainted and AFTER_TAINT_TOOLS.match(tool):
        return ("Diese Sitzung hat Fremdinhalt gelesen (Mail/Web/Laufwerk). Aktionen mit Folgen "
                "bitte bestätigen – eine versteckte Anweisung könnte dahinterstecken.")
    return None


def main() -> int:
    global EVENT
    data = json.loads(sys.stdin.read())
    EVENT = data.get("hook_event_name")
    tool = str(data.get("tool_name") or "")
    marker = _session_file(data)

    if EVENT == "PostToolUse":
        if _is_untrusted_read(data) and not marker.exists():
            _write(marker, f"{time.strftime('%F %T')} {tool}\n")
            _prune_markers()
        return 0
    if EVENT != "PreToolUse":
        return 0

    if not _guard_dir_ok():
        _ask("Guard-Hook: ~/.claude/guard ist kein normales Verzeichnis (manipuliert?) – bitte prüfen und bestätigen.")
        return 0
    reason = decide(data, marker.exists())
    try:
        _trusted_mcp()
    except re.error:
        reason = (reason + " " if reason else "") + "(CLAUDE_GUARD_TRUSTED_MCP ist kein gültiger Ausdruck - Fremdinhalt wird nicht erkannt)"

    ti = data.get("tool_input") or {}
    entry = {"t": time.strftime("%F %T"), "session": data.get("session_id"), "tool": tool,
             "mode": data.get("permission_mode"), "tainted": marker.exists(), "ask": bool(reason)}
    if tool in ("Bash", "Monitor"):
        entry["command"] = str(ti.get("command") or "")[:2000]
    elif tool.startswith("mcp__"):
        entry["aktion"] = ti.get("aktion")
    elif tool in ("Write", "Edit", "NotebookEdit", "Read"):
        entry["path"] = ti.get("file_path")
    elif tool in ("WebFetch", "WebSearch"):
        entry["url"] = str(ti.get("url") or ti.get("query") or "")[:500]
    try:
        _write(GUARD / "audit.jsonl", json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 - Protokoll kaputt: laut melden, nicht still weiter
        reason = (reason + " " if reason else "") + f"(Guard-Protokoll nicht schreibbar: {type(exc).__name__})"
    if reason:
        _ask(reason)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - fail-closed: lieber nachfragen als still durchlassen
        if EVENT in (None, "PreToolUse"):
            _ask(f"Guard-Hook-Fehler ({type(exc).__name__}) – Aktion bitte selbst prüfen und bestätigen.")
        sys.exit(0)
