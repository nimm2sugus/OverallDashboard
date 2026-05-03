import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import re

# --- KONFIGURATION ---
st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")
st.title("🛡️ re cap Energy Intelligence OS")

# --- DER ULTIMATIVE PARSER ---

@st.cache_data(show_spinner=False)
def universal_csv_loader(file_path):
    """Versucht eine CSV-Datei mit allen verfügbaren Methoden zu knacken."""
    # 1. Encodings durchprobieren
    for enc in ['utf-16', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            # Datei als Text laden, um Struktur zu analysieren
            with open(file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            
            if not lines: continue
            
            # 2. Header finden (Suche nach Datum/Anfang oder einfach der Zeile mit den meisten Trennern)
            header_idx = 0
            for i, line in enumerate(lines[:20]):
                if "Datum" in line or "Anfang" in line:
                    header_idx = i
                    break
            
            # 3. Trenner automatisch erkennen
            test_line = lines[header_idx]
            sep = ';' if test_line.count(';') > test_line.count(',') else ','
            
            # 4. Laden
            df = pd.read_csv(file_path, sep=sep, decimal=',', skiprows=header_idx, 
                             encoding=enc, on_bad_lines='skip', engine='python')
            
            # 5. Spaltennamen säubern (entfernt Zeilenumbrüche, \xa0, etc.)
            df.columns = [re.sub(r'\s+', ' ', str(c)).strip() for c in df.columns]
            
            # 6. Zeitstempel-Logik
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Timestamp'])
                
                # Datei-Präfix für die Sidebar-Gruppierung
                prefix = file_path.split('_202')[0] if '_' in file_path else file_path.replace('.csv','')
                
                # Nur Daten-Spalten identifizieren
                val_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                # Namen für globale Tabelle eindeutig machen
                renamed = {c: f"{prefix} | {c}" for c in val_cols}
                df = df.rename(columns=renamed)
                
                return df[['Timestamp'] + list(renamed.values())].set_index('Timestamp'), prefix, list(renamed.values())
        except:
            continue
    return None, None, []

@st.cache_data(show_spinner="Baue Datenbank auf... Bitte warten.")
def build_integrated_database():
    """Scannt das Repo und kombiniert alle gefundenen Daten."""
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 5]
    if not files:
        return None, {}

    all_dfs = []
    file_map = {} # Struktur für die Sidebar
    
    for f in files:
        df_part, prefix, cols = universal_csv_loader(f)
        if df_part is not None:
            all_dfs.append(df_part)
            file_map[prefix] = cols
            
    if not all_dfs:
        return None, {}

    # Kombinieren (Outer Join synchronisiert 1h und 15min automatisch)
    combined = pd.concat(all_dfs, axis=1).sort_index()
    # Lücken füllen für saubere Linien
    combined = combined.ffill(limit=3).reset_index()
    return combined, file_map

# --- UI LOGIK ---

# Daten laden (einmalig, danach aus Cache)
df, structure = build_integrated_database()

if df is not None:
    st.sidebar.title("🔍 Daten-Katalog")
    
    if st.sidebar.button("🔄 Datenbank aktualisieren"):
        st.cache_data.clear()
        st.rerun()

    # Hierarchische Filterung
    selected_metrics = []
    for file_group, columns in structure.items():
        with st.sidebar.expander(f"📁 {file_group}"):
            for col in columns:
                # UI-Label ohne das hässliche Präfix
                label = col.split(" | ")[1]
                if st.checkbox(label, key=col):
                    selected_metrics.append(col)

    if selected_metrics:
        # --- GRAFIK-ENGINE ---
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        for m in selected_metrics:
            # MW/Leistung/Last auf rechte Achse, alles andere (Preise) nach links
            is_volume = any(x in m.lower() for x in ["mw", "last", "verbrauch", "leistung", "erzeugung"])
            
            fig.add_trace(
                go.Scatter(
                    x=df['Timestamp'], 
                    y=df[m], 
                    name=m, 
                    line=dict(shape='hv' if not is_volume else 'linear', width=2),
                    connectgaps=True
                ),
                secondary_y=is_volume
            )

        fig.update_layout(
            template="plotly_dark", 
            hovermode="x unified", 
            height=750,
            legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
            margin=dict(l=10, r=10, t=80, b=10)
        )
        
        fig.update_yaxes(title_text="<b>Preis / Basiswerte</b>", secondary_y=False)
        fig.update_yaxes(title_text="<b>Volumen [MW / Last]</b>", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Statistische Quick-Facts
        with st.expander("📊 Statistische Zusammenfassung"):
            st.dataframe(df[selected_metrics].describe().T)
    else:
        st.info("💡 **Willkommen!** Bitte wählen Sie links in der Sidebar die gewünschten Datenreihen aus den geladenen CSV-Dateien aus.")
else:
    st.error("❌ Keine gültigen Daten gefunden.")
    st.markdown("""
    **Analyse:**
    - Befinden sich CSV-Dateien im Repository?
    - Haben diese die Spalten 'Datum' und 'Anfang'?
    - Aktueller Verzeichnisinhalt:
    """)
    st.write(os.listdir('.'))
