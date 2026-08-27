# -*- coding: utf-8 -*-
"""
BlairBot Web — mini interface web locale pour répondre aux questions à ton
rythme (coche Oui / Non / Pas sûr sur celles que tu peux vérifier tout de
suite, reviens plus tard sur les autres), avec un classement des fantômes
possibles qui se met à jour en direct.

Contrairement à blairbot.py (CLI, une question à la fois choisie de façon
adaptative), ici TOUTES les questions sont affichées d'un coup, regroupées
par thème, et le résultat est recalculé à chaque coche à partir de zéro —
pas besoin de répondre dans un ordre précis, ni même de toutes les remplir.

Aucune dépendance à installer : uniquement la bibliothèque standard Python
(http.server). Les réponses sont sauvegardées dans web_state.json à côté de
ce fichier, donc tu peux fermer le serveur et le relancer plus tard sans
perdre ta progression.

Utilisation :
    python blairbot_web.py
    -> ouvre automatiquement http://127.0.0.1:8765 dans ton navigateur.
"""

import http.server
import json
import os
import re
import sys
import webbrowser
from html import escape as _esc
from string import Template

# Même précaution que blairbot.py : la console Windows plante parfois sur
# les accents/emojis avec son encodage historique. On force l'UTF-8.
if sys.platform == "win32":
    os.system("chcp 65001 >nul")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ghosts_data import (
    EVIDENCES,
    EVIDENCE_QUESTIONS,
    GHOSTS,
    TRAIT_CATEGORY,
    TRAIT_CATEGORY_ORDER,
    TRAIT_GHOSTS,
    TRAIT_QUESTIONS,
)

PORT = 8765
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_state.json")

# --------------------------------------------------------------------------
# Questions (mêmes données que le CLI, juste réindexées pour un accès direct
# par identifiant de question).
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

STATE = {"evidence_mode": 3, "answers": {}}


def load_state():
    global STATE
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                STATE = {
                    "evidence_mode": int(data.get("evidence_mode", 3)),
                    "answers": {k: v for k, v in data.get("answers", {}).items() if k in QUESTIONS},
                }
        except Exception:
            pass


def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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
# Rendu HTML
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


def render_mode_options():
    labels = {0: "Aucune (mode sans preuve)", 1: "1 preuve", 2: "2 preuves", 3: "3 preuves (normal)"}
    opts = []
    for value in (3, 2, 1, 0):
        selected = " selected" if STATE["evidence_mode"] == value else ""
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

