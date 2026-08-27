# -*- coding: utf-8 -*-
"""
BlairBot Web — mini interface web locale pour répondre aux questions à ton
rythme (coche Oui / Non / Pas sûr sur celles que tu peux vérifier tout de
suite, reviens plus tard sur les autres), avec un classement des fantômes
possibles qui se met à jour en direct.

Contrairement à blairbot.py (CLI, une question à la fois choisie de façon
adaptative), ici TOUTES les questions sont affichées d'un coup, triées par
priorité, et le résultat est recalculé à chaque coche à partir de zéro —
pas besoin de répondre dans un ordre précis, ni même de toutes les remplir.

Aucune dépendance à installer : uniquement la bibliothèque standard Python
(http.server). Les réponses sont sauvegardées dans web_state.json à côté de
ce fichier, donc tu peux fermer le serveur et le relancer plus tard sans
perdre ta progression.

C'est la version pour un usage LOCAL (un process qui tourne en continu sur
ta machine). Pour un déploiement hébergé (Vercel...), voir api/index.py qui
réutilise la même logique (web_core.py) mais sans état côté serveur —
l'état vit dans le navigateur (localStorage), car un hébergeur serverless
ne garde ni mémoire ni disque entre deux requêtes.

Utilisation :
    python blairbot_web.py
    -> ouvre automatiquement http://127.0.0.1:8765 dans ton navigateur.
"""

import http.server
import json
import os
import sys
import webbrowser
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

from web_core import (
    BASE_CSS,
    QUESTIONS,
    build_results,
    render_ghosts_page,
    render_mode_options,
)

PORT = 8765
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_state.json")

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
        MODE_OPTIONS=render_mode_options(STATE["evidence_mode"]),
        UNANSWERED_HTML=results["unanswered_html"],
        ANSWERED_HTML=results["answered_html"],
        ANSWERED_COUNT=results["answered"],
        INITIAL_RESULTS_JSON=json.dumps(initial_json, ensure_ascii=False),
    )


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
