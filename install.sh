#!/usr/bin/env bash
# Richtet Polaris (Bridge, Curator, Health-Check-Widget, auf Wunsch
# omarchy-backup mit Widget und das Maschinengedaechtnis) auf einem Omarchy-
# Rechner ein - idempotent, auf dem Entwicklungsrechner ein No-op (seit 2026-10-07).
#
#   ./install.sh                 gefuehrte Einrichtung (fragt nach, bestaetigen)
#   ./install.sh [--yes] [--dry-run] [--projects <Ordner>] [--runtime codex|claude|command]
#                [--chat-sources both|chatgpt|claude|none]
#                [--no-units] [--no-widget] [--no-dock] [--no-restart] [--no-backup] [--no-memory]
#                [--backup-target <Ordner>] [--memory-mirror <Ordner>]
#
#   Ohne Optionen und in einem Terminal fragt das Skript die Einstellungen ab,
#   zeigt eine Zusammenfassung und richtet erst nach Bestaetigung ein.
#   --yes        nicht fragen (Standardwerte bzw. die angegebenen Optionen)
#   --dry-run    nur anzeigen, was passieren wuerde
#   --projects   Ordner, in dem die Projektordner liegen (polaris roots add)
#   --runtime    Modell-Runtime fuer eine NEU anzulegende curator.yaml:
#                codex, claude oder command (beliebige Agenten-CLI, Vorlage
#                curator/curator.example-command.yaml anpassen). Standard:
#                codex, falls installiert, sonst claude
#   --chat-sources  Browser-Chats fuer eine NEU anzulegende curator.yaml;
#                unabhaengig von der Curator-Runtime. Ohne Option gilt die Vorlage.
#   --language   Sprache von Widget und Health Check fuer eine NEU anzulegende
#                curator.yaml: en oder de. Standard: de bei deutscher
#                Systemsprache (LANG=de_*), sonst en. Spaeter: language: in
#                ~/.config/polaris/curator.yaml
#   --no-units   systemd-Units nicht installieren/aktivieren
#   --no-widget  Omarchy-Bar-Widgets nicht installieren (Health Check, Backup,
#                Agenten-Starter)
#   --no-dock    das Dock (omadock, oeffentliches git-Repo) nicht installieren
#   --no-restart Omarchy-Leiste am Ende nicht neu starten (sonst: nur wenn
#                Plugins kopiert/aktiviert wurden und kein Curator-Lauf aktiv ist)
#   --no-backup  omarchy-backup (eigenes oeffentliches git-Repo) nicht einrichten
#   --only-existing  nur Vorhandenes aktualisieren, keine Widgets/Dock neu holen
#                (fuer 'polaris update': ein Update richtet nichts Neues ein)
#   --no-memory  Maschinengedaechtnis (~/.config/ai-agents) nicht anlegen/aktualisieren
#   --backup-target  Ordner fuer die Sicherungen von omarchy-backup (z. B. auf
#                einem Cloud-Laufwerk); schaltet die taeglichen Snapshots ein
#   --storage-unit  systemd-User-Unit, die das Laufwerk mit den Projektordnern
#                einhaengt (z. B. rclone-projekte.service); Bridge, Curator und
#                Spiegel starten dann danach (Drop-in polaris-storage.conf).
#                Standard: bisheriger Eintrag, sonst rclone-projekte.service,
#                falls vorhanden. "none" fuer lokale Ordner (z. B. Nextcloud)
#   --memory-mirror  Ordner, in den das Maschinengedaechtnis gespiegelt wird
#                (z. B. <Projektordner>/Polaris/Maschinengedaechtnis); fehlt
#                ~/.config/ai-agents, wird es von dort zurueckgeholt
#
# Polaris wird per git verteilt (seit 2026-11-04, kein Installationspaket
# mehr). Ohne .git gestartet (z. B. GitHub-"Download ZIP" oder ein altes
# Paket), kopiert es die Programmdateien zuerst nach
# ~/.local/share/polaris/app und installiert von dort.
#
# Installiert keine Pakete. Aus dem Netz holt es nur die Bausteine aus
# eigenen oeffentlichen git-Repos: die Widgets (Backup, Agenten-Starter) und
# das Dock per 'omarchy plugin add' (danach aktualisiert sie 'omarchy plugin
# update'), die omarchy-backup-CLI per git clone nach
# ~/.local/share/polaris/extras/ (aktualisiert von 'polaris update').
# Abschaltbar mit --no-widget, --no-dock, --no-backup. Ersetzte Dateien werden
# vorher nach ~/.local/share/polaris/install-backups/<Zeit>/ gesichert.
# Die Firefox-Erweiterung selbst (AMO, signiert) wird von Hand installiert,
# siehe docs/browser-capture.md "Installing the extension".
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"
POLARIS_CFG="$HOME/.config/polaris"
PLUGIN_ID="mst.polaris-curator"
PLUGIN_DIR="$HOME/.config/omarchy/plugins/$PLUGIN_ID"
# Ein Update richtet nichts Neues ein: --only-existing (neues update.sh) oder
# Aufruf durch ein update.sh (aelteres update.sh kennt die Option nicht; erster
# Update-Lauf nach 2026-11-04). Ein Neulauf von Hand nach einer abgebrochenen
# Erstinstallation holt fehlende Widgets dagegen nach.
NO_NEW=0
NO_NEW_REASON=""
# Nur ein Argument, das auf update.sh endet (Skriptpfad), nicht jede Erwaehnung
# im Befehlstext (z. B. bash -c "...update.sh --check; ./install.sh ...").
if [ -r "/proc/$PPID/cmdline" ] && tr '\0' '\n' < "/proc/$PPID/cmdline" | grep -qE '(^|/)update\.sh$'; then
  NO_NEW=1 NO_NEW_REASON="Aufruf durch update.sh erkannt"
fi
BACKUP_DIR="$HOME/.local/share/polaris/install-backups/$(date +%Y%m%d-%H%M%S)"
# Bausteine aus eigenen oeffentlichen Repos (seit 2026-11-04 statt extras/ im Paket)
EXTRAS_DIR="$HOME/.local/share/polaris/extras"
OB_URL="https://github.com/mstio/omarchy-backup.git"
OB_PLUGIN_URL="https://github.com/mstio/mst.omarchy-backup.git"
AL_URL="https://github.com/mstio/mst.agent-launchers.git"

ORIG_ARGS=("$@")  # fuer den Neustart aus dem App-Ordner (die Schleife verbraucht "$@")
ONLY_EXISTING=0 DRY=0 PROJECTS="" RUNTIME="" UI_LANG="" CHAT_SOURCES="" STORAGE_UNIT="" UNITS=1 WIDGET=1 DOCK=1 RESTART=1 OBACKUP=1 MEMORY=1 YES=0 OB_TARGET="" MIRROR=""
GUIDED=0; [ $# -eq 0 ] && [ -t 0 ] && [ -t 1 ] && GUIDED=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --projects) PROJECTS="${2:?--projects braucht einen Ordner}"; shift ;;
    --runtime) RUNTIME="${2:?--runtime braucht codex|claude|command}"; shift ;;
    --language) UI_LANG="${2:?--language braucht en|de}"; shift ;;
    --chat-sources) CHAT_SOURCES="${2:?--chat-sources braucht both|chatgpt|claude|none}"; shift ;;
    --no-units) UNITS=0 ;;
    --no-widget) WIDGET=0 ;;
    --no-dock) DOCK=0 ;;
    --only-existing) ONLY_EXISTING=1 NO_NEW=1 NO_NEW_REASON="--only-existing" ;;
    --no-restart) RESTART=0 ;;
    --no-backup) OBACKUP=0 ;;
    --no-memory) MEMORY=0 ;;
    --yes|-y) YES=1 ;;
    --backup-target) OB_TARGET="${2:?--backup-target braucht einen Ordner}"; shift ;;
    --memory-mirror) MIRROR="${2:?--memory-mirror braucht einen Ordner}"; shift ;;
    --storage-unit) STORAGE_UNIT="${2:?--storage-unit braucht eine Unit oder none}"; shift ;;
    -h|--help) awk 'NR>1 && /^#/{sub(/^# ?/,"");print;next} NR>1{exit}' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$RUNTIME" in ""|codex|claude|command) ;; *) echo "--runtime: codex, claude oder command" >&2; exit 2 ;; esac
