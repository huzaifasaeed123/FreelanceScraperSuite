# Telegram bot — developer brief (client requirements, original German)

Source of truth for what the Telegram module must do. The implementation plan is `TELEGRAM_PLAN.md`;
section numbers below (§1–§15) are the ones the plan refers to. The Telegram area is integrated fully
into the existing admin panel.

## 1. Telegram-Konto / Bot verbinden
- Telegram-Bot/Konto muss mit dem Adminpanel verbunden werden können.
- Der Status der Verbindung soll sichtbar sein: Online / Offline / Fehler.
- Die Verbindung muss jederzeit getrennt und neu verbunden werden können.
- Im Dashboard sollen die wichtigsten Telegram-Statistiken angezeigt werden.

## 2. Eingehende Chats erfassen
Der Bot soll eingehende bzw. vorhandene Chats erfassen und im Adminpanel speichern. Je Chat möglichst:
Name / Benutzername · Telegram-ID · Datum des letzten Kontakts · Datum des ersten Kontakts · letzter
Nachrichteninhalt bzw. Status · Bearbeitungsstatus · Anzahl bisher gesendeter Nachrichten · Zeitpunkt der
letzten Bearbeitung. Die Chats sollen durchsucht und gefiltert werden können.
Status: 🟢 Noch nicht bearbeitet · 🔵 In Bearbeitung · ✅ Bearbeitet · ❌ Fehler · ⏸️ Pausiert

## 3. Nachrichtenablauf / Workflow (wichtigster Bereich)
Im Adminpanel einen individuellen Nachrichtenablauf erstellen, z. B.
Sprachmemo ↓60 s Pause → Text ↓30 s → Bild ↓10 s → Sprachmemo. Komplett frei konfigurierbar.
Schritte: 🎤 Sprachmemo · 📝 Text · 🖼️ Bild · weitere Telegram-Nachrichtentypen, sofern technisch möglich.
Jeder Schritt einzeln bearbeiten, verschieben, löschen oder ersetzen.

## 4. Pausen individuell einstellen
Nach jedem Schritt eine eigene Pause: 0 / 10 / 30 / 60 Sekunden, mehrere Minuten, frei eingegebene Zeit.
0 Sekunden = nächste Nachricht direkt senden. Pausen für jeden Schritt separat einstellbar.

## 5. Workflow-Editor
Übersichtlicher Editor: Karten je Schritt (Typ, "Pause danach: n Sekunden", Bearbeiten), Pfeile zwischen den
Schritten, "[+ Nachricht hinzufügen]", "[Ablauf speichern]". Reihenfolge per Drag & Drop veränderbar.

## 6. Chats auswählen (vor dem Start)
Einzelne Chats · mehrere Chats · alle noch nicht bearbeiteten · nach Status filtern · nach Datum filtern ·
nach Benutzername suchen · Suchfunktion. Danach anzeigen: „1.248 Chats ausgewählt“.

## 7. Versand starten
Deutlicher „START“-Button. Der Bot arbeitet die ausgewählten Chats einzeln nacheinander ab:
Chat 1: Sprachmemo → 60 s warten → Text → 30 s → Bild → 10 s → Sprachmemo → Chat 1 abgeschlossen →
Chat 2 … bis alle ausgewählten Chats bearbeitet wurden.

## 8. Keine parallele Bearbeitung
Chats grundsätzlich nacheinander: Chat 1 vollständig abschließen → Chat 2 → Chat 3 … Nicht gleichzeitig mehrere
Chats bearbeiten (damit Ablauf und Pausen zuverlässig eingehalten werden).

## 9. Steuerung während des laufenden Ablaufs
⏸ Pause (aktueller Prozess pausiert) · ▶ Fortsetzen (genau an der Stelle fortsetzen, an der pausiert wurde) ·
⛔ Stoppen (gesamter Ablauf beendet) · 🔄 Neustart (Ablauf erneut startbar). Sichtbar, welcher Chat gerade
bearbeitet wird.

## 10. Live-Status
Telegram-Bot: ● AKTIV · Aktueller Chat · Aktueller Schritt · Nächster Schritt · Nächste Aktion: „in 42 Sekunden“ ·
Fortschritt (Balken, 67 %) · Bearbeitet 670 / 1.000 · Erfolgreich · Fehler.

## 11. Fehlerbehandlung
Bei einem Fehler: protokollieren · Chat als Fehler markieren · Fehlergrund speichern (soweit technisch
verfügbar) · wählbar, ob der Bot zum nächsten Chat weitergeht oder den aktuellen Chat erneut versucht.
Wichtig: Ein Fehler bei einem Chat darf nicht automatisch den gesamten Ablauf stoppen.

## 12. Historie
Alle Aktionen speichern. Je Durchlauf: Startzeit · Endzeit · verwendeter Workflow · Anzahl ausgewählter Chats ·
erfolgreich bearbeitet · Fehler · abgebrochene Chats · Dauer. Nachvollziehbar, welcher Chat wann bearbeitet wurde.

## 13. Dashboard
Mindestens: Anzahl aller Chats · noch nicht bearbeitete · bereits bearbeitete · Chats mit Fehlern · aktuell
laufender Ablauf · erfolgreiche Sendungen · fehlgeschlagene Sendungen · letzter Durchlauf · aktuell aktiver
Chat · Fortschritt des aktuellen Durchlaufs.

## 14. Nachrichtenabläufe speichern
Mehrere verschiedene Abläufe speichern, z. B. „Workflow 1 – Neukontakt“ (🎤 → 60 s → 📝 → 30 s → 🖼️),
„Workflow 2 – Follow-up“ (📝 → 10 s → 🖼️ → 20 s → 🎤), „Workflow 3 – Ohne Pause“ (🎤 → 📝 → 🖼️ → 🎤).
Beim Start: Workflow auswählen → Chats auswählen → START.

## 15. Ziel
Einen festen Nachrichtenablauf einmal erstellen und automatisch Chat für Chat abarbeiten lassen. Jederzeit
sichtbar: welcher Chat wird bearbeitet · welcher Schritt wird ausgeführt · wie lange ist die nächste Pause · wie
viele Chats sind fertig · wie viele offen · gab es Fehler. Steuerung, Workflows, Chat-Auswahl, Start/Pause/Stop und
Historie direkt im Adminpanel.
