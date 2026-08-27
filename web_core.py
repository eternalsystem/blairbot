# -*- coding: utf-8 -*-
"""
web_core.py — logique et rendu HTML partagés entre les deux façons de
servir BlairBot sur le web :

- blairbot_web.py : serveur local classique (process persistant, état
  gardé en mémoire + sauvegardé dans web_state.json).
- api/index.py : fonction serverless Vercel (pas de process permanent, pas
  de disque persistant entre deux requêtes) — l'état vit dans le
  navigateur (localStorage) et est renvoyé à chaque appel.

Tout ce qui est ici est volontairement SANS ÉTAT GLOBAL : chaque fonction
reçoit (evidence_mode, answers) explicitement et ne dépend de rien d'autre,
pour pouvoir tourner aussi bien dans un process qui vit des heures que dans
une fonction qui ne vit que le temps d'une requête.
"""

import re
from html import escape as _esc
from string import Template

from ghosts_data import (
    EVIDENCES,
    EVIDENCE_QUESTIONS,
    GHOSTS,
    TRAIT_CATEGORY,
    TRAIT_CATEGORY_ORDER,
    TRAIT_GHOSTS,
    TRAIT_QUESTIONS,
)

# --------------------------------------------------------------------------
# Questions (mêmes données que le CLI, réindexées pour un accès direct par
# identifiant de question).
# --------------------------------------------------------------------------
QUESTIONS = {}
for _e in EVIDENCES:
    QUESTIONS[_e] = {
        "kind": "evidence",
        "text": EVIDENCE_QUESTIONS[_e],
        "category": "Preuves",
        "yes_ghosts": {g for g, d in GHOSTS.items() if _e in d["evidences"]},
    }
for _t, _text in TRAIT_QUESTIONS.items():
    QUESTIONS[_t] = {
        "kind": "trait",
        "text": _text,
        "category": TRAIT_CATEGORY.get(_t, "Autres"),
        "yes_ghosts": set(TRAIT_GHOSTS[_t]),
    }

CATEGORY_ORDER = ["Preuves"] + TRAIT_CATEGORY_ORDER
CATEGORY_RANK = {name: i for i, name in enumerate(CATEGORY_ORDER)}


def sanitize_answers(answers):
    """Ne garde que des réponses valides pour un client qui enverrait un
    state obsolète (vieux qid supprimé, valeur corrompue...)."""
    if not isinstance(answers, dict):
        return {}
    return {k: v for k, v in answers.items() if k in QUESTIONS and v in ("oui", "non", "sais_pas")}


def sanitize_mode(mode):
    return mode if mode in (0, 1, 2, 3) else 3


# --------------------------------------------------------------------------
# Logique de déduction : recalculée à chaque appel à partir de zéro (pas
# d'historique séquentiel, donc pas d'ordre imposé et pas besoin de revenir
# en arrière — il suffit de recocher une réponse pour la corriger).
# --------------------------------------------------------------------------
def compute_candidates(evidence_mode, answers):
    candidates = set(GHOSTS.keys())
    for qid, answer in answers.items():
        q = QUESTIONS.get(qid)
        if not q or answer == "sais_pas":
            continue
        if answer == "oui":
            candidates &= q["yes_ghosts"]
        elif q["kind"] == "evidence" and evidence_mode < 3:
            # Mode à preuves réduites : un "non" ne prouve rien (la preuve
            # peut juste être masquée par le mode), donc on ne filtre pas.
            continue
        else:
            candidates -= q["yes_ghosts"]
    return candidates


def find_culprits(evidence_mode, answers):
    """Si plus aucun fantôme ne correspond, cherche quelles réponses,
    repassées individuellement à 'pas sûr', débloqueraient la situation."""
    culprits = []
    for qid, answer in answers.items():
        if answer == "sais_pas":
            continue
        trial = dict(answers)
        trial[qid] = "sais_pas"
        if compute_candidates(evidence_mode, trial):
            culprits.append(qid)
    return culprits


def score_candidates(evidence_mode, answers, candidates):
    """Classement indicatif : tous les survivants respectent déjà les
    réponses fiables. Le seul signal qui peut encore les départager, ce
    sont les 'non' à des preuves en mode réduit (non filtrants, mais un
    fantôme qui n'a de toute façon pas cette preuve colle mieux à
    l'observation qu'un fantôme dont elle serait juste restée cachée)."""
    scores = {g: 1.0 for g in candidates}
    for qid, answer in answers.items():
        if answer != "non":
            continue
        q = QUESTIONS.get(qid)
        if not q or q["kind"] != "evidence" or evidence_mode >= 3:
            continue
        for g in candidates:
            if qid not in GHOSTS[g]["evidences"]:
                scores[g] += 1.0
    total = sum(scores.values()) or 1.0
    ranking = sorted(((g, scores[g] / total * 100) for g in scores), key=lambda kv: (-kv[1], kv[0]))
    return ranking


