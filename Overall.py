import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy OS", layout="wide")
st.title("🛡️ re cap Energy Intelligence OS")

@st.cache_data(show_spinner=False)
def brute_force_load(file_path):
    """Liest jede CSV-Datei, egal wie sie kodiert ist oder wie die Spalten heißen."""
    # Liste der Encodings (UTF-16 ist kritisch für SMARD 15min)
    for enc in ['utf-16', 'utf-8-sig', 'latin-1', 'cp1252', 'utf-8']:
        try:
            # 1. Datei einlesen - sep=None lässt pandas das Trennzeichen raten
            # Wir überspringen keine Zeilen, sondern suchen die erste mit Daten
            df = pd.read_csv(file_path, sep=None, engine='python', encoding=enc, decimal=',', on_bad_lines='skip')
            
            # Falls die Datei Metadaten oben hat, ist die erste Spalte oft fast leer.
            # Wir suchen die erste Zeile, die "Datum" oder "Anfang" enthält
            if not any(k in str(df.columns) for k in ["Datum", "Anfang", "Date"]):
                for i in range(1, 10):
                    test_df = pd.read_csv(file_path, sep=None, engine='python', encoding=enc, decimal=',', skiprows=i)
                    if any(k in str(test_df.columns) for k in ["Datum", "Anfang", "Date"]):
                        df = test_df
                        break

            # Spalten säubern
            df.columns = [str(c).strip().replace('\xa0', ' ') for c in df.columns]
            
            # 2. Zeitachse finden
            # Wir kombinieren 'Datum' und 'Anfang' falls vorhanden, sonst nehmen wir Spalte 0
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Datum'].astype(str) + ' ' + df['Anfang'].astype(str), dayfirst=True, errors='coerce')
            else:
                # Nimm einfach die erste Spalte als Zeit
                df['Timestamp'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
            
            df = df.dropna(subset=['Timestamp'])
            
            # 3. Daten-Spalten identifizieren (alles außer Zeit)
            forbidden = ['Datum', 'Anfang', 'Ende', 'Timestamp']
            val_cols = [c for c in df.columns if c not in forbidden and "Unnamed" not in c]
            
            # Präfix für Sidebar
            prefix = file_path.replace('.csv', '').split('_2025')[0]
            
            # Spalten für globalen Merge eindeutig benennen
            renamed = {c: f"{prefix} | {c}" for c in val_cols}
            df = df.rename(columns=renamed)
            
            return df[['Timestamp'] + list(renamed.values())].set_index('Timestamp'), prefix, list(renamed.values())
        except:
            continue
    return None, None, []

def get_integrated_data():
    # Alle CSVs im Ordner finden
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 5]
    if not files: return None, {}

    all_dfs = []
    structure = {}
    
    for f in files:
        df_part, prefix, cols = brute_force_load(f)
        if df_part is not None and not df_part.empty:
            all_dfs.append(df_part)
            structure[prefix] = cols
            
    if not all_dfs: return None, {}

    # Kombinieren
    combined = pd.concat(all_dfs, axis=1).sort_index()
    combined = combined.ffill(limit=3).reset_index()
    return combined, structure

# --- UI ---
df, structure = get_integrated_data()

if df is not None:
    st.sidebar.title("📂 Daten-Katalog")
    if st.sidebar.button("🔄 Cache leeren"):
        st.cache_data.clear()
        st.rerun()

    selected_metrics = []
    for group, columns in structure.items():
        with st.sidebar.expander(f"📁 {group}"):
            for col in columns:
                # Zeige nur den sauberen Spaltennamen
                clean_name = col.split(" | ")[1]
                if st.checkbox(clean_name, key=col):
                    selected_metrics.append(col)

    if selected_metrics:
        # GRAFIK
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for m in selected_metrics:
            # MW/Leistung/Last nach rechts, Rest nach links
            is_volume = any(x in m.lower() for x in ["mw", "last", "verbrauch", "leistung", "erzeugung"])
            fig.add_trace(go.Scatter(x=df['Timestamp'], y=df[m], name=m, 
                                     line=dict(shape='hv' if not is_volume else 'linear')), 
                          secondary_y=is_volume)
        
        fig.update_layout(template="plotly_dark", hovermode="x unified", height=750,
                          legend=dict(orientation="h", y=1.05))
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📊 Daten-Vorschau"):
            st.dataframe(df)
    else:
        st.info("Bitte wähle links in der Sidebar Spalten aus.")
else:
    st.error("❌ Keine Daten gefunden.")
    st.write("Verzeichnis-Inhalt:", os.listdir('.'))
