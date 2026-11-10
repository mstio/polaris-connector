# ADR 004: Zielarchitektur – Kern, Verträge, Module

Status: **Entwurf** (2026-11-07, Agent; offene Fragen vom Nutzer beantwortet). Entscheidung frühestens nach Auswertung des
Nutzungszählers (~05.12.2026). Bezug: ADR 002 (modulare Installation, zurückgestellt),
ADR 003 Stufe 2, README „Architecture: core and modules“. Fasst die Zielarchitektur aus
diesen drei Quellen in einem Dokument zusammen; ersetzt nach Annahme ADR 002, Stufen 2–3.

## Ziel (vom Nutzer bestätigt und gewichtet, 2026-11-07, aus einer anderen Agentensitzung übermittelt)

Vorrang, in dieser Reihenfolge:
1. Robustheit, Schutz von Rechner und Arbeit, Wartbarkeit („Größe ist kein Ziel an sich“, ADR 003).
   Konkret: Teile einzeln ändern, testen und entfernen können, ohne andere still zu brechen;
   Verträge zwischen den Teilen an einer Stelle; Health Check und Hintergrundlast klein.
2. Übertragbarkeit auf andere Omarchy-Setups (Nutzerziel seit 07.10., `handoff/polaris.md`):
   `update.sh` weiß, was installiert ist, statt zu raten. Auswahl je Modul nur so weit, wie
   belegte fremde Installationen sie brauchen – derzeit genau eine.

Nicht Ziel: neue Funktionen, neue Abhängigkeiten, neue Verzeichnisstruktur um ihrer selbst willen,
Health Check als eigenes Paket vor konkretem Bedarf, AUR-Listung.

## Befund (geprüft am 2026-11-07, Stand `6ba3192`; ADR-003-Stufe-1 bis `f22a1fc` nachgetragen)

| Befund | Beleg | Status |
|---|---|---|
| `raw/`-Layout doppelt definiert (Bridge und Curator), dazu im Health Check | `bridge/polaris/storage.py:56-69`, `curator/polaris_curator/layout.py:42-51`, `systemhealth.py` | Nachgewiesen |
| Bridge liest Curator-Interna `.polaris/curator-state.json` | `bridge/polaris/pipeline.py:353`, `conflicts.py:161` | Nachgewiesen |
| Bridge importiert den Curator nicht (Kopplung nur über Dateien) | `grep polaris_curator bridge/` ohne Treffer | Nachgewiesen |
| `update.sh` errät installierte Teile aus Ordnern; Backup wird nie aktualisiert | `update.sh:141-145` | Nachgewiesen |
| Health Check kennt jedes Teil fest (`GROUPS`) | `systemhealth.py:1115 ff.` | Nachgewiesen |
| Zustandsdateien je Teil gibt es schon, ohne gemeinsames Schema: `security.json`, `memory-mirror.json`, `update-check.json`, `capture-status.json`, `integrity-status.json`, `usage.json` | `~/.local/state/polaris/` | Nachgewiesen |
| Bridge-Ereignis ist versioniert (`schema_version` = 1, geprüft) | `bridge/polaris/schema.py:26-27` | Nachgewiesen |
| Ereignis-Vertrag eingefroren und Ende-zu-Ende getestet (echte Bridge → echter Curator) | `tests/contracts/bridge-event-{chatgpt,claude}.json`, `tests/test_contract_seam.py` (ADR 003, Schritt 6) | Nachgewiesen (Dateien vorhanden) |
| Wurzel-`AGENTS.md` mit Schutzdatei-Liste (inkl. `bridge/polaris/native_host.py`, `update.sh`) und Grenztest | `AGENTS.md`, `tests/test_boundaries.py` (ADR 003, Schritt 5) | Nachgewiesen (Dateien vorhanden) |
| `docs/contracts.md` fehlt | `ls` | Nachgewiesen |
| Fremde Installationen | genau eine, nur Claude-Erfassung (Angabe des Nutzers; `handoff/polaris.md`) | Plausibel |
| `check_system` kostet ~0,01 s, `du` nur bei fast voller Platte | Messung 07.11. nach `6ba3192` (andere Agentensitzung) | Plausibel (nicht selbst gemessen) |
| Welche Teile genutzt werden | Nutzungszähler läuft seit 07.11. | Unbekannt bis ~05.12. |
| Welche Health-Zeilen gelb bleiben, ohne dass jemand handelt (Alarmmüdigkeit) | Tage je Prüfung `health-warn:*`/`health-error:*` in `usage.json`, Nenner `health:day`, seit 08.11. | Unbekannt bis ~05.12. |

