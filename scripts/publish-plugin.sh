#!/usr/bin/env bash
# Veroeffentlicht das Polaris-Widget als eigenes Plugin-Repo (seit 2026-11-04).
#   scripts/publish-plugin.sh [<ref>] [--push]     <ref> Standard: HEAD
# Der Omarchy-Plugin-Marktplatz verlangt ein Repo mit manifest.json im
# Wurzelordner. Quelle bleibt omarchy-plugin/mst.polaris-curator/ in diesem
# Repo; das Plugin-Repo bekommt je Freigabe einen Commit mit genau diesem
# Ordnerstand (noreply-Adresse). Vorher laufen omarchy plugin validate und
# scripts/privacy-check.py; der pre-push-Hook (scripts/public-pre-push) prueft
# jeden Commit erneut. Ohne --push nur lokal committen; pruefen, dann --push.
# Arbeitskopie: $PLUGIN_REPO_DIR (Standard ~/Projects/mst.polaris-curator).
# Push nur mit Nutzerfreigabe (wie beim oeffentlichen Spiegel).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ID="mst.polaris-curator"
URL="https://github.com/mstio/$ID.git"
DIR="${PLUGIN_REPO_DIR:-$HOME/Projects/$ID}"
REF=HEAD PUSH=0
for a in "$@"; do
  case "$a" in --push) PUSH=1 ;; -h|--help) sed -n 2,12p "$0"; exit 0 ;; *) REF="$a" ;; esac
done

work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
git -C "$REPO" archive "$REF" "omarchy-plugin/$ID" | tar -C "$work" -xf -
src="$work/omarchy-plugin/$ID"
[ -f "$src/manifest.json" ] || { echo "FEHLER: $ID fehlt in $REF" >&2; exit 1; }
if command -v omarchy >/dev/null; then
  omarchy plugin validate "$src" || { echo "FEHLER: Manifest ungueltig - nichts uebernommen." >&2; exit 1; }
fi
python3 "$REPO/scripts/privacy-check.py" "$src" || { echo "FEHLER: Privatsphaere-Pruefung - nichts uebernommen." >&2; exit 1; }

if [ ! -d "$DIR/.git" ]; then
  git init -q -b main "$DIR"
  git -C "$DIR" remote add origin "$URL"
fi
HOOK="$DIR/.git/hooks/pre-push"
[ -L "$HOOK" ] || ln -sfn "$REPO/scripts/public-pre-push" "$HOOK"

rsync -a --delete --exclude=/.git "$src/" "$DIR/"
git -C "$DIR" add -A
if git -C "$DIR" diff --cached --quiet; then
  echo "Plugin-Repo ist bereits auf dem Stand von $REF."
else
  EMAIL="${PUBLIC_EMAIL:-$(gh api user -q '"\(.id)+\(.login)@users.noreply.github.com"')}"
  NAME="${PUBLIC_NAME:-$(gh api user -q .login)}"
  version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$src/manifest.json")"
  GIT_AUTHOR_NAME="$NAME" GIT_AUTHOR_EMAIL="$EMAIL" \
  GIT_COMMITTER_NAME="$NAME" GIT_COMMITTER_EMAIL="$EMAIL" \
    git -C "$DIR" commit -q -m "Polaris widget $version"
  git -C "$DIR" show --stat --format='%h %an <%ae> %s' HEAD
fi

if [ "$PUSH" = 1 ]; then
  git -C "$DIR" push -u origin main
else
  echo "Noch nicht veroeffentlicht. Pruefen, dann: scripts/publish-plugin.sh $REF --push"
fi
