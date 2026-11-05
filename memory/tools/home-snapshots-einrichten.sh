#!/usr/bin/env bash
# Btrfs-Snapshots fuer /home einrichten (seit 2026-11-04, Teil von Polaris; vom Nutzer
# in einem Terminalfenster auszufuehren, sudo fragt nach dem Passwort).
#
#   ~/.config/ai-agents/tools/home-snapshots-einrichten.sh            # Probelauf: zeigt nur, was passiert
#   ~/.config/ai-agents/tools/home-snapshots-einrichten.sh --ausfuehren
#
# Warum: Schutz gegen Zerstoerung (versehentlich oder durch eine eingeschleuste
# Anweisung an einen Agenten). Die Snapshots gehoeren root; ein Programm mit den
# Rechten des Nutzers kann sie weder lesen noch loeschen. Wiederherstellen braucht sudo.
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
# Rueckbau: sudo snapper -c home delete-config; sudo systemctl disable --now snapper-timeline.timer
# (die Subvolumes duerfen bleiben). Hinweis Datenschutz: Geloeschtes bleibt bis zu vier
# Wochen in den Snapshots erhalten.
set -euo pipefail
DO=0
[ "${1:-}" = "--ausfuehren" ] && DO=1
run() { if [ "$DO" = 1 ]; then echo "+ $*"; "$@"; else echo "[probe] $*"; fi; }
die() { echo "FEHLER: $*" >&2; exit 1; }
stamp="$(date +%Y%m%d-%H%M%S)"

[ "$(stat -f -c %T /home)" = "btrfs" ] || die "/home ist kein btrfs"
[ "$(stat -c %i /home)" = "256" ] || die "/home ist kein eigenes btrfs-Subvolume (snapper braucht das)"
command -v snapper >/dev/null || die "snapper fehlt"
command -v btrfs >/dev/null || die "btrfs-progs fehlt"
mv --help 2>/dev/null | grep -q -- '--exchange' || die "mv --exchange fehlt (coreutils >= 9.5)"
if pgrep -x steam >/dev/null || pgrep -x steamwebhelper >/dev/null; then
  [ "$DO" = 1 ] && die "Steam bitte vorher beenden"
  echo "WARNUNG: Steam laeuft - vor --ausfuehren beenden"
fi
if [ "$DO" = 1 ] && ! sudo -n true 2>/dev/null; then
  # Ohne Terminal (z. B. "!" in Claude Code) scheitert sudo erst nach dem Umbau (05.11.).
  [ -t 0 ] || die "sudo braucht ein Terminal fuer das Passwort - bitte in einem Terminalfenster ausfuehren"
  echo "sudo fragt gleich nach dem Passwort."
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

echo "== snapper-Konfiguration home"
run sudo snapper -c home create-config /home
run sudo snapper -c home set-config TIMELINE_CREATE=yes TIMELINE_CLEANUP=yes \
  TIMELINE_LIMIT_HOURLY=12 TIMELINE_LIMIT_DAILY=7 TIMELINE_LIMIT_WEEKLY=4 \
  TIMELINE_LIMIT_MONTHLY=0 TIMELINE_LIMIT_QUARTERLY=0 TIMELINE_LIMIT_YEARLY=0 \
  NUMBER_CLEANUP=yes NUMBER_LIMIT=10
run sudo systemctl enable --now snapper-timeline.timer
run sudo snapper -c home create --description "erster Snapshot nach Einrichtung"

echo "== Pruefung"
run sudo snapper -c home list
run ls -ld /home/.snapshots
echo "Fertig. Im Maschinengedaechtnis dokumentieren (handoff/sicherheit-rechte.md o. Ae.)."