Schluss: Die Modulgrenzen bestehen im Code schon weitgehend. Was fehlt, sind **beschriebene und
getestete Verträge** an den Nahtstellen und **gewusster statt erratener Installationszustand**.

## Bausteine (gemeinsam für alle Wege)

- **Kern:** Projektordner-Layout, Curator, CLIs `polaris` / `polaris-curator`.
- **Quellen:** Browser-Erfassung (Erweiterung, Native Host, Bridge), Export-Import, Inbox.
- **Anzeige:** Curator-Widget.
- **Querschnitt:** Health Check, Radar, Maschinengedächtnis, Backup (eigene Repos), Extras.
- **Regel:** Abhängigkeiten nur Modul → Kern/Querschnitt; `health` hängt von niemandem ab
  (Test der Importrichtung aus ADR 003, Schritt 5).

## Wege

### Weg 1 – Verträge zuerst, Module nur logisch (Bordmittel)

Keine neuen Ordner. Drei Verträge in `docs/contracts.md`, jeder mit Test:

1. **Projektordner-Vertrag:** `raw/<quelle>/{messages,conversations}`, `inbox/`, Wissensdateien,
   `.polaris/`. Eine einzige Definition (Kernmodul, das Bridge **und** Curator lesen dürfen,
   weil es Kern ist); Health nutzt dieselbe.
2. **Ereignis-Vertrag Bridge → Curator:** besteht bereits (ADR 003, Schritt 6): die
   eingefrorenen Beispieldateien unter `tests/contracts/` sind die verbindliche Form,
   `schema_version` steht im Ereignis. Hier nur noch in `docs/contracts.md` beschreiben und
   festhalten: neue Felder nur mit neuer `schema_version` und neuer Beispieldatei.
3. **Zustands-Vertrag Modul → Health:** jede vorhandene Zustandsdatei bekommt ein Mindestschema
   `{schema, module, status ∈ {ok,warn,error,unknown}, checked_at, stale_after, detail}`;
   `detail` ist nur Anzeige-Text, nie Befehl. Health wertet `checked_at + stale_after`
   (veraltet = `warn`). Bestehende Dateien bleiben, wo sie sind; kein `health.d`.
   Nachtrag 2026-11-10: `security.json` (Radar) trägt inzwischen eigene Felder
   (`findings`, `acknowledged`, `ack_basis`, `error`), die `systemhealth.py` selbst
   auswertet. Bei diesem Schritt meldet der Radar `status` und `detail` (z. B. „ok,
   1 quittiert“) selbst; die übrigen Felder bleiben Radar-intern.

Dazu: Curator veröffentlicht, was die Bridge braucht, als Vertragsdatei (statt dass die Bridge
`curator-state.json` liest). `~/.config/polaris/modules.conf` aus ADR 002, Stufe 1, ersetzt das
Raten in `update.sh`.

- Vorteile: löst die belegten Schwachstellen; wenige neue Dateien; jede Teiländerung einzeln
  umkehrbar; keine Migration von Ordnern.
- Nachteile: `install.sh` bleibt ein Ablauf (≈ 900 Zeilen); Health kennt Module weiter beim
  Namen (aber nur noch über Zustandsdateien).
- Kosten: keine neuen Timer; Health wird eher billiger (liest Dateien).

### Weg 2 – ADR 002 vollständig (Steckbriefe und Modulordner)

`modules/<id>/{module.conf,install.sh,remove.sh,health}`, `health.d/<id>.json`, Auflöser für
`requires` in `install.sh`.

- Vorteile: echte Auswahl je Modul, Kosten vor der Installation sichtbar, Health als eigenes Paket möglich.
- Nachteile: 20–30 neue Dateien mit gleichem Grundgerüst, Abhängigkeitsauflöser in bash,
  Migration bestehender Installationen über den bisher schwächsten Pfad (`update.sh`), neue
  Vertrauensgrenze `health.d`. Löst die Vertragsprobleme nicht.
- Lohnt erst bei mehreren unterschiedlich zusammengesetzten Installationen.

### Weg 3 – Pakete und Plugins (verworfen)

Vom Nutzer verworfen (07.11.): Verteilung nur per git (seit 04.11., `84d4a65`), keine signierten
Release-Tags (ADR 003); die Marktplatz-Einreichung von omarchy-backup wurde wegen
Signaturforderungen zurückgezogen. Das Curator-Widget im Omarchy-Plugin-Marktplatz ist davon
getrennt und bleibt.

