import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence", layout="wide")

st.title("📊 Energy Intelligence Hub | re cap")

@st.cache_data
def load_data_robust():
    # 1. Dateien filtern (nur die echten SMARD CSVs)
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and '2025' in f]
    
    if not files:
        return pd.DataFrame(), {}

    master_dfs = []
    file_structure = {}

    for file in files:
        df = None
        # 2. Versuche verschiedene Kodierungen (SMARD nutzt oft UTF-16 für 15min-Daten)
        for enc in ['utf-8-sig', 'utf-16', 'latin-1', 'cp1252']:
            try:
                # Suche Header-Zeile manuell
                with open(file, 'r', encoding=enc) as f:
                    lines = f.readlines()
                
                header_idx = -1
                sep = ';'
                for i, line in enumerate(lines[:20]):
                    if "Datum" in line and "Anfang" in line:
                        header_idx = i
                        sep = ';' if ';' in line else (',' if ',' in line else '\t')
                        break
                
                if header_idx != -1:
                    df = pd.read_csv(file, sep=sep, decimal=',', skiprows=header_idx, encoding=enc, on_bad_lines='skip')
                    break # Erfolg!
            except:
                continue
        
        # 3. Daten verarbeiten wenn Laden erfolgreich
        if df is not None and not df.empty:
            df.columns = [str(c).strip() for c in df.columns]
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                # Zeitstempel fixen
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Timestamp'])
                
                # Präfix erstellen (z.B. "Gro_handelspreise")
                prefix = file.split('_2025')[0]
                val_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                # Spalten umbenennen für Eindeutigkeit
                new_names = {c: f"{prefix} | {c}" for c in val_cols}
                df = df.rename(columns=new_names)
                
                file_structure[prefix] = list(new_names.values())
                master_dfs.append(df[['Timestamp'] + list(new_names.values())].set_index('Timestamp'))

    if not master_dfs:
        return pd.DataFrame(), {}

    # 4. Mergen und 1h-Daten auf 15min auffüllen
    combined = pd.concat(master_dfs, axis=1).sort_index().ffill(limit=3).reset_index()
    return combined, file_structure

# --- UI LOGIK ---
df, structure = load_data_robust()

if not df.empty:
    st.sidebar.title("🔍 Daten-Katalog")
    selected_metrics = []
    
    for group, cols in structure.items():
        with st.sidebar.expander(f"📁 {group}"):
            for c in cols:
                # Anzeige im UI verschönern
                clean_name = c.split(" | ")[1]
                if st.checkbox(clean_name, key=c):
                    selected_metrics.append(c)

    if selected_metrics:
        # Chart erstellen
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        for m in selected_metrics:
            # MW und Last nach rechts, Preise nach links
            is_mw = any(x in m.lower() for x in ["mw", "verbrauch", "last", "leistung"])
            
            fig.add_trace(
                go.Scatter(x=df['Timestamp'], y=df[m], name=m, 
                           line=dict(shape='hv' if not is_mw else 'linear')),
                secondary_y=is_mw
            )

        fig.update_layout(template="plotly_dark", hovermode="x unified", height=700)
        fig.update_yaxes(title_text="Preis [€/MWh]", secondary_y=False)
        fig.update_yaxes(title_text="Leistung [MW]", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Wähle links in der Sidebar die Daten aus, die du vergleichen möchtest.")
else:
    st.error("Keine gültigen SMARD-Daten erkannt.")
    st.markdown("### Fehleranalyse:")
    st.write(f"Gefundene Dateien im Repo: {os.listdir('.')}")
    st.info("Tipp: Die CSVs müssen direkt von SMARD kommen und 'Datum' sowie 'Anfang' als Spalten enthalten.")
