import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")
st.title("🛡️ re cap Energy Intelligence OS")

@st.cache_data(show_spinner=False)
def brute_force_load(file_path):
    """Liest Dateien extrem robust und bereinigt doppelte Zeitstempel."""
    for enc in ['utf-16', 'utf-8-sig', 'latin-1', 'cp1252', 'utf-8']:
        try:
            # 1. Datei laden
            df = pd.read_csv(file_path, sep=None, engine='python', encoding=enc, decimal=',', on_bad_lines='skip')
            
            # Header-Suche falls nötig
            if not any(k in str(df.columns) for k in ["Datum", "Anfang"]):
                for i in range(1, 15):
                    test_df = pd.read_csv(file_path, sep=None, engine='python', encoding=enc, decimal=',', skiprows=i)
                    if any(k in str(test_df.columns) for k in ["Datum", "Anfang"]):
                        df = test_df
                        break

            df.columns = [str(c).strip().replace('\xa0', ' ') for c in df.columns]
            
            # 2. Zeitachse bauen
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Datum'].astype(str) + ' ' + df['Anfang'].astype(str), dayfirst=True, errors='coerce')
            else:
                df['Timestamp'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
            
            df = df.dropna(subset=['Timestamp'])
            
            # --- LÖSUNG FÜR DEN FEHLER: Doppelte Zeitstempel entfernen ---
            df = df.sort_values('Timestamp').drop_duplicates('Timestamp', keep='last')
            
            # 3. Daten-Spalten identifizieren
            forbidden = ['Datum', 'Anfang', 'Ende', 'Timestamp']
            val_cols = [c for c in df.columns if c not in forbidden and "Unnamed" not in c]
            
            # Dateiname als Präfix für Eindeutigkeit
            prefix = file_path.replace('.csv', '').split('_2025')[0]
            renamed = {c: f"{prefix} | {c}" for c in val_cols}
            df = df.rename(columns=renamed)
            
            return df[['Timestamp'] + list(renamed.values())].set_index('Timestamp'), prefix, list(renamed.values())
        except:
            continue
    return None, None, []

@st.cache_data(show_spinner="Kombiniere Datenströme...")
def get_integrated_data():
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

    # Zusammenführen (axis=1) - der Index (Timestamp) ist jetzt garantiert eindeutig pro DF
    try:
        combined = pd.concat(all_dfs, axis=1).sort_index()
        combined = combined.ffill(limit=3).reset_index()
        return combined, structure
    except Exception as e:
        st.error(f"Kritischer Fehler beim Mergen: {e}")
        return None, {}

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
                label = col.split(" | ")[1]
                if st.checkbox(label, key=col):
                    selected_metrics.append(col)

    if selected_metrics:
        # GRAFIK
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for m in selected_metrics:
            is_volume = any(x in m.lower() for x in ["mw", "last", "verbrauch", "leistung", "erzeugung"])
            fig.add_trace(go.Scatter(x=df['Timestamp'], y=df[m], name=m, 
                                     line=dict(shape='hv' if not is_volume else 'linear', width=2)), 
                          secondary_y=is_volume)
        
        fig.update_layout(template="plotly_dark", hovermode="x unified", height=750,
                          legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"))
        fig.update_yaxes(title_text="Preis [€]", secondary_y=False)
        fig.update_yaxes(title_text="Volumen / Last [MW]", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📊 Daten-Vorschau & Statistik"):
            st.write(df[selected_metrics].describe().T)
            st.dataframe(df)
    else:
        st.info("💡 Bitte wähle links in der Sidebar Daten aus.")
else:
    st.error("❌ Keine gültigen Daten gefunden. Prüfe die Dateinamen und Inhalte im Repo.")
