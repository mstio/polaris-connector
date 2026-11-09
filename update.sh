#!/usr/bin/env bash
# Aktualisiert einen git-Checkout von Polaris (seit 2026-10-23), nach dem
# Vorbild von `omarchy plugin update`:
#
#   polaris update            neuen Stand holen, Aenderungen zeigen, nachfragen
#   polaris update --yes      ohne Nachfrage (Agenten, Skripte)
#   polaris update --check    nur nachsehen: Exit 0 = Update da, 1 = aktuell,
#                             2 = Fehler; schreibt den Zustand fuer den Health-Check
#
# Ablauf: git fetch -> nur Fast-Forward (lokale Commits oder geaenderte Dateien
# brechen ab, eigene Aenderungen gehoeren in einen Branch/Pull Request) ->
# install.sh fuer das, was schon eingerichtet ist (Units, Widget, Dock,
# Gedaechtnis) -> polaris-curator health. Wird der Health-Check durch das
# Update rot, geht es zurueck auf den alten Commit und install.sh laeuft erneut.
# Ohne git (altes Installationspaket, GitHub-ZIP) gibt es kein Update hier:
# einmal auf einen git-Checkout umsteigen (docs/install.md, "Switching from the install
# bundle to a git checkout"). Danach zieht es auch die Bausteine aus eigenen
# Repos mit (omarchy-backup, Widgets).
set -uo pipefail

export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -oBatchMode=yes}"

REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# Fester Pfad wie im Health-Check (Python: Path.home()), nicht XDG_STATE_HOME.
STATE="$HOME/.local/state/polaris/update-check.json"
# Fuer Tests austauschbar; Standard sind die echten Programme im Repo.
INSTALL="${POLARIS_UPDATE_INSTALL:-$REPO/install.sh}"
HEALTH="${POLARIS_UPDATE_HEALTH:-$REPO/curator/bin/polaris-curator health --json}"
SYSTEMCTL="${POLARIS_UPDATE_SYSTEMCTL:-systemctl}"
LOG_DIR="$HOME/.local/state/polaris"

YES=0 CHECK=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES=1 ;;
    --check) CHECK=1 ;;
    -h|--help) sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "polaris update: unbekannte Option $arg" >&2; exit 2 ;;
  esac
done

fail() { echo "polaris update: $*" >&2; exit 2; }
g() { git -C "$REPO" "$@"; }
# Version der Erweiterung plus Commit: zwischen zwei Erweiterungs-Releases
# aendert sich sonst nur der Code, nicht die Nummer.
version() {
  local v
  v="$(g show "$1:extension/manifest.json" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])' 2>/dev/null || echo "?")"
  echo "$v ($(g rev-parse --short "$1" 2>/dev/null))"
}
# Bausteine aus eigenen Repos mitziehen (seit 2026-11-04): omarchy-backup-CLI
# als git-Checkout unter ~/.local/share/polaris/extras/ (nur Fast-Forward),
# die Widgets per 'omarchy plugin update' (nur wenn sie git-verwaltet sind).
# Fehler hier sind nur Hinweise; Polaris selbst ist dann schon aktualisiert.
# Seit Gutachten Codex 2026-11-07: Fremdcode der Extras nicht ungesehen ziehen.
# Ohne Terminal bzw. mit --yes nur anzeigen, was neu waere; nachziehen nach
# Zustimmung im Terminal oder mit POLARIS_UPDATE_EXTRAS=1.
extras_ok() {
  [ "${POLARIS_UPDATE_EXTRAS:-0}" = 1 ] && return 0
  [ "$YES" = 1 ] && return 1
  [ -t 0 ] || return 1
  local answer
  read -r -p "$1 [j/N] " answer
  case "$answer" in j|J|y|Y|ja|Ja) return 0 ;; *) return 1 ;; esac
}

