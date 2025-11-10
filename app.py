import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Dashboard Trésorerie", layout="wide",
                   initial_sidebar_state="expanded")
st.title("💰 Dashboard automatique de trésorerie")

# -------------------------
# Listes de référence
# -------------------------
CLIENT_EXCEPTIONS = [
    "SMART DESIGN ET CONSTRUCTION", "SMART DESIGN", "SMART DESIGN VIVID",
    "SAVINGS 15%", "COMPTE PRINCIPAL", "SLIM LINDA"
]

TRANSPORT = ["TOTAL", "SNCF-VOYAGEURS", "ESSO BOBIGNY", "ESSOBOBIGNYPVC", "SANEF"]

SALARIES = [
    "DA CRUZ DIOGO ARISTIDES","BENVINDO FONSECA","AISSOU NORIDINE","BEN SIDHOUM YACINE",
    "HASSANI SALIM","RACEM HAMMI","JUNIOR YOUMSSI","GHEZAL BRAHIM","HACENE DJAIZ",
    "PATRICE CERCY","TOMAS GARCIA","TOUATI NADIR 3","SOFIANE MERSEL 2","HICHEM ESSAFI",
    "SABOUR OUALID","HASSANI NADJIM"
]

BUREAU = ["LIDL 1620","NESPRESSO FRANCE S.A.S","ORANGE SA-ORANGE","EDF","FNAC DARTY SERVICES"]

# -------------------------
# Fonction de catégorisation
# -------------------------
def categorize_entity(counterparty, amount):
    cp = str(counterparty).upper().strip()

    # Paiement client
    if amount > 0 and cp not in [x.upper() for x in CLIENT_EXCEPTIONS]:
        return "Paiement client"

    if cp in [x.upper() for x in TRANSPORT]:
        return "Transport"

    if cp in [x.upper() for x in SALARIES]:
        return "Salaires"

    if "SEIZURE" in cp or "SAISIE" in cp:
        return "Saisie"

    if "QONTO" in cp or "FRAIS BANCAIRES" in cp:
        return "Frais bancaires"

    if cp in [x.upper() for x in BUREAU]:
        return "Bureau"

    if any(k in cp for k in ["RESTAURANT", "BURGER", "RESTAU", "BISTRO", "CAFÉ", "CAFE", "BRASSERIE"]):
        return "Restaurant"

    return "Fournisseur"


@st.cache_data
def preprocess(df):
    df = df.copy()
    df = df.rename(columns=lambda c: c.strip())
    rename_map = {}
    if 'Nom de la contrepartie' in df.columns:
        rename_map['Nom de la contrepartie'] = 'counterparty'
    if 'Montant total (TTC)' in df.columns:
        rename_map['Montant total (TTC)'] = 'amount'
    if "Date de l'opération (UTC)" in df.columns:
        rename_map["Date de l'opération (UTC)"] = 'date'
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

# -------------------------
# Upload
# -------------------------
uploaded_file = st.file_uploader(
    "📂 Charger ton fichier Excel (.xlsx) contenant :\n- Nom de la contrepartie\n- Montant total (TTC)\n- Date de l'opération (UTC)",
    type=["xlsx", "xls"]
)

if uploaded_file is not None:
    try:
        raw = pd.read_excel(uploaded_file, sheet_name=0)
        df = preprocess(raw)
    except Exception as e:
        st.error(f"Erreur lors du chargement : {e}")
        st.stop()

    # Exclusion des entités internes pour toutes les analyses
    EXCLUDED_ENTITIES = [x.upper() for x in CLIENT_EXCEPTIONS]
    df = df[~df['counterparty'].str.upper().isin(EXCLUDED_ENTITIES)]

    # -------------------------
    # Filtres latéraux
    # -------------------------
    st.sidebar.header("🔎 Filtres")
    min_date, max_date = df['date'].min().date(), df['date'].max().date()
    date_range = st.sidebar.date_input("Période", [min_date, max_date])
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    cat_filter = st.sidebar.multiselect("Catégories", sorted(df['category'].unique()), default=None)
    search = st.sidebar.text_input("Recherche fournisseur")

    filt = (df['date'] >= start_date) & (df['date'] <= end_date)
    if cat_filter:
        filt &= df['category'].isin(cat_filter)
    if search:
        filt &= df['counterparty'].str.contains(search, case=False, na=False)

    filtered = df[filt]

    # -------------------------
    # KPIs
    # -------------------------
    total_received = filtered[filtered['amount'] > 0]['amount'].sum()
    total_spent = filtered[filtered['amount'] < 0]['amount'].sum()
    net = total_received + total_spent

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total reçu", f"{total_received:,.2f} €")
    k2.metric("Total dépensé", f"{abs(total_spent):,.2f} €")
    k3.metric("Solde net", f"{net:,.2f} €")
    k4.metric("Transactions", f"{len(filtered):,}")

    # -------------------------
    # Graphiques
    # -------------------------
    st.markdown("### 📂 Répartition par catégorie")
    cat_summary = filtered.groupby('category')['amount'].sum().reset_index()
    cat_summary['abs_amount'] = cat_summary['amount'].abs()

    if not cat_summary.empty:
        bar = alt.Chart(cat_summary).mark_bar().encode(
            x=alt.X('abs_amount:Q', title='Montant (€)'),
            y=alt.Y('category:N', sort='-x', title='Catégorie'),
            color=alt.condition(alt.datum.amount > 0, alt.value("#2ca02c"), alt.value("#d62728")),
            tooltip=['category', alt.Tooltip('amount', format=',.2f')]
        )
        st.altair_chart(bar.properties(height=400), use_container_width=True)

    st.markdown("### 🏆 Top fournisseurs payés")
    top_paid = (filtered[filtered['amount'] < 0]
                .groupby('counterparty')['amount']
                .sum().reset_index().sort_values('amount'))
    st.dataframe(top_paid.rename(columns={'counterparty':'Entité','amount':'Montant (€)'}))

    st.markdown("### 📅 Évolution temporelle")
    time_df = filtered.groupby([pd.Grouper(key='date', freq='W'), 'category'])['amount'].sum().reset_index()
    if not time_df.empty:
        area = alt.Chart(time_df).mark_area(opacity=0.7).encode(
            x='date:T', y='amount:Q', color='category:N',
            tooltip=['date', 'category', 'amount']
        )
        st.altair_chart(area.properties(height=350), use_container_width=True)

    # -------------------------
    # Table complète + export
    # -------------------------
    st.markdown("### 📋 Détails des transactions")
    st.dataframe(filtered.sort_values('date', ascending=False))
    csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Télécharger CSV filtré", data=csv, file_name="transactions_filtrees.csv", mime="text/csv")

else:
    st.info("💡 Charge ton fichier Excel pour commencer l’analyse.")