case "$CHAT_SOURCES" in ""|both|chatgpt|claude|none) ;; *) echo "--chat-sources: both, chatgpt, claude oder none" >&2; exit 2 ;; esac
# Sprache fuer eine neue curator.yaml: deutsche Systemsprache -> de, sonst en.
if [ -z "${UI_LANG:-}" ]; then case "${LANG:-}" in de_*|de) UI_LANG=de ;; *) UI_LANG=en ;; esac; fi
case "$UI_LANG" in en|de) ;; *) echo "--language: en oder de" >&2; exit 2 ;; esac

# Ohne .git gestartet (GitHub-ZIP, altes Installationspaket): Die
# Programmdateien kommen an einen festen Ort, damit Befehle, Units und Native
# Host nicht auf ~/Downloads zeigen. Aus einem git-Checkout bleibt alles dort.
APP_DIR="$HOME/.local/share/polaris/app"
if [ ! -d "$REPO/.git" ] && [ "$REPO" != "$APP_DIR" ]; then
  echo "== Programmdateien nach $APP_DIR"
  if [ "$DRY" = 1 ]; then
    echo "  [dry-run] Kopie von $REPO nach $APP_DIR (vorhandene Fassung wird gesichert)"
  else
    stage="$APP_DIR.new.$$"
    rm -rf -- "$stage"; mkdir -p -- "$(dirname -- "$APP_DIR")"
    cp -a -- "$REPO/." "$stage/"
    if [ -d "$APP_DIR" ]; then
      mkdir -p -- "$BACKUP_DIR"
      mv -- "$APP_DIR" "$BACKUP_DIR/app"
      echo "  bisherige Fassung gesichert: $BACKUP_DIR/app"
    fi
    mv -- "$stage" "$APP_DIR"
    echo "  installiert, weiter mit $APP_DIR/install.sh"
    exec "$APP_DIR/install.sh" "${ORIG_ARGS[@]}"
  fi
fi

WARNINGS=()
say()  { printf '%s\n' "$*"; }
STEP="Start"
step() { STEP="$1"; say "== $1"; }  # Ueberschrift + Schritt fuer das Abbruch-Protokoll
FAIL_REASON=""
die() { FAIL_REASON="$*"; echo "FEHLER: $*" >&2; exit 1; }
warn() { printf 'WARNUNG: %s\n' "$*"; WARNINGS+=("$*"); }
run()  { if [ "$DRY" = 1 ]; then printf '  [dry-run] %s\n' "$*"; else "$@"; fi; }
backup() {  # sichert eine Datei/ein Verzeichnis vor dem Ersetzen
  local rel="${1#"$HOME"/}"
  run mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
  run cp -a "$1" "$BACKUP_DIR/$rel"
  say "  gesichert: $1 -> $BACKUP_DIR/$rel"
}

# --- Gefuehrte Einrichtung --------------------------------------------------
ask() {  # ask <Frage> <Vorgabe> -> REPLY (Vorgabe bei leerer Eingabe)
  local answer
  if [ -n "$2" ]; then read -r -p "$1 [$2]: " answer || answer=""
  else read -r -p "$1: " answer || answer=""; fi
  REPLY="${answer:-$2}"
}
ask_yn() {  # ask_yn <Frage> <j|n> -> Exit 0 bei ja
  local def="$2" answer
  read -r -p "$1 [$([ "$def" = j ] && echo J/n || echo j/N)]: " answer || answer=""
  answer="${answer:-$def}"
  case "$answer" in j|J|ja|Ja|y|Y|yes) return 0 ;; *) return 1 ;; esac
}
tilde() { printf '%s' "${1/#$HOME/\~}"; }
SHELL_RESTART=0  # 1, sobald ein Plugin neu kopiert/aktiviert wurde
install_plugin_git() {  # install_plugin_git <id> <git-URL>: wie 'omarchy plugin add', danach 'omarchy plugin update'
  local id="$1" url="$2"
  step "Omarchy-Widget ($id)"
  local dir="$HOME/.config/omarchy/plugins/$id"
  if [ -d "$dir" ]; then
    if [ -d "$dir/.git" ]; then say "  vorhanden (git, aktualisiert von 'omarchy plugin update')"
    else say "  vorhanden als Kopie, wird nicht aktualisiert; umstellen: omarchy plugin remove $id && omarchy plugin add $url --enable"; fi
    # z. B. nach 'plugin add' ohne laufende Shell: geklont, aber nie aktiviert
    if ! plugin_enabled "$id"; then
      run omarchy plugin enable "$id" && SHELL_RESTART=1 || warn "$id liess sich nicht aktivieren: omarchy plugin enable $id"
    fi
  elif [ "$NO_NEW" = 1 ]; then
    say "  nicht eingerichtet, bleibt so (Update richtet nichts Neues ein; holen: omarchy plugin add $url --enable)"
  elif run omarchy plugin add "$url" --enable --yes 2>&1 | sed 's/^/  /'; then
    SHELL_RESTART=1
  else
    warn "$id nicht installiert (Netz?): omarchy plugin add $url --enable"
  fi
}
plugin_known() {  # plugin_known <id> -> Exit 0, wenn die laufende Shell das Plugin kennt
  omarchy plugin list --json 2>/dev/null | python3 -c \
    "import json,sys; sys.exit(0 if any(p.get('id')==sys.argv[1] for p in json.load(sys.stdin)) else 1)" "$1"
}
plugin_discover() {  # wie 'omarchy plugin add': neu einlesen, bis zu 2 s auf das Plugin warten
  plugin_known "$1" && return 0
  [ "$DRY" = 1 ] && { say "  [dry-run] omarchy-shell shell rescanPlugins"; return 0; }
  omarchy-shell shell rescanPlugins >/dev/null 2>&1 || true
  local i
  for i in $(seq 40); do plugin_known "$1" && return 0; sleep 0.05; done
  return 1
}
plugin_enabled() {  # plugin_enabled <id> -> Exit 0, wenn aktiviert
  omarchy plugin list --json 2>/dev/null | python3 -c \
    "import json,sys; sys.exit(0 if any(p.get('id')==sys.argv[1] and p.get('enabled') for p in json.load(sys.stdin)) else 1)" "$1"
}
install_plugin_copy() {  # install_plugin_copy <id> <Quellordner> [Platzierung]
  local id="$1" src="$2" dir="$HOME/.config/omarchy/plugins/$1"
  step "Omarchy-Widget ($id)"
  if [ -d "$dir/.git" ]; then
    say "  git-Checkout vorhanden, unveraendert"
  elif [ -d "$dir" ] && diff -rq "$src" "$dir" >/dev/null; then
    say "  Kopie aktuell"
  else
    # Omarchy lehnt ein symlinktes Plugin-Verzeichnis ab -> Kopie. Die
    # Sicherung liegt ausserhalb von plugins/, sonst faende Omarchy sie
    # als zweites Plugin mit derselben ID.
    [ -d "$dir" ] && { backup "$dir"; run rm -rf -- "$dir"; }
    run mkdir -p "$dir"
    run cp -a "$src/." "$dir/"
    say "  kopiert"
    SHELL_RESTART=1
  fi
  # Eine frisch kopierte Kopie kennt die Shell erst nach rescanPlugins
  # (sonst: "plugin is not known", erster Echtlauf 2026-10-15).
  if plugin_enabled "$id"; then
    say "  aktiviert"
  elif plugin_discover "$id" && run omarchy plugin enable "$id" ${3:+"$3"}; then
    SHELL_RESTART=1
  else
    warn "$id liess sich nicht aktivieren - nach 'omarchy restart shell': omarchy plugin enable $id"
  fi
}
untilde() { printf '%s' "${1/#\~/$HOME}"; }

