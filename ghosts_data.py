# -*- coding: utf-8 -*-
"""
Données de jeu pour BlairBot.

Source : le wiki Fandom du jeu Roblox "Blair" (blair-roblox.fandom.com),
pages "Ghosts", "Evidence", "Ghost Behaviours", "Ghost Event", "Ghost Hunts"
et les pages individuelles de chacun des 21 fantômes (Banshee, Demon,
Faejkur, Harrow, Jiangshi, Krasue, Lament, Mare, Nook, Oni, Phantom,
Poltergeist, Revenant, Shade, Spirit, Strigoi, Vuult, Wraith, Yama, Yurei,
ZoZo), consultées le 26/08/2026.

Le wiki étant maintenu par la communauté, certains détails peuvent changer
avec les mises à jour du jeu (ex: patch d'Halloween 2024 sur Yurei) ou être
approximatifs (le wiki lui-même indique manquer d'infos pour certains
fantômes, comme les seuils de sanité de Faejkur, Jiangshi, Krasue, Phantom
ou Yama). Si BlairBot devine mal, c'est probablement que le jeu a changé
depuis -> pense à mettre ce fichier à jour.

IMPORTANT : le MODÈLE (apparence) d'un fantôme n'a aucun rapport avec son
TYPE. Ce bot ne pose donc jamais de question sur l'apparence.
"""

# Les 7 types de preuves possibles (le journal en affiche jusqu'à 3 par
# fantôme, chaque combinaison des 3 preuves est unique à un seul fantôme).
EVIDENCES = [
    "EMF Level 5",
    "Freezing Temperatures",
    "Ghost Writing",
    "Ghost Orbs",
    "Spirit Box",
    "Ultraviolet",
    "SLS Anomaly",
]

# Libellés plus parlants utilisés dans les questions posées à l'utilisateur.
EVIDENCE_QUESTIONS = {
    "EMF Level 5": "As-tu obtenu un EMF de niveau 5 (détecteur EMF) ?",
    "Freezing Temperatures": "As-tu mesuré une température de pièce glaciale (sous 0°C) au thermomètre ?",
    "Ghost Writing": "Le fantôme a-t-il écrit dans le livre (Ghost Writing Book) ?",
    "Ghost Orbs": "As-tu vu des orbes fantômes à la caméra vidéo (vision nocturne) ?",
    "Spirit Box": "Le fantôme a-t-il répondu au Spirit Box ?",
    "Ultraviolet": "As-tu trouvé des empreintes UV (lampe UV) ?",
    "SLS Anomaly": "As-tu vu un squelette/anomalie à la caméra SLS ?",
}

