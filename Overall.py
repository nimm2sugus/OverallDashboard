import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="REAL Energy Data DACH", layout="wide")

# --- SMARD API KONFIGURATION ---
# IDs für 15-Minuten Werte (Deutschland/Luxemburg)
FILTER_IDS = {
    "Intraday_Preis_15min": 435,
    "PV_Erzeugung_15min": 122,
    "Wind_Onshore_15min": 125,
    "Wind_Offshore_15min": 123,
    "Netzlast_15min": 438
}


@st.cache_data(ttl=1800)  # 30 Min Cache
def fetch_smard_data(filter_id, days_back=7):
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)

    url = f"https://www.smard.de/cache/filter/data/{filter_id}/DE/ALL/{start_ts}/{end_ts}.json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            series = response.json()['series']
            df = pd.DataFrame(series, columns=['Timestamp', f'Value_{filter_id}'])
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
            return df
    except Exception as e:
        st.error(f"Fehler bei ID {filter_id}: {e}")
    return pd.DataFrame()


# --- DATEN LADEN & MERGEN ---
st.title("🔌 REAL-TIME Energy Intelligence (SMARD Data)")
st.info("Datenquelle: Bundesnetzagentur (SMARD.de) | Auflösung: 15 Minuten")

with st.spinner('Lade echte Marktdaten...'):
    # Alle Datenreihen abrufen
    days = st.sidebar.slider("Zeitraum (Tage)", 1, 14, 3)

    df_price = fetch_smard_data(FILTER_IDS["Intraday_Preis_15min"], days)
    df_pv = fetch_smard_data(FILTER_IDS["PV_Erzeugung_15min"], days)
    df_wind_on = fetch_smard_data(FILTER_IDS["Wind_Onshore_15min"], days)
    df_wind_off = fetch_smard_data(FILTER_IDS["Wind_Offshore_15min"], days)
    df_load = fetch_smard_data(FILTER_IDS["Netzlast_15min"], days)

    # Daten zusammenführen (Outer Join auf Timestamp)
    try:
        main_df = df_price.merge(df_pv, on='Timestamp', how='outer')
        main_df = main_df.merge(df_wind_on, on='Timestamp', how='outer')
        main_df = main_df.merge(df_wind_off, on='Timestamp', how='outer')
        main_df = main_df.merge(df_load, on='Timestamp', how='outer')
        main_df = main_df.sort_values('Timestamp').dropna()

        # Spaltennamen vereinfachen
        main_df.columns = ['Timestamp', 'Preis_EUR_MWh', 'PV_MW', 'Wind_On_MW', 'Wind_Off_MW', 'Netzlast_MW']
    except:
        st.error("Daten konnten nicht synchronisiert werden. Evtl. API-Zeitüberschreitung.")
        st.stop()

# --- KPIs ---
k1, k2, k3, k4 = st.columns(4)
k1.metric("Ø Intraday-Preis", f"{main_df['Preis_EUR_MWh'].mean():.2f} €")
k2.metric("Min. Preis (Negativ?)", f"{main_df['Preis_EUR_MWh'].min():.2f} €")
k3.metric("Max. PV Peak", f"{main_df['PV_MW'].max():.0f} MW")
k4.metric("Aktuelle Netzlast", f"{main_df['Netzlast_MW'].iloc[-1]:.0f} MW")

# --- GRAFIK: GEGENÜBERSTELLUNG ---
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Preis (15-min Treppenstufen)
fig.add_trace(go.Scatter(x=main_df['Timestamp'], y=main_df['Preis_EUR_MWh'],
                         name="Intraday-Preis (€/MWh)", line=dict(color='#FF4B4B', shape='hv')), secondary_y=False)

# Erzeugung (Gestapelt)
fig.add_trace(go.Scatter(x=main_df['Timestamp'], y=main_df['PV_MW'],
                         name="PV-Erzeugung (MW)", fill='tozeroy', line=dict(color='gold', width=0)), secondary_y=True)

fig.add_trace(go.Scatter(x=main_df['Timestamp'], y=main_df['Wind_On_MW'] + main_df['Wind_Off_MW'],
                         name="Wind Gesamt (MW)", line=dict(color='#00BFFF', width=2)), secondary_y=True)

# Netzlast (Gegenüberstellung Verbrauch)
fig.add_trace(go.Scatter(x=main_df['Timestamp'], y=main_df['Netzlast_MW'],
                         name="Netzlast (MW)", line=dict(color='white', dash='dot', width=1)), secondary_y=True)

# Null-Linie für Negativpreise
fig.add_hline(y=0, line_dash="dash", line_color="white", secondary_y=False)

fig.update_layout(title=f"Echtzeit-Analyse: Preis vs. Erzeugung & Last (Letzte {days} Tage)",
                  hovermode="x unified", height=600, template="plotly_dark")
st.plotly_chart(fig, use_container_width=True)

# --- BUSINESS LOGIC ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.subheader("💡 Arbitrage & Smart Charging")
    spread = main_df['Preis_EUR_MWh'].max() - main_df['Preis_EUR_MWh'].min()
    st.write(f"Der Preis-Spread im gewählten Zeitraum beträgt **{spread:.2f} €/MWh**.")
    if main_df['Preis_EUR_MWh'].min() < 0:
        st.warning("ACHTUNG: Es traten negative Preise auf. Ideales Ladefenster!")

with col2:
    st.subheader("📈 Korrelations-Check")
    corr_pv = main_df['Preis_EUR_MWh'].corr(main_df['PV_MW'])
    st.write(f"Korrelation PV zu Preis: **{corr_pv:.2f}**")
    st.write("(Werte nahe -1 zeigen: PV drückt den Preis massiv)")