if [ "$GUIDED" = 1 ] && [ "$YES" = 0 ]; then
  cat <<'TXT'

Polaris - gefuehrte Einrichtung
================================
Polaris archiviert Chats aus ChatGPT und Claude in deine Projektordner, laesst
einen Curator daraus Wissen, Entscheidungen und offene Punkte pflegen und zeigt
den Zustand im Health-Check-Widget der Omarchy-Leiste. Optional dazu:
omarchy-backup (Snapshots der Konfiguration) und ein Maschinengedaechtnis
(gemeinsame Regeln und Notizen fuer alle AI-Agenten auf diesem Rechner).

Es wird nichts aus dem Netz geladen und nichts ohne Rueckfrage ersetzt.
Ersetzte Dateien landen unter ~/.local/share/polaris/install-backups/.
Leere Eingabe uebernimmt den Vorschlag in [Klammern].

TXT
  # 1. Projektordner
  default_root="$HOME/Projekte"
  for c in "$HOME/Projekte" "$HOME/Projects" "$HOME/Dokumente/Projekte"; do
    [ -d "$c" ] && { default_root="$c"; break; }
  done
  say "1) Projektordner: Darunter liegt je Projekt ein Ordner (z. B. Kunde-A/)."
  say "   Liegt er auf einem Cloud-Laufwerk, muss das jetzt eingehaengt sein."
  ask "   Ordner" "$(tilde "$default_root")"; PROJECTS="$(untilde "$REPLY")"
  if [ ! -d "$PROJECTS" ]; then
    if ask_yn "   $PROJECTS gibt es nicht. Anlegen?" j; then
      [ "$DRY" = 1 ] || mkdir -p -- "$PROJECTS"
    else
      PROJECTS=""; say "   uebersprungen - spaeter: polaris roots add <Ordner>"
    fi
  fi
  # 2. Modell
  if command -v codex >/dev/null; then def_rt=codex; elif command -v claude >/dev/null; then def_rt=claude; else def_rt=codex; fi
  say ""
  say "2) Modell fuer den Curator: codex (OpenAI), claude (Anthropic) oder command (andere Agenten-CLI)."
  say "   Gefunden: $(for c in codex claude; do command -v $c >/dev/null && printf '%s ' $c; done)"
  while :; do
    ask "   Runtime" "$def_rt"; RUNTIME="$REPLY"
    case "$RUNTIME" in codex|claude|command) break ;; *) say "   bitte codex, claude oder command" ;; esac
  done
  if [ ! -f "$POLARIS_CFG/curator.yaml" ]; then
    say "   Welche Browser-Chats werden erfasst? Unabhaengig vom Curator-Modell."
    while :; do
      ask "   Chatquellen (both/chatgpt/claude/none)" "both"; CHAT_SOURCES="$REPLY"
      case "$CHAT_SOURCES" in both|chatgpt|claude|none) break ;; *) say "   bitte both, chatgpt, claude oder none" ;; esac
    done
  fi
  # 3. Hintergrunddienste und Widgets
  say ""
  ask_yn "3) Hintergrunddienste einrichten (Bridge alle 10 min, Curator nachts)?" j && UNITS=1 || UNITS=0
  if command -v omarchy >/dev/null; then
    ask_yn "   Widgets in der Omarchy-Leiste anzeigen (Health Check, Backup, Agenten-Starter; die beiden letzten von GitHub)?" j && WIDGET=1 || WIDGET=0
    ask_yn "   Dock (omadock) installieren? Wird von GitHub geholt." j && DOCK=1 || DOCK=0
  else
    WIDGET=0 DOCK=0
  fi
  # 4. omarchy-backup
  if command -v git >/dev/null; then
    say ""
    say "4) omarchy-backup sichert Konfiguration, Themes, Plugins und Paketlisten als Snapshots (von GitHub)."
    if ask_yn "   Einrichten?" j; then
      OBACKUP=1
      say "   Wohin sollen die Snapshots? (z. B. ein Ordner auf einem Cloud-Laufwerk; leer = spaeter)"
      ask "   Ziel" ""; OB_TARGET="$(untilde "$REPLY")"
    else
      OBACKUP=0
    fi
  fi
  # 5. Maschinengedaechtnis
  if [ -d "$REPO/memory/template" ]; then
    say ""
    say "5) Maschinengedaechtnis (~/.config/ai-agents): Regeln und Notizen, die alle"
    say "   AI-Agenten (Claude Code, Codex, Gemini ...) auf diesem Rechner lesen."
    if ask_yn "   Einrichten?" j; then
      MEMORY=1
      def_mirror=""
      [ -n "$PROJECTS" ] && [ -d "$PROJECTS/Polaris" ] && def_mirror="$(tilde "$PROJECTS/Polaris/Maschinengedaechtnis")"
      say "   Optional spiegeln (z. B. in einen Projektordner auf dem Cloud-Laufwerk; leer = nicht)."
      say "   Gibt es dort schon ein Gedaechtnis und hier noch keins, wird es zurueckgeholt."
      ask "   Spiegel-Ordner" "$def_mirror"; MIRROR="$(untilde "$REPLY")"
    else
      MEMORY=0
    fi
  fi
  say ""
  say "Zusammenfassung"
  say "  Projektordner:       $(tilde "${PROJECTS:-(spaeter)}")"
  say "  Curator-Modell:      $RUNTIME (nur fuer eine neue curator.yaml)"
  say "  Browser-Chatquellen: ${CHAT_SOURCES:-aus Vorlage} (nur fuer eine neue curator.yaml)"
  say "  Sprache:             $UI_LANG (nur fuer eine neue curator.yaml)"
  say "  Hintergrunddienste:  $([ "$UNITS" = 1 ] && echo ja || echo nein)"
  say "  Widgets:             $([ "$WIDGET" = 1 ] && echo ja || echo nein)"
  say "  Dock (omadock):      $([ "$DOCK" = 1 ] && echo ja || echo nein)"
  command -v git >/dev/null && \
  say "  omarchy-backup:      $([ "$OBACKUP" = 1 ] && echo "ja, Ziel: $(tilde "${OB_TARGET:-(spaeter)}")" || echo nein)"
  [ -d "$REPO/memory/template" ] && \
  say "  Maschinengedaechtnis: $([ "$MEMORY" = 1 ] && echo "ja, Spiegel: $(tilde "${MIRROR:-(keiner)}")" || echo nein)"
  say ""
  ask_yn "Jetzt einrichten?" j || { say "Abgebrochen, nichts eingerichtet."; exit 0; }
  say ""