PAGE_TEMPLATE = Template(r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BlairBot Web</title>
<style>$BASE_CSS</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div class="topbar-inner">
      <div id="results">Chargement…</div>
      <div class="controls">
        <a class="navlink" href="/fantomes" target="_blank" rel="noopener">📖 Fiches des fantômes</a>
        <select id="mode-select" title="Nombre de preuves cette partie">$MODE_OPTIONS</select>
        <button id="reset-btn" type="button">Réinitialiser</button>
      </div>
    </div>
  </div>
  <header>
    <h1>👻 BlairBot Web</h1>
    <div class="subtitle">
      Coche <b>Oui</b> / <b>Non</b> / <b>Pas sûr</b> au fil de ton enquête, dans n'importe quel
      ordre. Le classement en haut se met à jour tout seul. Pour une <b>preuve</b>,
      ne réponds « Non » que si tu l'as vraiment vérifiée en jeu et qu'elle n'y est pas —
      sinon laisse « Pas sûr ».
    </div>
  </header>

  <div class="unanswered-panel">
    <div class="panel-title">
      <span>❓ À répondre</span>
      <span class="panel-hint">triées par utilité : les plus décisives en premier</span>
    </div>
    <div class="qlist" id="unanswered-list">$UNANSWERED_HTML</div>
  </div>

  <details class="category">
    <summary>✅ Déjà répondu <span class="count" id="answered-count">($ANSWERED_COUNT)</span></summary>
    <div class="qlist" id="answered-list">$ANSWERED_HTML</div>
  </details>

  <footer>BlairBot Web — données du wiki Blair Roblox (Fandom), estimation indicative.</footer>
</div>

<script>
const INITIAL_RESULTS = $INITIAL_RESULTS_JSON;

async function postJSON(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

function renderResults(r, updateLists) {
  const panel = document.getElementById("results");

  if (r.contradiction) {
    panel.innerHTML = '<span class="warn">⚠️ Aucun fantôme ne correspond à ces réponses — repasse en \'Pas sûr\' une des réponses surlignées ci-dessous.</span>';
  } else if (r.count === 1) {
    const g = r.ranking[0];
    panel.innerHTML = '👻 C\'est un <strong class="winner-name">' + g.name + '</strong> ! (preuves : ' + g.evidences.join(", ") + ')';
  } else {
    let html = r.count + " fantôme(s) possible(s)" + (r.answered === 0 ? " — coche des réponses pour affiner" : "") + " :";
    html += '<ol class="ranking">';
    r.ranking.slice(0, 8).forEach((g) => {
      html += "<li><span class=\"pct\">" + g.pct.toFixed(1) + "%</span> " + g.name + "</li>";
    });
    html += "</ol>";
    panel.innerHTML = html;
  }

  // Au chargement initial, le serveur a déjà rendu les listes dans la page
  // (ordre de priorité inclus) : pas la peine de les réécrire à l'identique.
  // Après chaque réponse en revanche, on remplace leur contenu par la
  // version fraîchement recalculée côté serveur — pas besoin de
  // ré-attacher les écouteurs grâce à la délégation d'événements plus bas.
  if (updateLists) {
    document.getElementById("unanswered-list").innerHTML = r.unanswered_html;
    document.getElementById("answered-list").innerHTML = r.answered_html;
  }
  document.getElementById("answered-count").textContent = "(" + r.answered + ")";

  if (r.contradiction) {
    r.culprits.forEach((qid) => {
      const row = document.querySelector('.question[data-qid="' + CSS.escape(qid) + '"]');
      if (row) row.classList.add("culprit");
    });
  }
}

// Délégation d'événements : les lignes de question sont recréées à chaque
// réponse, donc on écoute sur un ancêtre stable plutôt que sur chaque
// <input> individuellement.
document.body.addEventListener("change", async (e) => {
  if (!e.target.matches('input[type=radio]')) return;
  const qid = e.target.dataset.qid;
  const answer = e.target.value;
  const r = await postJSON("/api/answer", { qid, answer });
  renderResults(r, true);
});

document.getElementById("mode-select").addEventListener("change", async (e) => {
  const r = await postJSON("/api/mode", { mode: parseInt(e.target.value, 10) });
  renderResults(r, true);
});

document.getElementById("reset-btn").addEventListener("click", async () => {
  if (!confirm("Réinitialiser toutes les réponses ?")) return;
  const r = await postJSON("/api/reset", {});
  renderResults(r, true);
});

renderResults(INITIAL_RESULTS, false);
</script>
</body>
</html>
""")


def render_page():
    results = build_results(STATE["evidence_mode"], STATE["answers"])
    # Les listes sont déjà rendues directement dans la page (voir
    # UNANSWERED_HTML/ANSWERED_HTML) : inutile de les dupliquer dans le JSON
    # embarqué, qui ne sert qu'à peindre la barre de résultats au chargement.
    initial_json = {k: v for k, v in results.items() if k not in ("unanswered_html", "answered_html")}
    return PAGE_TEMPLATE.substitute(
        BASE_CSS=BASE_CSS,
        MODE_OPTIONS=render_mode_options(),
        UNANSWERED_HTML=results["unanswered_html"],
        ANSWERED_HTML=results["answered_html"],
        ANSWERED_COUNT=results["answered"],
        INITIAL_RESULTS_JSON=json.dumps(initial_json, ensure_ascii=False),
    )


# --------------------------------------------------------------------------
# Page de référence : fiche de chaque fantôme (preuves, description, indices
# de repérage) — accessible depuis le questionnaire via "📖 Fiches des
# fantômes".
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


# --------------------------------------------------------------------------
# Serveur HTTP (bibliothèque standard uniquement)
# --------------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_str, status=200):
        body = html_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_html(render_page())
        elif self.path in ("/fantomes", "/fantomes/"):
            self._send_html(render_ghosts_page())
        elif self.path == "/api/state":
            self._send_json(build_results(STATE["evidence_mode"], STATE["answers"]))
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {}

        if self.path == "/api/answer":
            qid, answer = payload.get("qid"), payload.get("answer")
            if qid in QUESTIONS and answer in ("oui", "non", "sais_pas"):
                STATE["answers"][qid] = answer
                save_state()
        elif self.path == "/api/mode":
            mode = payload.get("mode")
            if mode in (0, 1, 2, 3):
                STATE["evidence_mode"] = mode
                save_state()
        elif self.path == "/api/reset":
            STATE["answers"] = {}
            save_state()
        else:
            self.send_error(404)
            return

        self._send_json(build_results(STATE["evidence_mode"], STATE["answers"]))

    def log_message(self, format, *args):
        pass  # silence les logs d'accès dans la console


def main():
    load_state()
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"BlairBot Web démarré sur {url}  (Ctrl+C pour arrêter)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur.")


if __name__ == "__main__":
    main()
