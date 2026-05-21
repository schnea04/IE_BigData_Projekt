"""
validate_chess_errors.py
-------------------------------------------------------------------
Eigenstaendige Validierung der chess_games-Fehleranalyse.

Zweck: Nachvollziehen, WELCHE Spalten echte Fehler enthalten und welcher
Fehlertyp (MV / T / IV / WV) jeweils vorliegt -- BEVOR ihr die Pipeline baut.

Ausfuehren:
    pip install pandas
    python validate_chess_errors.py

Die beiden CSV-Pfade unten ggf. anpassen.
Jeder ABSCHNITT entspricht einer Notebook-Zelle und kann nach Databricks
kopiert werden (dort spark.read.csv statt pd.read_csv).
-------------------------------------------------------------------
"""

import pandas as pd

CLEAN_PATH = "chess_games.csv"
DIRTY_PATH = "dirty_chess_games.csv"

# Wichtig: dtype=str + keep_default_na=False  -> nichts wird automatisch
# umgewandelt. So vergleichen wir die ROHWERTE und nicht pandas'
# Interpretation davon. "" bleibt "" und wird nicht zu NaN.
clean = pd.read_csv(CLEAN_PATH, dtype=str, keep_default_na=False)
dirty = pd.read_csv(DIRTY_PATH, dtype=str, keep_default_na=False)


# =====================================================================
# ABSCHNITT 1 -- Grundstruktur und Ausrichtung der beiden Dateien
# =====================================================================
print("=" * 70)
print("ABSCHNITT 1 -- Struktur & Ausrichtung")
print("=" * 70)
print(f"clean: {clean.shape[0]} Zeilen, {clean.shape[1]} Spalten")
print(f"dirty: {dirty.shape[0]} Zeilen, {dirty.shape[1]} Spalten")
print(f"Zusatzspalte in dirty: {set(dirty.columns) - set(clean.columns)}")

# Damit ein zeilenweiser Vergleich gueltig ist, muss die Reihenfolge passen.
ids_aligned = (clean["id"].values == dirty["id"].values).all()
print(f"id-Spalte identisch & gleiche Reihenfolge: {ids_aligned}")

# STOLPERFALLE: id ist NICHT eindeutig -> nicht als alleiniger Join-Key nutzen!
print(f"id eindeutig? {clean['id'].nunique()} unique von {len(clean)} "
      f"-> {len(clean) - clean['id'].nunique()} Duplikate")
print("=> In Gold auf positionsbasierten row_id joinen, nicht auf id.")

# Die 'changed'-Spalte ist ein Zeilen-Flag (1 = Zeile wurde manipuliert).
# Nutzbar als grobe Gegenprobe -- die ZELLEN-Wahrheit kommt aber aus dem
# direkten Vergleich clean vs dirty, nicht aus diesem Flag.
print("\n'changed'-Flag Verteilung:")
print(dirty["changed"].value_counts().to_string())


# =====================================================================
# ABSCHNITT 2 -- Differenz pro Spalte (Rohvergleich)
# =====================================================================
print("\n" + "=" * 70)
print("ABSCHNITT 2 -- Differierende Zellen pro Spalte (roh)")
print("=" * 70)
shared = [c for c in clean.columns if c in dirty.columns]
diff_counts = {}
for c in shared:
    n = int((clean[c].values != dirty[c].values).sum())
    diff_counts[c] = n
    print(f"  {c:18s}: {n:6d}  ({100 * n / len(clean):5.2f} %)")

print("\nHinweis: Hohe Werte heissen NICHT automatisch 'Fehlerfeld'.")
print("Abschnitt 3 trennt echte Fehler von Export-Artefakten.")


# =====================================================================
# ABSCHNITT 3 -- Schein-Fehler entlarven (Export-Artefakte)
# =====================================================================
print("\n" + "=" * 70)
print("ABSCHNITT 3 -- Welche Differenzen sind KEINE echten Fehler?")
print("=" * 70)

# rated: clean nutzt TRUE/FALSE, dirty True/False. Wenn ALLE Differenzen
# beim Kleinschreiben verschwinden, ist es ein reines Formatproblem aus
# dem CSV-Export -- kein absichtlich eingebauter Fehler.
m_rated = clean["rated"].values != dirty["rated"].values
same_lower = clean["rated"].str.lower().values == dirty["rated"].str.lower().values
print(f"rated      : {m_rated.sum()} Differenzen, davon "
      f"{int((m_rated & same_lower).sum())} nur Gross-/Kleinschreibung")
print(f"             echte Wertfehler: {int((m_rated & ~same_lower).sum())} "
      f"-> {'KEIN Fehlerfeld' if (m_rated & ~same_lower).sum() == 0 else 'pruefen!'}")

