# ADR 003: Refactoring – robust, schützend, wartbar

Status: **Angenommen** (2026-11-07, Nutzer). Signierte Tags abgelehnt; Repo heißt jetzt `mstio/polaris`. Bezug: ADR 002 (modulare Installation),
Funktionsstopp bis zur Auswertung des Nutzungszählers (~05.12.2026).

## Ziel

Polaris soll robust und stabil laufen, Rechner und Arbeit schützen und wartbar
bleiben, auch wenn die meisten Änderungen von KI-Agenten kommen. Größe ist kein
Ziel an sich. Randbedingungen wie bisher: keine neuen Abhängigkeiten, lokal
zuerst, ressourcenschonend, menschenlesbar, an Omarchy ausgerichtet.

## Befund (geprüft am 2026-11-07)

- Betrieb robust: Health 17/17, 251 fehlerfreie Curator-Läufe seit 24.10., 682 Tests grün.
- **Jeder Commit ist live:** `~/.local/bin/polaris*` und der Native-Host-Eintrag zeigen in den
  Entwicklungs-Checkout (`install.sh:484-494`); `update.sh` und seine Rücknahme laufen auf diesem
  Rechner nie (er ist selbst upstream). Keine Prüfung auf laufende Dienste vor einem Wechsel.
- `update.sh:136` nimmt nur zurück, wenn der Gesamtstatus vorher nicht schon `error` war; die
  Rücknahme urteilt mit dem neuen Code, ihre Ausgabe wird verworfen (`:138`).
- Der Nutzungszähler erfasst nur Curator-Befehle; Bridge-CLI, `retract`, `transfer`,
  `reclassify`, Widget-Aktionen und die Claude-Erfassung fehlen. Die Auswertung am 05.12. wäre blind.
- Health Check ist der größte Dauerverbraucher: Widget alle 10 min, `health --json` 2,6 s,
  `status-all --json` 7,5 s; `check_system` läuft `du` über Caches, startet memlint und git;
  `check_update` macht einen `git fetch` (bis 70 s) im Health-Lauf.
- Sandbox fällt offen zurück: ohne nutzbares bwrap laufen Modelle und pdftotext ungeschützt weiter
  (`sandbox.py:82-83`, `llm.py:161,279`, `documents_source.py:133`); Health meldet es nur.
  `llm.py:75-97` schreibt Anmeldedateien aus der Sandbox zurück ins echte Home.
- Curator-Schreiber nutzt einen festen `<name>.tmp` (`storage.py:42`), die Bridge eindeutige Namen.
- Verträge implizit und mehrfach definiert: `raw/`-Layout in `bridge/polaris/storage.py:64-69`,
  `curator/polaris_curator/layout.py:43-51`, `systemhealth.py:140`; die Bridge liest
  curator-internes `.polaris/curator-state.json` (`bridge/polaris/pipeline.py:351`, `conflicts.py:161`).
  Bridge- und Curator-Tests treffen sich nie (Testdaten von Hand, `conftest_helpers.py:73-105`).
- Schutzdateien (`sandbox.py`, `guard.py`, `integrity.py`, `scripts/privacy-check.py`,
  `memory/tools/claude-guard-hook.py`) werden an verschiedene Ziele verteilt; `install.sh:779-786`
  ersetzt den aktiven Guard-Hook bei jedem Update (Lieferkette eines Schutzwerkzeugs).
- Kein Einstieg für Agenten im Repo-Wurzelverzeichnis (`AGENTS.md`); Leitfaden nur über README.
- Release-Prozess faktisch eingeschlafen: ein Tag (`v0.4.2`, kein Vorfahr von master), 80 Commits
  seit 0.4.4. `publish-public.sh` prüft bereits Tests, Vorlagen-Gleichstand und Privatsphäre.

## Geprüft von

Fünf unabhängige Prüfungen (Claude Fable 5.1) aus je einer Sicht: Betrieb/Release, Sicherheit,
Architektur, Tests, Gegenpart „Einfachheit“; dazu eine externe Einschätzung (ChatGPT). Einig:
nicht neu schreiben; kein Verschieben in neue Verzeichnisse; Schutzregel statt `safety/`-Ordner;
`modules.conf`, `health.d` und Pipeline-Zerlegung erst nach dem 05.12. und nur bei Bedarf.
Strittig war „Live nur auf Release-Tags“; gelöst durch getrennten Live-Stand ohne Pflicht-Tags.

## Entscheidung

### Stufe 1 – jetzt (Fehlerbehebung und Sicherheitsnetze, passt in den Funktionsstopp)

1. **Live vom Entwicklungsstand trennen:** Live-Stand als `git worktree` unter
   `~/.local/share/polaris/app` (Befehle, Units, Native Host zeigen dorthin); entwickelt wird in
   `~/Projects/…`. Live bewegt sich nur über `polaris update`. Vorher Tests für `update.sh`, dann:
   kein Wechsel, solange `polaris-curator`/`polaris-bridge` laufen; Vergleich je kritischer Prüfung
   statt Gesamtstatus; Rücknahme-Ausgabe ins Protokoll. Vorhandenes `publish-public.sh` bleibt die
   Freigabeprüfung; ein Pre-Push-Hook führt `scripts/run-tests.sh` aus.
