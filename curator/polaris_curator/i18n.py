"""Zweisprachige Ausgabe von Health Check und Curator-Status (seit 2026-11-04).

Deutsch ist Quelle und Schluessel: t("deutscher Text") liefert bei
language() == "en" die Uebersetzung aus EN, sonst den deutschen Text
unveraendert (fehlt eine Uebersetzung, ebenfalls Deutsch). Sprache: Umgebung
POLARIS_LANG (fuer Tests) vor `language` in ~/.config/polaris/curator.yaml;
fehlt der Schluessel, gilt "de" (aeltere Installationen bleiben deutsch).
"""

from __future__ import annotations

import os

SUPPORTED = ("de", "en")
DEFAULT = "de"

_config_language: str | None = None


def normalize(value: object) -> str | None:
    """'de'/'en' (Gross-/Kleinschreibung, Leerraum egal), sonst None."""
    name = str(value).strip().lower() if value is not None else ""
    return name if name in SUPPORTED else None


def resolve(config_language: str | None) -> str:
    """Sprache bei bekanntem Konfigurationswert (config.py nutzt das waehrend
    des Ladens, ohne Rekursion ueber load_config)."""
    return normalize(os.environ.get("POLARIS_LANG")) or normalize(config_language) or DEFAULT


def language() -> str:
    env = normalize(os.environ.get("POLARIS_LANG"))
    if env:
        return env
    global _config_language
    if _config_language is None:
        try:
            from . import config as config_mod

            _config_language = config_mod.load_config().language
        except Exception:  # noqa: BLE001 - kaputte curator.yaml: Health Check meldet das selbst
            _config_language = DEFAULT
    return _config_language


def reset_cache() -> None:
    global _config_language
    _config_language = None


def t_lang(lang: str, de: str, **kw) -> str:
    text = EN.get(de, de) if lang == "en" else de
    return text.format(**kw) if kw else text


def t(de: str, **kw) -> str:
    return t_lang(language(), de, **kw)