# Chaque fantôme : ses 3 preuves + ses traits comportementaux particuliers
# (clés qui renvoient vers TRAITS ci-dessous) + une description utilisée à
# la révélation finale.
GHOSTS = {
    "Banshee": {
        "evidences": {"EMF Level 5", "Freezing Temperatures", "SLS Anomaly"},
        "traits": {"relentless_single_target", "parabolic_scream", "favors_throwing_parabolic_mic", "cries_often", "sings_often"},
        "desc": "S'acharne sur une seule cible jusqu'à la mort, en ignorant "
                "quasiment tout le monde d'autre. On peut l'entendre hurler "
                "au micro parabolique, qu'elle adore aussi lancer. Pleure et "
                "chante plus souvent que la moyenne.",
    },
    "Demon": {
        "evidences": {"Freezing Temperatures", "Ghost Writing", "Spirit Box"},
        "traits": {"hunts_at_very_high_sanity", "hunts_very_frequently", "weak_to_extended_crucifix", "short_incense_cleanse_block", "frequent_flash_events", "salt_speed_increases_per_hunt", "crucifix_burns_red_ignored"},
        "desc": "Le plus agressif : chasse très souvent et même à très haute "
                "sanité (jusqu'à 90%). Très sensible au crucifix (portée "
                "étendue, bloque même depuis une pièce ou deux plus loin), "
                "mais a 1 chance sur 30 de le faire devenir rouge et de "
                "l'ignorer en rugissant. À "
                "l'inverse, l'encens/la purification ne le bloquent qu'une "
                "minute (deux fois moins longtemps que la normale), il "
                "adore les flashs lumineux, et marche de plus en plus vite "
                "dans le sel à chaque traque.",
    },
    "Faejkur": {
        "evidences": {"EMF Level 5", "Freezing Temperatures", "Ghost Writing"},
        "traits": {"sound_mimicry_lower_pitch", "fake_footsteps_wrong_direction_end"},
        "desc": "Imite les sons qu'il a déjà entendus, mais sur un ton plus "
                "grave, et laisse de faux bruits de pas dans une autre "
                "direction en fin de traque.",
    },
    "Harrow": {
        "evidences": {"Ghost Writing", "Ghost Orbs", "SLS Anomaly"},
        "traits": {"cannot_roam_ever", "speed_depends_on_distance_to_room"},
        "desc": "Ne quitte jamais sa pièce favorite (sauf difficulté Hard/"
                "Nightmare) : très rapide près de celle-ci, beaucoup plus "
                "lent en s'en éloignant.",
    },
    "Jiangshi": {
        "evidences": {"Freezing Temperatures", "Ultraviolet", "SLS Anomaly"},
        "traits": {"hopping_skips_footstep", "repeats_events_three_times", "skips_salt_footstep"},
        "desc": "Répète ses manifestations (par exemple claquer une porte) "
                "trois fois de suite et a une petite chance de « sautiller » "
                "(sauter un bruit de pas) pendant une traque — y compris "
                "dans le sel, où une empreinte sur deux manque à l'appel.",
    },
    "Krasue": {
        "evidences": {"EMF Level 5", "Freezing Temperatures", "Ultraviolet"},
        "traits": {"floating_head_transformation", "fills_sink_dirty_water", "cries_often"},
        "desc": "Peut se transformer en tête flottante séparée de son corps, "
                "surtout à proximité de bougies allumées. Aime aussi remplir "
                "les éviers d'eau sale et pleurer dans sa pièce favorite.",
    },
    "Lament": {
        "evidences": {"EMF Level 5", "Ghost Orbs", "Spirit Box"},
        "traits": {"no_los_speedup", "quiet_footsteps_at_hunt_end", "full_stamina_drain", "fakes_hunt_end_lights"},
        "desc": "N'accélère jamais même s'il vous voit (on peut le boucler "
                "autour d'un meuble). Ses bruits de pas deviennent presque "
                "silencieux juste avant la fin d'une traque, il peut éteindre "
                "les interrupteurs pour faire croire que la traque est finie "
                "alors qu'elle continue, et il est seul à pouvoir vider "
                "entièrement votre endurance.",
    },
    "Mare": {
        "evidences": {"Freezing Temperatures", "Spirit Box", "SLS Anomaly"},
        "traits": {"never_hunts_lit_room", "dark_dependent_smashes_lights"},
        "desc": "Ne peut absolument pas chasser dans une pièce dont les "
                "plafonniers sont allumés. Beaucoup plus actif dans le noir, "
                "et peut faire exploser des lumières en les éteignant.",
    },
    "Nook": {
        "evidences": {"EMF Level 5", "Freezing Temperatures", "Ghost Orbs"},
        "traits": {"extreme_roamer_changes_room", "makes_objects_vanish", "frequently_throws_and_steals_items"},
        "desc": "Le fantôme le plus « baladeur » du jeu : change sans cesse "
                "de pièce favorite pour se rapprocher du plus d'objets "
                "possible, peut faire disparaître des objets (ou du "
                "matériel du van) dans un petit souffle d'air, et adore "
                "lancer/voler des objets.",
    },
    "Oni": {
        "evidences": {"Ghost Writing", "Ultraviolet", "SLS Anomaly"},
        "traits": {"weakens_with_more_equipment", "cannot_sing", "reduced_crucifix_range"},
        "desc": "Très dangereux et rapide en début de partie, il devient "
                "de plus en plus lent et faible au fur et à mesure que "
                "l'équipe utilise du matériel de protection. Incapable de "
                "chanter/fredonner, et le crucifix a une portée plus "
                "petite que la normale contre lui (il faut être très "
                "proche pour qu'il fonctionne).",
    },
    "Phantom": {
        "evidences": {"Ultraviolet", "Ghost Orbs", "SLS Anomaly"},
        "traits": {"photo_stuns_blind", "invisible_on_camera_feeds"},
        "desc": "Une photo prise pendant une manifestation le rend aveugle "
                "quelques secondes (voire le fait disparaître). Il "
                "n'apparaît jamais sur les flux caméra/CCTV.",
    },
    "Poltergeist": {
        "evidences": {"Ultraviolet", "Ghost Orbs", "Spirit Box"},
        "traits": {"multi_item_throw_during_hunt", "frequently_throws_and_steals_items"},
        "desc": "Le seul fantôme capable de lancer des objets pendant une "
                "traque, et peut en faire s'envoler jusqu'à dix d'un coup "
                "(« Poltsplosion »). Adore aussi lancer/voler des objets en "
                "dehors des traques.",
    },
    "Revenant": {
        "evidences": {"EMF Level 5", "Ghost Writing", "Ultraviolet"},
        "traits": {"slow_normally_fast_on_los", "flicks_lights_rapidly"},
        "desc": "Extrêmement lent tant qu'il ne vous voit pas, mais "
                "accélère radicalement dès qu'il vous repère en traque. "
                "Timide : préfère les hallucinations et chasse moins "
                "souvent. Adore aussi faire clignoter les lumières très "
                "vite.",
    },
    "Shade": {
        "evidences": {"EMF Level 5", "Ghost Writing", "SLS Anomaly"},
        "traits": {"hunts_very_rarely_low_sanity", "cries_often", "cannot_sing", "cannot_flash_false_hunt_redlight"},
        "desc": "Le moins agressif : ne chasse presque jamais (il faut une "
                "sanité d'équipe ≤35%), et encore moins si un joueur est "
                "déjà présent dans sa pièce. Ne fait jamais de fausse "
                "traque, d'événement flash ou de lumière rouge, et ne "
                "chante jamais — mais pleure plus souvent que la moyenne.",
    },
    "Spirit": {
        "evidences": {"Ghost Writing", "Ultraviolet", "Spirit Box"},
        "traits": {"extra_long_incense_and_cleanse"},
        "desc": "Le fantôme le plus « moyen » du jeu, sans grande "
                "particularité, si ce n'est une réaction plus marquée à "
                "l'encens (étourdi 6s au lieu de 2s) et à la purification "
                "de sa pièce (bloqué 3 min au lieu de 2).",
    },
    "Strigoi": {
        "evidences": {"EMF Level 5", "Ultraviolet", "Ghost Orbs"},
        "traits": {"invisible_near_water", "four_finger_uv_print", "fills_sink_dirty_water"},
        "desc": "Devient invisible en chassant lorsqu'il est renforcé par "
                "de l'eau à proximité, laisse une empreinte UV à quatre "
                "doigts au lieu de cinq, et c'est le fantôme qui remplit le "
                "plus souvent les éviers d'eau sale.",
    },
    "Vuult": {
        "evidences": {"EMF Level 5", "Ghost Orbs", "SLS Anomaly"},
        "traits": {"charge_based_hunting", "flicks_lights_rapidly"},
        "desc": "Sa capacité à chasser dépend d'une jauge de charge « "
                "vuultage » qui augmente avec l'électronique utilisée à "
                "proximité, les joueurs présents, le générateur ou un orage "
                "— plus il est chargé, plus il peut chasser même à haute "
                "sanité, et plus il aime faire clignoter les lumières très "
                "vite.",
    },
    "Wraith": {
        "evidences": {"Freezing Temperatures", "Ghost Orbs", "SLS Anomaly"},
        "traits": {"never_steps_in_salt", "can_fly_teleport"},
        "desc": "Le seul fantôme qui ne laisse jamais d'empreintes dans le "
                "sel : il vole/flotte au lieu de marcher, et peut se "
                "téléporter directement près d'un joueur.",
    },
    "Yama": {
        "evidences": {"Ghost Writing", "Spirit Box", "SLS Anomaly"},
        "traits": {"extreme_roamer_changes_room", "spirit_box_roar"},
        "desc": "Change de pièce favorite quasiment à chaque fois qu'il se "
                "déplace (avec Nook, c'est le fantôme qui erre le plus), et "
                "répond au Spirit Box par un rugissement plutôt qu'un mot.",
    },
    "Yurei": {
        "evidences": {"Freezing Temperatures", "Ultraviolet", "Spirit Box"},
        "traits": {"no_los_speedup", "blind_relies_on_sound"},
        "desc": "Aveugle : il repère les joueurs au bruit et à l'usage "
                "d'appareils électroniques actifs plutôt qu'à la vue, et "
                "n'accélère jamais en vous voyant.",
    },
    "ZoZo": {
        "evidences": {"EMF Level 5", "Ultraviolet", "Spirit Box"},
        "traits": {"reacts_to_being_watched", "spirit_box_says_own_name", "hunts_at_very_high_sanity", "hunts_very_frequently", "cannot_sing", "frequent_flash_events", "frequent_red_light_event"},
        "desc": "Ralentit fortement si on le regarde et accélère si on ne "
                "le regarde pas. Peut prendre le contrôle du Spirit Box "
                "pour n'épeler que « ZoZo » en rouge, impossible à arrêter. "
                "Ne chante jamais, mais adore les flashs lumineux et surtout "
                "l'événement « lumière rouge ».",
    },
}

