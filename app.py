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

# Catégories / listes de référence (tu peux compléter)
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
# Fonctions utilitaires
# -------------------------
def categorize_entity(counterparty, amount):
    cp = str(counterparty).upper().strip()

    # Paiement client : montant positif et non dans les exceptions
    if amount > 0 and cp not in [x.upper() for x in CLIENT_EXCEPTIONS]:
        return "Paiement client"

    # Transport
    if cp in [x.upper() for x in TRANSPORT]:
        return "Transport"

    # Salaires
    if cp in [x.upper() for x in SALARIES]:
        return "Salaires"

    # Saisie / seizure (sensibilité à la présence de 'SEIZURE' ou 'SAISIE')
    if "SEIZURE" in cp or "SAISIE" in cp:
        return "Saisie"

    # Frais bancaires
    if "QONTO" in cp or "FRAIS BANCAIRES" in cp or "VIR BANCAIRE" in cp:
        return "Frais bancaires"

    # Bureau (magasins & services)
    if cp in [x.upper() for x in BUREAU]:
        return "Bureau"

    # Restaurant (si le nom contient restaurant / burger / restau / bistro / cafe)
    if any(k in cp for k in ["RESTAURANT", "BURGER", "RESTAU", "BISTRO", "CAFÉ", "CAFE", "BRASSERIE"]):
        return "Restaurant"

    # Fournisseur si aucun cas précédent
    return "Fournisseur"