# Deutsch -> Englisch. Platzhalter ({n}, {age} ...) muessen gleich bleiben
# (test_i18n prueft das und die Vollstaendigkeit).
EN: dict[str, str] = {
    'nie':
        'never',
    'gerade eben':
        'just now',
    'vor {n} h':
        '{n} h ago',
    'vor {n} Tag(en)':
        '{n} day(s) ago',
    'keine':
        'none',
    ' und ':
        ' and ',
    ' u. a.':
        ' and more',
    ' (+{n} weitere)':
        ' (+{n} more)',
    '{path} fehlt':
        '{path} missing',
    'nicht eingerichtet (optional)':
        'not set up (optional)',
    'keine Auffälligkeiten':
        'no issues',
    '{names} in Ordnung':
        '{names} OK',
    # Namen, die gleich bleiben, stehen trotzdem hier (Vollstaendigkeitstest).
    'ChatGPT':
        'ChatGPT',
    'Claude':
        'Claude',
    'Bridge':
        'Bridge',
    'Native Host':
        'Native Host',
    'Curator':
        'Curator',
    'Widget':
        'Widget',
    'Erfassung':
        'Capture',
    'Konfiguration':
        'Configuration',
    'Erweiterung':
        'Extension',
    'Speicher & Sicherung':
        'Storage & backup',
    'Timer':
        'Timer',
    'Backup':
        'Backup',
    'ChatGPT-Archivierung':
        'ChatGPT archive',
    'Claude-Archivierung':
        'Claude archive',
    'noch keine ChatGPT-Nachricht archiviert':
        'no ChatGPT message archived yet',
    'noch keine Claude-Nachricht archiviert':
        'no Claude message archived yet',
    'letzte Nachricht {age}':
        'last message {age}',
    'letzte Nachricht {age} ({n} Projekt(e) mit Claude-Quelle)':
        'last message {age} ({n} project(s) with Claude source)',
    'noch keine Claude-Nachricht archiviert – Erweiterung, Zugriff auf claude.ai und Projektzuordnung prüfen (oder claude aus monitoring.chat_sources entfernen)':
        'no Claude message archived yet – check the extension, access to claude.ai and project mapping (or remove claude from monitoring.chat_sources)',
    'seit {days} Tagen keine Claude-Nachricht – falls du Claude genutzt hast: Erweiterung/Berechtigung für claude.ai und Sync im Popup prüfen':
        'no Claude message for {days} days – if you used Claude: check the extension/permission for claude.ai and Sync in the popup',
    'Kurationsschritte':
        'Curation steps',
    'Kuration':
        'Curation',
    '{name} (offen seit {h} h)':
        '{name} (open for {h} h)',
    'unterbrochen: {items} – `polaris-curator journal <Projekt>`':
        'interrupted: {items} – `polaris-curator journal <project>`',
    'keiner offen':
        'none open',
    '{name}: letzter Lauf mit Fehler ({error})':
        '{name}: last run failed ({error})',
    '{name}: Rückstand seit {age} Tagen ({n} Tages-Batches)':
        '{name}: backlog for {age} days ({n} day batches)',
    '{name}/{file}: Verzeichnis belegt {pct} % des Kontext-Budgets – aufräumen (compact / review-loops) oder full_context_chars erhöhen':
        '{name}/{file}: index uses {pct} % of the context budget – clean up (compact / review-loops) or raise full_context_chars',
    '{name}: {n} Einheit(en) scheitern wiederholt':
        '{name}: {n} unit(s) failing repeatedly',
    'Projekttrennung':
        'Project separation',
    'Prüfung fehlgeschlagen: {exc}':
        'check failed: {exc}',
    '{n} Nachricht(en) im falschen Projekt/Chat ({projects}) – betroffene Projekte werden nicht kuratiert; z. B. {example}':
        '{n} message(s) in the wrong project/chat ({projects}) – affected projects are not curated; e.g. {example}',
    'Chat-Verzeichnis(se) mit fremden IDs':
        'chat index(es) with foreign IDs',
    'unlesbare Nachrichtendatei(en)':
        'unreadable message file(s)',
    'Nachricht(en) ohne zugeordnete Projekt-ID (werden nicht kuratiert)':
        'message(s) without a mapped project ID (not curated)',
    'keine Nachricht im falschen Projekt':
        'no message in the wrong project',
    'Firefox-Erweiterung':
        'Firefox extension',
    'v{version} ist deaktiviert':
        'v{version} is disabled',
    'läuft als temporär geladene Version (installiert: v{version}) – fällt nach einem Firefox-Neustart weg; neue Version signieren lassen und installieren':
        'running as a temporarily loaded version (installed: v{version}) – gone after a Firefox restart; get the new version signed and install it',
    'v{version}: Zugriff auf chatgpt.com nicht erteilt – exportiert nur nach Klick (about:addons → Polaris → Berechtigungen)':
        'v{version}: access to chatgpt.com not granted – exports only on click (about:addons → Polaris → Permissions)',
    'installiert ist v{version}; eine neuere Version läuft höchstens temporär und fällt nach einem Firefox-Neustart weg (signieren lassen)':
        'v{version} is installed; a newer version runs only temporarily and is gone after a Firefox restart (get it signed)',
    'v{version} unterstützt Claude-Erfassung noch nicht':
        'v{version} does not support Claude capture yet',
    'v{version}: Zugriff auf claude.ai nicht erteilt – Claude-Export ruht (Polaris-Symbol auf claude.ai anklicken → Zugriff erlauben)':
        'v{version}: access to claude.ai not granted – Claude export paused (click the Polaris icon on claude.ai → allow access)',
    'v{version}, Zugriff auf {granted} erteilt':
        'v{version}, access to {granted} granted',
    'nicht installiert':
        'not installed',
    'nicht registriert – Erweiterung nutzt Downloads (bridge/install-native-host.sh)':
        'not registered – extension uses downloads (bridge/install-native-host.sh)',
    'registriert, aber {path} fehlt/nicht ausführbar':
        'registered, but {path} missing/not executable',
    'registriert':
        'registered',
    'Kopie nicht lesbar: {exc}':
        'copy not readable: {exc}',
    'Kopie veraltet ({names}) – {hint}':
        'copy outdated ({names}) – {hint}',
    './install.sh --yes --no-units --no-backup --no-memory, dann omarchy restart shell':
        './install.sh --yes --no-units --no-backup --no-memory, then omarchy restart shell',
    'git-Checkout, aktualisiert per omarchy plugin update':
        'git checkout, updated by omarchy plugin update',
    'Kopie aktuell':
        'copy up to date',
    'Prüfung nicht möglich (offline?) – polaris update --check':
        'check not possible (offline?) – polaris update --check',
    'verfügbar: {local} → {remote} – polaris update':
        'available: {local} → {remote} – polaris update',
    'aktuell ({local})':
        'up to date ({local})',
    'Timer nicht aktiviert':
        'timer not enabled',
    'letzter Timer-Lauf: {result}':
        'last timer run: {result}',
    'Timer aktiv, letzter Lauf erfolgreich':
        'timer active, last run successful',
    'Modell':
        'Model',
    'curator.yaml unlesbar: {e}':
        'curator.yaml unreadable: {e}',
    'unbekannte runtime {runtime!r}':
        'unknown runtime {runtime!r}',
    '{main} fehlt – polaris-curator llm-check':
        '{main} missing – polaris-curator llm-check',
    'installiert, aber noch kein Snapshot':
        'installed, but no snapshot yet',
    'Zustandsdatei unlesbar':
        'state file unreadable',
    'Snapshot {last}, hochgeladen {pushed}, doctor {doctor}':
        'snapshot {last}, uploaded {pushed}, doctor {doctor}',
    ', letzter Lauf: {result}':
        ', last run: {result}',
    'Projektordner':
        'Project folders',
    'Projektordner ({roots})':
        'Project folders ({roots})',
    'keine project_roots konfiguriert – polaris roots add <Ordner>':
        'no project_roots configured – polaris roots add <folder>',
    'Laufwerk eingehängt?':
        'drive mounted?',
    '{short} fehlt – {hint}':
        '{short} missing – {hint}',
    '{n} zugeordnete(r) Projektordner unter {short} fehlt – {hint}':
        '{n} mapped project folder(s) under {short} missing – {hint}',
    'eingehängt, aber {n} Datei(en) seit {h} h nicht hochgeladen – rclone-Log prüfen':
        'mounted, but {n} file(s) not uploaded for {h} h – check the rclone log',
    'rclone eingehängt':
        'rclone mounted',
    'erreichbar':
        'reachable',
    'Maschinengedächtnis':
        'Machine memory',
    'memlint konnte nicht ausgeführt werden':
        'memlint could not be run',
    '{n} Fehler (z. B. {check}: {file}) – memlint.py ausführen':
        '{n} error(s) (e.g. {check}: {file}) – run memlint.py',
    ', {n} Hinweis(e)':
        ', {n} note(s)',
    'konsistent, {n} Einträge':
        'consistent, {n} entries',
    'Spiegel noch nie gelaufen – polaris-memory-mirror':
        'mirror never ran – polaris-memory-mirror',
    'Spiegel neuer als lokal – Unterschiede prüfen, nur nach Entscheidung zurückholen (polaris-memory-mirror)':
        'mirror newer than local – review the differences, restore only after deciding (polaris-memory-mirror)',
    'Spiegel {age}':
        'mirror {age}',
    'gespiegelt {age}':
        'mirrored {age}',
    'Sicherheit':
        'Security',
    'noch nicht geprüft – polaris-radar':
        'not checked yet – polaris-radar',
    'zuletzt geprüft {age} – polaris-radar':
        'last checked {age} – polaris-radar',
    'Abgleich unvollständig ({error}) – polaris-radar':
        'check incomplete ({error}) – polaris-radar',
    'keine Befunde (geprüft {age})':
        'no findings (checked {age})',
    'Abstürze':
        'Crashes',
    '{n} seit {h} h: {listed}{more} – coredumpctl list':
        '{n} in the last {h} h: {listed}{more} – coredumpctl list',
    'keine neuen (zuletzt {name}, {age})':
        'no new ones (last {name}, {age})',
    '{pct:.0f} % belegt, {free:.0f} GB frei':
        '{pct:.0f} % used, {free:.0f} GB free',
    ' – größte Posten: ':
        ' – largest items: ',
    'Platte {mount}':
        'Disk {mount}',
    'fehlgeschlagen: {units}':
        'failed: {units}',
    'keine fehlgeschlagen':
        'none failed',
    'Akku':
        'Battery',
    'pacman-Cache':
        'pacman cache',
    'Papierkorb':
        'Trash',
    'yay-Cache':
        'yay cache',
    'paru-Cache':
        'paru cache',
    'Journal':
        'Journal',
    'Coredumps':
        'Core dumps',
    'Chatquellen-Konfiguration':
        'Chat source configuration',
    'ChatGPT-Schnittstelle um {local} nicht nutzbar ({error}) - Erfassung liest ersatzweise aus der Seite.':
        'ChatGPT API unusable at {local} ({error}) - capture falls back to reading the page.',
    'Falls ChatGPT hier nicht genutzt wird: in ~/.config/polaris/curator.yaml monitoring.chat_sources setzen, z. B. [claude] (siehe CHANGELOG).':
        'If ChatGPT is not used here: set monitoring.chat_sources in ~/.config/polaris/curator.yaml, e.g. [claude] (see CHANGELOG).',
    'Noch keine ChatGPT-Nachricht archiviert.':
        'No ChatGPT message archived yet.',
    'Seit {days} Tagen keine ChatGPT-Nachricht mehr archiviert (in keinem Projekt) - Firefox-Erweiterung, Berechtigung für chatgpt.com und Native Host prüfen.':
        'No ChatGPT message archived for {days} days (in any project) - check the Firefox extension, permission for chatgpt.com and the native host.',
    '{n} Datei(en) liegen seit über einer Stunde unverarbeitet in der Bridge-Inbox.':
        '{n} file(s) unprocessed in the bridge inbox for over an hour.',
    '{n} Nachricht(en) warten auf eine Projektzuordnung (polaris pending).':
        '{n} message(s) waiting for a project mapping (polaris pending).',
    '{n} Datei(en) hat die Bridge abgelehnt (~/.local/share/polaris/failed/) - Grund im Bridge-Protokoll.':
        '{n} file(s) rejected by the bridge (~/.local/share/polaris/failed/) - reason in the bridge log.',
    '{n} Fehler im Bridge-Protokoll in den letzten 24 Stunden.':
        '{n} error(s) in the bridge log in the last 24 hours.',
    '{n} Chat(s) mit noch nicht übernommener letzter Antwort seit über 1 h: {names} – Chat öffnen oder im Popup „Sync now“ (gelöschter Chat: `polaris held-back --clear …`).':
        '{n} chat(s) with a last reply not yet captured for over 1 h: {names} – open the chat or use “Sync now” in the popup (deleted chat: `polaris held-back --clear …`).',
    '{n} Datei(en) lassen sich seit über einer Stunde nicht ablegen (z. B. {name}: {error}) - Projektordner/Mount prüfen.':
        '{n} file(s) could not be stored for over an hour (e.g. {name}: {error}) - check project folder/mount.',
    'Polaris: Archivierung prüfen':
        'Polaris: check archiving',
    '{name}: {messages} Messages, {documents} Dokumente, {calls} geplante LLM-Calls':
        '{name}: {messages} messages, {documents} documents, {calls} planned LLM calls',
    '{pending} von {total} Projekten offen, {calls} geplante LLM-Calls':
        '{pending} of {total} projects pending, {calls} planned LLM calls',
    'Letzte ChatGPT-Nachricht: {at}':
        'Last ChatGPT message: {at}',
    'WARNUNG: {warning}':
        'WARNING: {warning}',
    'FEHL':
        'FAIL',
    '{name}: nicht kuratiert - {error}':
        '{name}: not curated - {error}',
    'Projekttrennung verletzt, nicht kuratiert: {names} (polaris-curator health, Quarantäne/retract)':
        'project separation violated, not curated: {names} (polaris-curator health, quarantine/retract)',
    'curator.yaml: nicht unterstützte Chatquelle(n) {unknown} ignoriert (möglich: {supported})':
        'curator.yaml: unsupported chat source(s) {unknown} ignored (possible: {supported})',
    'curator.yaml: monitoring.chat_sources muss eine Liste sein, z. B. [chatgpt, claude] oder [] - bis zur Korrektur werden beide Quellen geprüft':
        'curator.yaml: monitoring.chat_sources must be a list, e.g. [chatgpt, claude] or [] - both sources are checked until fixed',
    'ohne Sandbox: {problem}':
        'without sandbox: {problem}',
    '{missing} (Ersatz/Prüfer) fehlt':
        '{missing} (fallback/reviewer) missing',
    'Spiegel gesperrt: bei der Installation nicht zurückgeholt – entscheiden (polaris-memory-mirror)':
        'mirror on hold: not restored during installation – decide (polaris-memory-mirror)',
    '{file}: unlesbar ({error}) - Projekt-Override ignoriert':
        '{file}: unreadable ({error}) - project override ignored',
    '{file}: nicht erlaubte Schluessel ignoriert ({keys}) - Laufzeit, Befehl und Modell nur in der lokalen curator.yaml':
        '{file}: disallowed keys ignored ({keys}) - runtime, command and model only in the local curator.yaml',
    'curator.yaml: language muss de oder en sein (gefunden: {value}) - bis zur Korrektur gilt de':
        'curator.yaml: language must be de or en (found: {value}) - de applies until fixed',
}
