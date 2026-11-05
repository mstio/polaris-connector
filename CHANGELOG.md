# Änderungen

Was sich je Stand für Nutzer ändert. Die Versionsnummer ist die der
Firefox-Erweiterung (`extension/manifest.json`), unter ihr ändern sich auch
Bridge, Curator, Installer und Werkzeuge. Hier stehen vor allem Dinge, die
`install.sh` bzw. `polaris update` ungefragt mitändern oder die eine Nacharbeit
verlangen. Einzelheiten stehen in der README.

## Unveröffentlicht

- **READMEs auf Englisch (2026-11-05):** `curator/README.md`, `memory/README.md`
  und `dist/README.md` übersetzt und gegen den Code abgeglichen (u. a.
  vollständige CLI, Module, Health-Check-Gruppen, Sandbox, `replaces_id`,
  Modell `gpt-6-astra` in der Vorlage, erledigte „Bekannte Grenzen“).
  Beispielnamen in der Curator-README neutralisiert.

- **Widget 0.3.2: „Agent fragen“ (2026-11-05):** Bei jeder auffälligen
  Health-Check-Zeile öffnet „Agent fragen“ den Standard-Agenten (Laufzeit
  des Curators) mit der Meldung und, wo bekannt, einem passenden Befehl als
  Vorschlag; er prüft und schlägt vor, ändert aber erst nach Zustimmung
  etwas. Neu:
  `polaris-curator health --ask <id>`. Meldung „Repos“ nennt Pfad und Datei.
- **Health Check: Hinweise auf Übersehenes (2026-11-05):** neue Teile
  „Backup-Ziel“ (Befunde der Zielprüfung von omarchy-backup sofort, nicht
  erst nach `doctor`), „Repos“ (neue, nicht versionierte Dateien in
  gesicherten Repos fehlen im Backup), „Neustart“ (Kernel aktualisiert) und
  „Plattenfehler“ (btrfs-Fehlerzähler). Lesen nur lokale Dateien.
- **Widget 0.3.1 (2026-11-05):** zeigt fremde Texte (Dateinamen, Radar,
  Fehlermeldungen der Modell-CLI) nur noch als reinen Text, nie als HTML
  (Härtung vom 04.11. jetzt auch im Marktplatz-Repo `mst.polaris-curator`).
- **Entschlackt (2026-11-05):** alte Migration der Curator-Zustände aus
  September (`legacy_migration`, Feld `coverage_migrated`), Journale am alten
  Ort auf dem Laufwerk (bis 10.10.), toter Code (`guard.strip_invisible`,
  `ids.ID_RE`) und die Machbarkeitsstudie `experiments/agent-runtime-poc`
  (archiviert im Tag `archiv/agent-runtime-poc-20261105`) entfernt.
  Wer Polaris vor dem 10.10.2026 zuletzt laufen ließ: erst auf den Stand
  `3e89a3e` aktualisieren und einen Curator-Lauf abwarten.
  `scripts/publish-public.sh` startet jetzt alle Tests (`scripts/run-tests.sh`).
- **Nutzungszähler (2026-11-05):** Der Curator zählt lokal, wie oft welcher
  Befehl und welche Funktion (Verdichtung, Schleifenprüfung, Prüfer) läuft:
  `~/.local/state/polaris/usage.json`, nur Name, Anzahl, erstes/letztes Datum,
  nie Inhalte. Grundlage, um Ungenutztes mit Beleg zu entfernen.
- **Sicherheitswerkzeuge im Maschinengedächtnis (2026-11-05):** `install.sh`
  legt `claude-guard-hook.py`, `claude-guard-einschalten.sh` und
  `home-snapshots-einrichten.sh` nach `~/.config/ai-agents/tools/`, schaltet
  aber nichts ein (Hook für Claude Code gegen versteckte Anweisungen aus Mails
  und Webseiten; stündliche, für Agenten unerreichbare Snapshots von `/home`).
  Einzelheiten: `memory/README.md`.
