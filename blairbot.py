# -*- coding: utf-8 -*-
"""
BlairBot — un bot type "devine le fantôme" pour le jeu Roblox Blair.

Principe : comme un vrai joueur, le bot pose des questions sur les preuves
(EMF, température, écriture, orbes, Spirit Box, UV, SLS) et sur des
comportements particuliers observés en jeu, puis élimine au fur et à mesure
les fantômes qui ne correspondent plus, jusqu'à trouver le bon (ou réduire
la liste au minimum).

À chaque tour, le bot choisit lui-même la question la plus utile parmi
celles qui restent (celle qui coupe le mieux la liste des suspects en deux),
un peu à la Akinator, plutôt que de suivre un ordre fixe.

Utilisation :
    python blairbot.py            -> lance le questionnaire interactif
    python blairbot.py --liste    -> affiche la table de référence complète
                                      (fantôme / preuves / comportements)

Réponses acceptées à chaque question : o (oui) / n (non) / p (je ne sais
pas, passer). Tape "stop" à tout moment pour forcer une conclusion avec les
infos déjà données, ou "quitter" pour abandonner.
"""

import os
import sys

# La console Windows utilise souvent un encodage historique (cp1252/cp437)
# qui plante sur les accents ou les emojis. On force l'UTF-8 partout avant
# le moindre print/input.
if sys.platform == "win32":
    os.system("chcp 65001 >nul")
