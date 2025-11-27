# -*- coding: utf-8 -*-
"""
Quiz Management / Ressources Humaines
- Questions chargées depuis qcm_mana.json
- Explications IA via Groq (lib 'groq')
"""

import os
import json
import random

import streamlit as st
from groq import Groq, BadRequestError


# ================== CLIENT GROQ ==================

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

client = Groq(api_key=GROQ_API_KEY)


# ================== CHARGEMENT DES QUESTIONS ==================

@st.cache_data(show_spinner=True)
def load_questions():
    """
    Charge les questions depuis qcm_mana.json.

    Le fichier peut contenir :
    - des commentaires commençant par '#'
    - des lignes vides

    Le champ "answer" est un INDEX 0-BASED.
    """
    json_path = os.path.join(os.path.dirname(__file__), "qcm_mana.json")

    with open(json_path, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        lines.append(line)

    clean = "\n".join(lines)
    data = json.loads(clean)

    for q in data:
        assert "text" in q and "choices" in q and "answer" in q, \
            "Chaque question doit avoir 'text', 'choices', 'answer'"

    return data


# ================== IA D'EXPLICATION (GROQ) ==================

def get_ai_explanation(question_text, choices, user_index, correct_index):
    """
    Utilise Groq pour expliquer la bonne réponse et la mauvaise.
    user_index et correct_index sont des indices 0-BASED.
    """

    if not GROQ_API_KEY:
        return (
            "⚠️ IA inactive : aucune clé GROQ_API_KEY configurée dans les Secrets "
            "Streamlit. Ajoute-la pour activer l'explication automatique."
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
2. Si la réponse de l'étudiant est fausse, explique en quoi elle est trompeuse.
3. Réponds en français, de manière concise et pédagogique.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # modèle Groq léger, rapide et dispo partout
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    except BadRequestError as e:
        # Erreur côté API (mauvais modèle, quota, etc.)
        return (
            "⚠️ Erreur lors de l'appel à Groq (BadRequestError).\n"
            f"Détails retournés par l'API : {e}"
        )
    except Exception as e:
        # Toute autre erreur (réseau, etc.)
        return (
            "⚠️ Erreur inattendue lors de l'appel à Groq.\n"
            f"Détails techniques : {e}"
        )


# ================== FONCTIONS UTILITAIRES DU QUIZ ==================

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

    st.title("👥 Quiz Management des Ressources Humaines (avec IA Groq)")
    st.write(
        "Choisis un cours à réviser, réponds aux questions, et je calcule ton score.\n"
        "Les questions sont chargées depuis **qcm_mana.json**."
    )

    all_questions = load_questions()
    if not all_questions:
        st.error("Aucune question trouvée dans qcm_mana.json.")
        return

    # Numéros de cours possibles (si 'course' est présent dans le JSON)
    courses = sorted({q.get("course", 1) for q in all_questions})
    course_options = ["Tous"] + courses

    # Initialisation de l'état
    if "initialized_mana" not in st.session_state:
        st.session_state.initialized_mana = True
        reset_quiz("Tous", all_questions)

    # === Barre latérale ===
    st.sidebar.header("Paramètres du quiz")
    choix_cours = st.sidebar.selectbox(
        "Cours à réviser",
        options=course_options,
        help="Choisis un numéro de cours ou 'Tous' pour mélanger.",
    )

    if st.sidebar.button("🔁 (Re)commencer le quiz"):
        reset_quiz(choix_cours, all_questions)

    # === Feedback question précédente ===
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

    # === État courant ===
    qs = st.session_state.questions_selection
    idx = st.session_state.current_index
    total = len(qs)

    if total == 0:
        st.warning("Aucune question disponible pour ce cours.")
        return

    # === Quiz terminé ? ===
    if st.session_state.completed or idx >= total:
        st.header("🏁 Quiz terminé")
        score = st.session_state.score
        pct = score / total * 100
        st.write(f"Score final : **{score} / {total}** ({pct:.1f} %)")

        if pct == 100:
            st.balloons()
            st.success("Incroyable, score parfait ! 👏")
        elif pct >= 70:
            st.success("Très bon résultat, tu maîtrises déjà bien le cours.")
        else:
            st.warning("Courage, rejoue le quiz pour progresser 😊")

        return

    # === Affichage de la question courante ===
    q = qs[idx]
    st.markdown(f"### Question {idx + 1} / {total} (cours {q.get('course')})")
    st.write(q["text"])

    choices = q["choices"]
    correct_index = q["answer"]  # index 0-based dans le JSON

    choix = st.radio(
        "Ta réponse :",
        options=list(range(len(choices))),  # 0,1,2,...
        format_func=lambda i: f"{i+1}. {choices[i]}",
        key=f"q_{idx}_answer",
    )

    # === Validation ===
    if st.button("Valider ➜"):
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

        # Explication IA (sans cache, avec gestion d'erreur)
        with st.spinner("L'IA Groq prépare une explication..."):
            st.session_state.last_explanation = get_ai_explanation(
                question_text=q["text"],
                choices=choices,
                user_index=choix,
                correct_index=correct_index,
            )

        # Question suivante
        st.session_state.current_index += 1
        if st.session_state.current_index >= total:
            st.session_state.completed = True

        st.rerun()

    # === Score provisoire ===
    st.progress(idx / total)
    st.caption(f"Score provisoire : {st.session_state.score} / {total}")


if __name__ == "__main__":
    main()