# created_at / last_move_at: wissenschaftliche Notation vs Float-Schreibweise.
# Beide beschreiben denselben Zeitstempel -> Format, kein Fehler.
for c in ["created_at", "last_move_at"]:
    print(f"{c:11s}: clean-Beispiel {clean[c].iloc[0]!r} vs "
          f"dirty {dirty[c].iloc[0]!r}  -> Formatdifferenz, KEIN Fehlerfeld")

print("\n=> FINGER WEG von rated, created_at, last_move_at als Fehlerfelder.")


# =====================================================================
# ABSCHNITT 4 -- Die 5 echten Fehlerfelder im Detail
# =====================================================================
print("\n" + "=" * 70)
print("ABSCHNITT 4 -- Echte Fehlerfelder: Typ + Beispiele")
print("=" * 70)


def zeige_beispiele(col, n=6):
    """Gibt die ersten n Zeilen aus, in denen clean != dirty ist."""
    m = clean[col].values != dirty[col].values
    bsp = pd.DataFrame({"clean": clean[col][m], "dirty": dirty[col][m]}).head(n)
    print(bsp.to_string())
    return m


# --- winner: Missing Value (MV) -------------------------------------
print("\n--- winner  [Fehlertyp: MISSING VALUE] ---")
m = zeige_beispiele("winner")
leer = int((dirty["winner"][m] == "").sum())
print(f"Pruefung: {m.sum()} Differenzen, davon {leer} geleert (\"\").")
print(f"Erlaubte Werte: {sorted(v for v in clean['winner'].unique())}")

# --- victory_status: Illegal Value (IV) -----------------------------
print("\n--- victory_status  [Fehlertyp: ILLEGAL VALUE] ---")
m = zeige_beispiele("victory_status")
print(f"Erlaubte Werte (clean): {sorted(clean['victory_status'].unique())}")
print(f"Werte in dirty:         {sorted(dirty['victory_status'].unique())}")
print("=> 'regicide' ist kein gueltiger Status -> illegaler Wert.")

# --- white_rating / black_rating: Illegal/Wrong Value ---------------
for col in ["white_rating", "black_rating"]:
    print(f"\n--- {col}  [Fehlertyp: ILLEGAL/WRONG VALUE] ---")
    m = zeige_beispiele(col)
    c_num = pd.to_numeric(clean[col])
    d_num = pd.to_numeric(dirty[col])
    print(f"gueltiger Bereich (clean): {c_num.min()} - {c_num.max()}")
    print(f"Bereich der Fehlerwerte:   {d_num[m].min()} - {d_num[m].max()}")
    print(f"Fehlerwerte, die plausibel aussehen (<3000): "
          f"{int((d_num[m] < 3000).sum())}")
    print("=> Erkennung trivial (alle Fehler 5-stellig), "
          "exakte Reparatur aber nicht moeglich -> unverifizierbar.")

# --- opening_name: Typo (T) -----------------------------------------
print("\n--- opening_name  [Fehlertyp: TYPO] ---")
zeige_beispiele("opening_name", n=8)
# opening_eco ist sauber -> als Reparatur-Kontext nutzbar
eco_diffs = int((clean["opening_eco"].values != dirty["opening_eco"].values).sum())
eco_map = clean.groupby("opening_eco")["opening_name"].nunique()
print(f"\nopening_eco Differenzen: {eco_diffs}  -> opening_eco ist sauber.")
print(f"ECO-Codes gesamt: {len(eco_map)}, "
      f"davon mit mehreren Namen: {int((eco_map > 1).sum())}")
print("=> opening_eco als Kandidaten-Filter fuers Fuzzy-Matching nutzbar,")
print("   aber kein eindeutiges Reverse-Lookup moeglich.")


# =====================================================================
# ABSCHNITT 5 -- Zusammenfassung
# =====================================================================
print("\n" + "=" * 70)
print("ABSCHNITT 5 -- Zusammenfassung: Fehlerfelder fuer die Pipeline")
print("=" * 70)
echte_fehlerfelder = {
    "opening_name":   "Typo",
    "winner":         "Missing Value",
    "victory_status": "Illegal Value",
    "black_rating":   "Illegal/Wrong Value",
    "white_rating":   "Illegal/Wrong Value",
}
for col, typ in echte_fehlerfelder.items():
    print(f"  {col:16s} {diff_counts[col]:6d} Fehler   [{typ}]")
print("\nBei 3 Personen / 4 Feldern: opening_name, winner, victory_status")
print("plus EIN Rating waehlen. Das fuenfte Feld optional als Bonus.")