fi

if [ -n "$CHAT_SOURCES" ] && [ -f "$POLARIS_CFG/curator.yaml" ]; then
  echo "--chat-sources gilt nur bei neuer curator.yaml; vorhandene Datei gezielt bearbeiten" >&2
  exit 2
fi

# --- Protokoll und Spur fuer Agenten (seit 2026-10-08) -----------------------
# Bricht die Installation ab, soll ein lokaler AI-Agent selbststaendig
# weitermachen koennen: Protokoll unter ~/.local/state/polaris/, Leitfaden
# docs/AGENTEN-LEITFADEN.md, Stand in ~/.config/ai-agents/handoff/polaris.md.
GUIDE="$REPO/docs/AGENTEN-LEITFADEN.md"
MEM="$HOME/.config/ai-agents"
LOG=""
if [ "$DRY" = 0 ]; then
  mkdir -p "$HOME/.local/state/polaris"
  LOG="$HOME/.local/state/polaris/install-$(date +%Y%m%d-%H%M%S).log"
  exec > >(tee -a "$LOG") 2>&1
  say "INSTALL: $(date -Iseconds) Protokoll $LOG"
  say "INSTALL: Optionen ${ORIG_ARGS[*]:-(gefuehrt)}"
  if [ "$NO_NEW" = 1 ]; then say "INSTALL: richtet nichts Neues ein ($NO_NEW_REASON)"; fi
  say "INSTALL: Auswahl projects=${PROJECTS:-} runtime=${RUNTIME:-auto} chat_sources=${CHAT_SOURCES:-template} units=$UNITS widget=$WIDGET dock=$DOCK backup=$OBACKUP backup_target=${OB_TARGET:-} memory=$MEMORY memory_mirror=${MIRROR:-}"
fi

memory_note() {  # memory_note <Status>: Polaris-Eintrag im Maschinengedaechtnis
  [ "$DRY" = 0 ] && [ "$MEMORY" = 1 ] && [ -f "$MEM/AI_HANDOFF.md" ] || return 0
  local note="$MEM/handoff/polaris.md" today; today="$(date +%Y-%m-%d)"
  # Nur eine vom Installer angelegte Datei wird fortgeschrieben; eigene
  # Aufzeichnungen des Nutzers oder seiner Agenten bleiben unangetastet.
  if [ -f "$note" ] && ! grep -q 'polaris-install: auto' "$note"; then return 0; fi
  mkdir -p "$MEM/handoff"
  {
    printf '# Polaris\n\n<!-- polaris-install: auto - von install.sh geschrieben, solange niemand die Datei uebernimmt -->\n'
    printf 'Aktueller Stand der Polaris-Installation. Leitfaden fuer Agenten: `%s`.\n\n' "$(tilde "$GUIDE")"
    printf '## Stand\n<!-- mem: id=polaris-install-state type=current_state status=current date=%s source=polaris-install ref=file:docs/AGENTEN-LEITFADEN.md -->\n' "$today"
    printf -- '- Installation: %s (%s)\n' "$1" "$(date '+%Y-%m-%d %H:%M')"
    printf -- '- Programmordner: `%s`; Protokoll: `%s`\n' "$(tilde "$REPO")" "$(tilde "${LOG:-}")"
    printf -- '- Optionen: `%s`\n' "${ORIG_ARGS[*]:-(gefuehrt)}"
    printf -- '- Bei Abbruch oder Fehlern: Leitfaden lesen, Ursache beheben, `install.sh --dry-run`, dann `install.sh --yes` mit denselben Optionen.\n'
    printf '\n## Offene Punkte\n<!-- mem: id=polaris-install-open type=open_item status=current date=%s source=polaris-install ref=file:docs/AGENTEN-LEITFADEN.md -->\n' "$today"
    [ -n "${2:-}" ] && printf -- '- Abbruchgrund laut Protokoll: %s\n' "$2"
    if [ ${#WARNINGS[@]} -gt 0 ]; then printf -- '- %s\n' "${WARNINGS[@]}"
    elif [ -z "${2:-}" ]; then printf -- '- keine\n'; fi
  } > "$note.tmp" && mv -- "$note.tmp" "$note"
  if ! grep -q 'handoff/polaris.md' "$MEM/AI_HANDOFF.md"; then
    printf '| `handoff/polaris.md` | Polaris (Bridge, Curator, Health Check, Backup, Spiegel) | siehe Datei |\n' >> "$MEM/AI_HANDOFF.md"
  fi
}

finish() {
  local rc=$?
  [ "$DRY" = 1 ] && return 0
  if [ "$rc" -eq 0 ]; then
    memory_note "abgeschlossen"
    say "INSTALL: abgeschlossen (Exit 0)"
  else
    local reason=""
    reason="$FAIL_REASON"
    if [ -z "$reason" ] && [ -n "$LOG" ]; then  # unerwarteter Fehler: letzte Fehlerzeile
      sleep 0.3  # tee schreibt asynchron
      reason="$(grep -E '^(FEHLER|ERROR|Error|error)|: line [0-9]+:|[Ff]ailed' "$LOG" 2>/dev/null | grep -v '^INSTALL:' | tail -1 | cut -c1-200)"
    fi
    memory_note "ABGEBROCHEN im Schritt '$STEP' (Exit $rc)" "${reason:-siehe Protokoll}"
    say ""
    say "INSTALL: ABGEBROCHEN im Schritt '$STEP' (Exit $rc)"
    say "  Ein lokaler AI-Agent kann hier weitermachen. Er findet:"
    say "    Leitfaden:  $GUIDE"
    say "    Protokoll:  $LOG"
    [ "$MEMORY" = 1 ] && say "    Stand:      $MEM/handoff/polaris.md"
  fi
}
trap finish EXIT

# Das Gedaechtnis entsteht als Erstes, damit ein Agent auch nach einem
# fruehen Abbruch (z. B. fehlendes PyYAML) Regeln und Wegweiser vorfindet.
# Vorhandene Gedaechtnisse bleiben unveraendert.
if [ "$MEMORY" = 1 ] && [ -d "$REPO/memory/template" ] && [ ! -e "$MEM" ]; then
  step "Maschinengedaechtnis anlegen ($MEM)"
  mirror_src="$MIRROR"
  if [ -z "$mirror_src" ] && [ -f "$POLARIS_CFG/config.yaml" ]; then
    mirror_src="$(sed -n "s/^memory_mirror: *['\"]\{0,1\}\([^'\"]*\)['\"]\{0,1\} *$/\1/p" "$POLARIS_CFG/config.yaml" | head -1)"
    mirror_src="$(untilde "$mirror_src")"
  fi
  if [ -n "$mirror_src" ] && [ -f "$mirror_src/AGENTS.md" ]; then
    if [ "$DRY" = 1 ]; then say "  [dry-run] aus dem Spiegel zurueckholen: $(tilde "$mirror_src")"
    else
      mkdir -p "$MEM"
      if command -v rsync >/dev/null; then rsync -rlt --exclude=.alt/ -- "$mirror_src/" "$MEM/"
      else cp -a -- "$mirror_src/." "$MEM/" && rm -rf -- "$MEM/.alt"; fi
      say "  aus dem Spiegel zurueckgeholt: $(tilde "$mirror_src")"
    fi
  else
    run mkdir -p "$MEM"/handoff "$MEM"/knowledge "$MEM"/history "$MEM"/system-history "$MEM"/tools
    run cp -n "$REPO"/memory/template/AGENTS.md "$REPO"/memory/template/AI_HANDOFF.md \
      "$REPO"/memory/template/entrypoints.conf "$MEM/"
    # Platzhalter, bis polaris-radar das erste Mal laeuft (AGENTS.md verweist darauf)
    run cp -n "$REPO"/memory/template/handoff/omarchy-radar.md "$MEM/handoff/"
    say "  aus der Vorlage angelegt - AGENTS.md und AI_HANDOFF.md an den Rechner anpassen"
    AGENTS_FROM_TEMPLATE=1
  fi
  # Werkzeug und Agenten-Einstiege sofort: sonst lesen Claude Code, Codex usw.
  # nach einem fruehen Abbruch die Regeln gar nicht (memlint braucht nur python3).
  if [ "$DRY" = 0 ]; then
    mkdir -p "$MEM/tools"
    [ -f "$MEM/tools/memlint.py" ] || install -m 755 "$REPO/memory/tools/memlint.py" "$MEM/tools/memlint.py"
    if command -v python3 >/dev/null; then
      python3 "$MEM/tools/memlint.py" --link --no-system 2>&1 | sed 's/^/  /' || true
    fi
  fi
  memory_note "laeuft (gestartet)"
fi

step "Voraussetzungen"
command -v python3 >/dev/null || die "python3 fehlt"
python3 -c 'import yaml' 2>/dev/null || {
  die "PyYAML fehlt (Arch: sudo pacman -S python-yaml)"; }
say "  python3 + PyYAML vorhanden"
command -v rsync >/dev/null || warn "rsync fehlt - Spiegel des Maschinengedaechtnisses geht erst danach (sudo pacman -S rsync)"

step "Befehle in $BIN_DIR"
[ -d "$BIN_DIR" ] || run mkdir -p "$BIN_DIR"
for pair in "polaris:bridge/bin/polaris" "polaris-curator:curator/bin/polaris-curator" \
            "polaris-memory-mirror:memory/tools/memory-mirror" "polaris-awake:bridge/bin/polaris-awake" \
            "polaris-radar:memory/tools/polaris-radar"; do
  name="${pair%%:*}" target="$REPO/${pair#*:}" link="$BIN_DIR/${pair%%:*}"
  if [ "$(readlink -f "$link" 2>/dev/null)" = "$target" ]; then
    say "  $name: ok"
    continue
  fi
  [ -e "$link" ] || [ -L "$link" ] && { backup "$link"; run rm -f -- "$link"; }
  run ln -s "$target" "$link"
  say "  $name -> $target"
done
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "$BIN_DIR steht nicht im PATH" ;; esac
POLARIS=("$REPO/bridge/bin/polaris") CURATOR=("$REPO/curator/bin/polaris-curator")

step "Bridge-Konfiguration ($POLARIS_CFG)"
if [ "$DRY" = 1 ]; then run "${POLARIS[@]}" status
else "${POLARIS[@]}" status >/dev/null; fi  # legt Konfiguration und Arbeitsordner an
if [ -n "$PROJECTS" ]; then
  if [ "$DRY" = 1 ]; then run "${POLARIS[@]}" roots add "$PROJECTS"
  else
    out="$("${POLARIS[@]}" roots add "$PROJECTS" 2>&1)" || true
    case "$out" in *"bereits eingetragen"*) say "  $PROJECTS: bereits eingetragen" ;; *) say "${out//$'\n'/$'\n'  }" ;; esac
  fi
