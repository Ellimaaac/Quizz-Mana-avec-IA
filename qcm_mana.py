# -*- coding: utf-8 -*-
"""
Quiz Management / Ressources Humaines
- Questions chargées depuis qcm_mana.json
- Explication des réponses via IA (Groq, API OpenAI-compatible)
"""

import os
import json
import random

import streamlit as st
from openai import OpenAI

# ================== CLIENT GROQ ==================

# La clé est lue depuis les secrets Streamlit Cloud ou une variable d'environnement.
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


# ================== CHARGEMENT DES QUESTIONS ==================

@st.cache_data(show_spinner=True)
def load_questions():
    """
    Charge les questions depuis qcm_mana.json.

    Le fichier peut contenir :
    - des commentaires commençant par '#'
    - des lignes vides

    Le champ "answer" dans le JSON est un INDEX 0-BASED
    (0 = 1ère proposition, 1 = 2ème, etc.).
    """
    json_path = os.path.join(os.path.dirname(__file__), "qcm_mana.json")
    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # On enlève les commentaires et lignes vides pour obtenir un JSON valide
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue  # ligne vide
        if stripped.startswith("#"):
            continue  # commentaire
        lines.append(line)

    clean = "\n".join(lines)
    data = json.loads(clean)

    # sécurité minimale : vérifier quelques champs
    for q in data:
        assert "text" in q and "choices" in q and "answer" in q, \
            "Chaque question doit avoir les clés 'text', 'choices', 'answer'"
    return data


# ================== IA D'EXPLICATION ==================

@st.cache_data(show_spinner=False)
def get_ai_explanation(question_text, choices, user_index, correct_index):
    """
    Utilise Groq (API OpenAI-compatible) pour expliquer la bonne réponse
    et pourquoi la réponse donnée est juste ou fausse.

    user_index et correct_index sont des indices 0-BASED.
    """
    if not GROQ_API_KEY:
        return (
            "⚠️ L'IA d'explication n'est pas configurée (clé GROQ_API_KEY manquante).\n"
            "Ajoute-la dans les *Secrets* Streamlit Cloud pour activer cette fonction."
        )

    user_answer = choices[user_index]
    correct_answer = choices[correct_index]

    prompt = f"""
Tu es un professeur qui explique simplement le management des ressources humaines
à un élève (niveau école d'ingénieur).

Question :
{question_text}

Choix possibles :
""" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)]) + f"""

Réponse de l'élève : {user_index+1}. {user_answer}
Bonne réponse : {correct_index+1}. {correct_answer}

1. Explique en quelques phrases pourquoi la bonne réponse est correcte.
2. Si la réponse de l'élève est fausse, explique en quoi sa réponse est trompeuse.
3. Reste concis, niveau ENSEA, en français.
"""

    response = client.responses.create(
        model="openai/gpt-oss-20b",  # modèle Groq : tu peux changer pour un autre
        input=prompt,
        instructions="Réponds en français, de manière pédagogique mais concise.",
    )

    return response.output_text.strip()


# ================== FONCTIONS UTILITAIRES ==================

def reset_quiz(selected_course, all_questions):
    """Initialise ou réinitialise le quiz dans st.session_state."""
    if selected_course == "Tous":
        qs = list(all_questions)
    else:
        qs = [q for q in all_questions if q.get("course") == selected_course]

    random.shuffle(qs)

    st.session_state.questions_selection = qs
    st.session_state.current_index = 0
    st.session_state.score = 0
    st.session_state.completed = False
    st.session_state.last_feedback = ""
    st.session_state.last_correct_answer = ""
    st.session_state.last_explanation = ""


# ================== APPLICATION STREAMLIT ==================

