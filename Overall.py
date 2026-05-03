import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")

st.title("📊 Energy Intelligence Dashboard | re cap")

# --- DIAGNOSE: WAS SIEHT DIE APP? ---
st.sidebar.header("🛠 Diagnose")
all_files = os.listdir('.')
st.sidebar.write("Gefundene Dateien im Repo:")
st.sidebar.write([f for f in all_files if not f.startswith('.')]) # Zeigt alle Dateien außer versteckten

# --- FUNKTION: SMARD CSV PARSER ---
@st.cache_data
def load_and_merge_smard_files():
    # Suche alle CSV Dateien (egal ob .csv oder .CSV)
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv')]
    
    if not files:
        return pd.DataFrame()

    data_frames = []
    
    for file in files:
        try:
            # SMARD Dateien haben oft Semikolon; wir versuchen es robust zu lesen
            # Manche SMARD Exports haben eine Kopfzeile, manche nicht. 
            # Wir suchen die Zeile, in der "Datum" steht.
            df = pd.read_csv(file, sep=';', decimal=',', encoding='utf-8', on_bad_lines='skip')
            
            # Falls UTF-8 nicht klappt, versuche latin-1
            if 'Datum' not in df.columns:
                df = pd.read_csv(file, sep=';', decimal=',', encoding='latin-1', on_bad_lines='skip')

            if 'Datum' not in df.columns:
                continue

            # Zeitstempel erstellen
            df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], format='%d.%m.%Y %H:%M')
            
            # Mapping der Spalten basierend auf Schlagworten im Dateinamen
            fname = file.lower()
            
            # Zielspalten-Logik
            if "gro_handelspreise" in fname:
                col_type = "Preis_Viertelstunde" if "viertelstunde" in fname else "Preis_Stunde"
                # Suche die Spalte mit dem EUR Wert
                val_col = [c for c in df.columns if "EUR" in c][0]
                df = df.rename(columns={val_col: col_type})
            
            elif "realisierte_erzeugung" in fname:
                for col in df.columns:
                    if "Photovoltaik" in col: df = df.rename(columns={col: "PV_Real"})
                    if "Wind Onshore" in col: df = df.rename(columns={col: "Wind_On_Real"})
            
            elif "realisierter_stromverbrauch" in fname:
                val_col = [c for c in df.columns if "MW" in c][0]
                df = df.rename(columns={val_col: "Netzlast"})
            
            elif "prognostizierte_erzeugung" in fname:
                suffix = "Intra" if "intraday" in fname else "DA"
                for col in df.columns:
                    if "Photovoltaik" in col: df = df.rename(columns={col: f"PV_Prog_{suffix}"})

            # Nur Timestamp und die neuen umbenannten Spalten behalten
            keep = ["Timestamp", "Preis_Viertelstunde", "Preis_Stunde", "PV_Real", "Wind_On_Real", "Netzlast", "PV_Prog_Intra", "PV_Prog_DA"]
            existing_keep = [c for c in keep if c in df.columns]
            
            if len(existing_keep) > 1:
                data_frames.append(df[existing_keep].set_index('Timestamp'))
                
        except Exception as e:
            st.sidebar.error(f"Fehler bei {file}: {e}")

    if not data_frames:
        return pd.DataFrame()

    # Zusammenführen
    master_df = pd.concat(data_frames, axis=1).sort_index().reset_index()
    # Duplikate entfernen (falls Spalten doppelt vorhanden)
    master_df = master_df.loc[:, ~master_df.columns.duplicated()]
    return master_df

# --- HAUPTTEIL ---
df = load_and_merge_smard_files()

if not df.empty:
    st.sidebar.success(f"Daten geladen: {len(df)} Zeilen")
    
    # Zeige die ersten Zeilen zur Kontrolle
    with st.expander("Rohdaten-Vorschau (Top 5)"):
        st.write(df.head())

    # --- GRAFIK ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Preise
    if 'Preis_Viertelstunde' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['Preis_Viertelstunde'], name="Preis 15min", line=dict(color='red', shape='hv')), secondary_y=False)
    if 'Preis_Stunde' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['Preis_Stunde'], name="Preis 1h", line=dict(color='white', dash='dot')), secondary_y=False)
    
    # Erzeugung
    if 'PV_Real' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['PV_Real'], name="PV Real", fill='tozeroy', line=dict(width=0, color='gold'), opacity=0.5), secondary_y=True)
    if 'Netzlast' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['Netzlast'], name="Netzlast", line=dict(color='gray', width=1)), secondary_y=True)

    fig.update_layout(template="plotly_dark", hovermode="x unified", height=600)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Keine CSV-Dateien gefunden oder erkannt.")
    st.info("Prüfe die Liste in der Seitenleiste (Sidebar). Wenn dort keine Dateien stehen, liegen sie nicht im Hauptverzeichnis des Repos.")
