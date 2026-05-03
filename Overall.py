import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import io

st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")

st.title("📊 Energy Intelligence Hub | re cap")

# --- DER INTELLIGENTE PARSER ---
@st.cache_data
def load_data_intelligent():
    # 1. Alle CSV-Dateien finden
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 10]
    
    if not files:
        return pd.DataFrame(), {}

    master_dfs = []
    file_structure = {}

    for file in files:
        try:
            # 2. Encoding & Header Forensik
            # Wir probieren erst utf-8-sig (wegen Excel-BOM), dann latin-1
            encoding = 'utf-8-sig'
            try:
                with open(file, 'r', encoding=encoding) as f:
                    lines = f.readlines()
            except:
                encoding = 'latin-1'
                with open(file, 'r', encoding=encoding) as f:
                    lines = f.readlines()

            # 3. Den Tabellenstart finden (Suche nach Datum UND Anfang)
            header_idx = -1
            sep = None
            for i, line in enumerate(lines):
                # Wir entfernen unsichtbare Zeichen und prüfen auf die Kern-Header
                clean_line = line.replace('"', '').replace("'", "")
                if "Datum" in clean_line and "Anfang" in clean_line:
                    header_idx = i
                    # Trennzeichen erkennen
                    sep = ';' if ';' in line else ','
                    break
            
            if header_idx == -1:
                continue

            # 4. Daten laden mit automatischer Typerkennung
            df = pd.read_csv(
                file, 
                sep=sep, 
                decimal=',', 
                skiprows=header_idx, 
                encoding=encoding, 
                on_bad_lines='skip',
                engine='python'
            )

            # 5. Spaltennamen "säubern" (entfernt \xa0, \n, und Leerzeichen)
            df.columns = [str(c).replace('\xa0', ' ').strip() for c in df.columns]
            
            # 6. Zeitstempel-Validierung
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Timestamp'])
                
                # Werte-Spalten extrahieren (alles außer Zeit-Referenzen)
                value_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                # Datei-Präfix für Eindeutigkeit (z.B. "Gro_handelspreise")
                prefix = file.split('_202')[0] if '_' in file in file else "Daten"
                
                # Spalten umbenennen: Präfix | Echter Name
                new_col_names = {c: f"{prefix} | {c}" for c in value_cols}
                df = df.rename(columns=new_col_names)
                
                # In Struktur-Dictionary speichern für Sidebar
                file_structure[prefix] = list(new_col_names.values())
                
                # Nur Timestamp und Daten-Spalten behalten
                master_dfs.append(df[['Timestamp'] + list(new_names for new_names in new_col_names.values())].set_index('Timestamp'))
        
        except Exception as e:
            st.sidebar.error(f"Konnte {file} nicht verarbeiten: {e}")

    if not master_dfs:
        return pd.DataFrame(), {}

    # 7. Daten-Fusion (Synchronisierung von 15m und 1h)
    combined_df = pd.concat(master_dfs, axis=1).sort_index()
    # Auffüllen von 1h-Werten auf 15m-Raster für lückenlose Grafik
    combined_df = combined_df.ffill(limit=3) 
    
    return combined_df.reset_index(), file_structure

# --- UI EXECUTION ---
df, structure = load_data_intelligent()

if not df.empty:
    # SIDEBAR: Hierarchische Auswahl
    st.sidebar.title("🔍 Daten-Katalog")
    st.sidebar.info("Wähle Kategorien aus den exportierten SMARD-Files:")
    
    selected_metrics = []
    for file_group, columns in structure.items():
        with st.sidebar.expander(f"📁 {file_group}"):
            for col in columns:
                # Wir zeigen nur den bereinigten Namen der Spalte an
                clean_label = col.split(" | ")[1]
                if st.checkbox(clean_label, key=col):
                    selected_metrics.append(col)

    # HAUPTANZEIGE
    if selected_metrics:
        # GRAFIK-ENGINE
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        for metric in selected_metrics:
            # Intelligenz: Preise nach links, Leistungen (MW/Last) nach rechts
            is_volume = any(x in metric.lower() for x in ["mw", "last", "verbrauch", "leistung"])
            
            fig.add_trace(
                go.Scatter(
                    x=df['Timestamp'], 
                    y=df[metric], 
                    name=metric,
                    line=dict(shape='hv' if not is_volume else 'linear'),
                    connectgaps=True
                ),
                secondary_y=is_volume
            )

        fig.update_layout(
            template="plotly_dark", 
            hovermode="x unified", 
            height=700,
            legend=dict(orientation="h", y=1.05)
        )
        
        fig.update_yaxes(title_text="Preis [€/MWh]", secondary_y=False)
        fig.update_yaxes(title_text="Leistung / Last [MW]", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # TABELLE
        with st.expander("Rohdaten & Statistik"):
            st.write(df[['Timestamp'] + selected_metrics].describe())
            st.dataframe(df[['Timestamp'] + selected_metrics])
    else:
        st.info("← Bitte wähle rechts in der Sidebar die gewünschten Datenreihen aus.")

else:
    st.error("Keine gültigen SMARD-Daten gefunden.")
    st.warning("Diagnose: Die Dateien liegen im Repo, aber der Header 'Datum;Anfang' wurde nicht erkannt.")
    # Debug Hilfe
    if st.checkbox("Debug: Dateiliste anzeigen"):
        st.write(os.listdir('.'))
