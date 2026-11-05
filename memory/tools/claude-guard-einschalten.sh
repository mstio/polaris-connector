#!/usr/bin/env bash
# Bindet tools/claude-guard-hook.py in ~/.claude/settings.json ein (seit 2026-11-05, Teil von Polaris).
# Vom Nutzer auszufuehren: Agenten duerfen ihre eigenen Rechte nicht aendern.
#
#   ~/.config/ai-agents/tools/claude-guard-einschalten.sh            # Stufe standard
#   ~/.config/ai-agents/tools/claude-guard-einschalten.sh streng      # nach einer Woche
#   ~/.config/ai-agents/tools/claude-guard-einschalten.sh aus         # Rueckbau
#
# Vorher Sicherung settings.json.bak-<Zeit>. Andere Eintraege bleiben unveraendert.
# Wirkt sofort, auch in laufenden Claude-Code-Sitzungen (Datei-Beobachtung; pruefen mit /hooks).
# PreToolUse mit "onFailure": "block" (ab Claude Code 2.1.295): startet der Hook nicht
# oder haengt er, wird die Aktion blockiert statt durchgelassen. Dann: "aus" ausfuehren.
# Schreibt Claude Code gleichzeitig in settings.json, gewinnt der letzte Schreiber.
set -euo pipefail
level="${1:-standard}"
case "$level" in standard|streng|aus) ;; *) echo "Stufe: standard | streng | aus" >&2; exit 2 ;; esac
f="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
[ -f "$f" ] || echo '{}' > "$f"
bak="$f.bak-$(date +%Y%m%d-%H%M%S)"
[ -e "$bak" ] && { echo "Sicherung $bak gibt es schon - in einer Sekunde erneut versuchen" >&2; exit 1; }
cp -- "$f" "$bak"
python3 -I - "$f" "$level" <<'EOF'
import json, os, sys, tempfile
path, level = sys.argv[1], sys.argv[2]
d = json.load(open(path))
hooks = d.setdefault("hooks", {})
mark = "claude-guard-hook.py"
cmd = f"CLAUDE_GUARD_LEVEL={level} python3 -I $HOME/.config/ai-agents/tools/claude-guard-hook.py"
for ev in ("PreToolUse", "PostToolUse"):
    keep = [h for h in hooks.get(ev, []) if not any(mark in x.get("command", "") for x in h.get("hooks", []))]
    if level != "aus":
        h = {"type": "command", "command": cmd, "timeout": 10}
        if ev == "PreToolUse":
            h["onFailure"] = "block"
        keep.append({"matcher": ".*", "hooks": [h]})
    if keep:
        hooks[ev] = keep
    else:
        hooks.pop(ev, None)
if not hooks:
    d.pop("hooks")
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".settings.", suffix=".tmp")
with os.fdopen(fd, "w") as fh:
    json.dump(d, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
os.chmod(tmp, os.stat(path).st_mode & 0o777)
os.replace(tmp, path)
print(f"Guard-Hook: {level}")
EOF
echo "Sicherung: $bak"
