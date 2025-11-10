import streamlit as st
import pandas as pd

st.set_page_config(page_title="Analyse de trésorerie", layout="wide")
st.title("💰 Analyse automatique des virements et paiements")
st.write("Téléverse ton fichier Excel contenant les colonnes **Nom de la contrepartie** et **Montant total (TTC)**")

uploaded_file = st.file_uploader("📂 Charger ton fichier Excel (.xlsx)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        required_cols = ['Nom de la contrepartie', 'Montant total (TTC)']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Les colonnes {required_cols} doivent exister dans le fichier.")
        else:
            tx = df[required_cols].copy()
            tx = tx.rename(columns={
                'Nom de la contrepartie': 'counterparty',
                'Montant total (TTC)': 'amount'
            })
            tx = tx.dropna(subset=['counterparty', 'amount'])
            tx['counterparty'] = tx['counterparty'].astype(str).str.strip()
            tx['amount'] = pd.to_numeric(tx['amount'], errors='coerce')

            received = tx[tx['amount'] > 0].groupby('counterparty')['amount'].sum().reset_index().sort_values('amount', ascending=False)
            paid = tx[tx['amount'] < 0].groupby('counterparty')['amount'].sum().reset_index().sort_values('amount')

            st.success("✅ Analyse terminée avec succès !")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📥 Entités ayant reçu de l'argent")
                st.dataframe(received, use_container_width=True)
                st.download_button(
                    label="⬇️ Télécharger la liste des récepteurs",
                    data=received.to_csv(index=False).encode('utf-8'),
                    file_name="entities_received.csv",
                    mime="text/csv"
                )
            with col2:
                st.subheader("💸 Entités ayant payé de l'argent")
                st.dataframe(paid, use_container_width=True)
                st.download_button(
                    label="⬇️ Télécharger la liste des payeurs",
                    data=paid.to_csv(index=False).encode('utf-8'),
                    file_name="entities_paid.csv",
                    mime="text/csv"
                )

    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier : {e}")

else:    # =========================
# Section de catégorisation
# =========================
st.subheader("📝 Catégoriser les entités")

# On combine toutes les entités pour éviter les doublons
combined = pd.concat([received, paid])
combined = combined.drop_duplicates(subset=['counterparty'])

# Dictionnaire pour stocker les catégories
category_dict = {}

# Création d’un champ texte pour chaque entité
for e in combined['counterparty']:
    cat = st.text_input(f"Catégorie pour '{e}'", key=e, placeholder="Ex : salarié, fournisseur, virement interne, saisi...")
    category_dict[e] = cat

# Bouton pour télécharger les catégories
if st.button("💾 Sauvegarder les catégories"):
    cat_df = pd.DataFrame(list(category_dict.items()), columns=['counterparty', 'category'])
    st.download_button(
        "⬇️ Télécharger les catégories",
        data=cat_df.to_csv(index=False).encode('utf-8'),
        file_name="entities_categories.csv",
        mime="text/csv"
    )
    st.success("✅ Catégories prêtes à être téléchargées !")

