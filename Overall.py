import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Pro-Level Energy Dashboard", layout="wide")

# --- DATA LOADING ---
@st.cache_data
def load_data():
    df = pd.read_csv('historical_energy_data_15min.csv')
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    return df

df = load_data()

# --- SIDEBAR & FILTER ---
st.sidebar.title("🔍 Analyse-Filter")
view_mode = st.sidebar.selectbox("Daten-Auflösung", ["15-Minuten (Intraday)", "Stündlich (Day-Ahead)"])
date_range = st.sidebar.date_input("Zeitraum wählen", [df['Timestamp'].max() - pd.Timedelta(days=3), df['Timestamp'].max()])
only_negative = st.sidebar.checkbox("Nur Phasen mit Negativpreisen zeigen")

# Daten filtern
mask = (df['Timestamp'].dt.date >= date_range[0]) & (df['Timestamp'].dt.date <= date_range[1])
filtered_df = df.loc[mask]

if only_negative:
    filtered_df = filtered_df[filtered_df['Intraday_15min_Price'] <= 0]

# --- KPI DASHBOARD ---
st.title("⚡ Energy & Mobility Profitability Dashboard")
st.markdown("### 15-Minuten Markt-Analyse für Ladeinfrastruktur (DACH)")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

avg_p = filtered_df['Intraday_15min_Price'].mean()
neg_hours = len(filtered_df[filtered_df['Intraday_15min_Price'] < 0]) * 0.25 # Da 15 min Takte
max_spread = filtered_df['Intraday_15min_Price'].max() - filtered_df['Intraday_15min_Price'].min()
arbitrage_pot = max_spread * 0.5 # Vereinfachte Formel für Einsparung pro MWh

kpi1.metric("Ø Strompreis", f"{avg_p:.2f} €/MWh")
kpi2.metric("Negativ-Stunden", f"{neg_hours:.1f} h", delta="Kritisch für LIS", delta_color="inverse")
kpi3.metric("Max. Spread", f"{max_spread:.2f} €", help="Differenz zw. teuerstem und günstigstem Zeitpunkt")
kpi4.metric("Arbitrage-Potential", f"{arbitrage_pot:.2f} €/MWh", help="Mögliche Ersparnis durch Lastverschiebung")

# --- CHART BEREICH ---
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Preis-Linie
price_col = 'Intraday_15min_Price' if view_mode == "15-Minuten (Intraday)" else 'DayAhead_60min_Price'
fig.add_trace(go.Scatter(x=filtered_df['Timestamp'], y=filtered_df['Intraday_15min_Price'], 
                         name="Preis 15-min", line=dict(color='#00ffcc', width=2)), secondary_y=False)

# EE-Anteil (Area Chart)
fig.add_trace(go.Scatter(x=filtered_df['Timestamp'], y=filtered_df['PV_MW'], 
                         name="PV-Einspeisung", fill='tozeroy', line=dict(width=0, color='gold'), opacity=0.3), secondary_y=True)
fig.add_trace(go.Scatter(x=filtered_df['Timestamp'], y=filtered_df['Wind_MW'], 
                         name="Wind-Einspeisung", line=dict(color='#00bfff', width=1, dash='dot')), secondary_y=True)

# Null-Linie markieren (Wichtig für Negativpreise)
fig.add_hline(y=0, line_dash="dash", line_color="red", secondary_y=False)

fig.update_layout(title="Interaktive Strompreis-Analyse vs. EE-Erzeugung", 
                  hovermode="x unified", height=600, template="plotly_dark")
fig.update_yaxes(title_text="Preis [€/MWh]", secondary_y=False)
fig.update_yaxes(title_text="Erzeugung [MW]", secondary_y=True)

st.plotly_chart(fig, use_container_width=True)

# --- BUSINESS CASE TABELLE ---
st.subheader("📋 Top Lade-Zeitfenster (Ideale KPIs)")
best_slots = filtered_df.sort_values(by='Intraday_15min_Price').head(10)
st.table(best_slots[['Timestamp', 'Intraday_15min_Price', 'EE_Anteil']])

st.info("""
**Business-Tipp:** Nutze die Phasen mit negativen Preisen, um Flottenkunden von 'Managed Charging' zu überzeugen. 
Ein Elektroauto mit 100 kWh Batterie könnte in diesen Top-10-Slots theoretisch Geld verdienen oder kostenlos laden.
""")
