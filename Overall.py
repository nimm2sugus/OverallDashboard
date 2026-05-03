import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- APP CONFIG ---
st.set_page_config(page_title="re cap Intelligence OS", layout="wide")
st.title("📊 Energy Market Intelligence OS")

# --- CACHED DATA ENGINE ---

@st.cache_data(show_spinner=False)
def read_single_csv(file_path):
    """Liest eine einzelne Datei hocheffizient ein."""
    for enc in ['utf-16', 'utf-8-sig', 'latin-1']:
        for separator in [';', ',']:
            try:
                # Schneller Check: Wo fängt der Header an?
                header_idx = 0
                with open(file_path, 'r', encoding=enc) as f:
                    for i in range(15):
                        line = f.readline()
                        if "Datum" in line:
                            header_idx = i
                            break
                
                df = pd.read_csv(file_path, sep=separator, decimal=',', 
                                 skiprows=header_idx, encoding=enc, 
                                 on_bad_lines='skip', engine='c') # 'c' ist schneller als 'python'
                
                if 'Datum' in df.columns and 'Anfang' in df.columns:
                    # Zeitstempel optimiert konvertieren
                    df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True, errors='coerce')
                    df = df.dropna(subset=['Timestamp'])
                    
                    prefix = file_path.split('_202')[0]
                    val_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                    
                    # Spalten umbenennen
                    new_names = {c: f"{prefix} | {c}" for c in val_cols}
                    df = df.rename(columns=new_names)
                    
                    return df[['Timestamp'] + list(new_names.values())].set_index('Timestamp'), list(new_names.values()), prefix
            except:
                continue
    return None, [], None

@st.cache_data(show_spinner="Kombiniere Datenbank...")
def get_final_dataframe():
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 10]
    if not files: return None, {}

    all_dfs = []
    structure = {}

    for f in files:
        df_part, cols, prefix = read_single_csv(f)
        if df_part is not None:
            all_dfs.append(df_part)
            structure[prefix] = cols
    
    if not all_dfs: return None, {}
    
    # Effizientes Mergen
    combined = pd.concat(all_dfs, axis=1).sort_index()
    # Nur 1h-Daten auffüllen, um Löcher im 15min-Grid zu stopfen
    combined = combined.ffill(limit=3).reset_index()
    return combined, structure

# --- UI LOGIK ---

# Spinner nur beim ersten Laden oder bei Datei-Änderung
df, structure = get_final_dataframe()

if df is not None:
    st.sidebar.header("📂 Filter & Auswahl")
    
    # Reset Button für Cache
    if st.sidebar.button("Daten neu einlesen"):
        st.cache_data.clear()
        st.rerun()

    selected_metrics = []
    
    # Hierarchische Auswahl
    for group, columns in structure.items():
        with st.sidebar.expander(f"📄 {group}"):
            for col in columns:
                clean_name = col.split(" | ")[1]
                if st.checkbox(clean_name, key=col):
                    selected_metrics.append(col)

    if selected_metrics:
        # Plotting - Hier nutzen wir den bereits geladenen 'df'
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        for m in selected_metrics:
            is_right = any(x in m.lower() for x in ["mw", "verbrauch", "last", "leistung", "erzeugung"])
            
            fig.add_trace(go.Scatter(
                x=df['Timestamp'], 
                y=df[m], 
                name=m.split(" | ")[0][:10] + ".." + m.split(" | ")[1][-15:], # Name kürzen für Legende
                line=dict(shape='hv' if not is_right else 'linear', width=1.5),
                mode='lines'
            ), secondary_y=is_right)
        
        fig.update_layout(
            template="plotly_dark", 
            hovermode="x unified", 
            height=700,
            legend=dict(orientation="h", y=1.08, xanchor="center", x=0.5)
        )
        
        fig.update_yaxes(title_text="Preis [€]", secondary_y=False)
        fig.update_yaxes(title_text="Volumen [MW]", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("💡 Bitte wähle links die gewünschten Datenreihen aus.")
else:
    st.error("Keine SMARD-Daten im Verzeichnis gefunden.")
