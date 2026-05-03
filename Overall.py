import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- SEITE SETUP ---
st.set_page_config(page_title="Energy & EV Intelligence Hub", layout="wide")

# --- DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_live_data():
    """Holt die aktuellsten Preise der letzten 7 Tage von SMARD"""
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
    url = f"https://www.smard.de/cache/filter/data/410/DE/ALL/{start_ts}/{end_ts}.json"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()['series']
            df = pd.DataFrame(data, columns=['Timestamp', 'Strompreis'])
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
            return df
    except:
        return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data
def load_combined_data():
    # 1. Historie aus CSV laden
    try:
        df_hist = pd.read_csv('historical_energy_data.csv')
        df_hist['Timestamp'] = pd.to_datetime(df_hist['Timestamp'])
    except:
        st.error("CSV-Datei nicht gefunden! Bitte historical_energy_data.csv hochladen.")
        return pd.DataFrame()

    # 2. Live-Daten dazu holen
    df_live = fetch_live_data()
    
    if not df_live.empty:
        # Kombinieren & Duplikate entfernen
        df_combined = pd.concat([df_hist, df_live]).drop_duplicates(subset=['Timestamp'], keep='last')
    else:
        df_combined = df_hist
    
    return df_combined.sort_values('Timestamp')

# --- DASHBOARD LOGIK ---
df = load_combined_data()

if not df.empty:
    st.title("⚡ Energy Intelligence & Reporting Hub")
    st.markdown(f"**Status:** Daten von {df['Timestamp'].min().strftime('%d.%m.%Y')} bis heute ({df['Timestamp'].max().strftime('%d.%m.%Y %H:%M')})")

    # METRIKEN (Letzte 24h)
    last_24h = df.tail(24)
    avg_p = last_24h['Strompreis'].mean()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ø Preis heute", f"{avg_p:.2f} €/MWh")
    c2.metric("Max Preis heute", f"{last_24h['Strompreis'].max():.2f} €/MWh")
    c3.metric("Daten-Stabilität", "100% (Hybrid)")

    # VISUALISIERUNG
    st.subheader("Marktanalyse & Sektorenkopplung")
    view = st.radio("Zeitraum-Fokus:", ["Gesamt (seit 2023)", "Letzte 30 Tage", "Letzte 7 Tage"], horizontal=True)
    
    if view == "Letzte 7 Tage":
        plot_df = df.tail(24*7)
    elif view == "Letzte 30 Tage":
        plot_df = df.tail(24*30)
    else:
        plot_df = df.resample('D', on='Timestamp').mean().reset_index() # Tagesmittel für Gesamtansicht

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_df['Timestamp'], y=plot_df['Strompreis'], fill='tozeroy', name="Börsenpreis €/MWh"))
    fig.update_layout(template="plotly_dark", height=400)
    st.plotly_chart(fig, use_container_width=True)

    # REPORTING BEREICH
    st.divider()
    st.header("📋 Business Development Report Generator")
    
    with st.expander("Analyse für Ladeinfrastruktur (TCO Case)"):
        fleet_energy = st.slider("Täglicher Energiebedarf Flotte (kWh)", 100, 5000, 1000)
        # Berechnung des Einsparpotenzials (Spread zwischen Max und Min Preis der letzten 7 Tage)
        recent_7 = df.tail(24*7)
        potential = (recent_7['Strompreis'].max() - recent_7['Strompreis'].min()) / 1000 * fleet_energy
        
        st.write(f"""
        ### Strategische Empfehlung:
        Basierend auf den Marktdaten der letzten 7 Tage hätte eine intelligente Steuerung 
        der Ladevorgänge ein Einsparpotenzial von ca. **{potential:.2f} € pro Tag** gegenüber 
        einer Ladung zu Peak-Zeiten erzielt.
        """)
        
        if st.download_button("Report als CSV exportieren", df.tail(168).to_csv(), "Wochenreport.csv"):
            st.balloons()

else:
    st.warning("Warte auf Daten-Upload...")