- **Sicherheit (Prüfung vom 2026-11-04, Grundsatz „never trust your input“):**
  - `<Projekt>/.polaris/curator-config.yaml` darf nur noch `batching`, `budget`,
    `context`, `monitoring`, `compaction` und `attachments` setzen. Laufzeit,
    Befehl (`runtime: command`), Anbieter und Modelle kommen nur aus der lokalen
    `curator.yaml`. Vorher konnte jeder, der in einen Projektordner auf dem
    Cloud-Laufwerk schreiben kann, damit Befehle als Nutzer ausführen. Andere
    Schlüssel werden ignoriert und im Health Check gemeldet.
  - Gedächtnis-Spiegel: `install.sh` holt ihn nur noch mit
    `--memory-from-mirror` oder nach Rückfrage zurück, `tools/` nie. Der Health
    Check startet memlint aus dem Programm, nicht aus `~/.config/ai-agents`.
    memlint legt nur noch Einstiege unter `$HOME` auf Markdown-Dateien bzw.
    Skill-Ordner im Gedächtnis an.
  - codex (Curator) und pdftotext laufen in bubblewrap: kein Blick ins Home,
    geleerte Umgebung (keine Tokens aus der Shell), codex mit eigenem
    `CODEX_HOME`, das nur die Anmeldung enthält (Sitzungsprotokolle in
    `~/.codex` bleiben unsichtbar), pdftotext ohne Netz. Fehlt die Sandbox,
    meldet der Health Check das (Zeile „Modell“). Seit dem gleichen Tag auch
    Claude (Ersatz und Prüfer, eigenes `CLAUDE_CONFIG_DIR` nur mit der
    Anmeldung) und `runtime: command` (eigenes leeres Home; nötige Pfade per
    `command_sandbox_ro`/`command_sandbox_rw` in der lokalen `curator.yaml`).
  - Projekt-Overrides dürfen Läufe nur billiger oder seltener machen, nie
    teurer; unlesbare Werte werden gemeldet statt den Lauf abzubrechen.
  - Spiegel: Links, die aus dem Gedächtnis hinauszeigen, kommen nicht mit;
    memlint meldet solche Links rot (`symlinks`). Wurde ein vorhandener
    Spiegel bei der Installation nicht zurückgeholt, sperrt `.mirror-hold` das
    Spiegeln, bis entschieden ist.
  - Radar: fremde Links, Kennungen, Daten und Versionen werden streng geprüft;
    Benachrichtigungen maskieren Markup, das Widget zeigt Fremdtext nur als
    reinen Text.
- Ausgabeprüfung: Modellantworten mit geheimnisähnlichem Text, dem lokalen
  Köder (`~/.config/polaris/canary`, wird beim ersten Lauf angelegt) oder
  Anweisungen an eine KI bzw. Shell-Befehlen werden nicht geschrieben, sondern
  lokal in Quarantäne gelegt (`polaris-curator quarantine list|show|release|drop`);
  der Health Check meldet sie. Die Prüfung normalisiert Unicode-Tricks
  (Nullbreite, ähnliche Buchstaben, Breitformen), gilt auch für Verdichtung,
  Neu-Einordnung, Aufräumen offener Punkte und den Dokumentindex; der Prompt
  verbietet an Software gerichtete Aufforderungen, Befehle und Zugangsdaten
  und erfasst angebliche Änderungen an Zahlungen/Bankverbindungen von außen
  als „Verifizieren“-Punkt.
- Agentenleitfaden: Updates erst nach Blick des Nutzers auf die neuen Commits
  einspielen; Spiegel nie blind zurückholen.
- Das Widget gibt es auch als eigenes Plugin-Repo `mstio/mst.polaris-curator`
  (für den Omarchy-Plugin-Marktplatz), Anzeigename jetzt „Polaris“. Ein so
  installiertes Widget (git-Checkout) lässt `install.sh` in Ruhe,
  `polaris update` aktualisiert es per `omarchy plugin update`, der Health Check
  vergleicht es nicht mehr mit dem Quellordner.
