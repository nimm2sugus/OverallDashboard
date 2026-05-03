import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="re cap Energy Hub", layout="wide")
st.title("⚡ re cap Energy Intelligence")

def load_data():
    # Suche alle CSV-Dateien im Ordner
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv')]
    all_dfs = []
    
    for f in files:
        try:
            # 1. Wir finden heraus, in welcher Zeile die Tabelle wirklich startet
            skip = 0
            with open(f, 'r', encoding='utf-8', errors='ignore') as temp_f:
                for i, line in enumerate(temp_f):
                    if "Datum" in line and "Anfang" in line:
                        skip = i
                        break
            
            # 2. Datei einlesen mit dem gefundenen Header-Start
            df = pd.read_csv(f, sep=';', decimal=',', skiprows=skip, encoding='utf-8', on_bad_lines='skip')
            
            # Spaltennamen säubern (Leerzeichen entfernen)
            df.columns = df.columns.str.strip()

            # Prüfen ob wichtige Spalten da sind
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                # Zeitstempel bauen
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True)
                
                # Nur relevante Spalten behalten (Timestamp + die Werte-Spalte)
                # Wir nehmen alle Spalten außer die Zeit-Spalten
                cols_to_keep = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                # Wir behalten nur den Timestamp und die erste Werte-Spalte für die Übersichtlichkeit
                if cols_to_keep:
                    temp_df = df[['Timestamp', cols_to_keep[0]]]
                    all_dfs.append(temp_df.set_index('Timestamp'))
        except Exception as e:
            st.sidebar.warning(f"Konnte {f} nicht laden: {e}")

    if all_dfs:
        # Alles zusammenführen
        merged = pd.concat(all_dfs, axis=1).sort_index().reset_index()
        return merged
    return None

# --- APP LOGIK ---
df = load_data()

if df is not None and not df.empty:
    st.success(f"Daten erfolgreich kombiniert! ({len(df)} Zeilen)")

    # Filter für die Spaltenauswahl
    available_cols = [c for c in df.columns if c != 'Timestamp']
    selected_metrics = st.sidebar.multiselect(
        "Metriken auswählen:", 
        available_cols, 
        default=available_cols[:2] if len(available_cols) > 1 else available_cols
    )

    if selected_metrics:
        # Grafik erstellen
        fig = px.line(df, x='Timestamp', y=selected_metrics, 
                      title="Marktdaten Vergleich (15-Min / 1-Std)",
                      template="plotly_dark",
                      color_discrete_sequence=px.colors.qualitative.Pastel)
        
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        
        # Rohdaten Tabelle
        with st.expander("Tabellarische Ansicht"):
            st.dataframe(df)
    else:
        st.info("Bitte wählen Sie mindestens eine Metrik in der Seitenleiste aus.")
else:
    st.error("Keine gültigen SMARD-Daten gefunden.")
    st.info("Hinweis: Stellen Sie sicher, dass die CSV-Dateien Trennzeichen ';' enthalten.")
