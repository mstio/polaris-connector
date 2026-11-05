#!/usr/bin/env bash
# Alle Testsuiten in einem Lauf (seit 2026-11-05; vorher liefen sie getrennt und
# fehlschlagende memlint-Tests blieben einen Tag unbemerkt). Etwa 45 s.
# Laeuft vor jeder Veroeffentlichung (scripts/publish-public.sh).
#   scripts/run-tests.sh      Exit 0 = alle gruen
set -uo pipefail
REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
fail=0
for suite in "memory/tests:." "curator/tests:curator" "tests:."; do
  dir="${suite%%:*}" cwd="${suite#*:}"
  out="$(cd "$REPO/$cwd" && python3 -m unittest discover -s "${dir#curator/}" 2>&1)"
  line="$(printf '%s\n' "$out" | grep -E '^(OK|FAILED)' | tail -1)"
  ran="$(printf '%s\n' "$out" | grep -E '^Ran ' | tail -1)"
  printf '%-14s %s, %s\n' "$dir" "${ran:-?}" "${line:-kein Ergebnis}"
  case "$line" in OK*) ;; *) fail=1; printf '%s\n' "$out" | grep -E -A15 '^(FAIL|ERROR):' | head -60 ;; esac
done
[ "$fail" = 0 ] && echo "Alle Tests gruen." || echo "FEHLER: Tests rot." >&2
exit "$fail"
