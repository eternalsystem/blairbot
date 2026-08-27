# BlairBot

Un petit bot en Python qui devine le type de fantôme dans le jeu Roblox
**Blair** (jeu d'enquête paranormale façon Phasmophobia), en te posant des
questions sur les preuves et les comportements observés en jeu — un peu
comme un Akinator spécialisé Blair.

## Lancer le bot

```
python blairbot.py
```

Réponds à chaque question par :
- `o` → oui
- `n` → non
- `p` → je ne sais pas / pas encore observé (passe la question)
- `stop` → arrête et donne le meilleur verdict avec ce que tu as déjà répondu
- `quitter` → abandonne l'enquête

Le bot choisit à chaque tour la question la plus utile pour départager les
fantômes encore possibles (au lieu de suivre un ordre fixe) : en pratique
il trouve le bon fantôme en 4 ou 5 questions dans la quasi-totalité des cas,
sur les 21 fantômes du jeu.

## Voir toute la base de données

```
python blairbot.py --liste
```

Affiche un tableau de référence : les 21 fantômes, leurs 3 preuves, et
leurs comportements particuliers.

## Version web (répondre à ton rythme)

```
python blairbot_web.py
```

Ouvre automatiquement `http://127.0.0.1:8765` dans ton navigateur, avec
trois boutons **Oui / Non / Pas sûr** par question. Contrairement à la
version terminal, tu n'as pas besoin de répondre dans l'ordre ni tout de
suite : coche ce que tu peux vérifier maintenant, laisse le reste sur "Pas
sûr", et reviens plus tard.

Les questions encore sans réponse sont **triées par ordre de priorité**
(celle qui départage le mieux les fantômes encore possibles en tête, avec
son thème affiché en étiquette — preuves, lumières, sel, crucifix,
eau/éviers...) et cet ordre se recalcule à chaque coche : la liste
raccourcit au fil de l'enquête, et les questions déjà répondues partent
dans une section repliée à part (modifiable à tout moment). Le classement
des fantômes possibles, en haut de page, se met aussi à jour en direct.
Tes réponses sont sauvegardées automatiquement dans `web_state.json`, donc
tu peux fermer le serveur et le relancer sans perdre ta progression. Aucune
dépendance à installer (bibliothèque standard Python uniquement).

Un lien **📖 Fiches des fantômes** en haut de page ouvre une page de
référence listant les 21 fantômes, chacun avec ses preuves, sa description
et la liste de tous ses comportements repérables (dans un nouvel onglet,
pour garder le questionnaire ouvert à côté). Elle a sa propre barre de
recherche pour filtrer par nom ou par preuve. Accessible directement via
`http://127.0.0.1:8765/fantomes`.

Si une réponse rend la situation impossible (aucun fantôme ne colle), la
ou les questions suspectes sont surlignées en orange — repasse-les en
"Pas sûr" si tu n'étais pas certain·e.

## Fichiers

- `ghosts_data.py` — toutes les données de jeu (preuves, comportements,
  descriptions, catégories), récupérées sur le wiki Fandom de Blair.
- `blairbot.py` — le moteur d'élimination adaptatif + l'interface en ligne
  de commande (une question à la fois, choisie automatiquement).
- `blairbot_web.py` — la mini interface web (toutes les questions d'un
  coup, réponses libres, sauvegardées dans `web_state.json`).

## D'où viennent les données

Du wiki communautaire du jeu (blair-roblox.fandom.com), pages *Ghosts*,
*Evidence*, *Ghost Behaviours* et les pages individuelles des 21 fantômes.
Le wiki lui-même signale des trous sur certains fantômes (seuils de sanité
non documentés pour Faejkur, Jiangshi, Krasue, Phantom, Yama...), donc les
questions de comportement ne couvrent que ce qui est confirmé.

**Le jeu est encore mis à jour régulièrement** (ex : un bug sur Yurei a été
corrigé lors de la mise à jour Halloween 2024). Si BlairBot se trompe
souvent sur un fantôme précis, c'est probablement que son comportement a
changé en jeu — il suffit de modifier `ghosts_data.py` en conséquence
(chaque fantôme y est un simple dict avec ses preuves et ses traits).

## Ajouter/corriger un fantôme ou un comportement

Dans `ghosts_data.py` :
1. `GHOSTS["NomDuFantome"]["evidences"]` doit contenir exactement 3 valeurs
   parmi celles listées dans `EVIDENCES`.
2. `GHOSTS["NomDuFantome"]["traits"]` est un ensemble de clés qui doivent
   exister dans `TRAIT_QUESTIONS` (ajoute une nouvelle entrée dans
   `TRAIT_QUESTIONS` si tu introduis un nouveau comportement, avec le texte
   de la question à poser).

Le reste (construction des questions, sélection de la meilleure question,
élimination) est entièrement automatique et n'a pas besoin d'être modifié.
