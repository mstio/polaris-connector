# ADR 002: Modulare Installation (Kern und Module)

Status: **Angenommen** (2026-11-04): Weg 1 in drei Stufen, Umsetzung offen (Stufe 1 als Nächstes).
Bezug: Zielbild „Kern und Module“ (README, Abschnitt *Architecture*),
Verteilung nur per git (seit 2026-11-04).

## Ziel

Polaris soll sich so installieren lassen, dass man die Module auswählt und
deren Abhängigkeiten sich von selbst richtig einfügen. Ein Update richtet
nichts Neues ein. Dabei gelten die bestehenden Vereinbarungen:

- ressourcenschonend: keine Dauerprozesse, Timer so selten wie möglich, Netz
  nur, wo nötig; die Kosten jedes Moduls stehen vor der Auswahl da
- keine neuen Abhängigkeiten (bash, python3, PyYAML, git, Omarchy-Bordmittel)
- menschenlesbar: Konfiguration und Zustand als Klartext-Dateien
- an der Omarchy-Architektur ausgerichtet (`omarchy plugin add/update` für
  Widgets, systemd `--user`, Hooks unter `~/.config/omarchy/hooks/`)
- klein, nachvollziehbar, umkehrbar; jede Stufe einzeln nutzbar

## Befund (Stand `84d4a65`)

- Im Code sind die Teile schon über Dateien gekoppelt (Bridge ↔ Curator nur
  über `raw/` und den Konfliktordner).
- `install.sh` ist eine Folge fester Schritte: Gedächtnis, Voraussetzungen,
  Befehle, Bridge-Konfiguration, Curator-Modell, systemd-Units, Native Host,
  Widgets, Dock, Radar-Hook, omarchy-backup, Gedächtnis-Werkzeuge, Prüfung.
  Abwählbar sind nur einzelne Gruppen (`--no-units`, `--no-widget`,
  `--no-dock`, `--no-backup`, `--no-memory`).
- Welche Teile eingerichtet sind, errät `update.sh` aus vorhandenen
  Verzeichnissen (Widget-Ordner, Units, Gedächtnis).
- Der Health Check kennt jedes Modul fest (`GROUPS` in `systemhealth.py`).
  Nur der Radar liefert schon eine Zustandsdatei
  (`~/.local/state/polaris/security.json`), die der Health Check liest.

## Module und Abhängigkeiten

| Modul | braucht | Hintergrund-Kosten |
|---|---|---|
| `core` (Projektordner, Curator, CLIs) | python3, PyYAML, eine Modell-CLI | Curator-Timer nachts |
| `capture` (Erweiterung, Native Host, Bridge) | `core`, Firefox | Path-Unit, Timer alle 10 min (Sicherheitsnetz), Host nur bei offenem Tab |
| `widget` (Curator-Widget) | `core`, Omarchy, jq | keine (liest beim Öffnen) |
| `health` (Health Check) | – (eigenständig, Ziel: eigenes Paket) | keine eigenen Abfragen; liest Zustandsdateien |
| `memory` (Maschinengedächtnis, memlint) | python3 | keine |
| `memory-mirror` | `memory` | Timer alle 30 min, nur lokale Kopie |
| `radar` (Neuigkeiten, Sicherheit) | `memory` | Timer täglich, ~3 MB; NVD höchstens 5 Abfragen |
| `backup` (omarchy-backup + Widget) | Omarchy, git | eigene Timer (täglich, monatlich) |
| `agent-launchers`, `dock` | Omarchy | keine |

Abhängigkeiten nur in eine Richtung: Module hängen vom Kern oder von
Querschnittsmodulen ab, nie umgekehrt. `health` hängt von niemandem ab.

## Wege

1. **Modul-Steckbriefe mit Orchestrierung durch `install.sh`** (Bordmittel).
   Je Modul ein Ordner `modules/<id>/` mit
   - `module.conf` (Klartext `schluessel=wert`): Titel, `requires=`,
     benötigte Befehle, Kosten-Text, Units, Widget-URL
   - `install.sh` / `remove.sh` (idempotent, `--dry-run`, `--only-existing`)
   - optional `health` (schreibt bzw. liefert
     `~/.local/state/polaris/health.d/<id>.json`)

   `install.sh` liest die Steckbriefe, zeigt Auswahl und Kosten, löst
   `requires` auf (in Abhängigkeitsreihenfolge) und merkt sich die Auswahl in
   `~/.config/polaris/modules.conf` (eine Zeile je Modul). `update.sh`
   aktualisiert genau diese Module; der Health Check zeigt, was in
   `health.d/` liegt.
2. **Ein `install.sh` mit Modul-Schaltern** (`--with`/`--without`) und einer
   festen Abhängigkeitstabelle im Skript. Kleinster Umbau, bleibt aber
   monolithisch; der Health Check kennt weiter jedes Modul.
3. **Arch-Pakete je Modul (PKGBUILD)**, Abhängigkeiten über pacman. Sauber
   für systemweite Teile und Voraussetzung für eine offizielle Listung (AUR),
   aber unpassend für Einstellungen im Home (systemd `--user`, Widgets,
   Gedächtnis) und ein zweiter Update-Weg neben git.
4. **Alles als Omarchy-Plugins.** Passt nur für Widgets, nicht für CLIs,
   Units und Native Host.

## Empfehlung

**Weg 1, in drei Stufen**; jede ist für sich nützlich und umkehrbar:

1. **Auswahl merken:** `~/.config/polaris/modules.conf` plus
   Abhängigkeitstabelle; die geführte Einrichtung fragt Module statt Gruppen
   ab und zeigt die Kosten. `update.sh` liest die Datei statt zu raten. Für
   bestehende Installationen schreibt das erste Update die Datei aus dem
   vorgefundenen Zustand (Migration ohne Rückfrage, nichts Neues).
2. **Health über Zustandsdateien:** Module schreiben
   `~/.local/state/polaris/health.d/<id>.json` (Form wie `security.json`);
   der Health Check liest nur diese. Danach kann er ein eigenes Paket
   werden (offener Punkt „Health Check als eigenes Paket“).
3. **Steckbriefe und Modul-Skripte:** die Schritte aus `install.sh` nach
   `modules/<id>/` verschieben; `install.sh` bleibt der Einstieg.

Weg 3 (PKGBUILD) nur, falls eine offizielle Listung gewollt ist; dann für
die systemweiten Teile, ergänzend zu git.

## Prüfung je Stufe

- Frischinstallation in leerem `HOME` mit Platzhaltern (`omarchy`,
  `systemctl`, `omarchy-shell`) für jede Modulauswahl, inklusive „nur core“
- Update-Simulation von einem älteren öffentlichen Stand aus (altes
  `update.sh` ruft neues `install.sh` auf); nichts Neues darf entstehen
- Health Check vor/nach gleich oder besser; Tests aller drei Suiten grün
