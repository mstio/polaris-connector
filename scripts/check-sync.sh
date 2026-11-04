#!/usr/bin/env bash
# Gleichstand der mitgelieferten Vorlagen mit den Live-Fassungen dieses
# Rechners (seit 2026-11-04; vorher Teil von make-bundle.sh):
#   - memory/tools/memlint.py        == ~/.config/ai-agents/tools/memlint.py
#   - memory/template/skills/*/SKILL.md == ~/.config/ai-agents/skills/*/SKILL.md
#   - memory/template/AGENTS.md      aus den "allgemein"-Abschnitten der Live-AGENTS.md
# Laeuft vor jeder Veroeffentlichung (scripts/publish-public.sh) und gehoert
# nach jeder Aenderung an memlint, Skills oder allgemeinen Agentenregeln
# in denselben Commit. Auf Rechnern ohne Live-Fassung wird nichts verglichen.
#   scripts/check-sync.sh      Exit 0 = gleich, 1 = abweichend (mit Anleitung)
set -euo pipefail
REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$REPO"
fail=0
LIVE_MEMLINT="$HOME/.config/ai-agents/tools/memlint.py"
if [ -f "$LIVE_MEMLINT" ] && ! cmp -s "$LIVE_MEMLINT" memory/tools/memlint.py; then
  echo "FEHLER: memory/tools/memlint.py weicht von $LIVE_MEMLINT ab." >&2
  echo "  Uebernehmen: cp '$LIVE_MEMLINT' memory/tools/memlint.py, pruefen, committen." >&2
  fail=1
fi
for sk in memory/template/skills/*/; do
  live="$HOME/.config/ai-agents/skills/$(basename "$sk")/SKILL.md"
  if [ -f "$live" ] && ! cmp -s "$live" "${sk}SKILL.md"; then
    echo "FEHLER: ${sk}SKILL.md weicht von $live ab." >&2
    echo "  Uebernehmen: cp '$live' '${sk}SKILL.md', pruefen, committen." >&2
    fail=1
  fi
done
if ! python3 scripts/agents-template.py --check; then
  echo "FEHLER: memory/template/AGENTS.md passt nicht zur Live-AGENTS.md (siehe oben)." >&2
  echo "  Neu erzeugen: scripts/agents-template.py --write, pruefen, committen." >&2
  fail=1
fi
[ "$fail" = 0 ] && echo "Vorlagen im Gleichstand mit den Live-Fassungen."
exit "$fail"