# Description des traits comportementaux + ensemble des fantômes concernés
# (déduit automatiquement de GHOSTS ci-dessus, ne pas éditer à la main).
TRAIT_QUESTIONS = {
    "relentless_single_target": "Le fantôme s'acharne-t-il sur UNE seule personne, en ignorant presque tout le monde d'autre même quand ils sont visibles ?",
    "parabolic_scream": "As-tu entendu un cri distinct au micro parabolique ?",
    "hunts_at_very_high_sanity": "Le fantôme a-t-il déjà chassé alors que la sanité d'équipe était encore très haute (genre 80-90%+) ?",
    "hunts_very_frequently": "Le fantôme chasse-t-il très souvent, presque sans arrêt ?",
    "weak_to_extended_crucifix": "Le crucifix semble-t-il avoir une portée anormalement GRANDE sur ce fantôme (bloque la chasse même depuis une pièce ou deux plus loin) ?",
    "sound_mimicry_lower_pitch": "Le fantôme reproduit-il des sons déjà entendus, mais avec un ton plus grave que l'original ?",
    "fake_footsteps_wrong_direction_end": "En fin de traque, entends-tu de faux bruits de pas partir dans une direction différente de celle du fantôme ?",
    "cannot_roam_ever": "Le fantôme semble-t-il ne JAMAIS quitter une seule et même pièce, quoi qu'il arrive ?",
    "speed_depends_on_distance_to_room": "Le fantôme est-il beaucoup plus rapide en traque près de sa pièce favorite, et beaucoup plus lent loin d'elle ?",
    "hopping_skips_footstep": "As-tu remarqué le fantôme « sautiller » (sauter un bruit de pas) pendant une traque ?",
    "repeats_events_three_times": "Le fantôme répète-t-il ses manifestations (coups, pleurs...) trois fois de suite ?",
    "floating_head_transformation": "Le fantôme peut-il se transformer en tête flottante séparée du corps ?",
    "no_los_speedup": "Pendant une traque, le fantôme garde-t-il toujours la même vitesse, même quand il te voit directement (tu arrives à le boucler autour d'un meuble) ?",
    "quiet_footsteps_at_hunt_end": "Les bruits de pas du fantôme deviennent-ils presque silencieux juste avant la fin d'une traque ?",
    "full_stamina_drain": "Le fantôme a-t-il complètement vidé ton endurance d'un coup lors d'une manifestation ?",
    "never_hunts_lit_room": "Le fantôme a-t-il été incapable de chasser dans une pièce dont la lumière du plafond était allumée ?",
    "dark_dependent_smashes_lights": "Le fantôme semble-t-il beaucoup plus actif dans le noir, et a-t-il déjà fait exploser une lumière ?",
    "extreme_roamer_changes_room": "Le fantôme change-t-il de pièce favorite très souvent en cours de partie ?",
    "makes_objects_vanish": "As-tu vu un objet (ou du matériel) disparaître d'un coup avec un petit souffle d'air ?",
    "weakens_with_more_equipment": "Le fantôme semblait-il très rapide/dangereux au début, puis de plus en plus lent/faible avec le temps ?",
    "photo_stuns_blind": "Une photo prise pendant une manifestation a-t-elle rendu le fantôme aveugle quelques secondes (ou l'a fait disparaître) ?",
    "invisible_on_camera_feeds": "Le fantôme reste-t-il invisible sur les flux caméra/CCTV alors qu'il est bien présent dans la pièce ?",
    "multi_item_throw_during_hunt": "Le fantôme a-t-il lancé plusieurs objets d'un coup PENDANT une traque ?",
    "slow_normally_fast_on_los": "Le fantôme est-il très lent en temps normal, mais devient soudainement très rapide dès qu'il te repère en traque ?",
    "hunts_very_rarely_low_sanity": "Le fantôme chasse-t-il très rarement, et seulement quand la sanité d'équipe est très basse (≤35%) ?",
    "extra_long_incense_and_cleanse": "L'encens ou la purification de la pièce semblent-ils bloquer ce fantôme plus longtemps que la normale ?",
    "invisible_near_water": "Le fantôme devient-il invisible en traque quand il y a de l'eau active à proximité (robinet, piscine...) ?",
    "four_finger_uv_print": "L'empreinte UV laissée sur une porte n'a-t-elle que quatre doigts au lieu de cinq ?",
    "charge_based_hunting": "As-tu l'impression que sa capacité à chasser dépend de l'électronique utilisée, des joueurs présents ou d'un orage, comme s'il se « rechargeait » ?",
    "never_steps_in_salt": "Le fantôme évite-t-il TOUJOURS de marcher dans le sel, sans jamais laisser d'empreinte ?",
    "can_fly_teleport": "Le fantôme a-t-il l'air de voler/flotter, ou de se téléporter directement à côté d'un joueur ?",
    "spirit_box_roar": "Le Spirit Box a-t-il produit un rugissement plutôt qu'un mot ou une réponse normale ?",
    "blind_relies_on_sound": "Le fantôme semble-t-il aveugle, et réagir surtout au bruit / à l'électronique active plutôt qu'à la vue ?",
    "reacts_to_being_watched": "Le fantôme ralentit-il quand tu le regardes, et accélère-t-il quand tu ne le regardes pas ?",
    "spirit_box_says_own_name": "Le Spirit Box s'est-il mis à épeler en rouge le nom du fantôme en boucle, impossible à arrêter ?",
    # Comportements liés aux lumières, portes, éviers/eau et objets.
    "fills_sink_dirty_water": "Le fantôme a-t-il rempli un évier d'eau sale (eau trouble, bruit de robinet qui coule tout seul) ?",
    "flicks_lights_rapidly": "Le fantôme a-t-il fait clignoter des lumières très rapidement, bien plus vite qu'un joueur ne pourrait le faire ?",
    "cries_often": "Le fantôme pleure-t-il très souvent dans sa pièce favorite ?",
    "sings_often": "Le fantôme chante-t-il/fredonne-t-il plus souvent que la moyenne ?",
    "cannot_sing": "As-tu l'impression que le fantôme est incapable de chanter/fredonner ?",
    "frequent_flash_events": "Le fantôme déclenche-t-il très souvent des flashs lumineux soudains ?",
    "cannot_flash_false_hunt_redlight": "Le fantôme semble-t-il incapable de faire un flash lumineux, une fausse traque, ou l'événement « lumière rouge » ?",
    "frequent_red_light_event": "Les lumières sont-elles déjà devenues rouges puis ont explosé (événement « lumière rouge »), et ça semble arriver souvent avec ce fantôme ?",
    "favors_throwing_parabolic_mic": "Le fantôme a-t-il déjà lancé le micro parabolique ?",
    "frequently_throws_and_steals_items": "Le fantôme lance-t-il ou fait-il disparaître (vole) des objets très fréquemment, même en dehors des traques ?",
    "short_incense_cleanse_block": "L'encens ou la purification de la pièce semblent-ils bloquer ce fantôme MOINS longtemps que la normale (genre 1 minute) ?",
    "fakes_hunt_end_lights": "Le fantôme a-t-il déjà éteint les interrupteurs comme si la traque était terminée, alors qu'elle a continué juste après ?",
    # Comportements liés au sel (en plus de never_steps_in_salt pour le Wraith).
    "skips_salt_footstep": "En marchant dans le sel, le fantôme saute-t-il régulièrement une empreinte sur deux ?",
    "salt_speed_increases_per_hunt": "Le fantôme semble-t-il marcher de plus en plus vite dans le sel au fil des traques successives ?",
    # État/comportement du crucifix.
    "reduced_crucifix_range": "Le crucifix semble-t-il avoir une portée anormalement PETITE sur ce fantôme (il faut être très proche pour qu'il fonctionne) ?",
    "crucifix_burns_red_ignored": "As-tu déjà vu un crucifix devenir rouge/brûler alors que le fantôme a quand même chassé en rugissant, ignorant sa protection ?",
}