def question_priority(q, candidates):
    """Utilité d'une question pas encore répondue : à quel point elle
    départagerait les suspects encore possibles (même heuristique que le
    choix de question adaptatif du CLI : on maximise le plus petit des deux
    groupes 'oui'/'non'). -1 = ne départage plus rien pour l'instant, donc
    à renvoyer en bas de la liste plutôt qu'à cacher (répondre reste
    possible, ça sert au moins de garde-fou anti-contradiction)."""
    if len(candidates) <= 1:
        return -1
    yes = len(candidates & q["yes_ghosts"])
    no = len(candidates) - yes
    if yes == 0 or no == 0:
        return -1
    return min(yes, no)


def build_results(evidence_mode, answers):
    candidates = compute_candidates(evidence_mode, answers)
    answered = sum(1 for a in answers.values() if a != "sais_pas")
    result = {
        "evidence_mode": evidence_mode,
        "count": len(candidates),
        "answered": answered,
        "contradiction": not candidates,
        "culprits": find_culprits(evidence_mode, answers) if not candidates else [],
        "ranking": [],
        "unanswered_html": render_unanswered_html(candidates, answers, evidence_mode),
        "answered_html": render_answered_html(answers),
    }
    if candidates:
        result["ranking"] = [
            {
                "name": name,
                "pct": round(pct, 1),
                "evidences": sorted(GHOSTS[name]["evidences"]),
                "desc": GHOSTS[name]["desc"],
            }
            for name, pct in score_candidates(evidence_mode, answers, candidates)
        ]
    return result


# --------------------------------------------------------------------------
# Rendu HTML des questions
# --------------------------------------------------------------------------
def _slug(qid):
    return re.sub(r"[^a-zA-Z0-9_]", "_", qid)


def render_question(qid, q, current_answer):
    s = _slug(qid)
    text = _esc(q["text"])
    qid_attr = _esc(qid, quote=True)
    tag = _esc(q["category"])

    def radio(value, label):
        checked = " checked" if current_answer == value else ""
        return (
            f'<label class="opt opt-{value}{" is-checked" if checked else ""}">'
            f'<input type="radio" name="q_{s}" value="{value}"{checked} data-qid="{qid_attr}">'
            f"<span>{label}</span></label>"
        )

    return (
        f'<div class="question" data-qid="{qid_attr}">'
        f'<div class="qtext"><span class="tag">{tag}</span>{text}</div>'
        f'<div class="opts">{radio("oui", "Oui")}{radio("non", "Non")}{radio("sais_pas", "Pas sûr")}</div>'
        f"</div>"
    )


def render_unanswered_html(candidates, answers, evidence_mode):
    # En mode sans preuve, ou une fois le quota de preuves de cette partie
    # atteint (autant de "oui" que d'évidences annoncées), les questions de
    # preuve restantes ne servent plus à rien : on ne les propose plus,
    # comme le fait déjà le CLI (cf. BlairBot._candidate_questions).
    evidence_found = sum(
        1 for qid, a in answers.items() if a == "oui" and QUESTIONS.get(qid, {}).get("kind") == "evidence"
    )
    evidence_exhausted = evidence_mode == 0 or evidence_found >= evidence_mode

    unanswered = [
        (qid, q) for qid, q in QUESTIONS.items()
        if answers.get(qid, "sais_pas") == "sais_pas"
        and not (q["kind"] == "evidence" and evidence_exhausted)
    ]
    if not unanswered:
        return '<p class="empty">Toutes les questions utiles ont une réponse. 🎉</p>'
    unanswered.sort(
        key=lambda item: (
            -question_priority(item[1], candidates),
            CATEGORY_RANK.get(item[1]["category"], 99),
            item[1]["text"],
        )
    )
    return "".join(render_question(qid, q, "sais_pas") for qid, q in unanswered)


def render_answered_html(answers):
    answered = [(qid, QUESTIONS[qid]) for qid in answers if answers[qid] != "sais_pas" and qid in QUESTIONS]
    if not answered:
        return '<p class="empty">Aucune réponse pour l\'instant.</p>'
    answered.sort(key=lambda item: (CATEGORY_RANK.get(item[1]["category"], 99), item[1]["text"]))
    return "".join(render_question(qid, q, answers[qid]) for qid, q in answered)


def render_mode_options(evidence_mode):
    labels = {0: "Aucune (mode sans preuve)", 1: "1 preuve", 2: "2 preuves", 3: "3 preuves (normal)"}
    opts = []
    for value in (3, 2, 1, 0):
        selected = " selected" if evidence_mode == value else ""
        opts.append(f'<option value="{value}"{selected}>{labels[value]}</option>')
    return "".join(opts)