- Widget und Health Check sprechen Englisch oder Deutsch: `language: en|de` in
  `~/.config/polaris/curator.yaml`. Ohne die Zeile bleibt alles deutsch,
  bestehende Installationen ändern sich also nicht. Neue Installationen
  bekommen `language` aus `install.sh --language` bzw. der Systemsprache
  (`LANG=de_*` → `de`, sonst `en`). Die Feldbezeichnungen in `knowledge.md`
  bleiben vorerst deutsch.
- Polaris wird nur noch per git verteilt; das Installationspaket (`make-bundle.sh`,
  `dist/polaris-setup-*`) entfällt. `install.sh` holt die Begleit-Repos selbst:
  Backup-Widget, Agenten-Starter und Dock per `omarchy plugin add` (danach
  `omarchy plugin update`), die omarchy-backup-CLI per `git clone` nach
  `~/.local/share/polaris/extras/` – nur, wenn es noch keine eigene Installation
  gibt. `polaris update` zieht diese Teile mit und richtet nichts Neues ein
  (`install.sh --only-existing`; auf bestehenden Installationen fügt auch
  `install.sh --yes` keine neuen Widgets hinzu, sondern nennt den Befehl).
  Das Gedächtnis bekommt einen Platzhalter `handoff/omarchy-radar.md` samt
  Indexeintrag, auch ein bestehendes (sonst meldete memlint „fehlende Datei“
  bzw. „nicht im Index verlinkt“, weil der Radar sich nicht selbst einträgt).
  Ein vorhandenes, aber nie aktiviertes Widget wird jetzt aktiviert; Widgets,
  die noch als Kopie aus dem alten Paket laufen, nennen den Umstieg auf git.
  Gleichstand der Vorlagen prüft `scripts/check-sync.sh`. Nacharbeit: keine;
  Installationen aus dem alten Paket steigen einmal auf git um (README).

- README und CONTRIBUTING auf Englisch, die README nach Kern und Modulen gegliedert
  (Projektgedächtnis als Kern; Quellen, Modell-Runtimes, Widget, Health Check,
  Radar, Maschinengedächtnis als Module). Übrige Doku bleibt deutsch. Nacharbeit: keine.

- Neu: Versionsabgleich im Radar-Sicherheitsabschnitt. Aktiv ausgenutzte Lücken
  (CISA KEV) auf ein installiertes Paket werden mit den Versionsbereichen der NVD
  verglichen; ist die installierte Version nicht betroffen, bleibt der Health
  Check grün. Höchstens 5 NVD-Abfragen je Lauf, Zwischenspeicher
  `~/.local/state/polaris/nvd.json`. Nacharbeit: keine.

- Neu: geschützte Ordner für die Privatsphäre-Prüfung (Paket und öffentlicher
  Spiegel). Eine leere Datei `.polaris-protected` im Projektordner oder eine
  Zeile in `~/.config/polaris/protected.txt` sperrt alles aus dem Ordner:
  Namen (exakte Schreibweise), Pfad, Dateien byte-gleich, jede Inhaltszeile und
  5-Wort-Bruchstücke. Das allgemeine kleingeschriebene Wort bleibt erlaubt.
  Dazu ein `pre-push`-Hook im Spiegel-Klon, den `publish-public.sh` einrichtet;
  er prüft auch Autor und Nachricht der Commits, Spiegel-Commits tragen die
  GitHub-noreply-Adresse. Nacharbeit: keine.

