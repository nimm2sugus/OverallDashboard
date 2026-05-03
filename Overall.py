import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# Konfiguration der Seite
st.set_page_config(page_title="Energy Intelligence Dashboard", layout="wide")

st.title("⚡ Energy & Mobility Intelligence DACH")
st.sidebar.header("Filter & Einstellungen")

# 1. Daten laden (Beispiel: SMARD API oder CSV)
def get_energy_data():
    # Hier würde der API Call stehen
    # Beispiel-Daten für die Demonstration:
    data = {
        'Zeit': pd.date_range(start='2023-10-01', periods=24, freq='H'),
        'Spotpreis_Euro_MWh': [100, 90, 85, 80, 95, 110, 150, 180, 160, 140, 120, 110, 105, 115, 130, 160, 200, 220, 210, 180, 150, 130, 120, 110],
        'PV_Erzeugung_MW': [0, 0, 0, 0, 0, 5, 20, 50, 100, 150, 180, 200, 190, 160, 120, 80, 30, 5, 0, 0, 0, 0, 0, 0]
    }
    return pd.DataFrame(data)

df = get_energy_data()

# Layout Spalten
col1, col2 = st.columns(2)

with col1:
    st.subheader("Börsenstrompreise (Day-Ahead)")
    fig_price = px.line(df, x='Zeit', y='Spotpreis_Euro_MWh', title="Strompreisverlauf (€/MWh)")
    st.plotly_chart(fig_price, use_container_width=True)

with col2:
    st.subheader("PV-Einspeisung vs. Last")
    fig_gen = px.bar(df, x='Zeit', y='PV_Erzeugung_MW', color_discrete_sequence=['gold'])
    st.plotly_chart(fig_gen, use_container_width=True)

# Sektion Ladeinfrastruktur
st.divider()
st.header("🚗 Ladeinfrastruktur Analyse (DACH)")
# Hier könnten Karten von Folium oder Mapbox eingebunden werden
st.info("Hier integrieren wir das Marktstammdatenregister, um neue Wettbewerber-Standorte zu identifizieren.")
