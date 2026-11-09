"""Ausgabepruefung vor jedem Schreiben (ADR 003, 2026-11-07).

In jeder Funktion, die ein Modell aufruft und danach Dateien schreibt, muss
die Ausgabepruefung (guard.*) zwischen dem Modellaufruf und dem ersten
Schreibzugriff stehen. Strukturtest ueber den Quelltext: faengt ab, dass ein
Umbau die Pruefung hinter das Schreiben schiebt oder verliert.
"""
import ast
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "polaris_curator"
LLM_CALLS = {"llm_fn", "call_llm", "_call_llm"}
GUARD_CALLS = {"stop_if_suspicious", "scan", "scan_text", "quarantine", "check_change"}
WRITE_CALLS = {"atomic_write_text", "atomic_write_json", "write_text", "write_bytes",
               "apply_change_object", "commit_files", "begin", "replay_files", "write_files",
               "_journaled_write"}


def _walk_own(fn: ast.AST):
    """Knoten der Funktion selbst, ohne verschachtelte Funktionen/Lambdas (die
    werden nur definiert; ihr Aufruf steht als eigener Call im Rumpf)."""
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _calls(fn: ast.AST):
    for node in _walk_own(fn):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else None
            yield node.lineno, name, owner


class TestGuardBeforeWrite(unittest.TestCase):
    def test_every_llm_writer_checks_output_before_writing(self):
        checked = []
        for path in sorted(PKG.glob("*.py")):
            if path.name in ("llm.py", "guard.py"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                calls = sorted(_calls(fn), key=lambda c: c[0])
                llm = [ln for ln, name, _o in calls if name in LLM_CALLS]
                if not llm:
                    continue
                first_llm = min(llm)
                writes = [ln for ln, name, _o in calls if name in WRITE_CALLS and ln > first_llm]
                if not writes:
                    continue
                guards = [ln for ln, name, owner in calls
                          if name in GUARD_CALLS and (owner in ("guard", "guard_mod") or name == "stop_if_suspicious")
                          and first_llm < ln]
                where = f"{path.name}:{fn.name}"
                checked.append(where)
                self.assertTrue(guards and min(guards) < min(writes),
                                f"{where}: Modellaufruf Zeile {first_llm}, erstes Schreiben Zeile {min(writes)}, "
                                f"Ausgabepruefung {guards or 'fehlt'}")
        # Die bekannten Schreiber muessen erfasst sein (sonst prueft der Test nichts).
        for expected in ("reclassify.py", "loops_review.py", "compact.py", "pipeline.py"):
            self.assertTrue(any(c.startswith(expected) for c in checked), f"{expected} nicht erfasst: {checked}")


if __name__ == "__main__":
    unittest.main()
