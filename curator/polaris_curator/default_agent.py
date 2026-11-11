"""Read Omarchy's user-selected default without starting another process."""

from pathlib import Path

SUPPORTED = frozenset({"claude", "codex"})


def omarchy_default(path: Path | None = None) -> str | None:
    """Only agent names supported by Polaris' interactive and curator paths."""
    path = path or Path.home() / ".config/omarchy/defaults/agent"
    try:
        # Omarchy's omarchy-default-agent reads only the first line. Match it:
        # later lines must not change which provider receives project data.
        with path.open(encoding="utf-8") as source:
            first = source.readline(128)
        if len(first) == 128 and not first.endswith("\n"):
            return None
        agent = first.removesuffix("\n").strip(" \t")
    except (OSError, UnicodeError):
        return None
    return agent if agent in SUPPORTED else None
