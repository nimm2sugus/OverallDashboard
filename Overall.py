import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io

st.set_page_config(page_title="re cap Intelligence Hub", layout="wide")
st.title("🛡️ Energy Market Intelligence OS")

def robust_load_csv(file_path):
    """Liest SMARD-Dateien, egal wie sie formatiert sind."""
    encodings = ['utf-8-sig', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                lines = f.readlines()
            
            # 1. Header-Suche: Wo fängt die Tabelle an?
            header_idx = -1
            sep = ';' # Default
            for i, line in enumerate(lines[:20]):
                if "Datum" in line or "Anfang" in line:
                    header_idx = i
                    # Trennzeichen-Check: Komma oder Semikolon?
                    sep = ';' if line.count(';') > line.count(',') else ','
                    break
            
            if header_idx == -1: continue

            # 2. Einlesen mit den erkannten Parametern
            df = pd.read_csv(file_path, sep=sep, decimal=',', skiprows=header_idx, 
                             encoding=enc, on_bad_lines='skip', engine='python')
            
            # 3. Bereinigung
            df.columns = [str(c).strip() for c in df.columns]
            
            if 'Datum' in df.columns and 'Anfang' in df.columns:
                # Zeitstempel-Fussion
                df['Timestamp'] = pd.to_datetime(df['Datum'] + ' ' + df['Anfang'], dayfirst=True, errors='coerce')
                df = df.dropna(subset=['Timestamp'])
                
                # Werte-Spalten identifizieren (alles außer Zeit)
                value_cols = [c for c in df.columns if c not in ['Datum', 'Anfang', 'Ende', 'Timestamp']]
                
                # Spaltennamen mit Dateiname ergänzen, um Duplikate zu vermeiden (z.B. Preis_Intraday vs Preis_DA)
                short_name = file_path.split('_')[0] if '_' in file_path else "Data"
                new_names = {c: f"{short_name}_{c}" for c in value_cols}
                df = df.rename(columns=new_names)
                
                return df[['Timestamp'] + list(new_names.values())].set_index('Timestamp')
        except:
            continue
    return None

def get_all_data():
    files = [f for f in os.listdir('.') if f.lower().endswith('.csv') and len(f) > 5]
    if not files: return None
    
    all_dfs = []
    for f in files:
        df = robust_load_csv(f)
        if df is not None:
            all_dfs.append(df)
    
    if all_dfs:
        # Zusammenführen über Zeitstempel (Outer Join)
        merged = pd.concat(all_dfs, axis=1).sort_index().reset_index()
        return merged
    return None

# --- UI LOGIK ---
with st.spinner("Analysiere Repositories..."):
    df = get_all_data()

if df is not None and not df.empty:
    st.sidebar.success(f"Datenquelle: {len(os.listdir('.'))} Dateien erkannt")
    
    # Verfügbare Metriken (Spalten)
    available_cols = [c for c in df.columns if c != 'Timestamp']
    
    # Gruppierung nach Dateinamen für bessere Übersicht
    selected_metrics = st.sidebar.multiselect(
        "Verfügbare Datensätze (Viertelstunde & Stunde):", 
        available_cols,
        default=available_cols[:3] if len(available_cols) > 3 else available_cols
    )

    if selected_metrics:
        # Haupt-Grafik
        fig = px.line(df, x='Timestamp', y=selected_metrics, 
                      title="Markt-Analyse: Erzeugung, Preis & Verbrauch",
                      template="plotly_dark",
                      color_discrete_sequence=px.colors.qualitative.Bold)
        
        fig.update_layout(
            hovermode="x unified",
            xaxis_title="Zeitverlauf",
            yaxis_title="Wert (MW / EUR / MWh)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # BUSINESS INSIGHTS
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📊 Statistik (gewählter Zeitraum)")
            st.write(df[selected_metrics].describe().T[['mean', 'min', 'max']])
        with c2:
            st.subheader("💡 Business-Check")
            # Prüfen ob ein Preis im Datensatz ist
            price_cols = [c for c in selected_metrics if "preis" in c.lower()]
            if price_cols:
                curr_price = price_cols[0]
                neg_count = len(df[df[curr_price] < 0])
                st.write(f"Anzahl Negativpreis-Phasen: **{neg_count}**")
                if neg_count > 0:
                    st.warning("⚠️ Strategischer Hinweis: Profitabilität von Flexibilitäten hoch!")

        with st.expander("📥 Daten-Vorschau & Export"):
            st.dataframe(df)
            st.download_button("Als CSV exportieren", df.to_csv(index=False), "energy_intelligence_export.csv")
else:
    st.error("Keine gültigen SMARD-Dateien im Repository gefunden!")
    st.markdown("""
    ### Kurze Checkliste:
    1. Sind die CSV-Dateien im Hauptverzeichnis des GitHub-Repos?
    2. Haben die Dateien die Endung `.csv`?
    3. **Tipp:** Lösche alle Dateien, die keine SMARD-Daten sind, um Verwirrung zu vermeiden.
