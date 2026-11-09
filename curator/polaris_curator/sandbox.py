"""Fremdinhalte mit wenig Rechten verarbeiten (bubblewrap).

Sicherheitspruefung 2026-11-04 ("never trust your input"): Chats, Mails und
Anhaenge sind fremder Inhalt. Programme, die sie automatisch verarbeiten
(pdftotext, die Modell-CLI), sehen in der Sandbox nur das System (/usr, /etc,
nur lesend), die eigenen Arbeitsdateien und ausdruecklich freigegebene Pfade,
nicht das Home mit Schluesseln, Tokens und anderen Projekten, und keine
Umgebungsvariablen ausser einer kurzen Positivliste.

Bekannte Grenze: Mit Netz (codex) teilt die Sandbox den Netz-Namensraum des
Rechners; abstrakte Unix-Sockets anderer Programme bleiben damit erreichbar
(der D-Bus-Sitzungsbus nicht, er liegt als Datei unter /run/user).

bubblewrap bringt Omarchy als Abhaengigkeit mit (flatpak, webkit2gtk). Fehlt
es oder sind unprivilegierte Namensraeume gesperrt, schlaegt der Aufruf seit
2026-11-07 geschlossen fehl (SandboxUnavailable, ADR 003): Fremdinhalt wird
dann nicht verarbeitet, bis die Sandbox wieder geht; der Health Check nennt den
Grund (`status()`). Ohne Sandbox nur mit ausdruecklichem POLARIS_NO_SANDBOX=1.
Vorher lief der Aufruf ungeschuetzt weiter und wurde nur gemeldet.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

_SYSTEM = [
    "--ro-bind", "/usr", "/usr",
    "--symlink", "usr/bin", "/bin",
    "--symlink", "usr/bin", "/sbin",
    "--symlink", "usr/lib", "/lib",
    "--symlink", "usr/lib", "/lib64",
    "--ro-bind", "/etc", "/etc",
    "--proc", "/proc",
    "--dev", "/dev",
    "--tmpfs", "/tmp",
]


def _base(net: bool) -> list[str]:
    argv = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all"]
    if net:
        # Namensaufloesung: /etc/resolv.conf zeigt auf systemd-resolved.
        argv += ["--share-net", "--ro-bind-try", "/run/systemd/resolve", "/run/systemd/resolve"]
    return argv + _SYSTEM


@lru_cache(maxsize=1)
def available() -> bool:
    """bwrap vorhanden und benutzbar (einmal je Prozess geprueft)."""
    if os.environ.get("POLARIS_NO_SANDBOX") == "1" or not shutil.which("bwrap"):
        return False
    try:
        r = subprocess.run([*_base(False), "--", "/usr/bin/true"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def status() -> str | None:
    """None, wenn die Sandbox greift; sonst ein Hinweis fuer den Health Check."""
    if available():
        return None
    if os.environ.get("POLARIS_NO_SANDBOX") == "1":
        return "POLARIS_NO_SANDBOX=1 gesetzt"
    if not shutil.which("bwrap"):
        return "bubblewrap (bwrap) fehlt"
    return "bubblewrap nicht nutzbar (unprivilegierte Namensräume gesperrt?)"


# Nur diese Umgebungsvariablen gelangen in die Sandbox (Zweitmeinung
# 2026-11-04: sonst sahen codex/pdftotext z. B. GH_TOKEN oder API-Schluessel
# der aufrufenden Shell).
_ENV_ALLOW = ("LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "SSL_CERT_FILE", "SSL_CERT_DIR",
              "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy")


class SandboxUnavailable(RuntimeError):
    """bubblewrap fehlt oder ist nicht nutzbar, und POLARIS_NO_SANDBOX=1 ist
    nicht gesetzt: Fremdinhalt wird nicht ungeschuetzt verarbeitet."""


def enabled() -> bool:
    """True: in der Sandbox ausfuehren. False nur bei ausdruecklichem
    POLARIS_NO_SANDBOX=1. Sonst SandboxUnavailable (geschlossen fehlschlagen)."""
    if os.environ.get("POLARIS_NO_SANDBOX") == "1":
        return False
    if available():
        return True
    raise SandboxUnavailable(f"{status()} - Fremdinhalt wird nicht ohne Sandbox verarbeitet "
                             "(bewusst ohne: POLARIS_NO_SANDBOX=1)")


def wrap(argv: list[str], *, ro: list[str | Path] = (), rw: list[str | Path] = (),
         net: bool = False, home: str | Path | None = None,
         env: dict[str, str] | None = None) -> list[str]:
    """argv in der Sandbox mit geleerter Umgebung (nur _ENV_ALLOW, PATH,
    HOME und `env`). Bei POLARIS_NO_SANDBOX=1 unveraendert; ist bwrap nicht
    nutzbar, SandboxUnavailable (seit 2026-11-07)."""
    if not enabled():
        return list(argv)
    out = _base(net) + ["--clearenv", "--setenv", "PATH", "/usr/bin"]
    for key in _ENV_ALLOW:
        if key in os.environ:
            out += ["--setenv", key, os.environ[key]]
    out += ["--setenv", "HOME", str(home if home is not None else "/tmp")]
    for key, value in (env or {}).items():
        out += ["--setenv", key, value]
    for p in rw:
        out += ["--bind", str(p), str(p)]
    for p in ro:
        out += ["--ro-bind", str(p), str(p)]
    return out + ["--", *argv]


def resolve_binary(name: str) -> Path | None:
    """Echter Pfad eines Programms. mise-Shims/-Wrapper starten mise selbst,
    das in der Sandbox fehlt; dann `mise which` fragen."""
    found = shutil.which(name)
    if not found:
        return None
    real = Path(found).resolve()
    if real.name == name and "mise" not in real.parts[-3:-1] and real.name != "mise":
        return real
    if shutil.which("mise"):
        try:
            r = subprocess.run(["mise", "which", name], capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return Path(r.stdout.strip()).resolve()
        except (OSError, subprocess.SubprocessError):
            pass
    return real
