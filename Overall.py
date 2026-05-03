import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="Reliable Energy Intelligence", layout="wide")

# --- KONFIGURATION ---
FILTER_IDS = {
    "Intraday_Preis": 435, # 15-min
    "PV_Erzeugung": 122,   # 15-min
    "Wind_Onshore": 125,   # 15-min
    "Netzlast": 438        # 15-min
}

@st.cache_data(ttl=3600)
def fetch_smard_data_safe(filter_id, days_back=3):
    """Holt Daten mit robustem Fehlerhandling"""
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
    url = f"https://www.smard.de/cache/filter/data/{filter_id}/DE/ALL/{start_ts}/{end_ts}.json"
    
    try:
        response = requests.get(url, timeout=20) # Erhöhter Timeout
        if response.status_code == 200:
            json_data = response.json().get('series', [])
            if not json_data:
                return pd.DataFrame()
            df = pd.DataFrame(json_data, columns=['Timestamp', f'Value_{filter_id}'])
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
            return df
    except Exception as e:
        return pd.DataFrame() # Leeres DF bei Fehler
    return pd.DataFrame()

# --- HAUPTPROGRAMM ---
st.title("🛡 Robust Energy Intelligence OS")
st.sidebar.header("Abfrage-Parameter")
days = st.sidebar.slider("Zeitraum (Tage)", 1, 7, 2)

if st.sidebar.button("Daten manuell aktualisieren"):
    st.cache_data.clear()

with st.spinner('Verbinde mit SMARD-Servern...'):
    # Einzelabfragen
    df_price = fetch_smard_data_safe(FILTER_IDS["Intraday_Preis"], days)
    df_pv = fetch_smard_data_safe(FILTER_IDS["PV_Erzeugung"], days)
    df_wind = fetch_smard_data_safe(FILTER_IDS["Wind_Onshore"], days)
    df_load = fetch_smard_data_safe(FILTER_IDS["Netzlast"], days)

# --- DATEN-FUSION (SICHERER WEG) ---
data_frames = []
if not df_price.empty: data_frames.append(df_price.set_index('Timestamp'))
if not df_pv.empty: data_frames.append(df_pv.set_index('Timestamp'))
if not df_wind.empty: data_frames.append(df_wind.set_index('Timestamp'))
if not df_load.empty: data_frames.append(df_load.set_index('Timestamp'))

if len(data_frames) > 0:
    # Kombinieren aller verfügbaren Daten
    main_df = pd.concat(data_frames, axis=1).sort_index().reset_index()
    main_df.columns = ['Timestamp'] + [col for col in main_df.columns if col != 'Timestamp']
    
    # Benennung der Spalten basierend auf vorhandenen Daten
    col_mapping = {
        f'Value_{FILTER_IDS["Intraday_Preis"]}': 'Preis_EUR',
        f'Value_{FILTER_IDS["PV_Erzeugung"]}': 'PV_MW',
        f'Value_{FILTER_IDS["Wind_Onshore"]}': 'Wind_MW',
        f'Value_{FILTER_IDS["Netzlast"]}': 'Last_MW'
    }
    main_df = main_df.rename(columns=col_mapping)
    
    # KPIs anzeigen
    cols = st.columns(len(main_df.columns)-1)
    for i, col_name in enumerate(main_df.columns[1:]):
        val = main_df[col_name].iloc[-1] if not main_df[col_name].dropna().empty else 0
        cols[i].metric(col_name, f"{val:.2f}")

    # --- GRAFIK ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    if 'Preis_EUR' in main_df.columns:
        fig.add_trace(go.Scatter(x=main_df['Timestamp'], y=main_df['Preis_EUR'], 
                                 name="Preis (€/MWh)", line=dict(color='#FF4B4B', shape='hv')), secondary_y=False)
    
    if 'PV_MW' in main_df.columns:
        fig.add_trace(go.Scatter(x=main_df['Timestamp'], y=main_df['PV_MW'], 
                                 name="PV (MW)", fill='tozeroy', line=dict(width=0, color='gold')), secondary_y=True)

    if 'Last_MW' in main_df.columns:
        fig.add_trace(go.Scatter(x=main_df['Timestamp'], y=main_df['Last_MW'], 
                                 name="Netzlast (MW)", line=dict(color='white', dash='dot')), secondary_y=True)

    fig.update_layout(template="plotly_dark", hovermode="x unified", height=600)
    fig.update_yaxes(title_text="Preis [€]", secondary_y=False)
    fig.update_yaxes(title_text="Leistung [MW]", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)

    # --- EXPERTEN-KPI: NEGATIVPREIS-CHECK ---
    if 'Preis_EUR' in main_df.columns:
        neg_data = main_df[main_df['Preis_EUR'] < 0]
        if not neg_data.empty:
            st.warning(f"🚨 Achtung: {len(neg_data)} negative 15-Minuten-Intervalle gefunden!")
            st.dataframe(neg_data[['Timestamp', 'Preis_EUR']].tail(10))
else:
    st.error("Die API hat keine Daten geliefert. Bitte Zeitraum verringern oder später versuchen.")
    if st.button("Demo-Modus aktivieren"):
        st.info("Hier könnten wir jetzt simulierte Daten einblenden.")
