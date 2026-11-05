#!/usr/bin/env bash
# Btrfs-Snapshots fuer /home einrichten (seit 2026-11-04, Teil von Polaris; vom Nutzer
# in einem Terminalfenster auszufuehren, sudo fragt nach dem Passwort).
#
#   ~/.config/ai-agents/tools/home-snapshots-einrichten.sh            # Probelauf: zeigt nur, was passiert
#   ~/.config/ai-agents/tools/home-snapshots-einrichten.sh --ausfuehren
#   ... --ausfuehren --pkexec   # root-Schritte per pkexec statt sudo (Polkit-Dialog)
#
# Alle root-Schritte laufen in EINEM Aufruf (sudo oder pkexec), in der Regel also
# eine Passwortabfrage; pkexec merkt sich die Anmeldung nicht. --pkexec auf Rechnern,
# deren Regeln pkexec statt sudo vorschreiben (Rueckmeldung von bernhard2804, 2026-11-05).
#
# Warum: Schutz gegen Zerstoerung (versehentlich oder durch eine eingeschleuste
# Anweisung an einen Agenten). Die Snapshots gehoeren root; ein Programm mit den
# Rechten des Nutzers kann sie weder lesen noch loeschen. Wiederherstellen braucht root (sudo/pkexec).
#
# Ablauf:
#  1. Pruefen: /home ist btrfs, snapper da, Steam laeuft nicht.
#  2. Laufende rclone-Laufwerke und vorhandene Polaris-Timer kurz anhalten (der
#     rclone-Cache liegt in ~/.cache). Andere Programme, die ~/.cache benutzen
#     (Browser ...), am besten vorher schliessen; am einfachsten kurz nach dem Anmelden.
#  3. ~/.cache, ~/.local/share/Steam, ~/Games zu eigenen Subvolumes machen: sie aendern
#     sich staendig und waeren sonst in jedem Snapshot (Platz). Erst neues Subvolume
#     <Ordner>.neu-<Zeit> anlegen und per reflink fuellen (ohne zusaetzlichen Platz),
#     dann atomar tauschen (mv --exchange, coreutils >= 9.5); scheitert etwas, bleibt das Original unberuehrt. Der alte Ordner
#     bleibt als <Ordner>.alt-<Zeit> liegen, bis du ihn nach einer Pruefung loeschst.
#  4. snapper-Konfiguration "home": stuendlich 12, taeglich 7, woechentlich 4 behalten.
#     Die Konfiguration "root" (Boot-Snapshots, limine-snapper-sync) bleibt unberuehrt;
#     sie nutzt keine Zeitplaene.
#  5. snapper-timeline.timer einschalten, Timer und Laufwerk wieder starten.
#
# Rueckbau (als root, sudo oder pkexec): snapper -c home delete-config; systemctl disable --now snapper-timeline.timer
# (die Subvolumes duerfen bleiben). Hinweis Datenschutz: Geloeschtes bleibt bis zu vier
# Wochen in den Snapshots erhalten.
set -euo pipefail
DO=0 ROOT=sudo
die() { echo "FEHLER: $*" >&2; exit 1; }
for arg in "$@"; do
  case "$arg" in
    --ausfuehren) DO=1 ;;
    --pkexec) ROOT=pkexec ;;   # nur diese zwei Werte, nichts frei Waehlbares
    *) die "unbekannte Option $arg (erlaubt: --ausfuehren, --pkexec)" ;;
  esac
done
run() { if [ "$DO" = 1 ]; then echo "+ $*"; "$@"; else echo "[probe] $*"; fi; }
stamp="$(date +%Y%m%d-%H%M%S)"

[ "$(stat -f -c %T /home)" = "btrfs" ] || die "/home ist kein btrfs"
[ "$(stat -c %i /home)" = "256" ] || die "/home ist kein eigenes btrfs-Subvolume (snapper braucht das)"
command -v snapper >/dev/null || die "snapper fehlt"
command -v btrfs >/dev/null || die "btrfs-progs fehlt"
command -v "$ROOT" >/dev/null || die "$ROOT fehlt"
mv --help 2>/dev/null | grep -q -- '--exchange' || die "mv --exchange fehlt (coreutils >= 9.5)"
if pgrep -x steam >/dev/null || pgrep -x steamwebhelper >/dev/null; then
  [ "$DO" = 1 ] && die "Steam bitte vorher beenden"
  echo "WARNUNG: Steam laeuft - vor --ausfuehren beenden"
fi
if [ "$DO" = 1 ] && [ "$ROOT" = sudo ] && ! sudo -n true 2>/dev/null; then
  # Ohne Terminal (z. B. "!" in Claude Code) scheitert sudo erst nach dem Umbau (05.11.).
  [ -t 0 ] || die "sudo braucht ein Terminal fuer das Passwort - bitte in einem Terminalfenster ausfuehren"
  echo "sudo fragt gleich nach dem Passwort."
  sudo -v || die "sudo-Anmeldung gescheitert - nichts geaendert"
