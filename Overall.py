import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Intelligence OS", layout="wide")
st.title("📊 Energy Market Intelligence OS")

@st.cache_data
def load_data_simple():
    # Suche alle CSV-Dateien
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 5]
    if not files: return None, {}

    all_dfs = []
    structure = {} # Speichert Dateiname -> Liste der Spalten

    for file in files:
        df = None
        # Probiere Encodings (UTF-16 ist oft der Grund für Fehler bei 15min-Daten)
        for enc in ['utf-16', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                # Automatisches Trennzeichen (sep=None) erkennt ; , oder Tab
                temp_df = pd.read_csv(file, sep=None, engine='python', encoding=enc, decimal=',', on_bad_lines='skip')
                
                # Suche die Zeile, in der "Datum" steht, falls Metadaten drüber sind
                if 'Datum' not in temp_df.columns:
                    for i in range(1, 15):
                        retry_df = pd.read_csv(file, sep=None, engine='python', encoding=enc, decimal=',', skiprows=i)
                        if 'Datum' in retry_df.columns:
                            temp_df = retry_df
                            break
                
                if 'Datum' in temp_df.columns:
                    # Zeitstempel bauen
                    temp_df['Timestamp'] = pd.to_datetime(temp_df['Datum'] + ' ' + temp_df['Anfang'], dayfirst=True, errors='coerce')
                    temp_df = temp_df.dropna(subset=['Timestamp'])
                    
                    # Spaltennamen säubern und mit Dateiname kennzeichnen
                    prefix = file.split('_202')[0]
                    val_cols = [c for c in temp_df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                    
                    # Mapping für die Sidebar
                    new_names = {c: f"{prefix} | {c}" for c in val_cols}
                    temp_df = temp_df.rename(columns=new_names)
                    structure[prefix] = list(new_names.values())
                    
                    all_dfs.append(temp_df[['Timestamp'] + list(new_names.values())].set_index('Timestamp'))
                    df = temp_df
                    break
            except:
                continue
    
    if not all_dfs: return None, {}
    
    # Alles zusammenführen & Lücken (bei 1h-Daten) füllen
    combined = pd.concat(all_dfs, axis=1).sort_index().ffill(limit=3).reset_index()
    return combined, structure

# --- UI LOGIK ---
df, structure = load_data_simple()

if df is not None:
    st.sidebar.header("📂 Datei- & Spaltenauswahl")
    selected_metrics = []
    
    # Hierarchischer Filter: Datei -> Spalten
    for file_group, columns in structure.items():
        with st.sidebar.expander(f"📄 {file_group}"):
            for col in columns:
                clean_name = col.split(" | ")[1] # Zeige nur den Original-Header im UI
                if st.checkbox(clean_name, key=col):
                    selected_metrics.append(col)

    if selected_metrics:
        # Grafik
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for m in selected_metrics:
            # MW/Leistung rechts, Preise links
            is_right = any(x in m.lower() for x in ["mw", "verbrauch", "last", "leistung", "erzeugung"])
            fig.add_trace(go.Scatter(x=df['Timestamp'], y=df[m], name=m, 
                                     line=dict(shape='hv' if not is_right else 'linear')), 
                          secondary_y=is_right)
        
        fig.update_layout(template="plotly_dark", hovermode="x unified", height=700,
                          legend=dict(orientation="h", y=1.08))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Wähle links in der Sidebar Dateien aus und hake die gewünschten Spalten an.")
else:
    st.error("Keine SMARD-Daten gefunden. Bitte prüfe die Dateien im GitHub-Repo.")