fi
if [ -n "$MIRROR" ]; then
  if [ "$DRY" = 1 ]; then say "  [dry-run] memory_mirror: $(tilde "$MIRROR")"
  else
    PYTHONPATH="$REPO/bridge" python3 - "$(tilde "$MIRROR")" <<'PY'
import sys
from polaris import config
cfg = config.load_config()
cfg.extra["memory_mirror"] = sys.argv[1]
config.save_config(cfg)
PY
    say "  memory_mirror: $(tilde "$MIRROR")"
  fi
fi
if [ "$DRY" = 0 ] && ! "${POLARIS[@]}" roots >/dev/null 2>&1; then
  warn "kein Projektordner eingetragen: polaris roots add <Ordner, in dem die Projektordner liegen>"
fi

step "Curator-Modell ($POLARIS_CFG/curator.yaml)"
if [ -f "$POLARIS_CFG/curator.yaml" ]; then
  say "  vorhanden, unveraendert"
else
  if [ -z "$RUNTIME" ]; then
    if command -v codex >/dev/null; then RUNTIME=codex
    elif command -v claude >/dev/null; then RUNTIME=claude
    else RUNTIME=codex; warn "weder codex noch claude installiert - Curator laeuft erst nach Einrichtung einer CLI"; fi
  fi
  tmpl="$REPO/curator/curator.example-$RUNTIME.yaml"
  run mkdir -p "$POLARIS_CFG"
  run cp "$tmpl" "$POLARIS_CFG/curator.yaml"
  if [ -n "$CHAT_SOURCES" ]; then
    case "$CHAT_SOURCES" in
      both) source_list='[chatgpt, claude]' ;;
      chatgpt) source_list='[chatgpt]' ;;
      claude) source_list='[claude]' ;;
      none) source_list='[]' ;;
    esac
    run sed -i "s/^  chat_sources: .*/  chat_sources: $source_list/" "$POLARIS_CFG/curator.yaml"
  fi
  run sed -i "s/^language: .*/language: $UI_LANG/" "$POLARIS_CFG/curator.yaml"
  say "  angelegt aus $(basename "$tmpl")"
fi

CAPTURE_ENABLED=1
if [ -f "$POLARIS_CFG/curator.yaml" ]; then
  CAPTURE_ENABLED="$(python3 - "$POLARIS_CFG/curator.yaml" <<'PY'
import sys
import yaml
with open(sys.argv[1], encoding="utf-8") as f:
    settings = yaml.safe_load(f) or {}
sources = (settings.get("monitoring") or {}).get("chat_sources", ["chatgpt", "claude"])
# Wie config._parse_chat_sources: keine Liste -> beide; Unbekanntes zaehlt nicht.
if not isinstance(sources, list):
    sources = ["chatgpt", "claude"]
print(1 if any(str(s).strip().lower() in ("chatgpt", "claude") for s in sources) else 0)
PY
)"
elif [ "$CHAT_SOURCES" = none ] || { [ -z "$CHAT_SOURCES" ] && [ "$RUNTIME" = command ]; }; then
  CAPTURE_ENABLED=0  # dry-run: die noch nicht angelegte Vorlage haette keine Chatquellen
fi

