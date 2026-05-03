import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

st.set_page_config(page_title="re cap Energy Intelligence OS", layout="wide")

# --- FUNKTION: SMARD CSV PARSER ---
@st.cache_data
def load_and_merge_smard_files():
    # Liste aller Dateien im Verzeichnis
    files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    data_frames = []
    
    for file in files:
        try:
            # SMARD Dateien: Trenner ';', Dezimal ',', oft UTF-8 oder ISO-8859-1
            df = pd.read_csv(file, sep=';', decimal=',', encoding='utf-8')
            
            # Zeitstempel erstellen
            df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], format='%d.%m.%Y %H:%M')
            
            # Relevante Spalten identifizieren (SMARD Namen sind lang)
            # Wir suchen nach Schlüsselwörtern und benennen sie um
            new_cols = {'Timestamp': 'Timestamp'}
            
            if "Gro_handelspreise" in file and "Viertelstunde" in file:
                target = "Preis_Intraday"
            elif "Gro_handelspreise" in file and "Stunde" in file:
                target = "Preis_DayAhead"
            elif "Realisierte_Erzeugung" in file:
                # Hier gibt es oft mehrere Spalten (PV, Wind Onshore etc.)
                # Wir extrahieren alle MW-Spalten
                for col in df.columns:
                    if "Photovoltaik" in col: df = df.rename(columns={col: "PV_Real"})
                    if "Wind Onshore" in col: df = df.rename(columns={col: "Wind_On_Real"})
                target = None # Schon erledigt
            elif "Realisierter_Stromverbrauch" in file:
                target = "Netzlast_Real"
            elif "Prognostizierte_Erzeugung_Intraday" in file:
                for col in df.columns:
                    if "Photovoltaik" in col: df = df.rename(columns={col: "PV_Prog_Intra"})
                target = None
            else:
                continue # Unwichtige Datei

            if target:
                # Die Spalte mit den Werten finden (meistens die dritte Spalte nach Datum/Zeit)
                val_col = [c for c in df.columns if "[MW]" in c or "[EUR" in c][0]
                df = df.rename(columns={val_col: target})
            
            # Nur notwendige Spalten behalten
            keep_cols = [c for c in df.columns if c in ["Timestamp", "Preis_Intraday", "Preis_DayAhead", "PV_Real", "Wind_On_Real", "Netzlast_Real", "PV_Prog_Intra"]]
            data_frames.append(df[keep_cols].set_index('Timestamp'))
            
        except Exception as e:
            st.sidebar.warning(f"Konnte {file} nicht parsen: {e}")

    if not data_frames:
        return pd.DataFrame()

    # Alle Dateien über den Zeitstempel zusammenführen
    master_df = pd.concat(data_frames, axis=1).sort_index().reset_index()
    # Duplikate durch das Mergen entfernen
    master_df = master_df.loc[:, ~master_df.columns.duplicated()]
    return master_df

# --- DATEN LADEN ---
st.title("📊 Energy Intelligence Dashboard | re cap")
st.sidebar.header("Daten-Status")

df = load_and_merge_smard_files()

if not df.empty:
    st.sidebar.success(f"Erfolgreich geladen: {len(df)} Datenpunkte")
    
    # --- ZEITRAUM FILTER ---
    st.sidebar.subheader("Analyse-Zeitraum")
    start_date = st.sidebar.date_input("Start", df['Timestamp'].min())
    end_date = st.sidebar.date_input("Ende", df['Timestamp'].max())
    
    mask = (df['Timestamp'].dt.date >= start_date) & (df['Timestamp'].dt.date <= end_date)
    pdf = df.loc[mask] # Plotted Dataframe

    # --- KPI ZEILE ---
    c1, c2, c3, c4 = st.columns(4)
    if 'Preis_Intraday' in pdf.columns:
        c1.metric("Ø Intraday Preis", f"{pdf['Preis_Intraday'].mean():.2f} €")
    if 'PV_Real' in pdf.columns:
        c2.metric("Max PV Erzeugung", f"{pdf['PV_Real'].max():,.0f} MW")
    if 'Preis_Intraday' in pdf.columns:
        neg_hours = len(pdf[pdf['Preis_Intraday'] < 0]) / 4
        c3.metric("Negativ-Stunden", f"{neg_hours:.1f} h")
    if 'Netzlast_Real' in pdf.columns:
        c4.metric("Ø Netzlast", f"{pdf['Netzlast_Real'].mean():,.0f} MW")

    # --- GRAFIK: DIE GROSSE GEGENÜBERSTELLUNG ---
    st.subheader("Markt-Dynamik: Preise vs. Erzeugung & Last")
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Preis-Kurven
    if 'Preis_Intraday' in pdf.columns:
        fig.add_trace(go.Scatter(x=pdf['Timestamp'], y=pdf['Preis_Intraday'], name="Preis Intraday (15m)", line=dict(color='#FF4B4B', shape='hv')), secondary_y=False)
    if 'Preis_DayAhead' in pdf.columns:
        fig.add_trace(go.Scatter(x=pdf['Timestamp'], y=pdf['Preis_DayAhead'], name="Preis Day-Ahead (1h)", line=dict(color='white', dash='dot')), secondary_y=False)
    
    # Erzeugung & Last
    if 'PV_Real' in pdf.columns:
        fig.add_trace(go.Scatter(x=pdf['Timestamp'], y=pdf['PV_Real'], name="PV Real [MW]", fill='tozeroy', line=dict(width=0, color='gold'), opacity=0.5), secondary_y=True)
    if 'Wind_On_Real' in pdf.columns:
        fig.add_trace(go.Scatter(x=pdf['Timestamp'], y=pdf['Wind_On_Real'], name="Wind Onshore [MW]", line=dict(color='#00BFFF', width=2)), secondary_y=True)
    if 'Netzlast_Real' in pdf.columns:
        fig.add_trace(go.Scatter(x=pdf['Timestamp'], y=pdf['Netzlast_Real'], name="Netzlast [MW]", line=dict(color='rgba(255,255,255,0.3)', width=1)), secondary_y=True)

    fig.update_layout(template="plotly_dark", hovermode="x unified", height=600)
    fig.update_yaxes(title_text="Preis [€/MWh]", secondary_y=False)
    fig.update_yaxes(title_text="Leistung [MW]", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # --- BUSINESS CASE: PROGNOSE-CHECK ---
    if 'PV_Real' in pdf.columns and 'PV_Prog_Intra' in pdf.columns:
        st.divider()
        st.subheader("🎯 Prognose-Güte Analyse (PV)")
        pdf['Abweichung'] = pdf['PV_Real'] - pdf['PV_Prog_Intra']
        
        fig_err = go.Figure()
        fig_err.add_trace(go.Scatter(x=pdf['Timestamp'], y=pdf['Abweichung'], name="Abweichung Real vs. Prognose", fill='tozeroy', line=dict(color='orange')))
        fig_err.update_layout(title="Delta MW (Real - Prognose) | Relevanz für Ausgleichsenergie", template="plotly_dark", height=300)
        st.plotly_chart(fig_err, use_container_width=True)

else:
    st.error("Keine passenden CSV-Dateien im Repository gefunden.")
    st.info("Stellen Sie sicher, dass die Dateien von SMARD im Hauptverzeichnis Ihres GitHub-Repos liegen.")