2. **Nutzungszähler vervollständigen** (Bridge-CLI, retract/transfer/reclassify, Widget-Aktionen,
   Claude-Erfassung), damit der 05.12. auf Belegen beruht.
3. **Health Check entlasten:** `check_system` stündlich zwischenspeichern, `git fetch` aus dem
   Health-Lauf in einen täglichen Timer; Health liest nur noch Zustand. Danach nachmessen.
4. **Schutz schließen:** Sandbox schlägt geschlossen fehl (Abbruch, Exit 75), außer bei
   ausdrücklichem `POLARIS_NO_SANDBOX=1`; Rückschreiben von Anmeldedaten auf bekannte Schlüssel
   begrenzen; Test „Ausgabeprüfung vor jedem Schreiben“; eindeutige tmp-Namen im Curator-Schreiber;
   `install.sh` zeigt den Unterschied und ersetzt einen aktiven Guard-Hook nur mit Freigabe
   (`POLARIS_ADOPT_GUARD=1`, nach Gutachten agy).
5. **Regeln ausführbar machen:** benannte Liste der Schutzdateien mit Zweitmeinungspflicht (Test:
   Liste = vorhandene Dateien); `AGENTS.md` im Wurzelverzeichnis mit „wo ändere ich was“;
   Test der Importrichtung (Bridge importiert nie Curator, Health nie Curator-Interna).
6. **Nahtstellen testen:** gemeinsame Beispieldatei für das Bridge-Ereignis, die Bridge- und
   Curator-Tests beide nutzen; ein Ende-zu-Ende-Test über die echten Befehle mit Fake-Modell
   (`runtime: command`), inklusive Abbruch mitten im Schreiben und verschwundenem Projektordner.

**Umgesetzt am 2026-11-07** (je Schritt Tests zuerst, Schutzdateien mit Zweitprüfung):
1. Live-worktree, `update.sh` abgesichert: `78f04ef`, `aa92612`, `4207bd6`, `5f33c40`, `f21ebf3`
2. Nutzungszähler vollständig: `df20d93`
3. Health Check entlastet (`health` ~0,45 s statt ~1,7 s, keine Cloud-Inhalte mehr je Aufruf): `6ba3192`
4. Schutz geschlossen (Sandbox fail-closed, Anmeldedaten, Zwischendateien, Hook-Diff): `b917d85`
5. `AGENTS.md`, Schutzdatei-Liste, Grenztests: `4870508`
6. Nahtstellen- und Ende-zu-Ende-Tests: `6b9a1e8`
Tests 682 → 722. Danach (`c692a71`): Größenlimits für Office-Archive, Dateien und Mails;
verwaiste `.tmp`-Dateien im Health Check. Offen für Stufe 2: die Bridge liest noch
`curator-state.json`.

Korrektur zu Schritt 6: Ein Ende-zu-Ende-Abbruch *mitten im Schreiben* ist nicht als
Ende-zu-Ende-Test umgesetzt; die Journal-Wiederherstellung prüfen die Unit-Tests des Curators
(Gutachten Codex/agy). Der Ende-zu-Ende-Test läuft seit dem Gutachten auch in der echten Sandbox.

### Stufe 2 – nach dem 05.12. (auf Grundlage des Zählers)

- Ungenutztes löschen; eine Seite `docs/contracts.md` für die verbleibenden Verträge.
- `check_system` (Maschinengesundheit) gegebenenfalls aus Polaris herauslösen.
- `modules.conf` und `health.d` (ADR 002, Stufen 1–2) nur, wenn eine zweite Installation sie braucht;
  dann `health.d` gehärtet (Schema-Version, nur Aufzählungswerte, kein freier Befehlstext).
- Pipelines nur entlang der Journal-Schritte zerlegen, wenn ein Fehler ohnehin dorthin führt.

### Entscheidungen des Nutzers (2026-11-07)

- **Keine signierten Release-Tags.** Die Update-Lieferkette bleibt so gesichert wie dokumentiert
  (Updates sind Fremdinhalt, bis der Nutzer sie gesehen hat; Commits an Schutzdateien vorher ansehen).
- **Repo-Name `polaris`:** das private Repo heißt seit 07.11. `mstio/polaris` (GitHub leitet die alte
  Adresse weiter). Der öffentliche Spiegel `mstio/polaris-connector` behält seinen Namen, weil die
  `update_url` der Erweiterung auf ihn zeigt. Der lokale Ordner wird mit Stufe 1, Schritt 1 neu geordnet.

## Bewusst nicht

Neuschreiben; neue Verzeichnisstruktur nach Schichten; `safety/`-Ordner; zweites
Freigabe-Skript; CI-Plattform; Datenbank, Dienste, Message Broker; Tests gegen das Live-ChatGPT.

## Prüfung je Schritt

Alle drei Testsuiten grün; neue Tests vor jeder Verhaltensänderung; Health vorher/nachher gleich
oder besser; Laufzeit von `health --json`/`status-all --json` nachgemessen; Frischinstallation in
leerem `HOME`; Schutzdateien nur mit Zweitmeinung.