# Regroupement des comportements par thème, pour l'affichage dans
# l'interface web (blairbot_web.py). Purement cosmétique : n'affecte pas la
# logique de déduction. Toute clé de TRAIT_QUESTIONS non listée ici tombe
# automatiquement dans "Autres".
TRAIT_CATEGORY_ORDER = [
    "Vitesse & poursuite",
    "Chasse : sanité & fréquence",
    "Lumières & électronique",
    "Portes, objets & vols",
    "Eau & éviers",
    "Sel",
    "Crucifix & encens",
    "Sons, cris & Spirit Box",
    "Pièce favorite & déplacements",
    "Apparence & manifestations",
    "Ciblage",
    "Autres",
]

_TRAIT_CATEGORY_MAP = {
    "Vitesse & poursuite": [
        "speed_depends_on_distance_to_room", "no_los_speedup", "slow_normally_fast_on_los",
        "reacts_to_being_watched",
    ],
    "Chasse : sanité & fréquence": [
        "hunts_at_very_high_sanity", "hunts_very_frequently", "hunts_very_rarely_low_sanity",
    ],
    "Lumières & électronique": [
        "never_hunts_lit_room", "dark_dependent_smashes_lights", "flicks_lights_rapidly",
        "frequent_flash_events", "cannot_flash_false_hunt_redlight", "frequent_red_light_event",
        "fakes_hunt_end_lights", "charge_based_hunting",
    ],
    "Portes, objets & vols": [
        "repeats_events_three_times", "makes_objects_vanish", "multi_item_throw_during_hunt",
        "favors_throwing_parabolic_mic", "frequently_throws_and_steals_items",
    ],
    "Eau & éviers": [
        "invisible_near_water", "fills_sink_dirty_water",
    ],
    "Sel": [
        "never_steps_in_salt", "skips_salt_footstep", "salt_speed_increases_per_hunt",
    ],
    "Crucifix & encens": [
        "weak_to_extended_crucifix", "reduced_crucifix_range", "crucifix_burns_red_ignored",
        "extra_long_incense_and_cleanse", "short_incense_cleanse_block",
    ],
    "Sons, cris & Spirit Box": [
        "parabolic_scream", "sound_mimicry_lower_pitch", "spirit_box_roar", "blind_relies_on_sound",
        "spirit_box_says_own_name", "cries_often", "sings_often", "cannot_sing",
    ],
    "Pièce favorite & déplacements": [
        "cannot_roam_ever", "extreme_roamer_changes_room",
    ],
    "Apparence & manifestations": [
        "hopping_skips_footstep", "fake_footsteps_wrong_direction_end", "floating_head_transformation",
        "quiet_footsteps_at_hunt_end", "full_stamina_drain", "weakens_with_more_equipment",
        "photo_stuns_blind", "invisible_on_camera_feeds", "four_finger_uv_print", "can_fly_teleport",
    ],
    "Ciblage": [
        "relentless_single_target",
    ],
}

TRAIT_CATEGORY = {}
for _cat, _traits in _TRAIT_CATEGORY_MAP.items():
    for _t in _traits:
        TRAIT_CATEGORY[_t] = _cat
for _t in TRAIT_QUESTIONS:
    TRAIT_CATEGORY.setdefault(_t, "Autres")

# Construction automatique : pour chaque trait, l'ensemble des fantômes qui le possèdent.
TRAIT_GHOSTS = {trait: set() for trait in TRAIT_QUESTIONS}
for _name, _data in GHOSTS.items():
    for _trait in _data["traits"]:
        TRAIT_GHOSTS[_trait].add(_name)