def main():
    st.set_page_config(page_title="Quiz Management / RH", page_icon="👥")

    st.title("👥 Quiz Management des Ressources Humaines")
    st.write(
        "Choisis un cours à réviser, réponds aux questions, et je calcule ton score.\n"
        "Les questions sont chargées depuis **qcm_mana.json**."
    )

    # Charger toutes les questions une fois
    all_questions = load_questions()
    if not all_questions:
        st.error("Aucune question trouvée dans qcm_mana.json.")
        return

    # Liste des cours disponibles (d'après le champ 'course' du JSON)
    courses = sorted({q.get("course", 1) for q in all_questions})
    course_options = ["Tous"] + courses

    # === Initialisation de l'état ===
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        reset_quiz("Tous", all_questions)

    # === Barre latérale : paramètres ===
    st.sidebar.header("Paramètres du quiz")
    choix_cours = st.sidebar.selectbox(
        "Cours à réviser",
        options=course_options,
        help="Choisis un numéro de cours ou 'Tous' pour mélanger.",
    )

    if st.sidebar.button("🔁 (Re)commencer le quiz"):
        reset_quiz(choix_cours, all_questions)

    # === Feedback de la question précédente ===
    if st.session_state.last_feedback:
        if "✅" in st.session_state.last_feedback:
            st.success(st.session_state.last_feedback)
        else:
            st.error(st.session_state.last_feedback)
            if st.session_state.last_correct_answer:
                st.info(f"Bonne réponse : {st.session_state.last_correct_answer}")

        if st.session_state.get("last_explanation"):
            with st.expander("📚 Explication par l'IA"):
                st.write(st.session_state.last_explanation)

    # === Raccourcis vers l'état courant ===
    qs = st.session_state.questions_selection
    idx = st.session_state.current_index
    total = len(qs)

    if total == 0:
        st.warning("Aucune question disponible. Vérifie qcm_mana.json.")
        return

    # === Quiz terminé ? ===
    if st.session_state.completed or idx >= total:
        st.header("🏁 Quiz terminé")
        score = st.session_state.score
        pourcentage = score / total * 100
        st.write(f"Score final : **{score} / {total}** ({pourcentage:.1f} %)")

        if pourcentage == 100:
            st.balloons()
            st.success("Parfait, tu maîtrises ce(s) cours !")
        elif pourcentage >= 70:
            st.success("Très bien, encore un peu de révisions et ce sera parfait.")
        else:
            st.warning("Ça vaut le coup de refaire un tour sur le cours et de rejouer le quiz.")

        st.write(
            "Tu peux changer de cours dans la barre latérale et cliquer sur "
            "**(Re)commencer le quiz** pour recommencer."
        )
        return

    # === Affichage de la question courante ===
    question = qs[idx]
    st.markdown(f"### Question {idx + 1} / {total} (cours {question.get('course')})")
    st.write(question["text"])

    # Radio pour choisir la réponse
    choices = question["choices"]
    correct_index = question["answer"]  # 0-based

    choix = st.radio(
        "Ta réponse :",
        options=list(range(len(choices))),  # 0,1,2,...
        format_func=lambda i: f"{i+1}. {choices[i]}",
        key=f"q_{idx}_answer",
    )

    # Bouton de validation
    if st.button("Valider et question suivante ➜"):
        bonne_reponse_texte = choices[correct_index]

        if choix == correct_index:
            st.session_state.score += 1
            st.session_state.last_feedback = "✅ Bonne réponse !"
            st.session_state.last_correct_answer = ""
        else:
            st.session_state.last_feedback = "❌ Mauvaise réponse."
            st.session_state.last_correct_answer = (
                f"{correct_index+1}. {bonne_reponse_texte}"
            )

        # Explication IA (Groq)
        with st.spinner("L'IA prépare une explication..."):
            st.session_state.last_explanation = get_ai_explanation(
                question_text=question["text"],
                choices=choices,
                user_index=choix,
                correct_index=correct_index,
            )

        # Passer à la question suivante
        st.session_state.current_index += 1
        if st.session_state.current_index >= total:
            st.session_state.completed = True

        st.rerun()

    # Affichage du score provisoire
    st.progress(idx / total)
    st.caption(f"Score provisoire : {st.session_state.score} / {total}")


if __name__ == "__main__":
    main()

