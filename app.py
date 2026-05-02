import streamlit as st
import sqlite3
import pandas as pd
import re
import pdfplumber
from docx import Document

# Connexion à la base de données SQLite
conn = sqlite3.connect("ats_database.db")
cursor = conn.cursor()
def extraire_texte_pdf(fichier):
    texte = ""
    with pdfplumber.open(fichier) as pdf:
        for page in pdf.pages:
            texte += page.extract_text() or ""
    return texte


def extraire_texte_docx(fichier):
    doc = Document(fichier)
    return "\n".join([p.text for p in doc.paragraphs])


def extraire_infos_cv(texte):
    infos = {
        "nom": "",
        "email": "",
        "telephone": "",
        "competences": ""
    }

    email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", texte)
    telephone = re.search(r"(\+33|0)[1-9](\s?\d{2}){4}", texte)

    if email:
        infos["email"] = email.group()

    if telephone:
        infos["telephone"] = telephone.group()

    mots_cles = [
        "Python", "Excel", "SIRH", "Paie", "RH", "SQL",
        "Power BI", "ADP", "Workday", "SAP", "SuccessFactors",
        "Recruitment", "Recrutement", "Administration du personnel"
    ]

    competences_trouvees = [
        mot for mot in mots_cles if mot.lower() in texte.lower()
    ]

    infos["competences"] = ", ".join(competences_trouvees)

    return infos
    
# Création de la table candidats si elle n'existe pas
cursor.execute("""
CREATE TABLE IF NOT EXISTS candidats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    email TEXT NOT NULL,
    poste TEXT NOT NULL,
    experience INTEGER,
    competences TEXT,
    salaire INTEGER,
    disponibilite TEXT,
    score INTEGER,
    statut TEXT
)
""")

conn.commit()

# Fonction de scoring
def calcul_score(experience, competences, salaire, disponibilite):
    score = 0

    if experience >= 5:
        score += 3
    elif experience >= 2:
        score += 1

    if "recrutement" in competences.lower():
        score += 2

    if disponibilite == "Immédiate":
        score += 1

    if salaire > 50000:
        score -= 2

    if score >= 4:
        statut = "Prioritaire"
    elif score >= 1:
        statut = "À étudier"
    else:
        statut = "Refusé"

    return score, statut

# Interface
st.title("Mini ATS RH")

# Dashboard RH
df_dashboard = pd.read_sql_query("SELECT * FROM candidats", conn)

total = len(df_dashboard)
prioritaires = len(df_dashboard[df_dashboard["statut"] == "Prioritaire"])
entretien = len(df_dashboard[df_dashboard["statut"] == "En entretien"])
recrutes = len(df_dashboard[df_dashboard["statut"] == "Recruté"])
a_etudier = len(df_dashboard[df_dashboard["statut"] == "À étudier"])

st.subheader("Indicateurs RH")

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Total candidats", total)
col2.metric("Prioritaires", prioritaires)
col3.metric("À étudier", a_etudier)
col4.metric("En entretien", entretien)
col5.metric("Recrutés", recrutes)

tab1, tab2, tab3, tab4 = st.tabs([
    "Ajouter un candidat",
    "Consulter les candidats",
    "Mettre à jour le statut",
    "Supprimer un candidat"
])

# Formulaire
with tab1:
    st.header("Ajouter un candidat")

cv_file = st.file_uploader("Importer un CV", type=["pdf", "docx"])

infos_cv = {
    "nom": "",
    "email": "",
    "telephone": "",
    "competences": ""
}

if cv_file:
    if cv_file.name.endswith(".pdf"):
        texte_cv = extraire_texte_pdf(cv_file)
    elif cv_file.name.endswith(".docx"):
        texte_cv = extraire_texte_docx(cv_file)
    else:
        texte_cv = ""

    infos_cv = extraire_infos_cv(texte_cv)

    st.success("CV analysé. Formulaire pré-rempli.")
    
    nom = st.text_input("Nom", value=infos_cv["nom"])
    email = st.text_input("Email", value=infos_cv["email"])
    poste = st.text_input("Poste")
    experience = st.number_input("Expérience (années)", 0, 50)
    competences = st.text_input("Compétences", value=infos_cv["competences"])
    salaire = st.number_input("Salaire souhaité")
    disponibilite = st.selectbox("Disponibilité", ["Immédiate", "1 mois", "3 mois"])

    if st.button("Ajouter le candidat"):
        score, statut = calcul_score(experience, competences, salaire, disponibilite)

        cursor.execute("""
        INSERT INTO candidats (nom, email, poste, experience, competences, salaire, disponibilite, score, statut)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nom, email, poste, experience, competences, salaire, disponibilite, score, statut))

        conn.commit()

        st.success("Candidat enregistré avec score et statut")

# Tableau
with tab2:
    st.header("Candidats enregistrés")

    filtre_statut = st.selectbox(
        "Choisir un statut",
        ["Tous", "Prioritaire", "À étudier", "Refusé"]
    )

    recherche = st.text_input("Rechercher un candidat par nom")

    if filtre_statut == "Tous":
        query = "SELECT * FROM candidats"
    else:
        query = f"SELECT * FROM candidats WHERE statut = '{filtre_statut}'"

    df = pd.read_sql_query(query, conn)

    if recherche:
        df = df[df["nom"].str.contains(recherche, case=False, na=False)]

    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Exporter les candidats en CSV",
        data=csv,
        file_name="candidats_mini_ats.csv",
        mime="text/csv"
    )

with tab3:
    st.header("Mettre à jour le statut d’un candidat")

    df = pd.read_sql_query("SELECT * FROM candidats", conn)

    if not df.empty:
        df["affichage_candidat"] = (
            df["nom"] + " - " + df["poste"] + " - " + df["statut"]
        )

        candidat_selectionne = st.selectbox(
            "Sélectionner un candidat",
            df["affichage_candidat"]
        )

        candidat_id = df.loc[
            df["affichage_candidat"] == candidat_selectionne,
            "id"
        ].iloc[0]

        nouveau_statut = st.selectbox(
            "Nouveau statut",
            ["Prioritaire", "À étudier", "En entretien", "Recruté", "Refusé"]
        )

        if st.button("Mettre à jour le statut"):
            cursor.execute(
                "UPDATE candidats SET statut = ? WHERE id = ?",
                (nouveau_statut, int(candidat_id))
            )

            conn.commit()

            st.success("Statut mis à jour")
    else:
        st.info("Aucun candidat à mettre à jour")

with tab4:
    st.header("Supprimer un candidat")

    df_delete = pd.read_sql_query("SELECT * FROM candidats", conn)

    if not df_delete.empty:
        df_delete["affichage_candidat"] = (
            df_delete["nom"] + " - " + df_delete["poste"] + " - " + df_delete["statut"]
        )

        candidat_a_supprimer = st.selectbox(
            "Sélectionner un candidat à supprimer",
            df_delete["affichage_candidat"]
        )

        candidat_id = df_delete.loc[
            df_delete["affichage_candidat"] == candidat_a_supprimer,
            "id"
        ].iloc[0]

        confirmation = st.checkbox("Je confirme vouloir supprimer ce candidat")

        if st.button("Supprimer le candidat"):
            if confirmation:
                cursor.execute(
                    "DELETE FROM candidats WHERE id = ?",
                    (int(candidat_id),)
                )
                conn.commit()
                st.success("Candidat supprimé")
            else:
                st.warning("Veuillez confirmer la suppression")
    else:
        st.info("Aucun candidat à supprimer")
