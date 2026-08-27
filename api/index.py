# -*- coding: utf-8 -*-
"""
Fonction serverless Vercel pour BlairBot Web.

Contrairement à blairbot_web.py (process local persistant, état gardé en
mémoire et sur disque), une fonction serverless ne garde RIEN entre deux
requêtes : ni mémoire, ni fichier. L'état (mode de preuves + réponses)
vit donc entièrement dans le navigateur (localStorage) et est renvoyé par
le client à chaque appel — le serveur se contente de recalculer le
résultat à partir de ce qu'on lui donne, sans jamais rien stocker.

Vercel détecte automatiquement une variable de module `app` suivant la
convention WSGI (`app(environ, start_response)`) — aucune dépendance
externe (pas de Flask) n'est nécessaire ici.

Toutes les routes (/, /fantomes, /api/answer, /api/mode, /api/reset,
/api/compute) passent par ce seul fichier ; voir vercel.json pour la
règle de réécriture qui route tout vers /api/index.
"""

import json
import os
import sys
from string import Template
from urllib.parse import parse_qs

# ghosts_data.py et web_core.py sont à la racine du repo, un niveau
# au-dessus de ce fichier (api/index.py) : on l'ajoute au chemin d'import.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_core import (  # noqa: E402
    BASE_CSS,
    SINGLE_MODE_BUTTON_HTML,
    SINGLE_MODE_VIEW_HTML,
    SINGLE_QUESTION_JS,
    build_results,
    render_ghosts_page,
    render_mode_options,
    sanitize_answers,
    sanitize_mode,
)

VERCEL_PAGE_TEMPLATE = Template(r"""<!doctype html>
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
        $SINGLE_MODE_BUTTON
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
      sinon laisse « Pas sûr ». « 🎯 Question par question » pose les questions une par
      une dans l'ordre le plus utile — sors-en quand tu veux. Tes réponses restent sur cet
      appareil (mémoire du navigateur), rien n'est envoyé ailleurs que le calcul du résultat.
    </div>
  </header>

  $SINGLE_MODE_VIEW

  <div class="unanswered-panel" id="unanswered-panel">
    <div class="panel-title">
      <span>❓ À répondre</span>
      <span class="panel-hint">triées par utilité : les plus décisives en premier</span>
    </div>
    <div class="qlist" id="unanswered-list">$UNANSWERED_HTML</div>
  </div>

  <details class="category" id="answered-details">
    <summary>✅ Déjà répondu <span class="count" id="answered-count">($ANSWERED_COUNT)</span></summary>
    <div class="qlist" id="answered-list">$ANSWERED_HTML</div>
  </details>

  <footer>BlairBot Web — données du wiki Blair Roblox (Fandom), estimation indicative.</footer>
</div>

<script>
const STORAGE_KEY = "blairbot_state";

function loadLocal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return { mode: parsed.mode ?? 3, answers: parsed.answers ?? {} };
      }
    }
  } catch (e) { /* localStorage indisponible ou corrompu : on repart à zéro */ }
  return { mode: 3, answers: {} };
}

function saveLocal() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(localState)); } catch (e) {}
}

let localState = loadLocal();

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
  const r = await postJSON("/api/answer", { mode: localState.mode, answers: localState.answers, qid, answer });
  localState.answers = r.answers;
  saveLocal();
  renderResults(r, true);
});

document.getElementById("mode-select").addEventListener("change", async (e) => {
  const mode = parseInt(e.target.value, 10);
  const r = await postJSON("/api/mode", { mode, answers: localState.answers });
  localState.mode = mode;
  localState.answers = r.answers;
  saveLocal();
  renderResults(r, true);
});

document.getElementById("reset-btn").addEventListener("click", async () => {
  if (!confirm("Réinitialiser toutes les réponses ?")) return;
  const r = await postJSON("/api/reset", { mode: localState.mode });
  localState.answers = {};
  saveLocal();
  renderResults(r, true);
});

document.getElementById("mode-select").value = String(localState.mode);

$SINGLE_QUESTION_JS

// Le serveur n'a aucune mémoire : la page qu'il vient de rendre reflète un
// état par défaut. On l'hydrate immédiatement avec l'état sauvegardé dans
// ce navigateur (s'il y en a un).
(async () => {
  const r = await postJSON("/api/compute", localState);
  localState.answers = r.answers;
  renderResults(r, true);
})();
</script>
</body>
</html>
""")


def render_vercel_page():
    results = build_results(3, {})
    return VERCEL_PAGE_TEMPLATE.substitute(
        BASE_CSS=BASE_CSS,
        MODE_OPTIONS=render_mode_options(3),
        UNANSWERED_HTML=results["unanswered_html"],
        ANSWERED_HTML=results["answered_html"],
        ANSWERED_COUNT=results["answered"],
        SINGLE_MODE_BUTTON=SINGLE_MODE_BUTTON_HTML,
        SINGLE_MODE_VIEW=SINGLE_MODE_VIEW_HTML,
        SINGLE_QUESTION_JS=SINGLE_QUESTION_JS,
    )


def _html_response(start_response, body_str, status="200 OK"):
    body = body_str.encode("utf-8")
    start_response(status, [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return [body]


def _json_response(start_response, obj, status="200 OK"):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return [body]


def _resolve_path(environ):
    """Détermine le chemin réellement demandé.

    Sur Vercel, vercel.json route tout vers ce fichier via "routes" (pas
    "rewrites" : celui-ci ne préservait pas le chemin d'origine dans
    l'environ WSGI, PATH_INFO restait figé sur "/api/index" quel que soit
    l'URL demandée). Le vrai chemin est glissé dans le paramètre de requête
    "vpath" par la règle "dest": "/api/index.py?vpath=$1". En local ou dans
    un autre contexte WSGI (tests), on retombe sur PATH_INFO classique.
    """
    params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    if "vpath" in params:
        return "/" + params["vpath"][0].lstrip("/")
    return environ.get("PATH_INFO", "/") or "/"


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    path = _resolve_path(environ)

    if method == "GET":
        if path in ("/", "/index.html"):
            return _html_response(start_response, render_vercel_page())
        if path in ("/fantomes", "/fantomes/"):
            return _html_response(start_response, render_ghosts_page())
        return _json_response(start_response, {"error": "not found"}, "404 Not Found")

    if method == "POST":
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except (TypeError, ValueError):
            length = 0
        raw = environ["wsgi.input"].read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}

        mode = sanitize_mode(payload.get("mode", 3))
        answers = sanitize_answers(payload.get("answers"))

        if path == "/api/answer":
            qid, answer = payload.get("qid"), payload.get("answer")
            from web_core import QUESTIONS  # import local pour rester minimal en haut de fichier
            if qid in QUESTIONS and answer in ("oui", "non", "sais_pas"):
                answers[qid] = answer
        elif path == "/api/reset":
            answers = {}
        elif path not in ("/api/mode", "/api/compute"):
            return _json_response(start_response, {"error": "not found"}, "404 Not Found")

        result = build_results(mode, answers)
        result["answers"] = answers
        return _json_response(start_response, result)

    return _json_response(start_response, {"error": "method not allowed"}, "405 Method Not Allowed")