@st.cache_data
def preprocess(df):
    df = df.copy()
    df = df.rename(columns=lambda c: c.strip())
    # Normalisation des colonnes attendues
    rename_map = {}
    if 'Nom de la contrepartie' in df.columns:
        rename_map['Nom de la contrepartie'] = 'counterparty'
    if 'Montant total (TTC)' in df.columns:
        rename_map['Montant total (TTC)'] = 'amount'
    if "Date de l'opération (UTC)" in df.columns:
        rename_map["Date de l'opération (UTC)"] = 'date'
    df = df.rename(columns=rename_map)

    # Filtre colonnes
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
uploaded_file = st.file_uploader("📂 Charger ton fichier Excel (.xlsx) contenant au moins :\n- Nom de la contrepartie\n- Montant total (TTC)\n- Date de l'opération (UTC)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        raw = pd.read_excel(uploaded_file, sheet_name=0)
        df = preprocess(raw)
    except KeyError as ke:
        st.error(str(ke) + " — vérifie les entêtes de colonnes.")
        st.stop()
    except Exception as e:
        st.error(f"Erreur lecture/processing : {e}")
        st.stop()

    # -------------------------
    # Sidebar : filtres
    # -------------------------
    st.sidebar.header("🔎 Filtres et options")
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()
    date_range = st.sidebar.date_input("Période", [min_date, max_date], min_value=min_date, max_value=max_date)
    if len(date_range) != 2:
        st.sidebar.warning("Sélectionne une plage de deux dates")
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    categories_list = sorted(df['category'].unique().tolist())
    selected_categories = st.sidebar.multiselect("Catégories", ["-- Tout --"] + categories_list, default=["-- Tout --"])
    supplier_search = st.sidebar.text_input("Rechercher un fournisseur (nom partiel)")

    # Filtrage effectif
    filt = (df['date'] >= start_date) & (df['date'] <= end_date)
    filtered = df[filt].copy()
    if selected_categories and "-- Tout --" not in selected_categories:
        filtered = filtered[filtered['category'].isin(selected_categories)]
    if supplier_search:
        filtered = filtered[filtered['counterparty'].str.contains(supplier_search, case=False, na=False)]

    # -------------------------
    # KPIs
    # -------------------------
    total_received = filtered[filtered['amount'] > 0]['amount'].sum()
    total_spent = filtered[filtered['amount'] < 0]['amount'].sum()
    net = total_received + total_spent

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total reçu", f"{total_received:,.2f} €", delta=None)
    k2.metric("Total dépensé", f"{abs(total_spent):,.2f} €", delta=None)
    k3.metric("Solde net", f"{net:,.2f} €", delta=None)
    k4.metric("Transactions", f"{len(filtered):,}", delta=None)

    # -------------------------
    # Répartition par catégorie
    # -------------------------
    st.markdown("### 📂 Répartition par catégorie")
    cat_summary = filtered.groupby('category')['amount'].sum().reset_index()
    cat_summary['abs_amount'] = cat_summary['amount'].abs()
    cat_summary = cat_summary.sort_values('amount')

    if not cat_summary.empty:
        bar = alt.Chart(cat_summary).mark_bar().encode(
            x=alt.X('abs_amount:Q', title='Montant (valeur absolue)'),
            y=alt.Y('category:N', sort='-x', title='Catégorie'),
            color=alt.condition(alt.datum.amount > 0, alt.value("#2ca02c"), alt.value("#d62728")),
            tooltip=['category', alt.Tooltip('amount', format=',.2f')]
        )
        st.altair_chart(bar.properties(height=400), use_container_width=True)
    else:
        st.info("Aucune donnée dans la période / filtres sélectionnés.")

    # -------------------------
    # Top fournisseurs (dépenses)
    # -------------------------
    st.markdown("### 🏆 Top entités payées (dépenses)")
    top_paid = filtered[filtered['amount'] < 0].groupby('counterparty')['amount'].sum().reset_index().sort_values('amount')
    top_paid['abs_amount'] = top_paid['amount'].abs()
    st.dataframe(top_paid[['counterparty','amount']].rename(columns={'counterparty':'Entité','amount':'Montant'}), use_container_width=True)

    # -------------------------
    # Courbe temporelle (stacked area par catégorie)
    # -------------------------
    st.markdown("### 📅 Evolution temporelle par catégorie")
    time_df = (filtered.set_index('date')
                     .resample('W')['amount']
                     .sum()
                     .reset_index()
                     .rename(columns={'amount':'total_week'}))
    # ligne totale
    if not time_df.empty:
        line = alt.Chart(time_df).mark_line(point=True).encode(
            x='date:T',
            y='total_week:Q',
            tooltip=['date','total_week']
        )
        st.altair_chart(line.properties(height=300), use_container_width=True)

    # détail par catégorie sur la période (daily or weekly stacked)
    stacked = (filtered.groupby([pd.Grouper(key='date', freq='W'), 'category'])['amount']
               .sum().reset_index().rename(columns={'date':'week'}))
    if not stacked.empty:
        area = alt.Chart(stacked).mark_area(opacity=0.7).encode(
            x='week:T',
            y='amount:Q',
            color='category:N',
            tooltip=['week', 'category', 'amount']
        ).interactive()
        st.altair_chart(area.properties(height=350), use_container_width=True)

    # -------------------------
    # Table complète et export
    # -------------------------
    st.markdown("### 📋 Détail des transactions (filtré)")
    st.dataframe(filtered.sort_values('date', ascending=False).reset_index(drop=True), use_container_width=True)

    csv = filtered.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Télécharger CSV (filtré)", data=csv, file_name="transactions_filtered.csv", mime="text/csv")

    # -------------------------
    # Tips & small analyses
    # -------------------------
    st.markdown("### 🔍 Analyses rapides")
    # Moyenne paiement par catégorie
    avg_by_cat = filtered.groupby('category')['amount'].mean().reset_index().sort_values('amount')
    st.write("Moyenne par catégorie :")
    st.dataframe(avg_by_cat, use_container_width=True)

    # Pourcentage des dépenses par catégorie (sur dépenses uniquement)
    spent_by_cat = filtered[filtered['amount'] < 0].groupby('category')['amount'].sum().abs().reset_index()
    total_spent_abs = spent_by_cat['amount'].sum()
    if total_spent_abs > 0:
        spent_by_cat['pct'] = spent_by_cat['amount'] / total_spent_abs
        st.write("Répartition (%) des dépenses par catégorie :")
        st.dataframe(spent_by_cat.sort_values('pct', ascending=False), use_container_width=True)

else:
    st.info("💡 Charge ton fichier Excel pour lancer l'analyse. Assure-toi que les colonnes existent :\n- Nom de la contrepartie\n- Montant total (TTC)\n- Date de l'opération (UTC)")