BASE_CSS = r"""
  :root {
    --bg: #0f1115; --panel: #171a21; --panel2: #1f2330; --border: #2a2f3d;
    --text: #e8e9ee; --muted: #9aa0b0; --accent: #8b5cf6;
    --oui: #22c55e; --non: #ef4444; --pas-sur: #6b7280;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, Segoe UI, Roboto, sans-serif;
    background: var(--bg); color: var(--text); padding-bottom: 4rem;
  }
  .wrap { max-width: 820px; margin: 0 auto; padding: 0 1rem; }
  header { padding: 1.5rem 0 1rem; }
  h1 { font-size: 1.4rem; margin: 0 0 0.3rem; }
  .subtitle { color: var(--muted); font-size: 0.9rem; line-height: 1.5; }
  .navlink { color: var(--accent); text-decoration: none; font-size: 0.85rem; }
  .navlink:hover { text-decoration: underline; }
  .topbar {
    position: sticky; top: 0; z-index: 10; background: rgba(15,17,21,0.97);
    backdrop-filter: blur(6px); border-bottom: 1px solid var(--border);
    padding: 0.75rem 0;
  }
  .topbar-inner { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; }
  #results { flex: 1 1 260px; font-size: 0.95rem; }
  .controls { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
  select, button {
    background: var(--panel2); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 0.4rem 0.6rem; font-size: 0.85rem; cursor: pointer;
  }
  button:hover, select:hover { border-color: var(--accent); }
  details.category {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    margin: 0.7rem 0; overflow: hidden;
  }
  summary {
    cursor: pointer; padding: 0.7rem 1rem; font-weight: 600; list-style: none;
    display: flex; justify-content: space-between; align-items: center;
  }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "▸"; color: var(--muted); transition: transform 0.15s; }
  details[open] > summary::after { transform: rotate(90deg); }
  .count { color: var(--muted); font-weight: 400; font-size: 0.8rem; }
  .qlist { border-top: 1px solid var(--border); }
  .unanswered-panel, details.category { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; margin: 0.7rem 0; overflow: hidden; }
  .panel-title { padding: 0.7rem 1rem; font-weight: 600; display: flex; justify-content: space-between; align-items: baseline; }
  .panel-hint { color: var(--muted); font-weight: 400; font-size: 0.78rem; }
  .question {
    display: flex; justify-content: space-between; align-items: center; gap: 1rem;
    padding: 0.65rem 1rem; border-bottom: 1px solid var(--border);
  }
  .question:last-child { border-bottom: none; }
  .question.culprit { background: rgba(234, 179, 8, 0.12); box-shadow: inset 3px 0 0 #eab308; }
  .qtext { font-size: 0.88rem; line-height: 1.4; }
  .tag {
    display: inline-block; font-size: 0.68rem; color: var(--accent); border: 1px solid var(--accent);
    border-radius: 4px; padding: 0.05rem 0.35rem; margin-right: 0.5rem; vertical-align: middle;
    white-space: nowrap;
  }
  .empty { color: var(--muted); font-size: 0.85rem; padding: 0.8rem 1rem; margin: 0; }
  .opts { display: flex; gap: 0.3rem; flex-shrink: 0; }
  .opt {
    display: flex; align-items: center; gap: 0.3rem; font-size: 0.8rem;
    border: 1px solid var(--border); border-radius: 6px; padding: 0.25rem 0.55rem;
    cursor: pointer; color: var(--muted); user-select: none;
  }
  .opt input { accent-color: var(--accent); margin: 0; }
  /* :has() couvre les navigateurs récents ; .is-checked (posé en JS) sert de
     filet pour les navigateurs plus anciens qui ne le supportent pas. */
  .opt-oui:has(input:checked), .opt-oui.is-checked { border-color: var(--oui); color: var(--oui); background: rgba(34,197,94,0.1); }
  .opt-non:has(input:checked), .opt-non.is-checked { border-color: var(--non); color: var(--non); background: rgba(239,68,68,0.1); }
  .opt-sais_pas:has(input:checked), .opt-sais_pas.is-checked { border-color: var(--pas-sur); color: var(--text); }
  .winner { font-size: 1.05rem; }
  .winner strong { color: var(--accent); }
  .ranking { margin: 0.2rem 0 0; padding-left: 1.1rem; max-height: 5.5rem; overflow-y: auto; }
  .ranking li { font-size: 0.85rem; margin-bottom: 0.15rem; }
  .pct { color: var(--accent); font-variant-numeric: tabular-nums; }
  .warn { color: #eab308; }
  footer { text-align: center; color: var(--muted); font-size: 0.75rem; margin-top: 2rem; }
  /* Page "Fiches des fantômes" */
  .ghost-index { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 1rem 0; }
  .ghost-index a {
    background: var(--panel2); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.25rem 0.6rem; font-size: 0.8rem; color: var(--text); text-decoration: none;
  }
  .ghost-index a:hover { border-color: var(--accent); color: var(--accent); }
  #search {
    width: 100%; margin: 0.7rem 0 0.2rem; background: var(--panel2); color: var(--text);
    border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem 0.7rem; font-size: 0.9rem;
  }
  .ghost-card {
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 1.1rem 1.3rem; margin: 1rem 0; scroll-margin-top: 5rem;
  }
  .ghost-card h2 { margin: 0 0 0.6rem; font-size: 1.15rem; color: var(--accent); }
  .ev-badges { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.8rem; }
  .ev-badge {
    background: rgba(139,92,246,0.15); border: 1px solid var(--accent); color: var(--accent);
    border-radius: 5px; padding: 0.15rem 0.5rem; font-size: 0.75rem;
  }
  .ghost-desc { font-size: 0.9rem; line-height: 1.55; margin: 0 0 0.9rem; }
  .clues-title { font-size: 0.8rem; font-weight: 600; color: var(--muted); margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: 0.02em; }
  .clues { margin: 0; padding-left: 1.2rem; font-size: 0.85rem; line-height: 1.7; }
  .clues li { margin-bottom: 0.25rem; }
  .empty-clue { color: var(--muted); font-style: italic; }
"""


