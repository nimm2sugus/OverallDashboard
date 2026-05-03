import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import io

st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")

st.title("📊 Energy Intelligence Dashboard | re cap")

# --- FUNKTION: ROBUSTER SMARD PARSER ---
@st.cache_data
def load_and_merge_smard_files():
    # Suche alle CSV Dateien (ignoriere Fragmente wie --.csv)
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 10]
    
    if not files:
        return pd.DataFrame()

    data_frames = []
    
    for file in files:
        try:
            # 1. Datei einlesen (wir probieren verschiedene Encodings)
            # Wir lesen die Datei erst als Text, um die Kopfzeile zu finden
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Suche die Zeile, in der "Datum" steht (Header-Suche)
            header_idx = 0
            for i, line in enumerate(lines[:10]): # Prüfe die ersten 10 Zeilen
                if "Datum" in line and "Anfang" in line:
                    header_idx = i
                    break
            
            # Jetzt mit dem richtigen Header einlesen
            df = pd.read_csv(file, sep=';', decimal=',', skiprows=header_idx, encoding='utf-8', on_bad_lines='skip')
            
            if 'Datum' not in df.columns:
                continue

            # Zeitstempel fixen
            df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True)
            
            fname = file.lower()
            new_cols = {'Timestamp': 'Timestamp'}
            
            # --- INTELLIGENTES SPALTEN-MAPPING ---
            # Wir suchen nach Schlagworten im Dateinamen und Spaltennamen
            if "gro_handelspreise" in fname:
                target = "Preis_Intraday" if "viertelstunde" in fname else "Preis_DayAhead"
                val_col = [c for c in df.columns if "deutschland" in c.lower() or "eur" in c.lower()][0]
                df = df.rename(columns={val_col: target})
            
            elif "realisierte_erzeugung" in fname:
                for col in df.columns:
                    if "Photovoltaik" in col.lower(): df = df.rename(columns={col: "PV_Real"})
                    if "wind onshore" in col.lower(): df = df.rename(columns={col: "Wind_On_Real"})
            
            elif "realisierter_stromverbrauch" in fname:
                val_col = [c for c in df.columns if "gesamt" in c.lower() or "mw" in c.lower()][0]
                df = df.rename(columns={val_col: "Netzlast"})
            
            elif "prognostizierte_erzeugung" in fname:
                pref = "Prog_Intra" if "intraday" in fname else "Prog_DA"
                for col in df.columns:
                    if "photovoltaik" in col.lower(): df = df.rename(columns={col: f"PV_{pref}"})
            
            else:
                continue

            # Nur relevante Spalten behalten
            keep = ["Timestamp", "Preis_Intraday", "Preis_DayAhead", "PV_Real", "Wind_On_Real", "Netzlast", "PV_Prog_Intra", "PV_Prog_DA"]
            valid_keep = [c for c in keep if c in df.columns]
            
            if len(valid_keep) > 1:
                data_frames.append(df[valid_keep].set_index('Timestamp'))
                
        except Exception as e:
            st.sidebar.warning(f"Datei übersprungen: {file} ({str(e)[:50]}...)")

    if not data_frames:
        return pd.DataFrame()

    # Zusammenführen aller Dateien
    master_df = pd.concat(data_frames, axis=1).sort_index()
    # Duplikate bei Spalten entfernen und Index zu Spalte machen
    master_df = master_df.loc[:, ~master_df.columns.duplicated()].reset_index()
    return master_df

# --- UI LOGIK ---
df = load_and_merge_smard_files()

if not df.empty:
    st.sidebar.success(f"✅ {len(df)} Datenpunkte geladen")
    
    # KPIs
    c1, c2, c3 = st.columns(3)
    if 'Preis_Intraday' in df.columns:
        c1.metric("Ø Intraday-Preis", f"{df['Preis_Intraday'].mean():.2f} €")
    if 'PV_Real' in df.columns:
        c2.metric("Max PV Erzeugung", f"{df['PV_Real'].max():,.0f} MW")
    if 'Netzlast' in df.columns:
        c3.metric("Ø Netzlast", f"{df['Netzlast'].mean():,.0f} MW")

    # Chart
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    if 'Preis_Intraday' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['Preis_Intraday'], name="Preis 15min", line=dict(color='red', shape='hv')), secondary_y=False)
    if 'Preis_DayAhead' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['Preis_DayAhead'], name="Preis 1h (DA)", line=dict(color='white', dash='dot')), secondary_y=False)
    
    if 'PV_Real' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['PV_Real'], name="PV Real", fill='tozeroy', line=dict(width=0, color='gold'), opacity=0.4), secondary_y=True)
    if 'Netzlast' in df.columns:
        fig.add_trace(go.Scatter(x=df['Timestamp'], y=df['Netzlast'], name="Netzlast", line=dict(color='gray', width=1)), secondary_y=True)

    fig.update_layout(template="plotly_dark", hovermode="x unified", height=600, 
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)
    
    # Daten-Check für dich
    with st.expander("Gefundene Daten-Spalten"):
        st.write(list(df.columns))

else:
    st.error("Keine Daten erkannt.")
    st.info("Bitte prüfen, ob die CSVs das Standard-SMARD Format haben.")
