import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="STARK Energy Hub", layout="wide")
st.title("⚡ STARK Energy Intelligence")

# --- DATEIEN LADEN ---
def load_data():
    files = [f for f in os.listdir('.') if f.endswith('.csv') and '2025' in f]
    all_dfs = []
    
    for f in files:
        # Einlesen: Wir überspringen keine Zeilen, sondern suchen Spalten
        df = pd.read_csv(f, sep=';', decimal=',', encoding='utf-8')
        
        # Zeitstempel aus Datum und Anfang bauen
        df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True)
        
        # Nur die Spalte behalten, die NICHT Datum/Anfang/Ende heißt
        cols_to_keep = ['Timestamp']
        for col in df.columns:
            if col not in ['Datum', 'Anfang', 'Ende', 'Timestamp']:
                cols_to_keep.append(col)
        
        all_dfs.append(df[cols_to_keep].set_index('Timestamp'))

    # Alles zusammenführen
    if all_dfs:
        merged = pd.concat(all_dfs, axis=1).sort_index().reset_index()
        return merged
    return None

df = load_data()

if df is not None:
    st.success(f"Daten geladen! Zeitraum: {df['Timestamp'].min()} bis {df['Timestamp'].max()}")

    # --- FILTER ---
    st.sidebar.header("Analyse")
    selected_cols = st.sidebar.multiselect(
        "Werte auswählen:", 
        [c for c in df.columns if c != 'Timestamp'],
        default=[c for c in df.columns if 'Großhandelspreise' in c][:1]
    )

    # --- GRAFIK ---
    if selected_cols:
        fig = px.line(df, x='Timestamp', y=selected_cols, 
                      title="Energie-Marktdaten Analyse",
                      template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    
    # --- TABELLE ---
    with st.expander("Rohdaten ansehen"):
        st.write(df)
else:
    st.error("Bitte lade die SMARD-CSV Dateien hoch!")