- Neu: Sicherheitsabgleich im Omarchy-Radar. `polaris-radar` gleicht installierte
  Pakete mit dem Arch Security Tracker, den laufenden Kernel mit kernel.org-Stable
  und aktiv ausgenutzte Lücken (CISA KEV) mit Kernel und Paketen ab; Abschnitt
  „Sicherheit“ in `handoff/omarchy-radar.md`, Health-Check-Zeile „Sicherheit“.
  `install.sh` (also auch `polaris update`) richtet dafür den Timer
  `polaris-radar.timer` ein (täglich, ~3 MB); der Hook nach `omarchy update`
  startet jetzt diese Unit. Abschalten in `~/.config/polaris/radar.yaml`
  (`security: {enabled: false}`).

- Neu: `polaris-radar` (Omarchy-Radar). Nach jedem `omarchy update` (Hook in
  `~/.config/omarchy/hooks/post-update.d/`) und auf Anfrage schreibt es
  `handoff/omarchy-radar.md`: Plugin-Updates, vorgemerkte Issues, passende
  Omarchy-Neuerungen und neue Plugins. Agenten lesen es vor Omarchy-Anpassungen
  (neue allgemeine Regel). Stichworte optional in `~/.config/polaris/radar.yaml`
  (Vorlage `memory/tools/radar.example.yaml`). `install.sh` richtet Befehl und
  Hook ein (`--no-memory` lässt beides aus).

- Updates weisen auf Neues hin: `install.sh` (also auch `polaris update`)
  schreibt, was im CHANGELOG seit dem letzten Lauf neu ist, nach
  `~/.local/state/polaris/neu-seit-update.md` und als offenen Punkt nach
  `handoff/polaris.md`. Der Agent stellt es dem Nutzer vor; entschieden wird
  gemeinsam. Geänderte allgemeine Agentenregeln meldet er ebenso, bis der
  Abgleich quittiert ist.
- Allgemeine Agentenregeln (`memory/template/AGENTS.md`) neu und vollständiger:
  u. a. ressourcenschonend arbeiten, Sicherungskopien nie unter erratenem
  Namen, knapp schreiben, vor `git push` privat/öffentlich prüfen. Die Vorlage
  wird aus den als „allgemein“ gekennzeichneten Abschnitten erzeugt
  (`scripts/agents-template.py`). Ein vorhandenes `~/.config/ai-agents/AGENTS.md`
  ändert `install.sh` nicht; Neues bei Bedarf von Hand übernehmen.
- Der Health Check überwacht nur die in `curator.yaml` unter
  `monitoring.chat_sources` ausgewählten Browser-Chatquellen (`chatgpt`,
  `claude` oder keine). Die Curator-Runtime bleibt davon unabhängig.
  Bestehende Konfigurationen ohne diese Angabe behalten beide Quellen als
  Voreinstellung. Auf Systemen ohne unterstützte Browser-Chats `[]` setzen;
  dann prüft der Health Check weder Erweiterung noch Native Host.
- Bei Claude-only bleibt die Bridge-Fehlerprüfung aktiv. Eine vorhandene
  Claude-Nachricht verdeckt eine fehlende ChatGPT-Erfassung nicht mehr.
- Nennt `monitoring.chat_sources` Claude ausdrücklich, prüft der Health Check
  Claude so streng wie ChatGPT: noch nie eine Claude-Nachricht oder fehlender
  Zugriff auf claude.ai ist dann rot. Ohne die Angabe bleibt Claude wie bisher
  nachsichtig (neutral bzw. gelb).
- Groß-/Kleinschreibung in `chat_sources` ist egal. Unbekannte Einträge (z. B.
  `grok`) brechen nichts mehr ab, sondern erscheinen als rote Zeile
  „Chatquellen-Konfiguration“ im Health Check und als Warnung im Curator-Lauf.
- Ohne `chat_sources`-Angabe nennen die ChatGPT-Warnungen den Ausweg
  (`monitoring.chat_sources` setzen); der Agenten-Leitfaden beschreibt die
  Liste ebenfalls.
- Ältere Firefox-Erweiterungen vor 0.2.0 melden bei aktiver Claude-Quelle jetzt
  rot („unterstützt Claude-Erfassung noch nicht“); bitte aktualisieren.
