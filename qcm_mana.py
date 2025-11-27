# -*- coding: utf-8 -*-
"""
Quiz Management / Ressources Humaines
- Questions chargées depuis qcm_mana.json
- Explications IA via GROQ (lib officielle groq)
"""

import os
import json
import random
import streamlit as st
from groq import Groq


# ================== CLIENT GROQ ==================

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

client = Groq(api_key=GROQ_API_KEY)


# ================== CHARGEMENT DES QUESTIONS ==================

@st.cache_data(show_spinner=True)
def load_questions():
    """
    Charge les questions depuis qcm_mana.json.
    Autorise les lignes vides et les commentaires (#).
    """

    json_path = os.path.join(os.path.dirname(__file__), "qcm_mana.json")

    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned_lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        cleaned_lines.append(line)

    clean = "\n".join(cleaned_lines)
    data = json.loads(clean)

    for q in data:
        assert "text" in q and "choices" in q and "answer" in q, \
            "Chaque question doit avoir 'text', 'choices', 'answer'"

    return data


# ================== IA GROQ ==================

@st.cache_data(show_spinner=False)
def get_ai_explanation(question_text, choices, user_index, correct_index):
    """Renvoie une explication pédagogique via Groq."""

    if not GROQ_API_KEY:
        return (
            "⚠️ Aucune clé GROQ_API_KEY configurée.\n"
            "Ajoute-la dans les Secrets Streamlit pour activer l'explication IA."
        )

    user_answer = choices[user_index]
    correct_answer = choices[correct_index]

    prompt = f"""
Tu es un professeur qui explique clairement le Management des Ressources Humaines
à un étudiant de niveau licence/master.

QUESTION :
{question_text}

CHOIX :
""" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)]) + f"""

L'étudiant a répondu : {user_index+1}. {user_answer}
La bonne réponse est : {correct_index+1}. {correct_answer}

1. Explique pourquoi la bonne réponse est correcte.
2. Si la réponse de l'étudiant est fausse, explique pourquoi elle est trompeuse.
3. Reste concis et pédagogue.
"""

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content.strip()


# ================== LOGIQUE QUIZ ==================

def reset_quiz(selected_course, all_questions):
    """Prépare les questions dans session_state."""

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
    st.set_page_config(page_title="Quiz Management RH", page_icon="👥")

    st.title("👥 Quiz Management / Ressources Humaines (avec IA)")
    st.write("Les questions sont chargées depuis **qcm_mana.json**.")

    # Charger les questions
    all_questions = load_questions()

    # Identifier les numéros de cours
    courses = sorted({q.get("course", 1) for q in all_questions})
    course_options = ["Tous"] + courses

    # Initialisation
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        reset_quiz("Tous", all_questions)

    # Barre latérale
    st.sidebar.header("Paramètres du quiz")
    choix_cours = st.sidebar.selectbox(
        "Cours à réviser :",
        options=course_options,
        help="Choisis un numéro ou 'Tous'",
    )

    if st.sidebar.button("🔁 (Re)commencer"):
        reset_quiz(choix_cours, all_questions)

    # Feedback de la question précédente
    if st.session_state.last_feedback:
        if st.session_state.last_feedback.startswith("✅"):
            st.success(st.session_state.last_feedback)
        else:
            st.error(st.session_state.last_feedback)
            if st.session_state.last_correct_answer:
                st.info(f"Bonne réponse : {st.session_state.last_correct_answer}")

        if st.session_state.last_explanation:
            with st.expander("📘 Explication IA"):
                st.write(st.session_state.last_explanation)

    # État actuel
    qs = st.session_state.questions_selection
    idx = st.session_state.current_index
    total = len(qs)

    # Fin du quiz
    if st.session_state.completed or idx >= total:
        st.header("🏁 Résultat final")
        score = st.session_state.score
        pct = score / total * 100

        st.write(f"### Score : **{score} / {total}** ({pct:.1f} %)")

        if pct == 100:
            st.balloons()
            st.success("Incroyable ! Score parfait 👏")
        elif pct >= 70:
            st.success("Très bien ! Tu maîtrises déjà une bonne partie du cours.")
        else:
            st.warning("Tu peux rejouer pour progresser 😊")

        return

    # Affichage de la question
    q = qs[idx]
    st.markdown(f"### Question {idx+1} / {total} (Cours {q.get('course')})")
    st.write(q["text"])

    choices = q["choices"]
    correct = q["answer"]

    choix = st.radio(
        "Ta réponse :",
        options=list(range(len(choices))),
        format_func=lambda i: f"{i+1}. {choices[i]}",
        key=f"q_{idx}_rep",
    )

    # Validation
    if st.button("Valider ➜"):
        if choix == correct:
            st.session_state.score += 1
            st.session_state.last_feedback = "✅ Bonne réponse !"
            st.session_state.last_correct_answer = ""
        else:
            st.session_state.last_feedback = "❌ Mauvaise réponse."
            st.session_state.last_correct_answer = f"{correct+1}. {choices[correct]}"

        # Explication IA
        with st.spinner("L'IA analyse ta réponse..."):
            st.session_state.last_explanation = get_ai_explanation(
                q["text"], choices, choix, correct
            )

        # Question suivante
        st.session_state.current_index += 1
        if st.session_state.current_index >= total:
            st.session_state.completed = True

        st.rerun()

    # Score provisoire
    st.progress(idx / total)
    st.caption(f"Score provisoire : {st.session_state.score} / {total}")


if __name__ == "__main__":
    main()