if [ "$UNITS" = 1 ]; then
  step "systemd-Units ($UNIT_DIR)"
  run mkdir -p "$UNIT_DIR"
  changed=0
  unit_sources=("$REPO"/curator/systemd/polaris-curator.{service,timer} "$REPO"/systemd/polaris-memory-mirror.{service,timer} "$REPO"/systemd/polaris-radar.{service,timer})
  [ "$CAPTURE_ENABLED" = 0 ] || unit_sources+=("$REPO"/systemd/polaris-bridge.{path,service,timer})
  for src in "${unit_sources[@]}"; do
    dst="$UNIT_DIR/$(basename "$src")"
    if cmp -s "$src" "$dst"; then say "  $(basename "$src"): ok"; continue; fi
    [ -e "$dst" ] && backup "$dst"
    run install -m 644 "$src" "$dst"
    say "  $(basename "$src"): installiert"
    changed=1
  done
  # Laufwerks-Dienst als Drop-in statt fest in den Units (seit 2026-10-23)
  dropin_name="polaris-storage.conf"
  if [ -z "$STORAGE_UNIT" ]; then
    STORAGE_UNIT="$(sed -n 's/^Wants=//p' "$UNIT_DIR/polaris-curator.service.d/$dropin_name" 2>/dev/null | head -1 || true)"
    [ -z "$STORAGE_UNIT" ] && systemctl --user cat rclone-projekte.service >/dev/null 2>&1 && STORAGE_UNIT=rclone-projekte.service
  fi
  services=(polaris-curator polaris-memory-mirror)
  [ "$CAPTURE_ENABLED" = 0 ] || services+=(polaris-bridge)
  for u in "${services[@]}"; do
    d="$UNIT_DIR/$u.service.d" f="$UNIT_DIR/$u.service.d/$dropin_name"
    if [ -z "$STORAGE_UNIT" ] || [ "$STORAGE_UNIT" = none ]; then
      [ -e "$f" ] && { backup "$f"; run rm -f -- "$f"; changed=1; say "  $u: ohne Laufwerks-Dienst"; }
      continue
    fi
    want="$(printf '[Unit]\n# von install.sh (--storage-unit): erst nach dem Laufwerk starten\nWants=%s\nAfter=%s\n' "$STORAGE_UNIT" "$STORAGE_UNIT")"
    [ "$(cat "$f" 2>/dev/null)" = "$want" ] && continue
    [ -e "$f" ] && backup "$f"
    run mkdir -p "$d"
    if [ "$DRY" = 1 ]; then say "  [dry-run] $f: Wants/After=$STORAGE_UNIT"; else printf '%s\n' "$want" >"$f"; fi
    say "  $u: nach $STORAGE_UNIT"
    changed=1
  done
  [ "$changed" = 1 ] && run systemctl --user daemon-reload
  if [ "$CAPTURE_ENABLED" = 0 ]; then
    for u in polaris-bridge.path polaris-bridge.timer; do
      if [ "$(systemctl --user is-enabled "$u" 2>/dev/null)" = enabled ]; then
        run systemctl --user disable --now "$u"
        say "  $u: deaktiviert (keine Browser-Chatquelle)"
      fi
    done
  fi
  timers=(polaris-curator.timer polaris-memory-mirror.timer polaris-radar.timer)
  [ "$CAPTURE_ENABLED" = 0 ] || timers+=(polaris-bridge.path polaris-bridge.timer)
  for u in "${timers[@]}"; do
    if [ "$(systemctl --user is-enabled "$u" 2>/dev/null)" = enabled ] && systemctl --user is-active -q "$u"; then
      say "  $u: aktiv"
    else
      run systemctl --user enable --now "$u"
      say "  $u: aktiviert"
    fi
  done
fi

if [ "$CAPTURE_ENABLED" = 1 ]; then
  step "Firefox Native Host"
  if [ -d "$HOME/.mozilla" ] || [ -d "$HOME/.config/mozilla/firefox" ]; then
    if [ "$DRY" = 1 ]; then run "$REPO/bridge/install-native-host.sh"
    else "$REPO/bridge/install-native-host.sh" | sed 's/^/  /'; fi
  else
    warn "Firefox-Profil fehlt: Firefox einmal starten, dann ./install.sh erneut ausfuehren (die Erweiterung gibt es nur fuer Firefox)"
  fi
fi

if [ "$WIDGET" = 1 ]; then
  if ! command -v omarchy >/dev/null; then
    warn "omarchy-Befehl fehlt - Widgets uebersprungen"
  else
    install_plugin_copy "$PLUGIN_ID" "$REPO/omarchy-plugin/$PLUGIN_ID" center
    command -v jq >/dev/null || warn "jq fehlt - das Widget braucht es (sudo pacman -S jq)"
    # Agenten-Starter (Claude, Codex, Antigravity): eigenes oeffentliches Repo
    install_plugin_git mst.agent-launchers "$AL_URL"
  fi
fi

# Dock: fremdes, oeffentliches Plugin -> per 'omarchy plugin add' aus git,
# damit 'omarchy plugin update' es weiter aktualisieren kann.
DOCK_ID="omadock" DOCK_URL="https://github.com/thepathless/omadock.git"
if [ "$DOCK" = 1 ] && command -v omarchy >/dev/null; then
  install_plugin_git "$DOCK_ID" "$DOCK_URL"
fi

# Omarchy-Radar nach jedem 'omarchy update' (Hook, kein Timer): neue Omarchy-
# Funktionen, Plugin-Updates und vorgemerkte Punkte fuer die Agenten.
HOOK_DIR="$HOME/.config/omarchy/hooks/post-update.d"
if [ "$MEMORY" = 1 ] && command -v omarchy >/dev/null; then
  step "Omarchy-Radar (Hook nach omarchy update)"
  hook_src="$REPO/memory/tools/polaris-radar.hook" hook_dst="$HOOK_DIR/polaris-radar.hook"
  if cmp -s "$hook_src" "$hook_dst" 2>/dev/null; then
    say "  ok"
  else
    [ -d "$HOOK_DIR" ] || run mkdir -p "$HOOK_DIR"
    [ -e "$hook_dst" ] && backup "$hook_dst"
    run install -m 755 "$hook_src" "$hook_dst"
    say "  $hook_dst eingerichtet"
  fi
fi

# omarchy-backup: eigenes oeffentliches Repo, per git clone nach
# ~/.local/share/polaris/extras/ (seit 2026-11-04; ein altes Paket bringt es
# noch als extras/ mit). Eine vorhandene eigene Installation bleibt unangetastet.
OB_SRC="$REPO/extras/omarchy-backup"
[ -d "$OB_SRC" ] || OB_SRC="$EXTRAS_DIR/omarchy-backup"
if [ "$OBACKUP" = 1 ]; then
  step "omarchy-backup (CLI)"
  current="$(readlink -f "$BIN_DIR/omarchy-backup" 2>/dev/null || true)"
  if [ "$current" = "$OB_SRC/bin/omarchy-backup" ]; then
    say "  ok ($OB_SRC)"
  elif [ -n "$current" ] && [ -e "$current" ]; then
    say "  eigene Installation vorhanden ($current), unveraendert"
  elif [ ! -d "$OB_SRC" ] && ! { run mkdir -p "$EXTRAS_DIR" && run git clone --quiet "$OB_URL" "$OB_SRC"; }; then
    warn "omarchy-backup nicht geholt (Netz?): git clone $OB_URL $OB_SRC"
  else
    if [ "$DRY" = 1 ]; then run "$OB_SRC/install.sh"
    else "$OB_SRC/install.sh" | sed 's/^/  /'; fi
    [ -n "$OB_TARGET" ] || warn "omarchy-backup: Ziel eintragen (omarchy-backup config set OB_CFG_REMOTE_PATH <Ordner>), dann 'omarchy-backup timers install'"
  fi
  if [ -n "$OB_TARGET" ]; then
    ob="$OB_SRC/bin/omarchy-backup"
    [ "$current" != "$OB_SRC/bin/omarchy-backup" ] && [ -n "$current" ] && [ -e "$current" ] && ob="$current"
    if [ ! -d "$OB_TARGET" ]; then
      warn "omarchy-backup: Ziel $OB_TARGET gibt es nicht (Laufwerk eingehaengt?) - nicht eingetragen"
    else
      run "$ob" config set OB_CFG_REMOTE_PATH "$OB_TARGET"
      [ "$DRY" = 1 ] || "$ob" timers install 2>&1 | sed 's/^/  /'
      say "  Ziel: $OB_TARGET, taegliche Snapshots eingeschaltet"
      warn "omarchy-backup: wenn alles laeuft, eine Baseline setzen: omarchy-backup snapshot --baseline <Name>"
    fi
  fi
  OB_PLUGIN_ID="mst.omarchy-backup"
  if [ "$WIDGET" = 1 ] && command -v omarchy >/dev/null; then
    install_plugin_git "$OB_PLUGIN_ID" "$OB_PLUGIN_URL"
  fi
