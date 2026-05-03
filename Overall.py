import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

# --- CONFIG & STYLING ---
st.set_page_config(page_title="EE & EV Intelligence Hub", layout="wide")


# --- FUNKTION: SMARD DATEN HOLEN ---
def get_smard_data(filter_id, timestamp_from, timestamp_to):
    # SMARD API Endpunkt (Beispiel: 410 = Spotmarktpreis)
    # IDs: 122=PV-Erzeugung, 410=Preis, 125=Wind-Onshore
    url = f"https://www.smard.de/cache/filter/data/{filter_id}/DE/ALL/{timestamp_from}/{timestamp_to}.json"
    try:
        response = requests.get(url)
        data = response.json()['series']
        df = pd.DataFrame(data, columns=['Timestamp', 'Value'])
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        return df
    except:
        return pd.DataFrame()


# --- SIDEBAR: PARAMETER ---
st.sidebar.title("🛠 Technical Settings")
charging_power = st.sidebar.slider("Ladeleistung (kW)", 11, 300, 50)
utilization = st.sidebar.slider("Auslastung (%)", 5, 50, 15)

# --- HAUPTBEREICH ---
st.title("⚡ Energy & Mobility Intelligence (EE-Edition)")

# 1. LIVE MARKTDATEN (EE-TECHNIK)
st.header("1. Aktuelle Marktsituation (DACH)")

# Zeitraum festlegen (letzte 48 Stunden)
end_time = datetime.now()
start_time = end_time - timedelta(days=2)
ts_start = int(start_time.timestamp() * 1000)
ts_end = int(end_time.timestamp() * 1000)

with st.spinner('Lade Marktdaten von SMARD...'):
    df_price = get_smard_data(410, ts_start, ts_end)  # Preis
    df_pv = get_smard_data(122, ts_start, ts_end)  # PV Erzeugung

if not df_price.empty and not df_pv.empty:
    fig = go.Figure()
    # Preis-Linie
    fig.add_trace(go.Scatter(x=df_price['Timestamp'], y=df_price['Value'], name="Spotpreis (€/MWh)",
                             line=dict(color='firebrick', width=2)))
    # PV-Fläche
    fig.add_trace(go.Scatter(x=df_pv['Timestamp'], y=df_pv['Value'], name="PV Erzeugung (MW)", fill='tozeroy',
                             line=dict(color='orange', width=0)))

    fig.update_layout(title="Zusammenhang Spotpreis vs. PV-Einspeisung", xaxis_title="Zeit", yaxis_title="Wert",
                      legend_alignment="h")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.error("Fehler beim Abruf der SMARD-Daten. Prüfe Internetverbindung.")

# 2. ENGINEERING CALCULATOR: §14a EnWG
st.divider()
st.header("2. Business Case: Netzentgelt-Reduzierung (§14a EnWG)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Input")
    annual_cons = charging_power * 8760 * (utilization / 100)
    st.write(f"Voraussichtlicher Jahresverbrauch: **{annual_cons:,.0f} kWh**")

    # Modulwahl nach §14a
    modul = st.selectbox("Wähle §14a Entgelt-Modul", ["Modul 1 (Pauschale)", "Modul 2 (Prozentual)"])

with col2:
    st.subheader("Ergebnis (Schätzung)")
    if modul == "Modul 1 (Pauschale)":
        savings = 150  # Beispielwert Bundesweit ca. 110-190€
        st.success(f"Vorteil: Ca. **{savings} €** Gutschrift pro Jahr (unabhängig vom Verbrauch).")
    else:
        # Modul 2: 60% Reduktion auf Arbeitspreis des Netzbetreibers
        savings = annual_cons * 0.02  # Annahme: 2 Cent Reduktion
        st.success(f"Vorteil: Ca. **{savings:,.2f} €** Ersparnis durch Arbeitspreis-Reduktion.")

st.info(
    "💡 **EE-Pro-Tipp:** Als Junior Business Developer kannst du hier zeigen, wie 'Steuerbare Verbrauchseinrichtungen' die OPEX der Ladeinfrastruktur senken.")