update_extras() {
  local ob="$HOME/.local/share/polaris/extras/omarchy-backup" id pd
  if [ -d "$ob/.git" ] && ! timeout 60 git -C "$ob" fetch --quiet 2>/dev/null; then
    echo "polaris update: omarchy-backup in $ob nicht abgefragt (Netz oder kein Upstream)" >&2
  elif [ -d "$ob/.git" ] && [ -n "$(git -C "$ob" rev-list HEAD..@{u} 2>/dev/null)" ]; then
    echo "omarchy-backup: neue Commits"
    git -C "$ob" log --oneline HEAD..@{u} | head -n 20
    git -C "$ob" diff --stat HEAD @{u} | tail -n 15
    if ! extras_ok "omarchy-backup aktualisieren?"; then
      echo "omarchy-backup nicht aktualisiert - nach Durchsicht: POLARIS_UPDATE_EXTRAS=1 polaris update"
    elif timeout 60 git -C "$ob" pull --ff-only --quiet 2>/dev/null; then
      echo "omarchy-backup: $(git -C "$ob" log -1 --format='%h %s')"
    else
      echo "polaris update: omarchy-backup in $ob nicht aktualisiert (lokale Aenderungen oder Netz)" >&2
    fi
  fi
  command -v omarchy >/dev/null || return 0
  for id in mst.polaris-curator mst.agent-launchers mst.omarchy-backup; do
    pd="$HOME/.config/omarchy/plugins/$id"
    [ -d "$pd/.git" ] || continue
    timeout 60 git -C "$pd" fetch --quiet 2>/dev/null || continue
    [ -n "$(git -C "$pd" rev-list HEAD..@{u} 2>/dev/null)" ] || continue
    echo "Widget $id: neue Commits"
    git -C "$pd" log --oneline HEAD..@{u} | head -n 20
    if ! extras_ok "Widget $id aktualisieren (omarchy plugin update)?"; then
      echo "Widget $id nicht aktualisiert - selbst: omarchy plugin update $id"
      continue
    fi
    timeout 120 omarchy plugin update "$id" --yes >/dev/null 2>&1 \
      || echo "polaris update: Widget $id nicht aktualisiert (omarchy plugin update $id)" >&2
  done
}
health_level() { $HEALTH 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("level","error"))' 2>/dev/null || echo error; }
# Kennungen der Health-Pruefungen mit Stufe "error", sortiert, eine je Zeile
# (seit 2026-11-07, ADR 003): ein Update wird zurueckgenommen, sobald eine
# Pruefung NEU rot ist - auch wenn vorher schon eine andere rot war.
health_errors() {
  $HEALTH 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("health-unlesbar"); sys.exit()
ids = [c.get("id", "?") for c in d.get("checks", []) if c.get("level") == "error"]
if not ids and d.get("level", "error") == "error":
    ids = ["gesamt"]
print("\n".join(ids))' 2>/dev/null | sort -u || echo health-unlesbar
}

write_state() {  # behind local remote
  mkdir -p "${STATE%/*}" 2>/dev/null || return 0
  printf '{"checked_at":"%s","behind":%s,"local":"%s","remote":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$3" >"$STATE.tmp" && mv -f "$STATE.tmp" "$STATE"
}

# -e: im Live-Stand (git worktree, ADR 003) ist .git eine Datei.
APP_DIR="$HOME/.local/share/polaris/app"
[ -e "$REPO/.git" ] || fail "$REPO ist kein git-Checkout. Einmal auf git umsteigen: docs/install.md, Abschnitt \"Switching from the install bundle to a git checkout\"."
g rev-parse --git-dir >/dev/null 2>&1 ||
  fail "$REPO ist ein worktree, dessen Hauptcheckout fehlt - Live-Stand neu anlegen (docs/AGENTEN-LEITFADEN.md, 'Live und Entwicklung getrennt')."
if [ "$REPO" != "$APP_DIR" ] && [ -f "$APP_DIR/.git" ] \
    && g worktree list --porcelain 2>/dev/null | grep -qxF "worktree $APP_DIR"; then
  fail "Live laeuft als worktree unter $APP_DIR - Update dort ausfuehren ('polaris update'), nicht im Entwicklungs-Checkout."
fi
upstream="$(g rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" ||
  fail "der Branch $(g branch --show-current) hat kein Upstream (git branch --set-upstream-to origin/main)"

timeout 60 git -C "$REPO" fetch --quiet "${upstream%%/*}" || fail "git fetch fehlgeschlagen (Netz?)"
old="$(g rev-parse HEAD)" new="$(g rev-parse "$upstream")"
behind="$(g rev-list --count "HEAD..$upstream")" ahead="$(g rev-list --count "$upstream..HEAD")"
write_state "$behind" "$(version HEAD)" "$(version "$upstream")"

if [ "$behind" = 0 ]; then
  echo "Polaris $(version HEAD) ist aktuell."
  [ "$CHECK" = 1 ] && exit 1
  update_extras
  exit 0
fi
if [ "$CHECK" = 1 ]; then
  echo "Update verfuegbar: Polaris $(version HEAD) -> $(version "$upstream") ($behind Commit(s))"
  exit 0
fi

