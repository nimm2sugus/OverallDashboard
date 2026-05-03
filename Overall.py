import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")

st.title("📊 Energy Market Intelligence OS | re cap")
st.markdown("### Analyse von Preisen, Erzeugung & Prognosen (SMARD)")

# --- ROBUSTER PARSER ---
@st.cache_data
def load_all_smard_files():
    # Suche alle relevanten CSVs im Verzeichnis
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 15]
    
    if not files:
        return pd.DataFrame()

    data_frames = []
    
    for file in files:
        try:
            # Header-Suche (Wo fängt die Tabelle an?)
            header_idx = -1
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if "Datum" in line and "Anfang" in line:
                        header_idx = i
                        break
            
            if header_idx == -1: continue

            # Einlesen (Semikolon-Trennzeichen ist Standard bei SMARD)
            df = pd.read_csv(file, sep=';', decimal=',', skiprows=header_idx, encoding='utf-8', on_bad_lines='skip')
            df.columns = [c.strip() for c in df.columns]

            if 'Datum' in df.columns and 'Anfang' in df.columns:
                # Zeitstempel erstellen
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True)
                
                # Identifiziere die Werte-Spalte (alles außer Zeit)
                value_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                # Präfix aus Dateinamen erstellen (z.B. "Realisierte_Erzeugung")
                prefix = file.split('_202')[0] # Schneidet den Zeitstempel ab
                
                for col in value_cols:
                    new_name = f"{prefix}: {col}"
                    df = df.rename(columns={col: new_name})
                    
                # Index setzen für Merge
                data_frames.append(df[['Timestamp'] + [f"{prefix}: {c}" for c in value_cols]].set_index('Timestamp'))
        except Exception as e:
            st.sidebar.warning(f"Fehler bei {file}: {e}")

    if not data_frames:
        return pd.DataFrame()

    # Zusammenführen über Zeitstempel
    master_df = pd.concat(data_frames, axis=1).sort_index()
    
    # WICHTIG: Stundendaten auf Viertelstunden auffüllen (Forward Fill)
    # Damit die Day-Ahead Preise keine Lücken in der 15min-Grafik haben
    master_df = master_df.ffill(limit=3) 
    
    return master_df.reset_index()

# --- DATEN LADEN ---
df = load_all_smard_files()

if not df.empty:
    st.sidebar.success(f"✅ {len(df.columns)-1} Datenreihen geladen")
    
    # Metriken filtern (Suchen vereinfachen)
    all_metrics = [c for c in df.columns if c != 'Timestamp']
    
    st.sidebar.subheader("🔌 Auswahl der Datenreihen")
    selected_metrics = st.sidebar.multiselect(
        "Wähle Kurven für das Diagramm:",
        options=all_metrics,
        default=[m for m in all_metrics if "Gro_handelspreise" in m and "Viertelstunde" in m][:1]
    )

    if selected_metrics:
        # --- HAUPTGRAFIK ---
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        for metric in selected_metrics:
            # Logik: Preise auf linke Achse, Erzeugung/Last auf rechte Achse
            is_price = "preis" in metric.lower()
            
            fig.add_trace(
                go.Scatter(
                    x=df['Timestamp'], 
                    y=df[metric], 
                    name=metric.split(": ")[0], # Kürzt den Namen in der Legende
                    line=dict(shape='hv' if is_price else 'linear', width=2),
                    hovertemplate=f"<b>{metric}</b><br>Wert: %{{y:.2f}}<br>Zeit: %{{x}}<extra></extra>"
                ),
                secondary_y=not is_price
            )

        fig.update_layout(
            template="plotly_dark",
            hovermode="x unified",
            height=700,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_title="Zeitverlauf",
        )

        fig.update_yaxes(title_text="<b>Preis</b> [€/MWh]", secondary_y=False)
        fig.update_yaxes(title_text="<b>Leistung / Verbrauch</b> [MW]", secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)
        
        # --- BUSINESS REPORT ---
        st.divider()
        st.subheader("📋 Business-Analyse (gewählter Zeitraum)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**Preis-Statistik**")
            price_data = df[[m for m in selected_metrics if "preis" in m.lower()]]
            if not price_data.empty:
                st.write(price_data.describe().T[['mean', 'min', 'max']])
        
        with col2:
            st.info("**EE-Einspeisung**")
            ee_data = df[[m for m in selected_metrics if "Erzeugung" in m]]
            if not ee_data.empty:
                st.write(ee_data.describe().T[['mean', 'max']])
        
        with col3:
            st.info("**Sektorenkopplung**")
            if not price_data.empty and not ee_data.empty:
                corr = pd.concat([price_data, ee_data], axis=1).corr().iloc[0, -1]
                st.metric("Korrelation Preis/EE", f"{corr:.2f}")
                st.caption("Ein negativer Wert zeigt: Viel EE senkt den Preis.")

    else:
        st.info("Bitte wähle mindestens eine Datenreihe in der Sidebar aus.")
else:
    st.error("Keine gültigen SMARD-Dateien gefunden.")
    st.info("Hinweis: Die CSV-Dateien müssen im Hauptverzeichnis des Repos liegen.")
