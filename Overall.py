import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence", layout="wide")
st.title("🛡️ re cap Energy Intelligence OS")

@st.cache_data(show_spinner=False)
def clean_numeric(series):
    """Bereinigt SMARD-Zahlenformate (Tausenderpunkte weg, Komma zu Punkt)."""
    return pd.to_numeric(
        series.astype(str)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False),
        errors='coerce'
    )

@st.cache_data(show_spinner=False)
def load_and_clean_smard(file_path):
    """Lädt und bereinigt SMARD-CSVs hocheffizient."""
    for enc in ['utf-16', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            df = pd.read_csv(file_path, sep=None, engine='python', encoding=enc, skiprows=0)
            
            # Header-Suche
            if not any(k in str(df.columns) for k in ["Datum", "Ende"]):
                for i in range(1, 15):
                    test_df = pd.read_csv(file_path, sep=None, engine='python', encoding=enc, skiprows=i)
                    if any(k in str(test_df.columns) for k in ["Datum", "Ende"]):
                        df = test_df
                        break

            df.columns = [str(c).strip() for c in df.columns]
            
            # Zeitreferenz auf Intervall-Ende ("Datum bis" / "Ende")
            if 'Datum' in df.columns and 'Ende' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Ende'], dayfirst=True, errors='coerce')
            elif 'Datum bis' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Datum bis'], dayfirst=True, errors='coerce')
            else:
                df['Timestamp'] = pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors='coerce')
            
            df = df.dropna(subset=['Timestamp']).sort_values('Timestamp').drop_duplicates('Timestamp', keep='last')
            
            # Nur echte Datenwerte (keine Zeitspalten)
            forbidden = ['datum', 'anfang', 'ende', 'von', 'bis', 'timestamp', 'zeit']
            val_cols = [c for c in df.columns if not any(k in c.lower() for k in forbidden) and "Unnamed" not in c]
            
            # Zahlen-Sanierung für alle Werte-Spalten
            for col in val_cols:
                df[col] = clean_numeric(df[col])
            
            prefix = file_path.replace('.csv', '').split('_2025')[0]
            renamed = {c: f"{prefix} | {c}" for c in val_cols}
            df = df.rename(columns=renamed)
            
            return df[['Timestamp'] + list(renamed.values())].set_index('Timestamp'), prefix, list(renamed.values())
        except:
            continue
    return None, None, []

@st.cache_data(show_spinner="Synchronisiere Einheiten...")
def get_final_data():
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 5]
    all_dfs, structure = [], {}
    for f in files:
        df_p, pref, cols = load_and_clean_smard(f)
        if df_p is not None:
            all_dfs.append(df_p)
            structure[pref] = cols
    if not all_dfs: return None, {}
    combined = pd.concat(all_dfs, axis=1).sort_index().ffill(limit=3).reset_index()
    return combined, structure

# --- UI ---
df, structure = get_final_data()

if df is not None:
    st.sidebar.title("🔍 Daten-Katalog")
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
        # Checkbox für Flächenfüllung
        fill_area = st.sidebar.checkbox("Flächen unter Kurven füllen?", value=False)
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        for m in selected_metrics:
            is_vol = any(x in m.lower() for x in ["mw", "last", "verbrauch", "leistung", "erzeugung"])
            
            fig.add_trace(go.Scatter(
                x=df['Timestamp'], y=df[m], name=m, 
                fill='tozeroy' if fill_area else None,
                line=dict(shape='hv' if not is_vol else 'linear', width=2)
            ), secondary_y=is_vol)
        
        fig.update_layout(template="plotly_dark", hovermode="x unified", height=750,
                          legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"))
        fig.update_yaxes(title_text="Preis / Basiswerte", secondary_y=False)
        fig.update_yaxes(title_text="MW / Volumen", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("📊 Tabellarische Analyse"):
            st.dataframe(df[['Timestamp'] + selected_metrics])
    else:
        st.info("Bitte wählen Sie links Datenreihen aus.")
else:
    st.error("Keine Daten gefunden.")