Systemweite Teile als PKGBUILD, Widgets als Omarchy-Plugins, Rest per git.

- Vorteile: Abhängigkeiten über pacman, Voraussetzung für AUR-Listung.
- Nachteile: zweiter Update-Weg neben git, unpassend für Home-Konfiguration (systemd `--user`,
  Gedächtnis); widerspricht „Verteilung nur per git“.

### Weg 4 – Gegenpart: nur aufräumen

Nach dem 05.12. Ungenutztes löschen, sonst nichts ändern.

- Vorteile: kein Risiko, kein Aufwand.
- Nachteile: belegte Schwachstellen (doppeltes Layout, Lesen fremder Interna, Raten in
  `update.sh`) bleiben; jede künftige Erweiterung vergrößert sie.

## Empfehlung

**Weg 1**, danach Weg 2 nur bei erfülltem Auslöser.

Reihenfolge (jeder Schritt einzeln nutzbar und umkehrbar, vorher Tests):

0. Offene Punkte aus ADR 003, Stufe 1 (`f22a1fc`) zuerst, weil Schutz Vorrang hat:
   Größenlimit in `office_extract` (Zip-Bombe); verwaiste eindeutige `.tmp`-Dateien im Health
   Check melden. (`curator-state.json` in der Bridge erledigt Schritt 3.)
1. Ungenutztes löschen (Zählerdaten 05.12.).
   **Prüfpunkt danach** (Tetralemma „keines von beiden“, Skill `perspektivwechsel`, 08.11.):
   Befund oben neu erheben; Schritte 2–5 nur, soweit die Schwachstellen nach dem Löschen noch
   bestehen (fällt ein Teil weg, entfällt ggf. sein Vertrag). Health-Zeilen mit vielen
   Alarmtagen ohne Handlung schärfen oder streichen.
2. `docs/contracts.md` mit den drei Verträgen (Ereignis-Vertrag nur beschreiben, Tests gibt es);
   Projektordner-Layout an einer Stelle mit Test.
3. Curator-Vertragsdatei statt `curator-state.json` in der Bridge.
4. Mindestschema für Zustandsdateien, Veraltungsprüfung im Health Check.
5. `modules.conf`; `update.sh` liest sie (Migration aus vorgefundenem Zustand, nichts Neues).

**Auslöser für Weg 2** (alle drei): mindestens zwei fremde Installationen mit abweichender
Modulauswahl; ein Modul soll unabhängig erscheinen oder entfernt werden können; die Verträge
aus Weg 1 sind stabil (zwei Monate ohne Vertragsänderung).

## Prüfung

- Alle drei Testsuiten grün; Vertragstests schlagen fehl, wenn eine Seite das Format ändert
  (bewusst gebrochener Test als Nachweis).
- Frischinstallation in leerem `HOME`; Update-Simulation von einem älteren Stand; nichts Neues entsteht.
- `health --json` und `status-all --json` vor/nach gemessen, gleich oder schneller.
- Zweitmeinung (stärkstes Modell) für Schritt 3 und 4, weil sie Schutz- und Health-Pfade berühren.
- **Vor der Annahme dieses ADR:** unabhängige Prüfung durch das stärkste Modell, zusätzlich ein
  Gremium anderer Anbieter, weil es eine Architekturentscheidung ist (Meilenstein-Regel in
  AGENTS.md). Nutzer 2026-11-08: nicht jetzt, sondern mit der Entscheidung nach dem 05.12.

## Antworten des Nutzers (2026-11-07, aus einer anderen Agentensitzung übermittelt)

1. **Ziel:** bestätigt, gewichtet (siehe „Ziel“): Robustheit, Schutz, Wartbarkeit vor
   Modulauswahl; Auswahl nur so weit, wie belegte fremde Installationen sie brauchen.
2. **Health als eigenes Paket:** kein Ziel vor dem 05.12. (Nutzer 04.11.: „später“). Zuerst
   Entkopplung über Zustandsdateien (Weg 1, Schritt 4); ein Paket nur bei konkretem Bedarf.
3. **AUR-Listung:** nicht gewollt → Weg 3 verworfen.
4. **`check_system`:** bleibt in Polaris (Hinweise zu Plattenfehlern, Neustart, Abstürzen,
   Backup-Ziel hat der Nutzer am 05.11. eingeführt; Kosten ~0,01 s). Neu bewerten nur, falls die
   Zählerdaten am 05.12. etwas anderes zeigen.

## Bewusst nicht

Neuschreiben; Schichtenordner; `safety/`-Ordner; Datenbank, Dienste, Broker; neue Abhängigkeiten.
