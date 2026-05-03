import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
import time

# --- INITIALISIERUNG ---
st.set_page_config(page_title="Energy Intelligence Hub", layout="wide")


# Hilfsfunktion für SMARD-Zeitstempel
def get_unix_ms(days_back):
    dt = datetime.now() - timedelta(days=days_back)
    return int(time.mktime(dt.timetuple())) * 1000


# --- DATA SOURCING (SMARD) ---
@st.cache_data(ttl=3600)  # Speichert Daten für 1 Std zwischen
def fetch_smard_data(filter_id, days=7):
    timestamp_from = get_unix_ms(days)
    timestamp_to = get_unix_ms(0)

    # SMARD API URL (Beispiel für Deutschland/Luxemburg Region)
    url = f"https://www.smard.de/cache/filter/data/{filter_id}/DE/ALL/{timestamp_from}/{timestamp_to}.json"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            raw_data = response.json()['series']
            df = pd.DataFrame(raw_data, columns=['Timestamp', 'Value'])
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
            return df
        else:
            return None
    except Exception as e:
        return None


# --- UI STRUKTUR ---
st.title("⚡ Energy & Mobility Intelligence Dashboard")
st.markdown("### Strategisches Analyse- & Reporting-Tool für Ladeinfrastruktur")

tab1, tab2, tab3 = st.tabs(["📊 Markt-Monitor", "📋 Business Report", "⚙️ Konfiguration"])

with tab1:
    st.header("Marktdaten Analyse")
    col1, col2 = st.columns([3, 1])

    with col2:
        days_to_show = st.slider("Zeitraum (Tage)", 1, 14, 7)
        st.info("Datenquelle: SMARD.de (Bundesnetzagentur)")

    # Daten laden (410 = Spotmarktpreis)
    with st.spinner('Verbinde mit Bundesnetzagentur...'):
        price_df = fetch_smard_data(410, days_to_show)
        pv_df = fetch_smard_data(122, days_to_show)  # PV-Erzeugung

    if price_df is not None:
        fig = px.line(price_df, x='Timestamp', y='Value',
                      title="Börsenstrompreis (Day-Ahead) €/MWh",
                      labels={'Value': '€/MWh', 'Timestamp': 'Zeit'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("SMARD API aktuell nicht erreichbar. Bitte später versuchen.")

with tab2:
    st.header("📄 Automatisierter Business Report")

    if price_df is not None:
        avg_price = price_df['Value'].mean()
        max_price = price_df['Value'].max()
        min_price = price_df['Value'].min()

        st.subheader("Wöchentliche Zusammenfassung")

        report_text = f"""
        **Marktanalyse der letzten {days_to_show} Tage:**
        *   Der durchschnittliche Börsenstrompreis lag bei **{avg_price:.2f} €/MWh**.
        *   Maximale Preisspitze: **{max_price:.2f} €/MWh**.
        *   Günstigster Ladezeitpunkt: **{min_price:.2f} €/MWh**.

        **Strategische Empfehlung für Business Development:**
        1. **Smart Charging:** Durch die Volatilität der Preise (Differenz zw. Min/Max: {(max_price - min_price):.2f} €) 
           ist ein gesteuertes Laden ökonomisch sinnvoll.
        2. **THG-Quote:** Die aktuelle Erzeugungssituation begünstigt Standorte mit hohem PV-Eigenanteil.
        """
        st.markdown(report_text)

        if st.button("Report als PDF/Text exportieren (Simulation)"):
            st.write("Report wird generiert... (Hier kann später ein PDF-Download stehen)")
    else:
        st.warning("Keine Daten für den Report verfügbar.")

with tab3:
    st.header("Einstellungen")
    st.write("Hier kannst du Regionen (DACH) und Grenzwerte für Preis-Alerts festlegen.")
