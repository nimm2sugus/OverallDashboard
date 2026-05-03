import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="re cap Intelligence Hub", layout="wide")
st.title("🛡️ Energy Market Intelligence OS")

def robust_load_csv(file_path):
    """Liest SMARD-Dateien, egal wie sie formatiert sind."""
    encodings = ['utf-8-sig', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            
            # 1. Header-Suche: Wo fängt die Tabelle an?
            header_idx = -1
            sep = ';' # Default
            for i, line in enumerate(lines[:30]):
                if "Datum" in line and "Anfang" in line:
                    header_idx = i
                    # Trennzeichen-Check: Komma oder Semikolon?
                    sep = ';' if line.count(';') > line.count(',') else ','
                    break
            
            if header_idx == -1: 
                continue

            # 2. Einlesen mit den erkannten Parametern
            df = pd.read_csv(file_path, sep=sep, decimal=',', skiprows=header_idx, 
                             encoding=enc, on_bad_lines='skip', engine='python')
            
            # 3. Spaltennamen säubern
            df.columns = [str(c).strip() for c in df.columns]
            
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                # Zeitstempel bauen
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Timestamp'])
                
                # Werte-Spalten identifizieren (alles außer Zeit-Metadaten)
                value_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                if not value_cols:
                    continue

                # Eindeutige Namen vergeben (Dateiname als Präfix)
                prefix = file_path.split('_')[0]
                new_names = {c: f"{prefix}_{c}" for c in value_cols}
                df = df.rename(columns=new_names)
                
                return df[['Timestamp'] + list(new_names.values())].set_index('Timestamp')
        except:
            continue
    return None

def get_all_data():
    # Suche alle echten SMARD CSVs (Länge > 10 Zeichen um Müll wie --.csv zu ignorieren)
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 10]
    if not files: 
        return None
    
    all_dfs = []
    for f in files:
        df_temp = robust_load_csv(f)
        if df_temp is not None and not df_temp.empty:
            all_dfs.append(df_temp)
    
    if all_dfs:
        # Über Zeitstempel zusammenführen (Outer Join)
        merged = pd.concat(all_dfs, axis=1).sort_index().reset_index()
        return merged
    return None

# --- UI LOGIK ---
df = get_all_data()

if df is not None and not df.empty:
    st.sidebar.success(f"Datenquelle: {len(df)} Zeilen geladen")
    
    # Metriken-Auswahl
    available_cols = [c for c in df.columns if c != 'Timestamp']
    selected_metrics = st.sidebar.multiselect(
        "Verfügbare Datensätze wählen:", 
        available_cols,
        default=available_cols[:2] if len(available_cols) > 1 else available_cols
    )

    if selected_metrics:
        # Hauptgrafik
        fig = px.line(df, x='Timestamp', y=selected_metrics, 
                      title="Energie-Marktdaten Vergleich",
                      template="plotly_dark")
        
        fig.update_layout(
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Rohdaten-Tabelle"):
            st.dataframe(df)
    else:
        st.info("Bitte wählen Sie mindestens einen Datensatz in der Seitenleiste aus.")

else:
    st.error("Keine gültigen SMARD-Daten gefunden.")
    st.markdown("### Checkliste:")
    st.write("1. Liegen die CSV-Dateien im Hauptverzeichnis auf GitHub?")
    st.write("2. Haben die Dateien die Spalten 'Datum' und 'Anfang'?")
