# Verträge zwischen Bridge und Curator (Beispieldateien)

Seit 2026-11-07 (ADR 003, Stufe 1, Schritt 6). Diese Dateien sind die
gemeinsame Referenz für das Bridge-Ereignis (`schema_version` 1), das die
Erweiterung liefert, die Bridge prüft und unter `raw/<quelle>/messages/`
ablegt und der Curator liest. `tests/test_contract_seam.py` schickt jede
Datei durch die echte Bridge und liest das Ergebnis mit dem echten Curator.
Ändert sich das Format, zuerst hier anpassen und `schema_version` erhöhen.
Nur erfundene Inhalte.
