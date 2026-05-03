import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")

st.title("📊 Energy Intelligence Hub | re cap")
st.markdown("### Präzise Marktanalyse: Alle Regionen & Kategorien")

# --- ROBUSTER HIERARCHISCHER PARSER ---
@st.cache_data
def load_data_with_structure():
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 15]
    
    if not files:
        return pd.DataFrame(), {}

    master_dfs = []
    file_structure = {} # Speichert {Datei-Kurzname: [Spaltennamen]}

    for file in files:
        try:
            # Header-Suche
            header_idx = -1
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if "Datum" in line and "Anfang" in line:
                        header_idx = i
                        break
            
            if header_idx == -1: continue

            df = pd.read_csv(file, sep=';', decimal=',', skiprows=header_idx, encoding='utf-8', on_bad_lines='skip')
            df.columns = [c.strip().replace('\n', ' ') for c in df.columns]

            if 'Datum' in df.columns and 'Anfang' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True)
                
                # Alle Spalten außer Zeit-Metadaten identifizieren
                value_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                # Eindeutiges Präfix pro Datei
                prefix = file.split('_202')[0]
                new_col_names = {c: f"{prefix} | {c}" for c in value_cols}
                df = df.rename(columns=new_col_names)
                
                # Struktur für Sidebar speichern
                file_structure[prefix] = list(new_col_names.values())
                
                master_dfs.append(df[['Timestamp'] + list(new_col_names.values())].set_index('Timestamp'))
        except Exception as e:
            st.sidebar.warning(f"Fehler bei {file}: {e}")

    if not master_dfs:
        return pd.DataFrame(), {}

    # Mergen und Auffüllen (1h auf 15min)
    final_df = pd.concat(master_dfs, axis=1).sort_index().ffill(limit=3).reset_index()
    return final_df, file_structure

# --- DATEN LADEN ---
df, structure = load_data_with_structure()

if not df.empty:
    # --- SIDEBAR FILTERUNG ---
    st.sidebar.title("🔍 Daten-Auswahl")
    st.sidebar.info("Wähle Kategorien aus den jeweiligen Dateien:")
    
    selected_metrics = []
    
    # Erstelle für jede Datei einen Expander in der Sidebar
    for file_name, columns in structure.items():
        with st.sidebar.expander(f"📁 {file_name}"):
            # Multi-Select für die Spalten dieser spezifischen Datei
            choice = st.multiselect(f"Spalten in {file_name}:", options=columns, key=file_name)
            selected_metrics.extend(choice)

    if selected_metrics:
        # --- ZEIT-FILTER ---
        st.sidebar.divider()
        date_range = st.sidebar.date_input("Analyse-Zeitraum", 
                                           [df['Timestamp'].min().date(), df['Timestamp'].max().date()])
        
        if len(date_range) == 2:
            mask = (df['Timestamp'].dt.date >= date_range[0]) & (df['Timestamp'].dt.date <= date_range[1])
            pdf = df.loc[mask]
        else:
            pdf = df

        # --- GRAFIK ---
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        for metric in selected_metrics:
            # Automatische Achsenzuweisung
            is_volume = any(unit in metric for unit in ["MW", "MWh", "kWh", "Anzahl"])
            
            # Name säubern für Legende (Präfix entfernen)
            clean_name = metric.split(" | ")[1]
            origin = metric.split(" | ")[0]

            fig.add_trace(
                go.Scatter(
                    x=pdf['Timestamp'], 
                    y=pdf[metric], 
                    name=f"{clean_name} ({origin})",
                    line=dict(shape='hv' if not is_volume else 'linear', width=2),
                    hovertemplate=f"<b>{clean_name}</b><br>Wert: %{{y:.2f}}<br>Zeit: %{{x}}<extra></extra>"
                ),
                secondary_y=is_volume # Volumen auf rechte Achse, Preise auf linke Achse
            )

        fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            height=750,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=100, b=10)
        )

        fig.update_yaxes(title_text="<b>Preis / Werte</b>", secondary_y=False)
        fig.update_yaxes(title_text="<b>Volumen [MW / Last]</b>", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)

        # --- DATA INSIGHTS TABELLE ---
        with st.expander("📊 Statistische Auswertung & Vergleich"):
            st.dataframe(pdf[selected_metrics].describe().T)
            
    else:
        st.info("💡 Bitte wähle mindestens eine Kategorie in den Ordnern links aus, um die Analyse zu starten.")
        # Zeige Demo-Bild wenn nichts gewählt
        st.image("https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?auto=format&fit=crop&q=80&w=1000", caption="Warte auf Daten-Auswahl...")

else:
    st.error("Keine gültigen SMARD-Dateien gefunden.")
    st.info("Stellen Sie sicher, dass Ihre CSVs (z. B. 'Gro_handelspreise...') im Hauptverzeichnis liegen.")