# --------------------------------------------------------------------------
# Page de référence : fiche de chaque fantôme (preuves, description, indices
# de repérage) — page statique, identique pour tout le monde, aucun état.
# --------------------------------------------------------------------------
def render_ghost_card(name):
    data = GHOSTS[name]
    badges = "".join(f'<span class="ev-badge">{_esc(e)}</span>' for e in sorted(data["evidences"]))

    ordered_traits = sorted(
        data["traits"],
        key=lambda t: (CATEGORY_RANK.get(TRAIT_CATEGORY.get(t, "Autres"), 99), TRAIT_QUESTIONS[t]),
    )
    if ordered_traits:
        clues = "".join(
            f'<li><span class="tag">{_esc(TRAIT_CATEGORY.get(t, "Autres"))}</span>{_esc(TRAIT_QUESTIONS[t])}</li>'
            for t in ordered_traits
        )
    else:
        clues = '<li class="empty-clue">Pas de comportement particulier connu — seules ses preuves permettent de l\'identifier.</li>'

    return (
        f'<article class="ghost-card" id="g-{_slug(name)}">'
        f"<h2>{_esc(name)}</h2>"
        f'<div class="ev-badges">{badges}</div>'
        f'<p class="ghost-desc">{_esc(data["desc"])}</p>'
        f'<div class="clues-title">🔎 Comment le repérer</div>'
        f'<ul class="clues">{clues}</ul>'
        f"</article>"
    )


def render_ghost_index():
    return "".join(f'<a href="#g-{_slug(n)}">{_esc(n)}</a>' for n in sorted(GHOSTS))


GHOSTS_PAGE_TEMPLATE = Template(r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BlairBot — Fiches des fantômes</title>
<style>$BASE_CSS</style>
</head>
<body>
<div class="wrap">
  <header>
    <a class="navlink" href="/">← Retour au questionnaire</a>
    <h1>📖 Fiches des 21 fantômes</h1>
    <div class="subtitle">
      Preuves, description et comportements observables pour repérer chaque
      fantôme. Données du wiki Blair Roblox (Fandom) — estimation
      indicative, le jeu évolue avec ses mises à jour.
    </div>
    <input id="search" type="text" placeholder="🔎 Filtrer par nom ou preuve…">
  </header>
  <div class="ghost-index">$GHOST_INDEX</div>
  $GHOST_CARDS
  <footer>BlairBot Web — données du wiki Blair Roblox (Fandom).</footer>
</div>
<script>
document.getElementById("search").addEventListener("input", (e) => {
  const q = e.target.value.trim().toLowerCase();
  document.querySelectorAll(".ghost-card").forEach((card) => {
    card.style.display = card.textContent.toLowerCase().includes(q) ? "" : "none";
  });
});
</script>
</body>
</html>
""")


def render_ghosts_page():
    cards = "".join(render_ghost_card(name) for name in sorted(GHOSTS))
    return GHOSTS_PAGE_TEMPLATE.substitute(BASE_CSS=BASE_CSS, GHOST_INDEX=render_ghost_index(), GHOST_CARDS=cards)