- Der Installer fragt bei neuen Konfigurationen nach den Chatquellen
  (`--chat-sources` für unbeaufsichtigte Läufe). Ohne Chatquellen richtet er
  keinen Native Host und keine Bridge-Timer ein bzw. deaktiviert vorhandene
  Bridge-Timer beim erneuten Lauf.

## 0.4.4 (2026-10-23)

- **Speicherwächter:** Der Native Host misst den größten Firefox-Tab-Prozess.
  Ab 4 GiB kommt eine Desktop-Meldung, ab 8 GiB eine dringende, dazu eine
  Hinweisleiste in ChatGPT- und Claude-Tabs.
- **`polaris update`** für git-Checkouts: `git fetch`, nur Fast-Forward,
  `install.sh --yes`, Health-Check, bei Fehler zurück. Neue Health-Zeile
  „Update“ (höchstens einmal am Tag `git fetch`). Wer vom Installationspaket
  kommt: README „Umstieg vom Paket auf den git-Checkout“.
- **Laufwerk als Drop-in:** Units hängen nicht mehr fest an
  `rclone-projekte.service`, sondern an
  `~/.config/systemd/user/polaris-*.service.d/polaris-storage.conf`
  (`install.sh --storage-unit <unit|none>`). Lokale Ordner: `none`.
- **`polaris-awake`:** Widget, Bridge und Gedächtnis-Spiegel greifen bei
  Sperre/Einschlafen nicht auf das Laufwerk zu (`ExecCondition=`).

## 0.4.3 (2026-10-21)

- Popup meldet Projektübersicht und Chats ohne Projekt eindeutig (PR #1).
- Altmarkup-Zweig der ChatGPT-Erfassung entfernt.

## 0.4.2 (2026-10-21)

- Erste Version mit `update_url`: Firefox aktualisiert die Erweiterung ab hier
  selbst über den öffentlichen Spiegel. 0.4.1 und älter einmal von Hand
  installieren.
- Widgets für Qt 6.12 angepasst (Omarchy-Kanal `rc`).

## Stand 2026-10-16/17 (Installer und Gedächtnis)

- **Neuer Skill `loesungsqualitaet`:** `install.sh` legt ihn unter
  `~/.config/ai-agents/skills/` ab, und `memlint.py --link` verlinkt ihn
  **ungefragt** in die Skill-Ordner aller eingerichteten Agenten
  (`~/.agents/skills`, `~/.claude/skills`, `~/.codex/skills`). Wer das nicht
  will, entfernt die Links. Dann `memlint` nicht mit `--link` ausführen, sonst
  kommen sie wieder.
- **memlint prüft mehr:** `type=pattern` nur in `knowledge/` und nur mit Beleg
  (`ref=history:`/`commit:`/`url:`), Skill-Köpfe, Skill-Links. `install.sh`
  ersetzt `memlint.py` bei jedem Lauf. Ein Gedächtnis, das vorher nie
  geprüft wurde, zeigt Fehler deshalb oft erst nach dem Update. Häufigster
  Fall: Im Handoff stehen Abschnitte mit `status=superseded`, `historical`
  usw. Diese Regel gilt schon seit 2026-10-08. Solche Abschnitte gehören nach
  `knowledge/` bzw. `history/`, im Handoff steht nur `status=current`.
  Danach `python3 ~/.config/ai-agents/tools/memlint.py` (Exit 0).
- Curator wartet nach ergebnislosen Läufen länger bis zur nächsten Verdichtung.

## Installationspaket 2026-10-15

- Installer richtet Agenten-Starter (`mst.agent-launchers`) und Dock mit ein
  und startet die Leiste am Ende neu. Native Host ohne `~/.mozilla`.
- omarchy-backup und beide Widgets liegen nur im Paket unter `extras/`, nicht
  im öffentlichen Spiegel.