for _stream in (sys.stdout, sys.stderr, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ghosts_data import (
    EVIDENCES,
    EVIDENCE_QUESTIONS,
    GHOSTS,
    TRAIT_GHOSTS,
    TRAIT_QUESTIONS,
)

# Filet de sécurité seulement : la boucle s'arrête d'elle-même dès qu'il ne
# reste qu'un suspect ou qu'il n'y a plus de question utile. En mode sans
# preuve (0), beaucoup de comportements ne concernent qu'un seul fantôme
# chacun (score d'info minimal), donc dans le pire cas il faut éliminer
# presque tout le monde un par un : la simulation interne monte jusqu'à 17
# questions dans ce cas. On garde de la marge.
MAX_QUESTIONS = 25

# Nombre max de questions de "vérification" (double-check d'un fantôme aux
# preuves proches avant de conclure). Trié par preuve la plus récente, donc
# le vrai coupable est presque toujours dans les toutes premières — pas
# besoin d'en enchaîner des dizaines.
MAX_VERIFICATIONS = 3


class Question:
    """Une question posée à l'utilisateur, avec l'ensemble des fantômes
    pour lesquels la réponse serait "oui"."""

    def __init__(self, qid, kind, text, yes_ghosts):
        self.qid = qid
        self.kind = kind  # "evidence" ou "trait"
        self.text = text
        self.yes_ghosts = yes_ghosts


def build_question_pool():
    pool = []
    for evidence in EVIDENCES:
        yes_ghosts = {name for name, data in GHOSTS.items() if evidence in data["evidences"]}
        pool.append(Question(evidence, "evidence", EVIDENCE_QUESTIONS[evidence], yes_ghosts))
    for trait, text in TRAIT_QUESTIONS.items():
        pool.append(Question(trait, "trait", text, TRAIT_GHOSTS[trait]))
    return pool


class BlairBot:
    def __init__(self, evidence_mode=3):
        """evidence_mode : nombre de preuves réellement disponibles cette
        partie (0, 1, 2 ou 3). En dessous de 3, un "non" à une question de
        preuve n'est pas fiable : la preuve peut simplement être masquée
        par le mode de difficulté plutôt que réellement absente chez ce
        fantôme. Seul un "oui" reste fiable dans ce cas."""
        self.candidates = set(GHOSTS.keys())
        self.pool = build_question_pool()
        self.asked = set()
        self.history = []  # (question, réponse, note) pour le récap final
        self.evidence_mode = evidence_mode
        self.evidence_found = 0
        # Pour chaque fantôme écarté, la question qui l'a écarté en
        # premier — sert à revenir en arrière si le suspect final ne colle
        # finalement pas (cf. pick_verification_question / neutralize).
        self.excluded_by = {}

    def _candidate_questions(self, kind):
        if kind == "evidence" and (self.evidence_mode == 0 or self.evidence_found >= self.evidence_mode):
            # Mode sans preuve, ou quota de preuves de cette partie déjà
            # atteint : plus aucune question de preuve n'a d'intérêt.
            return []
        return [q for q in self.pool if q.kind == kind and q.qid not in self.asked]

    def pick_next_question(self):
        """Choisit la question qui coupe le mieux les suspects restants en
        deux (maximise le plus petit des deux groupes 'oui'/'non'), en
        traitant toujours les preuves en priorité sur les comportements
        (comme un vrai joueur qui commence par relever les preuves).
        Renvoie None s'il n'y a plus de question utile (y compris quand il
        ne reste qu'un seul suspect, cf. pick_verification_question pour la
        suite dans ce cas)."""
        for kind in ("evidence", "trait"):
            best_q = None
            best_score = -1
            for q in self._candidate_questions(kind):
                yes = self.candidates & q.yes_ghosts
                no = self.candidates - q.yes_ghosts
                if not yes or not no:
                    continue  # ne départage rien parmi les suspects restants
                score = min(len(yes), len(no))
                if score > best_score:
                    best_score = score
                    best_q = q
            if best_q is not None:
                return best_q
        return None

    def pick_verification_question(self):
        """Une fois qu'il ne reste plus qu'un seul suspect, cherche un
        fantôme "proche" (au moins 2 preuves communes) qui a été écarté par
        une question de PREUVE — donc potentiellement à tort, si cette
        preuve n'avait en fait pas encore été vérifiée en jeu — et propose
        une question de comportement propre à ce fantôme pour trancher
        vraiment. Renvoie (question, nom_du_fantome_a_ecarter) ou None.

        Priorité à la preuve la plus RÉCENTE : c'est souvent la dernière
        qui a fait pencher la balance, donc la plus susceptible d'avoir été
        cochée trop vite plutôt que vraiment vérifiée."""
        if len(self.candidates) != 1:
            return None
        winner = next(iter(self.candidates))
        winner_evidences = GHOSTS[winner]["evidences"]
        winner_traits = GHOSTS[winner]["traits"]

        confirmed_oui = {q.qid for (q, a, _n) in self.history if a == "oui" and q.kind == "evidence"}
        if winner_evidences <= confirmed_oui:
            # Les 3 preuves de ce fantôme ont été positivement confirmées
            # (pas juste déduites par élimination) : la combinaison est
            # unique à ce fantôme, pas besoin de vérifier davantage.
            return None

        order = {q.qid: i for i, (q, _a, _n) in enumerate(self.history)}

        close_calls = []
        for candidate, culprit_q in self.excluded_by.items():
            if candidate == winner or culprit_q.kind != "evidence":
                continue
            shared = len(GHOSTS[candidate]["evidences"] & winner_evidences)
            if shared < 2:
                continue  # preuves trop différentes, pas de confusion plausible
            distinguishing = GHOSTS[candidate]["traits"] - winner_traits
            if not distinguishing:
                continue
            close_calls.append((order.get(culprit_q.qid, -1), candidate))
        close_calls.sort(key=lambda item: item[0], reverse=True)

        for _pos, candidate in close_calls:
            distinguishing = GHOSTS[candidate]["traits"] - winner_traits
            for q in self.pool:
                if q.kind == "trait" and q.qid in distinguishing and q.qid not in self.asked:
                    return q, candidate
        return None

    def apply_answer(self, question, answer):
        """answer: 'oui' / 'non' / 'sais_pas'. Renvoie True si la réponse a
        été appliquée, False si elle a été annulée (contradiction)."""
        self.asked.add(question.qid)
        if answer == "sais_pas":
            return True
        return self._apply_core(question, answer)

    def _apply_core(self, question, answer):
        before = set(self.candidates)
        note = ""
        filtered = False
        if answer == "oui":
            self.candidates &= question.yes_ghosts
            filtered = True
            if question.kind == "evidence":
                self.evidence_found += 1
        elif question.kind == "evidence" and self.evidence_mode < 3:
            # Mode à preuves réduites : un "non" ne prouve rien, cette
            # preuve peut juste être masquée par le mode. On ne filtre pas.
            note = "(non pris en compte : peut être masqué par le mode de preuves)"
        else:
            self.candidates -= question.yes_ghosts
            filtered = True

        if not self.candidates:
            # Plus aucun fantôme ne correspond -> réponse contradictoire
            # avec les précédentes, on l'ignore.
            self.candidates = before
            return False

        if filtered:
            for ghost in before - self.candidates:
                self.excluded_by.setdefault(ghost, question)

        self.history.append((question, answer, note))
        return True

    def neutralize(self, qid):
        """Oublie l'effet d'une question déjà répondue (comme si elle
        n'avait jamais filtré personne) et recalcule tout depuis le début
        avec le reste de l'historique. Utilisé quand une preuve s'avère
        avoir écarté à tort le vrai fantôme (probablement pas encore
        vérifiée en jeu plutôt que vraiment absente)."""
        remaining_log = [(q, a) for (q, a, _note) in self.history if q.qid != qid]
        self.candidates = set(GHOSTS.keys())
        self.evidence_found = 0
        self.excluded_by = {}
        self.history = []
        for q, a in remaining_log:
            self._apply_core(q, a)

    def score_candidates(self):
        """Classe les suspects restants du plus au moins probable.

        Tous les survivants respectent déjà les réponses fiables (c'est ce
        qui les a gardés en lice) : la seule chose qui peut encore les
        départager, ce sont les "non" à des preuves en mode réduit, qu'on
        n'a pas utilisés pour éliminer (car potentiellement masqués) mais
        qui restent un indice — un fantôme qui n'a de toute façon pas cette
        preuve colle mieux à ce qui a été observé qu'un fantôme qui l'a
        mais dont la preuve serait restée cachée par hasard.

        Renvoie une liste [(nom, pourcentage)] triée du plus probable au
        moins probable. C'est une estimation indicative, pas une vraie
        probabilité du jeu."""
        scores = {g: 1.0 for g in self.candidates}
        for question, answer, note in self.history:
            if question.kind == "evidence" and answer == "non" and note:
                for g in self.candidates:
                    if question.qid not in GHOSTS[g]["evidences"]:
                        scores[g] += 1.0

        total = sum(scores.values())
        ranking = [(g, scores[g] / total * 100) for g in scores]
        ranking.sort(key=lambda item: (-item[1], item[0]))
        return ranking


def ask(prompt_text):
    while True:
        raw = input(f"{prompt_text}\n  [o]ui / [n]on / [p]as sûr, ou 'stop' / 'quitter' > ").strip().lower()
        if raw in ("o", "oui", "y", "yes"):
            return "oui"
        if raw in ("n", "non", "no"):
            return "non"
        if raw in ("p", "sais pas", "sais_pas", "passe", "?"):
            return "sais_pas"
        if raw in ("stop",):
            return "stop"
        if raw in ("quitter", "quit", "exit"):
            return "quitter"
        print("  -> réponse non reconnue, réessaie (o / n / p / stop / quitter).")


def ask_evidence_setup():
    """Première question de la partie : est-ce qu'il y a des preuves cette
    fois-ci (certains modes de difficulté n'en donnent aucune), et si oui
    combien (1 à 3). Renvoie (evidence_mode, quitter)."""
    while True:
        raw = input(
            "Est-ce qu'il y a des preuves cette partie ? (certains modes de "
            "difficulté n'en donnent aucune)\n"
            "  [o]ui / [n]on (mode sans preuve) / [p]as sûr, ou 'quitter' > "
        ).strip().lower()
        if raw in ("o", "oui", "y", "yes"):
            break
        if raw in ("n", "non", "no"):
            return 0, False
        if raw in ("p", "sais pas", "sais_pas", "passe", "?"):
            print("  -> Je pars du principe qu'on est en mode normal (3 preuves).")
            return 3, False
        if raw in ("quitter", "quit", "exit"):
            return None, True
        print("  -> réponse non reconnue, réessaie (o / n / p / quitter).")

    while True:
        raw = input("Combien de preuves au total pour cette partie ? [1] / [2] / [3], ou 'quitter' > ").strip().lower()
        if raw in ("1", "2", "3"):
            return int(raw), False
        if raw in ("quitter", "quit", "exit"):
            return None, True
        print("  -> réponse non reconnue, réessaie (1 / 2 / 3 / quitter).")


def print_intro():
    print("=" * 60)
    print(" BlairBot — devine le fantôme (jeu Roblox : Blair)")
    print("=" * 60)
    print(
        "Réponds aux questions au fur et à mesure de ton enquête in-game.\n"
        "Je choisis à chaque fois la question la plus utile pour trancher\n"
        "entre les fantômes encore possibles.\n\n"
        "Important pour les preuves : réponds 'non' seulement si tu l'as\n"
        "vraiment vérifiée en jeu et qu'elle n'y est pas. Si tu n'as pas\n"
        "encore checké avec l'outil correspondant, réponds 'pas sûr' — un\n"
        "'non' trop hâtif peut faire éliminer le bon fantôme par erreur.\n"
    )


def reveal(bot):
    remaining = bot.candidates
    print("\n" + "-" * 60)
    if len(remaining) == 1:
        name = next(iter(remaining))
        data = GHOSTS[name]
        print(f"Je suis sûr : c'est un **{name}** !\n")
        print(f"  Preuves : {', '.join(sorted(data['evidences']))}")
        print(f"  {data['desc']}")
    elif len(remaining) == 0:
        print("Aucun fantôme ne correspond à toutes tes réponses. Une des\n"
              "réponses est probablement fausse, ou le jeu a changé depuis\n"
              "la dernière mise à jour de ghosts_data.py.")
    else:
        ranking = bot.score_candidates()
        print(f"Je n'ai pas pu trancher complètement, il reste {len(remaining)} suspects "
              f"possibles, classés par probabilité :\n")
        for name, pct in ranking:
            data = GHOSTS[name]
            print(f"  {pct:5.1f}%  {name}  (preuves : {', '.join(sorted(data['evidences']))})")
        print("\n(Estimation indicative basée sur les indices déjà connus, pas une\n"
              "vraie probabilité du jeu.)")
        print("\nContinue l'enquête in-game (encore une preuve ou un\ncomportement observé) et relance BlairBot pour trancher.")
    print("-" * 60)

    if bot.history:
        print("\nRécap de tes réponses :")
        for question, answer, note in bot.history:
            symbole = {"oui": "OUI", "non": "NON"}.get(answer, answer)
            suffixe = f"  {note}" if note else ""
            print(f"  [{symbole}] {question.text}{suffixe}")


def run_interactive():
    print_intro()

    evidence_mode, quit_now = ask_evidence_setup()
    if quit_now:
        print("\nÀ la prochaine enquête !")
        return

    if evidence_mode == 0:
        print("  -> Mode sans preuve : je vais me baser uniquement sur les comportements observés.\n")
    else:
        print(f"  -> Mode à {evidence_mode} preuve(s) : j'arrêterai les questions de preuve une "
              f"fois les {evidence_mode} trouvée(s), et je passerai aux comportements.\n")

    bot = BlairBot(evidence_mode)
    count = 0
    verifications = 0

    while count < MAX_QUESTIONS:
        verif_target = None

        if len(bot.candidates) > 1:
            question = bot.pick_next_question()
        elif verifications < MAX_VERIFICATIONS:
            result = bot.pick_verification_question()
            question, verif_target = result if result else (None, None)
        else:
            question = None

        if question is None:
            break

        if verif_target:
            verifications += 1

        if verif_target:
            label = f"✅ Vérification (pour écarter un {verif_target}, dont les preuves sont proches)"
        else:
            label = "🔍 Preuve" if question.kind == "evidence" else "👁️  Comportement"
        winner_before = next(iter(bot.candidates)) if len(bot.candidates) == 1 else None

        answer = ask(f"\n({len(bot.candidates)} fantôme(s) possible(s)) {label} : {question.text}")

        if answer == "quitter":
            print("\nÀ la prochaine enquête !")
            return
        if answer == "stop":
            break

        applied = bot.apply_answer(question, answer)
        if not applied:
            if verif_target:
                # Le suspect actuel ne colle pas à son propre comportement
                # attendu : la preuve qui a écarté "verif_target" était
                # sans doute une fausse alerte (pas encore vérifiée en jeu).
                # On revient dessus et on réintègre ce fantôme.
                culprit = bot.excluded_by.get(verif_target)
                print(f"  -> Ça ne colle pas avec {winner_before} : je reviens sur la "
                      f"réponse à \"{culprit.text}\" (sans doute pas encore vérifiée en "
                      f"jeu) et je réintègre {verif_target} parmi les suspects.")
                bot.neutralize(culprit.qid)
                reapplied = bot.apply_answer(question, answer)
                if not reapplied:
                    print("  -> Toujours incohérent, je laisse cette question de côté.")
                count += 1
                continue
            print("  -> Hmm, ça ne correspond à aucun fantôme compte tenu de\n"
                  "     tes réponses précédentes. Je mets cette réponse de côté.")
            continue

        if question.kind == "evidence" and answer == "oui":
            print(f"  -> Preuve confirmée ({bot.evidence_found}/{bot.evidence_mode}).")

        count += 1

    reveal(bot)


def print_reference_table():
    print("Table de référence — Blair (21 fantômes, 7 preuves)\n")
    header = f"{'Fantôme':<12} | {'Preuves':<55} | Comportements clés"
    print(header)
    print("-" * len(header))
    for name in sorted(GHOSTS):
        data = GHOSTS[name]
        evidences = ", ".join(sorted(data["evidences"]))
        traits = ", ".join(sorted(data["traits"])) or "-"
        print(f"{name:<12} | {evidences:<55} | {traits}")


if __name__ == "__main__":
    if "--liste" in sys.argv or "-l" in sys.argv:
        print_reference_table()
    else:
        try:
            run_interactive()
        except (KeyboardInterrupt, EOFError):
            print("\n\nÀ la prochaine enquête !")
