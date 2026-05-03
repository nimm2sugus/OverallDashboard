import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence", layout="wide")
st.title("📊 Energy Intelligence Hub | re cap")

@st.cache_data
def load_all_csv_files():
    # Suche alle CSV-Dateien im Verzeichnis
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and not f.startswith('.')]
    
    if not files:
        return pd.DataFrame(), []

    all_dfs = []
    debug_info = []

    for file in files:
        df = None
        # Probiere die drei gängigsten Kodierungen für SMARD-Daten
        for enc in ['utf-8-sig', 'utf-16', 'latin-1']:
            try:
                # Wir suchen die Kopfzeile (diejenige mit den meisten Semikolons)
                with open(file, 'r', encoding=enc) as f:
                    lines = f.readlines()
                
                # Finde die Zeile, die wahrscheinlich der Header ist (enthält Datum oder Zeit)
                header_idx = 0
                for i, line in enumerate(lines[:15]):
                    if ";" in line and any(keyword in line for keyword in ["Datum", "Anfang", "Zeit", "Date"]):
                        header_idx = i
                        break
                
                # Einlesen
                temp_df = pd.read_csv(file, sep=';', decimal=',', skiprows=header_idx, encoding=enc, on_bad_lines='skip')
                
                # Spalten säubern
                temp_df.columns = [str(c).strip() for c in temp_df.columns]
                
                if 'Datum' in temp_df.columns and 'Anfang' in temp_df.columns:
                    # Zeitstempel erstellen
                    temp_df['Timestamp'] = pd.to_datetime(temp_df['Datum'] + ' ' + temp_df['Anfang'], dayfirst=True, errors='coerce')
                    temp_df = temp_df.dropna(subset=['Timestamp'])
                    
                    # Dateiname als Präfix nutzen, um Spalten unterscheidbar zu machen
                    prefix = file.split('_202')[0]
                    val_cols = [c for c in temp_df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                    
                    # Umbenennen: Dateiname + Original-Header
                    new_names = {c: f"{prefix} > {c}" for c in val_cols}
                    temp_df = temp_df.rename(columns=new_names)
                    
                    all_dfs.append(temp_df[['Timestamp'] + list(new_names.values())].set_index('Timestamp'))
                    debug_info.append(f"✅ {file} geladen ({len(temp_df)} Zeilen)")
                    df = temp_df
                    break
            except Exception as e:
                continue
        
        if df is None:
            debug_info.append(f"❌ {file} konnte nicht gelesen werden.")

    if not all_dfs:
        return pd.DataFrame(), debug_info

    # Zusammenführen und fehlende Werte (bei 1h vs 15min) auffüllen
    combined = pd.concat(all_dfs, axis=1).sort_index().ffill(limit=3).reset_index()
    return combined, debug_info

# --- DATEN LADEN ---
df, debug_log = load_all_csv_files()

# --- SIDEBAR DIAGNOSE ---
with st.sidebar:
    st.header("🛠 System-Status")
    for log in debug_log:
        st.write(log)
    if st.button("Cache leeren"):
        st.cache_data.clear()
        st.rerun()

# --- HAUPTTEIL ---
if not df.empty:
    st.sidebar.divider()
    all_columns = [c for c in df.columns if c != 'Timestamp']
    
    st.sidebar.subheader("Daten auswählen")
    selected_metrics = st.sidebar.multiselect(
        "Wähle Original-Spalten aus:", 
        options=all_columns,
        default=all_columns[:1]
    )

    if selected_metrics:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        for m in selected_metrics:
            # MW/Last/Leistung auf die rechte Achse, alles andere (Preise) nach links
            is_right_axis = any(x in m.lower() for x in ["mw", "verbrauch", "last", "leistung"])
            
            fig.add_trace(
                go.Scatter(x=df['Timestamp'], y=df[m], name=m, 
                           line=dict(shape='hv' if not is_right_axis else 'linear')),
                secondary_y=is_right_axis
            )

        fig.update_layout(template="plotly_dark", hovermode="x unified", height=700,
                          legend=dict(orientation="h", y=1.08))
        fig.update_yaxes(title_text="Preis / Basiswerte", secondary_y=False)
        fig.update_yaxes(title_text="Leistung / Volumen [MW]", secondary_y=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Tabellen-Ansicht"):
            st.dataframe(df)
    else:
        st.info("Bitte wähle in der Sidebar die Spalten aus, die du im Diagramm sehen möchtest.")

else:
    st.error("Es wurden keine gültigen Daten gefunden.")
    st.write("Gefundene Dateien im Repo:", os.listdir('.'))
