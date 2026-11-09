---
name: perspektivwechsel
description: Bewusst den Blickwinkel wechseln, um übersehene Risiken und neue Lösungswege zu finden – mit Techniken aus systemischer Beratung und Kreativitätsmethodik (Kopfstand/Umkehrung, Prä-mortem, Tetralemma, zirkuläre Fragen, Wunderfrage, laterale Provokation). Einsetzen vor Architektur- und Konzeptentscheidungen, vor Meilensteinen und Veröffentlichungen, in Prüfgremien (je Prüfer eine Technik), wenn eine Aufgabe festgefahren ist oder alle Vorschläge sich ähneln, und wenn der Nutzer neue Ideen, Kopfstand, Umkehrung, Prä-mortem oder Tetralemma verlangt. Nicht für Routineänderungen und nicht als Ersatz für Messung, Tests und Code-Prüfung.
---

# Perspektivwechsel: übersehene Risiken und neue Wege finden

Anbieterneutrale Arbeitsanweisung für alle lokalen Agenten (Quelle:
`~/.config/ai-agents/skills/perspektivwechsel/SKILL.md`; Agenten ohne Skill-Unterstützung
lesen die Datei direkt). Ergänzt `skills/loesungsqualitaet/SKILL.md` (Abschnitt „Range“):
Lösungsqualität sucht den besten Weg im bekannten Raum, Perspektivwechsel erweitert den Raum.
Die Regeln in `AGENTS.md` (Freigaben, Ressourcen, Dokumentation, Zweitmeinung) haben Vorrang.

**Warum:** Prüfungen finden zuverlässig Fehler in dem, was gebaut wurde, aber selten, was
ganz fehlt oder ganz anders sein könnte (Beleg 2026-11-07: zehn Prüfungen ohne die Punkte
„Alarmmüdigkeit“ und „parallele Agentensitzungen“; ein Kopfstand fand beide in Minuten).

## 0. Einsatz – wann, wie viel

- **Ja:** Konzept- und Architekturentscheidungen, Meilensteine (Stufe abgeschlossen, vor einer
  Veröffentlichung), Prüfgremien, festgefahrene Fragen, „wir drehen uns im Kreis“, und wenn
  alle bisherigen Vorschläge Varianten derselben Idee sind.
- **Nein:** Routine, eindeutige kleine Änderungen, akute Störungen (dort erst messen und
  beheben, Perspektivwechsel höchstens danach für „wie kommt das nicht wieder?“).
- **Umfang:** Zwei bis drei passende Techniken, nicht alle. Je Technik wenige Minuten
  Denkarbeit, dann prüfen. Lieber drei belastbare neue Punkte als zwanzig Einfälle.

## 1. Techniken – Frage, Vorgehen, wofür

**Kopfstand / Umkehrung** (Kreativitätstechnik, in der systemischen Beratung verbreitet)
- Frage umdrehen: „Wie erreichen wir sicher das *Gegenteil* des Ziels?“ – z. B. „Wie
  bringen wir das System dazu, still Falsches zu schreiben / dass der Nutzer ihm nicht mehr
  vertraut / dass es unwartbar wird / dass Daten verloren gehen?“
- 5–10 konkrete „Schadensrezepte“ sammeln, dann jedes umdrehen: Gibt es dagegen schon
  Schutz? Wenn nein, ist das ein Kandidat.
- Wofür: Prüfungen, Sicherheit, Betrieb, Nutzervertrauen. Die ergiebigste Technik für Code.

**Prä-mortem** (Gary Klein, Risikomanagement)
- „Es ist sechs Monate später, das Vorhaben ist gescheitert. Schreib die Geschichte, warum.“
- Mehrere unterschiedliche Scheiter-Geschichten (technisch, organisatorisch, Nutzung,
  Abhängigkeiten, Kosten); je Geschichte den frühesten Warnhinweis und die billigste Vorkehrung.
- Wofür: vor Meilensteinen, vor Entscheidungen mit langer Wirkung.

**Tetralemma** (Insa Sparrer, Matthias Varga von Kibéd)
- Für Entscheidungen „A oder B“ alle fünf Positionen ernsthaft ausformulieren: **A**,
  **B**, **beides** (wie ginge beides zugleich?), **keines von beiden** (was wäre, wenn die
  Frage falsch gestellt ist?), **keins von alledem / ganz anders** (was liegt außerhalb?).
