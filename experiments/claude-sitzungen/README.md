# claude-sitzungen: Sitzungsübersicht für Claude Code (Experiment)

Claude Chat zeigt in der Seitenleiste alle früheren Gespräche: Man sieht auf
einen Blick, worüber man zuletzt gesprochen hat, und öffnet ein Gespräch mit
einem Klick wieder. Claude Code hat das nicht. `claude --resume` zeigt nur die
Sitzungen des aktuellen Ordners, und man muss vorher wissen, in welchem Ordner
man war.

`claude-sitzungen` schließt diese Lücke für Omarchy: Ein Tastenkürzel öffnet
ein schwebendes Terminalfenster mit allen lokalen Claude-Code-Sitzungen über
alle Ordner hinweg.

Das ist ein **Vorschlag zum Ansehen**, noch nicht in `install.sh`
eingebunden. Ob und wie es in Polaris kommt, entscheidet der Maintainer
(Ideen unten).

## Bedienung

- Liste: neueste Sitzung oben, Zeit als „Heute“, „Gestern“, Wochentag oder
  Datum, Titel = KI-Titel von Claude Code (ein eigener Titel hat Vorrang).
  Ordner, die vom häufigsten abweichen, stehen grau dahinter.
- Vorschau unten: Ordner, Zeitraum, Zahl der Eingaben, erste und letzte
  Eingabe, letzte Antwort.
- ● = Sitzung ist gerade in einem Fenster offen.

| Taste | Wirkung |
|---|---|
| Tippen | Titel filtern (fzf-Suche) |
| Enter | Sitzung in neuem Terminalfenster fortsetzen (`claude --resume <id>` im Ordner der Sitzung). Schon offen: deren Fenster nach vorn holen statt doppelt öffnen |
| Strg+F | Abzweig für eine Nachfrage (`--fork-session`): Der ursprüngliche Verlauf bleibt unverändert |
| Strg+S | Getippten Text im **Gesprächsinhalt** suchen, mit Trefferzahl je Sitzung |
| Strg+R | Wieder alle Sitzungen zeigen |
| Esc | Schließen |

## Ausprobieren

```bash
experiments/claude-sitzungen/claude-sitzungen          # direkt im Terminal
```

Als schwebendes Fenster mit Tastenkürzel (`~/.config/hypr/bindings.lua` bzw.
`hyprland.lua`; Pfad anpassen):

```lua
hl.unbind("SUPER + ALT + H")
o.bind("SUPER + ALT + H", "Claude-Sitzungen", "omarchy-launch-tui --app-id=org.omarchy.claude-sitzungen <pfad>/claude-sitzungen")
o.window("^org\\.omarchy\\.claude-sitzungen$", { float = true, size = { 1150, 760 }, center = true })
```

Abhängigkeiten: `python3`, `fzf` (getestet mit 0.74). Optional: `rg`
(schnellere Inhaltssuche), `hyprctl` (Fokus auf offene Sitzung),
`uwsm-app` + `xdg-terminal-exec` (Omarchy-Standard zum Starten).

## Wie es funktioniert

- Quelle sind allein die Verlaufsdateien von Claude Code:
  `~/.claude/projects/*/<session-id>.jsonl` (bzw. `$CLAUDE_CONFIG_DIR`).
  Ausgewertet werden die Einträge `ai-title`, `custom-title`, `last-prompt`
  sowie `cwd`, `timestamp` und Text von `user`/`assistant`.
  `<system-reminder>`-Blöcke (z. B. eingeblendetes Gedächtnis) zählen nicht
  als Inhalt, weder in der Vorschau noch in der Suche.
- Gelistet werden nur Sitzungen mit mindestens einer echten Eingabe, deren
  Ordner unter `$HOME` noch existiert (sonst ist `--resume` nicht möglich,
  z. B. bei Agenten in temporären Ordnern).
- „Gerade offen“ kommt aus `~/.claude/sessions/*.json` (PID wird geprüft,
  auch gegen PID-Wiederverwendung).
- Zwischenspeicher `~/.cache/claude-sitzungen/index.json`, je Datei nach
  mtime und Größe. Erster Aufbau bei ~180 Sitzungen / 490 MB rund 2,5 s,
  danach unter 0,1 s.

## Entscheidungen

Erwogen wurden drei Formen:

1. **Terminal-Übersicht mit fzf** (gewählt): passt zu Omarchy (TUIs wie btop
   per `omarchy-launch-tui`), kein Hintergrunddienst, kein neues Einfallstor,
   volle Suche und Vorschau.
2. Lokale HTML-Seite im Browser mit eigenem Link-Protokoll
   (`claude-sitzung://<id>`): schöner, aber jede Webseite könnte solche
   Links auslösen. Das wäre ein neues Einfallstor nur für die Optik.
3. Eintrag im Omarchy-Menü: schnell, aber nur Titel, keine Vorschau, keine
   Inhaltssuche.

## Sicherheit und Ressourcen

- Nur lesend auf den eigenen Verlauf; kein Netz, keine KI-Verarbeitung.
- Titel und Texte sind Fremdinhalt (Modellausgaben, eingefügte Texte):
  Steuerzeichen (ESC, C1, Bidi) werden vor der Anzeige entfernt, damit kein
  Text das Terminal steuern kann.
- Öffnen nur mit gültiger UUID und einem vorhandenen Ordner unter `$HOME`
  (Positivliste); Befehl als Argumentliste, keine Shell.
- Der neue Prozess startet ohne `CLAUDE_CODE_*`-Variablen. Sonst erbt eine
  aus einer Claude-Sitzung gestartete Sitzung u. a.
  `CLAUDE_CODE_CHILD_SESSION` und speichert ihren Verlauf nicht.
- Ressourcen: kein Dienst, kein Timer, keine Abfragen im Hintergrund. Arbeit
  fällt nur an, solange das Fenster offen ist.

## Ideen zur Integration in Polaris

- `install.sh` verlinkt das Skript nach `~/.local/bin` (wie `polaris-radar`).
- Tastenkürzel und Fensterregel optional, z. B. über das Widget
  `mst.agent-launchers` oder als Vorschlag im Installer.
- Später auch Codex-Sitzungen (`~/.codex/sessions`) in derselben Liste.
- Verknüpfung mit Polaris-Projekten: Sitzungen nach Projektordner
  (`projects.yaml`) gruppieren oder filtern.

## Grenzen

- Das `.jsonl`-Format von Claude Code ist nicht dokumentiert und kann sich
  mit Updates ändern. Bricht die Liste, zuerst die Eintragstypen in einer
  aktuellen Verlaufsdatei prüfen.
- Fokus auf ein schon offenes Fenster nur unter Hyprland. Ohne Hyprland kommt
  eine Meldung mit dem Hinweis auf Strg+F.

## Tests

```bash
python3 -m unittest discover -s experiments/claude-sitzungen
```

Ohne Netz und ohne fzf, mit erfundenen Sitzungen in einem temporären Home:
Filter (Ordner fehlt, außerhalb `$HOME`, nur Slash-Befehl), Auswertung ohne
`system-reminder`, Entfernen von Steuerzeichen, Zwischenspeicher,
Inhaltssuche, Öffnen nur über Positivliste, Fokus statt Doppelöffnen.
