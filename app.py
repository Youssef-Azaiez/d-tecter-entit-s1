import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ==============================
# CONFIGURATION GÉNÉRALE
# ==============================
st.set_page_config(page_title="Dashboard Trésorerie", layout="wide", initial_sidebar_state="expanded")
st.title("💰 Dashboard intelligent de trésorerie")

# ==============================
# LISTES DE RÉFÉRENCE
# ==============================
CLIENT_EXCEPTIONS = [
    "SMART DESIGN ET CONSTRUCTION", "SMART DESIGN", "SMART DESIGN VIVID",
    "SAVINGS 15%", "COMPTE PRINCIPAL", "SLIM LINDA"
]

TRANSPORT = ["TOTAL", "SNCF-VOYAGEURS", "ESSO BOBIGNY", "ESSOBOBIGNYPVC", "SANEF"]

SALARIES = [
    "DA CRUZ DIOGO ARISTIDES", "BENVINDO FONSECA", "AISSOU NORIDINE", "BEN SIDHOUM YACINE",
    "HASSANI SALIM", "RACEM HAMMI", "JUNIOR YOUMSSI", "GHEZAL BRAHIM", "HACENE DJAIZ",
    "PATRICE CERCY", "TOMAS GARCIA", "TOUATI NADIR 3", "SOFIANE MERSEL 2", "HICHEM ESSAFI",
    "SABOUR OUALID", "HASSANI NADJIM"
]

BUREAU = ["LIDL 1620", "NESPRESSO FRANCE S.A.S", "ORANGE SA-ORANGE", "EDF", "FNAC DARTY SERVICES"]

# ==============================
# FONCTION DE CATÉGORISATION
# ==============================
def categorize_entity(counterparty, amount):
    cp = str(counterparty).upper().strip()

    if amount > 0 and cp not in [x.upper() for x in CLIENT_EXCEPTIONS]:
        return "Paiement client"
    if cp in [x.upper() for x in TRANSPORT]:
        return "Transport"
    if cp in [x.upper() for x in SALARIES]:
        return "Salaires"
    if "SEIZURE" in cp or "SAISIE" in cp:
        return "Saisie"
    if "QONTO" in cp or "FRAIS BANCAIRES" in cp or "VIR BANCAIRE" in cp:
        return "Frais bancaires"
    if cp in [x.upper() for x in BUREAU]:
        return "Bureau"
    if any(k in cp for k in ["RESTAURANT", "BURGER", "RESTAU", "BISTRO", "CAFÉ", "CAFE", "BRASSERIE"]):
        return "Restaurant"
    return "Fournisseur"

# ==============================
# PRÉTRAITEMENT DU FICHIER
# ==============================
@st.cache_data
def preprocess(df):
    df = df.copy()
    df = df.rename(columns=lambda c: c.strip())
    rename_map = {
        'Nom de la contrepartie': 'counterparty',
        'Montant total (TTC)': 'amount',
        "Date de l'opération (UTC)": 'date'
    }
    df = df.rename(columns=rename_map)

    needed = ['counterparty', 'amount', 'date']
    for col in needed:
        if col not in df.columns:
            raise KeyError(f"Colonne manquante : {col}")

    df = df.dropna(subset=['counterparty', 'amount'])
    df['counterparty'] = df['counterparty'].astype(str).str.strip()
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    df['category'] = df.apply(lambda x: categorize_entity(x['counterparty'], x['amount']), axis=1)
    return df

# ==============================
# IMPORT DU FICHIER
# ==============================
uploaded_file = st.file_uploader("📂 Charger ton fichier Excel (.xlsx)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        raw = pd.read_excel(uploaded_file)
        df = preprocess(raw)
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")
        st.stop()

    # Exclusion des entités internes pour les totaux
    df_filtered_totals = df[~df['counterparty'].str.upper().isin([x.upper() for x in CLIENT_EXCEPTIONS])]

    # ==============================
    # BARRE LATÉRALE - FILTRES
    # ==============================
    st.sidebar.header("🎛️ Filtres")
    min_date, max_date = df['date'].min(), df['date'].max()
    date_range = st.sidebar.date_input("Période", [min_date, max_date])
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    selected_category = st.sidebar.selectbox("Catégorie à analyser", sorted(df['category'].unique()))

    # Filtrage
    filt = (df['date'] >= start_date) & (df['date'] <= end_date)
    filtered = df[filt & (df['category'] == selected_category)].copy()

    # ==============================
    # INDICATEURS CLÉS
    # ==============================
    total_received = df_filtered_totals[df_filtered_totals['amount'] > 0]['amount'].sum()
    total_spent = df_filtered_totals[df_filtered_totals['amount'] < 0]['amount'].sum()
    net_balance = total_received + total_spent

    st.subheader("📊 Indicateurs globaux")
    k1, k2, k3 = st.columns(3)
    k1.metric("Total reçu", f"{total_received:,.2f} €")
    k2.metric("Total dépensé", f"{abs(total_spent):,.2f} €")
    k3.metric("Solde net", f"{net_balance:,.2f} €")

    st.markdown("---")

    # ==============================
    # DÉTAIL DE LA CATÉGORIE SÉLECTIONNÉE
    # ==============================
    st.subheader(f"📈 Analyse détaillée : **{selected_category}**")

    if filtered.empty:
        st.warning("Aucune transaction trouvée pour cette catégorie.")
        st.stop()

    # KPI catégorie
    cat_total = filtered['amount'].sum()
    cat_positive = filtered[filtered['amount'] > 0]['amount'].sum()
    cat_negative = filtered[filtered['amount'] < 0]['amount'].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total catégorie", f"{cat_total:,.2f} €")
    c2.metric("Montants positifs", f"{cat_positive:,.2f} €")
    c3.metric("Montants négatifs", f"{abs(cat_negative):,.2f} €")

    # ==============================
    # TOP ENTITÉS
    # ==============================
    st.markdown("### 🏆 Top entités de cette catégorie")
    top_entities = filtered.groupby('counterparty')['amount'].sum().reset_index().sort_values('amount', ascending=False)
    top_entities['abs_amount'] = top_entities['amount'].abs()

    chart_entities = alt.Chart(top_entities).mark_bar().encode(
        x=alt.X('abs_amount:Q', title="Montant total (€)"),
        y=alt.Y('counterparty:N', sort='-x', title="Entité"),
        color=alt.condition(alt.datum.amount > 0, alt.value("#2ca02c"), alt.value("#d62728")),
        tooltip=['counterparty', alt.Tooltip('amount', format=',.2f')]
    )
    st.altair_chart(chart_entities.properties(height=400), use_container_width=True)

    # ==============================
    # ÉVOLUTION TEMPORELLE
    # ==============================
    st.markdown("### 📅 Évolution temporelle")
    time_series = filtered.groupby(pd.Grouper(key='date', freq='W'))['amount'].sum().reset_index()
    chart_time = alt.Chart(time_series).mark_line(point=True).encode(
        x='date:T', y='amount:Q',
        tooltip=['date', alt.Tooltip('amount', format=',.2f')]
    )
    st.altair_chart(chart_time.properties(height=300), use_container_width=True)

    # ==============================
    # TABLE DÉTAILLÉE
    # ==============================
    st.markdown("### 📋 Transactions détaillées")
    st.dataframe(filtered.sort_values('date', ascending=False), use_container_width=True)

    csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Télécharger les données filtrées", data=csv,
                       file_name=f"transactions_{selected_category}.csv", mime="text/csv")

else:
    st.info("💡 Charge ton fichier Excel pour commencer l’analyse.")