- Die Positionen 3–5 sind der Gewinn: Sie zeigen oft den eigentlichen nächsten Schritt.
- Wofür: Architektur- und Produktentscheidungen, Wege-Vergleiche.

**Zirkuläre Fragen** (systemische Familientherapie)
- Aus Sicht anderer Beteiligter fragen: „Was würde der Nutzer in drei Monaten dazu sagen?
  Ein anderer Rechner mit anderer Auswahl? Ein Agent, der den Code in einem Jahr ändern
  muss? Ein Angreifer? Der Betreiber des Cloud-Laufwerks?“
- Wofür: Nebenwirkungen auf andere Teile, Installationen und Menschen; Wartbarkeit.

**Wunderfrage** (Steve de Shazer, lösungsfokussiert)
- „Über Nacht ist das Problem gelöst. Woran merkst du das morgen früh als Erstes?“
- Liefert beobachtbare Erfolgskriterien und zeigt, ob das Gebaute auf das Ziel zielt.
- Wofür: Ziele schärfen, Erfolgskriterien für eine Stufe festlegen.

**Laterale Provokation** (Edward de Bono)
- Bewusst unvernünftige Aussage setzen („Po: Es gibt keinen Curator“, „Po: Updates gibt es
  nur einmal im Jahr“) und fragen, was daraus Brauchbares folgt.
- Wofür: festgefahrene Annahmen lösen, Vereinfachung finden („was, wenn wir X löschen?“).

## 2. Vorgehen

1. **Fokusfrage** in einem Satz festhalten (was soll besser verstanden oder entschieden werden).
2. **Techniken wählen:** Prüfung/Sicherheit → Kopfstand + zirkuläre Fragen; Entscheidung →
   Tetralemma + Prä-mortem; Ziel unklar → Wunderfrage; festgefahren → laterale Provokation.
3. **Ideen erzeugen** – erst sammeln, nicht bewerten.
4. **Jede Idee erden:** am Code, an Rohdaten, Logs oder Konfiguration prüfen, ob sie zutrifft
   bzw. ob es schon Schutz gibt. Ohne Prüfung bleibt sie Hypothese.
5. **Verdichten:** nur Punkte behalten, die (a) zutreffen, (b) neu sind (nicht schon in
   bisherigen Prüfungen/ADRs) und (c) eine konkrete Folge haben.
6. **Übergeben:** Ergebnis in der Antwortform unten; Umsetzung erst nach Entscheidung des
   Nutzers bzw. nach den üblichen Regeln (Tests, Zweitmeinung bei Schutzänderungen).

## 3. Im Prüfgremium

Bei Meilensteinen (siehe `AGENTS.md`, Zweitmeinung) jedem Prüfer zusätzlich *eine*
Technik als Brille geben, z. B. einen Kopfstand-Prüfer, einen Prä-mortem-Prüfer und bei
Entscheidungen einen Tetralemma-Prüfer. Im Auftrag die Technik und die Fokusfrage nennen,
nicht das eigene Urteil. Jede Antwort wie andere Befunde am Code nachprüfen.

## 4. Antwortform

- **Fokusfrage** und gewählte Techniken (mit kurzer Begründung).
- **Neue Punkte** (nummeriert): Herkunft (Technik), Befund mit Beleg oder ausdrücklich
  „Hypothese“, vorgeschlagene Folge, Status (Nachgewiesen / Plausibel / Experimentell / Unbekannt).
- **Verworfen** (kurz, warum: trifft nicht zu, schon abgedeckt, ohne Folge).
- **Ertrag** für die Erprobung: Anzahl neuer, zutreffender Punkte, die die klassische
  Prüfung nicht gefunden hat.

## 5. Grenzen und Fallen

- Kein Rollenspiel und kein Methodentheater: Es zählt die geänderte Frage, nicht der Ton.
- Kreative Einfälle sind keine Befunde. Erst die Prüfung am System macht sie zu einem.
- Ein höheres oder anderes Ziel ist ein Vorschlag, kein Auftrag; Ziele und Prioritäten
  legt der Nutzer fest.
- Mehr Ideen heißen nicht mehr Mechanik: Vereinfachen und Löschen sind gleichwertige Ergebnisse.

## 6. Ertrag festhalten

Erprobung seit 2026-11-07: Bei jedem Einsatz den Ertrag (Abschnitt 4) in die passende
`history/`-Datei schreiben. Hat sich die Technik nachweislich bewährt, wird sie als
`type=pattern` in `knowledge/loesungsmuster.md` aufgenommen (nur mit Beleg).