[ "$ahead" = 0 ] ||
  fail "$ahead lokale(r) Commit(s), die nicht in $upstream sind - kein Fast-Forward moeglich. Eigene Aenderungen in einen Branch legen oder als Pull Request einreichen."
[ -z "$(g status --porcelain --untracked-files=no)" ] ||
  fail "geaenderte Dateien in $REPO (git status) - erst committen oder zuruecklegen (git stash)."

echo "Polaris $(version HEAD) -> $(version "$upstream")"
g log --oneline "HEAD..$upstream"
g diff --stat HEAD "$upstream" | tail -n 25
echo
if [ "$YES" != 1 ]; then
  [ -t 0 ] || fail "ohne Terminal nur mit --yes"
  read -r -p "Aktualisieren? [j/N] " answer
  case "$answer" in j|J|y|Y|ja|Ja) ;; *) echo "Abgebrochen, nichts geaendert."; exit 0 ;; esac
fi

# install.sh nur fuer das, was schon eingerichtet ist - ein Update richtet
# nichts Neues ein (z. B. kein Dock, wenn es bewusst fehlt).
install_args=(--yes --only-existing)
ls "$HOME"/.config/systemd/user/polaris-*.service >/dev/null 2>&1 || install_args+=(--no-units)
[ -d "$HOME/.config/omarchy/plugins/mst.polaris-curator" ] || install_args+=(--no-widget)
[ -d "$HOME/.config/omarchy/plugins/omadock" ] || install_args+=(--no-dock)
[ -d "$HOME/.config/ai-agents" ] || install_args+=(--no-memory)
install_args+=(--no-backup)

# Nie den Code unter einem laufenden Lauf austauschen (bash liest Skripte
# stueckweise, Python laedt Module nach): dann spaeter erneut (Exit 75).
# Direkt vor dem Wechsel geprueft, nicht vor der Rueckfrage.
for unit in polaris-curator.service polaris-curator-manual.service polaris-bridge.service \
            polaris-memory-mirror.service polaris-radar.service polaris-radar-update.service; do
  if "$SYSTEMCTL" --user is-active --quiet "$unit" 2>/dev/null; then
    echo "polaris update: $unit laeuft gerade - nichts geaendert, bitte spaeter erneut." >&2
    exit 75
  fi
done
before="$(health_level)" before_errors="$(health_errors)"
g merge --ff-only --quiet "$upstream" || fail "Fast-Forward fehlgeschlagen; nichts geaendert."
if ! "$INSTALL" "${install_args[@]}"; then
  install_failed=1
else
  install_failed=0
fi
# Zustand vor dem Health-Check schreiben, sonst meldet er im selben Lauf noch
# "Update verfuegbar" (Rueckmeldung von bernhard2804, 2026-11-05). Beim Rueckweg
# unten wird er wieder auf den alten Stand gesetzt.
write_state 0 "$(version HEAD)" "$(version HEAD)"
after="$(health_level)" after_errors="$(health_errors)"
new_errors="$(comm -13 <(printf '%s\n' "$before_errors" | sed '/^$/d') <(printf '%s\n' "$after_errors" | sed '/^$/d') | tr '\n' ' ')"

if [ "$install_failed" = 1 ] || [ -n "${new_errors// /}" ]; then
  log="$LOG_DIR/update-$(date +%Y%m%d-%H%M%S).log"
  mkdir -p "$LOG_DIR" 2>/dev/null
  echo "polaris update: install.sh oder Health-Check nach dem Update fehlgeschlagen (vorher $before, nachher $after; neu rot: ${new_errors:-keine}; install.sh fehlgeschlagen: $install_failed) - zurueck auf $(g rev-parse --short "$old"). Protokoll: $log" >&2
  g reset --hard --quiet "$old"
  { echo "Rueckweg $(date -Iseconds): $(g rev-parse --short "$upstream") -> $(g rev-parse --short "$old"); neu rot: ${new_errors:-keine}"
    "$INSTALL" "${install_args[@]}"; } >"$log" 2>&1 \
    || echo "polaris update: auch die Wiederherstellung mit install.sh meldet Fehler ($log) - bitte $INSTALL von Hand ausfuehren." >&2
  write_state "$behind" "$(version HEAD)" "$(version "$upstream")"
  exit 2
fi

case "$after_errors" in
  *health-unlesbar*) echo "polaris update: WARNUNG - Health-Check nicht lesbar (vorher wie nachher), das Update ist ungeprueft. Pruefen: polaris-curator health" >&2 ;;
esac
echo "Polaris auf $(version HEAD) aktualisiert (Health-Check: $after)."
update_extras
exit 0