fi
if [ "$DO" = 1 ] && [ "$ROOT" = pkexec ]; then
  # pkexec merkt sich nichts; ohne Terminal (und ohne Polkit-Agent) scheitert es
  # erst nach dem Umbau der Ordner (Fable-Pruefung 2026-11-05).
  [ -t 0 ] || die "pkexec braucht ein Terminal (Polkit-Dialog oder Text-Agent) - bitte in einem Terminalfenster ausfuehren"
  echo "pkexec fragt nach dem Umbau der Ordner einmal (Polkit-Dialog oder im Terminal)."
fi
if [ -e /etc/snapper/configs/home ]; then die "snapper-Konfiguration 'home' gibt es schon"; fi

# Nur, was hier wirklich laeuft (Namen der Laufwerks-Units sind je Rechner verschieden).
mapfile -t UNITS < <(systemctl --user list-units --state=active --plain --no-legend \
  'polaris-*.timer' 'rclone*.service' 2>/dev/null | awk '{print $1}')
echo "== Laufwerk und Polaris-Timer anhalten: ${UNITS[*]:-(keine)}"
restart_units() { [ "${#UNITS[@]}" -gt 0 ] && run systemctl --user start "${UNITS[@]}" || true; }
if [ "${#UNITS[@]}" -gt 0 ]; then
  trap restart_units EXIT   # vor stop: auch ein teilweise gescheitertes stop startet alles wieder
  run systemctl --user stop "${UNITS[@]}"
fi

echo "== Fluechtige Ordner als eigene Subvolumes"
for d in "$HOME/.cache" "$HOME/.local/share/Steam" "$HOME/Games"; do
  [ -d "$d" ] || { echo "  $d fehlt, uebersprungen"; continue; }
  if [ "$(stat -c %i "$d")" = "256" ]; then echo "  $d ist schon ein Subvolume"; continue; fi
  old="$d.alt-$stamp" new="$d.neu-$stamp"
  [ -e "$old" ] || [ -e "$new" ] && die "$old oder $new existiert schon"
  run btrfs subvolume create "$new"
  if ! run cp -a --reflink=always -- "$d/." "$new/"; then
    run rm -rf -- "$new" || true
    die "Kopie nach $new gescheitert - $d ist unveraendert"
  fi
  # Atomarer Tausch (renameat2 RENAME_EXCHANGE): $d ist nie weg, auch fuer laufende Programme.
  run mv -T --exchange -- "$new" "$d"
  run mv -T -- "$new" "$old"
  echo "  $d: alter Ordner bleibt als $old (nach Pruefung: rm -rf '$old')"
done

echo "== snapper-Konfiguration home (als root per $ROOT, ein Aufruf)"
# Fester Text, keine Variablen: der root-Teil haengt von keiner Eingabe ab.
ROOT_STEPS='set -euo pipefail
trap '"'"'echo "FEHLER im root-Schritt: $BASH_COMMAND - Rueckbau: snapper -c home delete-config; systemctl disable --now snapper-timeline.timer" >&2'"'"' ERR
snapper -c home create-config /home
snapper -c home set-config TIMELINE_CREATE=yes TIMELINE_CLEANUP=yes TIMELINE_LIMIT_HOURLY=12 TIMELINE_LIMIT_DAILY=7 TIMELINE_LIMIT_WEEKLY=4 TIMELINE_LIMIT_MONTHLY=0 TIMELINE_LIMIT_QUARTERLY=0 TIMELINE_LIMIT_YEARLY=0 NUMBER_CLEANUP=yes NUMBER_LIMIT=10
systemctl enable --now snapper-timeline.timer
snapper -c home create --description "erster Snapshot nach Einrichtung"
snapper -c home list || true'
if [ "$DO" = 1 ]; then
  # sudo-Anmeldung auffrischen: Das Kopieren grosser Ordner kann laenger dauern als ihr Zeitfenster.
  [ "$ROOT" = sudo ] && { sudo -v || die "sudo-Anmeldung gescheitert - Ordner sind umgebaut, root-Teil fehlt; Skript erneut ausfuehren"; }
  printf '+ %s:\n%s\n' "$ROOT" "$ROOT_STEPS"
  "$ROOT" /usr/bin/bash -c "$ROOT_STEPS"
else
  printf '[probe] %s:\n%s\n' "$ROOT" "$ROOT_STEPS" | sed '2,$s/^/[probe]   /'
fi

echo "== Pruefung"
run ls -ld /home/.snapshots
echo "Fertig. Im Maschinengedaechtnis dokumentieren (handoff/sicherheit-rechte.md o. Ae.)."