fi

if [ -d "$HOME/.config/omarchy-backup/paths.d" ]; then
  step "omarchy-backup (Programmordner im Backup)"
  if grep -rqsF -- "${REPO/#$HOME/\~}" "$HOME/.config/omarchy-backup/paths.d" \
      || grep -rqsF -- "$REPO" "$HOME/.config/omarchy-backup/paths.d"; then
    say "  Programmordner ist bereits erfasst"
  else
    if [ -d "$REPO/.git" ]; then rule="repo ${REPO/#$HOME/\~}"; else rule="include ${REPO/#$HOME/\~}"; fi
    if [ "$DRY" = 1 ]; then say "  [dry-run] $rule -> paths.d/polaris-app.conf"
    else
      printf '# Von Polaris install.sh angelegt: Programmordner fuer den Restore\n%s\n' "$rule" \
        > "$HOME/.config/omarchy-backup/paths.d/polaris-app.conf"
      say "  $rule eingetragen (paths.d/polaris-app.conf)"
    fi
  fi
fi

# Neu seit dem letzten Update (seit 2026-10-31): Was der CHANGELOG seit dem
# zuletzt gesehenen Stand neu hat, kommt nach ~/.local/state/polaris/neu-seit-update.md
# und als offener Punkt nach handoff/polaris.md. Der Agent stellt es dem
# Nutzer vor; entschieden wird gemeinsam. Funktioniert ohne git (Paket) und
# unabhaengig davon, welches update.sh den Lauf gestartet hat.
NEWS="$HOME/.local/state/polaris/neu-seit-update.md" SEEN="$HOME/.local/state/polaris/changelog-gesehen.md"
if [ -f "$REPO/CHANGELOG.md" ] && [ "$DRY" = 0 ]; then
  mkdir -p "$(dirname "$NEWS")"
  if [ -f "$SEEN" ]; then
    news="$(diff --changed-group-format='%>' --unchanged-group-format='' "$SEEN" "$REPO/CHANGELOG.md" || true)"
  elif [ "$(ls -1 "$HOME"/.local/state/polaris/install-*.log 2>/dev/null | wc -l)" -le 1 ]; then
    news=""  # Neuinstallation (nur das Protokoll dieses Laufs): nichts zu vergleichen
  else
    # Erstes Update mit dieser Funktion: der oberste Abschnitt (meist "Unveroeffentlicht").
    news="$(awk '/^## /{n++} n==1' "$REPO/CHANGELOG.md")"
  fi
  if [ -n "$(printf '%s' "$news" | tr -d '[:space:]')" ]; then
    {
      [ -s "$NEWS" ] || printf '# Neu seit dem letzten Polaris-Update

Für Agenten: Jeden Punkt dem Nutzer kurz vorstellen (was neu ist, was es ihm bringt, ob etwas einzustellen wäre) und gemeinsam entscheiden. Nichts ungefragt aktivieren oder umstellen. Danach diese Datei löschen.
'
      printf '
## Update vom %s

%s
' "$(date '+%Y-%m-%d %H:%M')" "$news"
    } >> "$NEWS"
  fi
  cp -- "$REPO/CHANGELOG.md" "$SEEN"
  if [ -s "$NEWS" ]; then
    step "Neu seit dem letzten Update"
    sed -n '/^## Update vom/,$p' "$NEWS" | head -40 | sed 's/^/  /'
    warn "Neuerungen seit dem letzten Update in $(tilde "$NEWS"): mit dem Nutzer durchgehen und gemeinsam entscheiden, was eingestellt oder übernommen wird; danach die Datei löschen."
  fi
fi

