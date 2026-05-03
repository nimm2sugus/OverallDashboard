import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="Energy & LIS Intelligence Pro", layout="wide")

# --- DATA LOADING ---
@st.cache_data
def load_data():
    df = pd.read_csv('historical_energy_data.csv')
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    return df

df = load_data()

# --- HEADER ---
st.title("⚡ Sektorenkopplung & Markt-Monitor")
st.markdown("""
Dieses Dashboard analysiert die **Wechselwirkung zwischen Erneuerbaren Energien und dem Strommarkt**. 
Ziel: Optimierung von Ladefenstern für Elektroautos basierend auf EE-Erzeugung.
""")

# --- FILTER ---
st.sidebar.header("Analyse-Einstellungen")
timerange = st.sidebar.selectbox("Zeitraum wählen", ["Letzte 7 Tage", "Letzte 30 Tage", "Gesamtansicht"])

if timerange == "Letzte 7 Tage":
    plot_df = df.tail(24*7)
elif timerange == "Letzte 30 Tage":
    plot_df = df.tail(24*30)
else:
    plot_df = df.resample('D', on='Timestamp').mean().reset_index()

# --- HAUPTGRAFIK: GEGENÜBERSTELLUNG ---
st.subheader(f"Marktpreis vs. Erneuerbare Einspeisung ({timerange})")

# Erstellung einer Grafik mit zwei Y-Achsen
fig = make_subplots(specs=[[{"secondary_y": True}]])

# 1. Preis (Linke Achse)
fig.add_trace(
    go.Scatter(x=plot_df['Timestamp'], y=plot_df['Strompreis_Euro_MWh'], 
               name="Strompreis (€/MWh)", line=dict(color="#FF4B4B", width=3)),
    secondary_y=False,
)

# 2. PV-Erzeugung (Rechte Achse - Fläche)
fig.add_trace(
    go.Scatter(x=plot_df['Timestamp'], y=plot_df['PV_Erzeugung_MW'], 
               name="PV-Erzeugung (MW)", fill='tozeroy', line=dict(color="#FFD700", width=0)),
    secondary_y=True,
)

# 3. Wind-Erzeugung (Rechte Achse - Linie)
fig.add_trace(
    go.Scatter(x=plot_df['Timestamp'], y=plot_df['Wind_Erzeugung_MW'], 
               name="Wind-Erzeugung (MW)", line=dict(color="#00BFFF", width=2, dash='dot')),
    secondary_y=True,
)

# Layout-Optimierung
fig.update_layout(
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=20, r=20, t=50, b=20),
    hovermode="x unified"
)

fig.update_yaxes(title_text="<b>Preis</b> [€/MWh]", secondary_y=False)
fig.update_yaxes(title_text="<b>Erzeugung</b> [MW]", secondary_y=True)

st.plotly_chart(fig, use_container_width=True)

# --- BUSINESS ANALYSIS ---
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.header("📋 Business Insights")
    avg_price = plot_df['Strompreis_Euro_MWh'].mean()
    correlation = plot_df['Strompreis_Euro_MWh'].corr(plot_df['PV_Erzeugung_MW'] + plot_df['Wind_Erzeugung_MW'])
    
    st.write(f"**Durchschnittspreis:** {avg_price:.2f} €/MWh")
    st.write(f"**Korrelation EE zu Preis:** {correlation:.2f}")
    st.info("""
    *Hinweis:* Eine negative Korrelation (nahe -1.0) zeigt, dass hohe EE-Einspeisung den Preis drückt. 
    Dies sind die **idealen Ladezeitfenster** für HPC-Parks.
    """)

with col2:
    st.header("🚗 LIS-Strategie")
    low_price_threshold = plot_df['Strompreis_Euro_MWh'].quantile(0.2)
    st.success(f"**Ziel-Lade-Preis:** < {low_price_threshold:.2f} €/MWh")
    st.markdown(f"""
    **Handlungsempfehlung:**
    In den letzten {timerange} gab es besonders günstige Zeitfenster bei hoher Wind-Einspeisung. 
    Für Business Developer bedeutet dies: Standorte mit hoher lokaler EE-Erzeugung 
    profitieren am stärksten von **§14a EnWG** Netzentgeltreduzierungen.
    """)