# Maschinengedaechtnis: nur Werkzeug und leere Vorlage (memory/), nie Inhalte.
# Angelegt bzw. aus dem Spiegel geholt wird es schon zu Beginn (siehe oben).
if [ "$MEMORY" = 1 ] && [ -d "$REPO/memory/template" ]; then
  step "Maschinengedaechtnis ($MEM)"
  mirror_cfg="$MIRROR"
  [ -n "$mirror_cfg" ] || mirror_cfg="$(PYTHONPATH="$REPO/bridge" python3 -c \
    'from polaris import config; import os; print(os.path.expanduser(str(config.load_config().extra.get("memory_mirror") or "")))' 2>/dev/null || true)"
  [ -e "$MEM" ] && say "  vorhanden"
  if cmp -s "$REPO/memory/tools/memlint.py" "$MEM/tools/memlint.py"; then
    say "  memlint.py: ok"
  else
    [ -e "$MEM/tools/memlint.py" ] && backup "$MEM/tools/memlint.py"
    run mkdir -p "$MEM/tools"
    run install -m 755 "$REPO/memory/tools/memlint.py" "$MEM/tools/memlint.py"
    say "  memlint.py: installiert"
  fi
  # Gemeinsame Skills (seit 2026-10-16); memlint --link verlinkt sie unten
  # in die Skill-Ordner der eingerichteten Agenten.
  for sk in "$REPO"/memory/template/skills/*/; do
    [ -f "$sk/SKILL.md" ] || continue
    n="$(basename "$sk")"
    if cmp -s "$sk/SKILL.md" "$MEM/skills/$n/SKILL.md"; then
      say "  Skill $n: ok"
    else
      [ -e "$MEM/skills/$n/SKILL.md" ] && backup "$MEM/skills/$n/SKILL.md"
      run mkdir -p "$MEM/skills/$n"
      run install -m 644 "$sk/SKILL.md" "$MEM/skills/$n/SKILL.md"
      say "  Skill $n: installiert"
    fi
  done
  if [ -d "$HOME/.config/omarchy-backup" ]; then
    if grep -rqsE -- '^include +(~|\$HOME|'"$HOME"')/\.config/ai-agents/?$' \
        "$HOME/.config/omarchy-backup/paths.conf" "$HOME/.config/omarchy-backup/paths.d"; then
      say "  im Backup erfasst"
    elif [ "$DRY" = 1 ]; then say "  [dry-run] include ~/.config/ai-agents -> paths.d/ai-agents.conf"
    else
      mkdir -p "$HOME/.config/omarchy-backup/paths.d"
      printf '# Von Polaris install.sh angelegt: Maschinengedaechtnis\ninclude ~/.config/ai-agents\n' \
        > "$HOME/.config/omarchy-backup/paths.d/ai-agents.conf"
      say "  include ~/.config/ai-agents eingetragen (paths.d/ai-agents.conf)"
    fi
  fi
  # Neue allgemeine Agentenregeln (seit 2026-10-31): Ein vorhandenes AGENTS.md
  # wird nie ueberschrieben. Ist die Vorlage neuer als der letzte quittierte
  # Abgleich, steht das als offener Punkt in handoff/polaris.md, bis ein Agent
  # abgeglichen und quittiert hat. Auf dem Rechner, aus dessen AGENTS.md die
  # Vorlage erzeugt wird (agents-template.py --check ok), entfaellt das.
  tmpl="$REPO/memory/template/AGENTS.md" ack="$HOME/.local/state/polaris/agents-template.ack"
  if [ -f "$tmpl" ] && [ -f "$MEM/AGENTS.md" ] && [ "$DRY" = 0 ]; then
    tmpl_sum="$(sha256sum "$tmpl" | cut -d' ' -f1)"
    if [ "${AGENTS_FROM_TEMPLATE:-0}" = 1 ]; then
      mkdir -p "$(dirname "$ack")" && printf '%s\n' "$tmpl_sum" > "$ack"
    elif [ "$(cat "$ack" 2>/dev/null)" = "$tmpl_sum" ]; then
      say "  Agentenregeln: abgeglichen"
    elif [ -f "$REPO/scripts/agents-template.py" ] && python3 "$REPO/scripts/agents-template.py" --check >/dev/null 2>&1; then
      say "  Agentenregeln: Vorlage stammt aus diesem AGENTS.md"
    else
      warn "Allgemeine Agentenregeln haben sich geändert: $(tilde "$tmpl") mit ~/.config/ai-agents/AGENTS.md vergleichen, dem Nutzer die neuen oder geänderten Regeln mit ihrem Nutzen vorstellen und gemeinsam entscheiden, was übernommen wird (nichts ungefragt, eigene Regeln bleiben). Danach quittieren: sha256sum $(tilde "$tmpl") | cut -d' ' -f1 > $(tilde "$ack")"
    fi
  fi
  # Platzhalter auch fuer bestehende Gedaechtnisse, deren AGENTS.md schon auf
  # den Radar verweist (sonst memlint-Fehler bis zum ersten Radar-Lauf)
  # Der Radar schreibt handoff/omarchy-radar.md, traegt es aber nicht in den
  # Index ein (memlint: "nicht im Index verlinkt").
  radar_md="$MEM/handoff/omarchy-radar.md"
  if [ -e "$radar_md" ] || grep -qs 'handoff/omarchy-radar.md' "$MEM/AGENTS.md"; then
    if [ ! -e "$radar_md" ]; then
      run mkdir -p "$MEM/handoff"
      run cp -n "$REPO/memory/template/handoff/omarchy-radar.md" "$MEM/handoff/"
      say "  Platzhalter handoff/omarchy-radar.md angelegt (polaris-radar ersetzt ihn)"
    fi
    if [ -f "$MEM/AI_HANDOFF.md" ] && ! grep -qs 'handoff/omarchy-radar.md' "$MEM/AI_HANDOFF.md"; then
      if grep -v '^[[:space:]]*$' "$MEM/AI_HANDOFF.md" | tail -n 1 | grep -q '^|'; then
        row='| `handoff/omarchy-radar.md` | Omarchy-Radar: Neuigkeiten, Plugin-Updates, Sicherheit (erzeugt von `polaris-radar`) | automatisch |'
      else
        row='- `handoff/omarchy-radar.md`: Omarchy-Radar, Neuigkeiten, Plugin-Updates, Sicherheit (erzeugt von `polaris-radar`)'
      fi
      if [ "$DRY" = 1 ]; then say "  [dry-run] Indexeintrag handoff/omarchy-radar.md"
      else printf '%s\n' "$row" >> "$MEM/AI_HANDOFF.md"; say "  Index: handoff/omarchy-radar.md eingetragen"; fi
    fi
  fi
  if [ "$DRY" = 1 ]; then run python3 "$MEM/tools/memlint.py" --link
  else python3 "$MEM/tools/memlint.py" --link 2>&1 | sed 's/^/  /' || warn "memlint meldet Fehler: python3 $MEM/tools/memlint.py"; fi
  if [ -n "$mirror_cfg" ] && [ "$DRY" = 0 ]; then
    "$REPO/memory/tools/memory-mirror" 2>&1 | sed 's/^/  /' || true
  fi
fi

step "Pruefung"
if [ "$DRY" = 0 ]; then
  "${CURATOR[@]}" llm-check 2>&1 | sed 's/^/  /' || warn "Modell-CLI fehlt (siehe oben)"
  "${CURATOR[@]}" health 2>&1 | sed 's/^/  /' || true
fi

say ""
if [ ${#WARNINGS[@]} -gt 0 ]; then
  say "Offen:"
  for w in "${WARNINGS[@]}"; do say "  - $w"; done
fi
# Neue oder neu aktivierte Plugins zeigt die Leiste erst nach einem Neustart;
# nach rescanPlugins lud die Shell zudem eingebaute Bereiche doppelt
# (erster Echtlauf 2026-10-15). Deshalb auch mit --yes neu starten.
if [ "$SHELL_RESTART" = 1 ] && [ "$DRY" = 0 ]; then
  if [ "$RESTART" = 0 ]; then
    warn "Widgets/Dock erscheinen erst nach: omarchy restart shell"
  elif systemctl --user is-active -q polaris-curator-manual 2>/dev/null; then
    warn "Curator-Lauf aus dem Widget aktiv - danach von Hand: omarchy restart shell"
  elif [ "$GUIDED" = 1 ] && [ "$YES" = 0 ] && ! ask_yn "Omarchy-Leiste jetzt neu starten, damit Widgets und Dock erscheinen?" j; then
    warn "Widgets/Dock erscheinen erst nach: omarchy restart shell"
  else
    step "Omarchy-Leiste neu starten"
    omarchy restart shell >/dev/null 2>&1 && say "  neu gestartet" \
      || warn "Neustart fehlgeschlagen - von Hand: omarchy restart shell"
  fi
fi
XPI="$(ls -1 "$REPO"/dist/*-signed.xpi 2>/dev/null | sort -V | tail -n 1 || true)"  # im oeffentlichen Spiegel gibt es keine .xpi
say "Naechste Schritte (falls noch nicht erledigt):"
if [ "$CAPTURE_ENABLED" = 1 ]; then
  if [ -n "$XPI" ]; then
    say "  - Firefox-Erweiterung: firefox '$XPI'"
    say "    danach in about:addons Zugriff auf die konfigurierten Chatquellen erlauben"
  else
    say "  - Firefox-Erweiterung installieren und Zugriff auf die konfigurierten Chatquellen erlauben (docs/browser-capture.md)"
  fi
fi
say "  - polaris roots add <Ordner>          # wo die Projektordner liegen"
say "  - polaris-curator llm-check --call    # Anmeldung und Modell pruefen"
say "  Fuer AI-Agenten auf diesem Rechner: $(tilde "$GUIDE")"
[ "$OBACKUP" = 1 ] \
  || say "  Optional: omarchy-backup ($OB_URL) fuer Snapshots; der Health Check meldet es sonst als 'nicht eingerichtet'."
