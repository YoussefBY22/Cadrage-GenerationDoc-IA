"""Choix des 25 exemples du pilote v3 : repères dans les documents et phrases de sortie.

Aucun texte de source n'est copié ici sauf les phrases de sortie, qui sont des extraits courts et exacts
(vérifiés contre le passage à la construction). Les passages sont lus dans les documents par repères.

Formes de phrase de sortie (``p`` = rang du passage dans la liste ``passages``, avant mélange) :
- ``("v", p, texte)``      : phrase humaine recopiée telle quelle depuis le passage ;
- ``("a", p, amorce, item)`` : amorce + alinéa, tous deux recopiés, joints en une phrase (assemblage mécanique) ;
- ``("f", p, texte, theme, gravite)`` : constat recopié ; le thème et la gravité sont écrits par l'assistant.
"""

from __future__ import annotations


def P(doc: str, start: str, end: str | None = None, incl: bool = True, after: str | None = None) -> dict:
    return {"doc": doc, "start": start, "end": end, "incl": incl, "after": after}


E28, E27, E26 = "eca-sr-2024-28", "eca-sr-2024-27", "eca-sr-2024-26"
R27, R2613 = "eca-rep-sr-2024-27", "eca-rep-sr-2026-13"
C25, CSEC, C21, ROCH = "dinum-cctp-2025", "dinum-cctp-securite-2025", "dinum-cctp-2021", "ccas-rochefort-cdc-2025"

CONSIGNE_DIVERGENCE = ("Compare les deux passages : indique ce sur quoi ils divergent, sans trancher, "
                       "en citant chaque passage pour ce qu'il affirme.")

EXAMPLES: list[dict] = [
    # ---------------------------------------------------------------- feuille de route (5)
    {"id": "fdr0", "type": "feuille de route", "doc": E28, "section": ("roadmap", "initiatives"),
     "passages": [
         P(E28, "La Commission a fait des contrôles de transposition", "(voir points 23 à 28)."),
         P(E28, "Recommandation n° 1 – Améliorer la planification", "fin décembre 2025."),
         P(E28, "Parallèlement aux plaintes", "(voir point 39).")],
     "phrases": [
         ("a", 1, "La Commission devrait améliorer la planification et la documentation des contrôles de transposition et de conformité:",
          "en planifiant, dès que possible, les travaux requis pour faire contrôler l’application des directives, en particulier les ressources humaines et l’éventuelle expertise externe nécessaires"),
         ("a", 1, "La Commission devrait améliorer la planification et la documentation des contrôles de transposition et de conformité:",
          "en veillant à ce que les DG enregistrent les dates de début et de fin de tous les contrôles"),
         ("v", 0, "Nous avons également constaté que les directions générales manquaient d’informations sur les dates d’achèvement d’environ un tiers des contrôles de transposition et de conformité repris dans notre échantillon, ce qui trahit des lacunes dans la documentation et le suivi de ces activités prioritaires."),
         ("v", 1, "D’ici à fin décembre 2025.")],
     "doute": "Les deux premières phrases sont assemblées (amorce + alinéa) : la source les présente en liste, pas en phrases. "
              "La 3e garde le « Nous » de la Cour ; la roadmap de l'application parlerait à la 3e personne."},
    {"id": "fdr1", "type": "feuille de route", "doc": E28, "section": ("roadmap", "calendrier"),
     "passages": [
         P(E28, "Recommandation n° 3 – Renforcer la gestion", "pour l’alinéa b)."),
         P(E28, "Nous avons relevé que la plupart des cas", "(voir points 59 à 64).")],
     "phrases": [
         ("v", 0, "D’ici à fin décembre 2027 pour l’alinéa a) et fin décembre 2026 pour l’alinéa b)."),
         ("a", 0, "La Commission devrait renforcer sa gestion des dossiers d’infraction et le système de sanctions:",
          "en ajustant, plus rapidement si nécessaire, lors du contrôle des progrès réalisés dans le traitement des dossiers, les ressources requises et les priorités fixées, afin de repérer les éventuels goulets d’étranglement et de les anticiper"),
         ("a", 0, "La Commission devrait renforcer sa gestion des dossiers d’infraction et le système de sanctions:",
          "en réexaminant la méthode de proposition de sanctions afin que celles-ci soient suffisamment dissuasives"),
         ("v", 1, "Nous nous interrogeons donc sur l’effet dissuasif des sanctions financières.")],
     "doute": "Les échéances sont reprises telles quelles (2027 pour a, 2026 pour b : b arrive avant a). "
              "La dernière phrase est un doute de la Cour, pas un fait établi."},
    {"id": "fdr2", "type": "feuille de route", "doc": E27, "section": ("roadmap", "calendrier"),
     "passages": [
         P(E27, "Le groupe «Code de conduite» contribue", "(voir points 75 à 84)."),
         P(E27, "Recommandation n° 4 – Renforcer le soutien", "à partir de 2025 pour b).")],
     "phrases": [
         ("v", 1, "D’ici à la fin de 2026 pour a); chaque année à partir de 2025 pour b)."),
         ("a", 1, "Afin de soutenir plus efficacement le groupe «Code de conduite» et permettre aux actions de ce dernier d’avoir un effet dissuasif maximal, la Commission devrait:",
          "proposer au groupe de convenir de règles claires et de limiter les périodes de maintien des droits acquis et de démantèlement, et, en cas d’accord, d’en vérifier le respect"),
         ("a", 1, "Afin de soutenir plus efficacement le groupe «Code de conduite» et permettre aux actions de ce dernier d’avoir un effet dissuasif maximal, la Commission devrait:",
          "dans le cadre de son mandat élargi, procéder annuellement à une analyse des mesures fiscales préférentielles et des particularités fiscales de portée générale nouvellement introduites par les États membres, et notifier au groupe les cas potentiellement dommageables sur la base d’une analyse des risques"),
         ("v", 0, "De surcroît, le groupe ne suit pas des règles claires lorsqu’il décide des périodes de maintien des droits acquis concernant les régimes dommageables identifiés, de sorte que parfois, ces périodes sont particulièrement longues.")],
     "doute": "Échéance « chaque année à partir de 2025 » : récurrence, pas une date ; le modèle doit la garder telle quelle."},
    {"id": "fdr3", "type": "feuille de route", "doc": E27, "section": ("roadmap", "initiatives"),
     "passages": [
         P(E27, "En outre, la Commission n’a généralement pas établi", "(voir points 49 à 53)."),
         P(E27, "Clarifier le cadre législatif de l’UE Pour faire en sorte", "pour c).")],
     "phrases": [
         ("a", 1, "Pour faire en sorte que les États membres appliquent la législation de l’UE de manière uniforme, la Commission devrait:",
          "développer, en coopération avec les États membres, ses orientations et notamment fournir à ces derniers des lignes directrices sur la manière d’interpréter les textes législatifs portant sur la lutte contre les régimes fiscaux dommageables et l’évasion fiscale des entreprises, d’effectuer les analyses des risques et d’utiliser les informations fiscales reçues"),
         ("a", 1, "Pour faire en sorte que les États membres appliquent la législation de l’UE de manière uniforme, la Commission devrait:",
          "examiner la nécessité de modifier la DAC 6 sur la base du résultat de l’évaluation en cours et de l’issue des contentieux pendants"),
         ("v", 0, "La Commission supervise efficacement la transposition de la législation de l’UE en droit national et engage des procédures d’infraction lorsque c’est nécessaire, mais elle réalise ses évaluations parfois trop tardivement."),
         ("v", 1, "D’ici à la fin de 2026 pour a) et b); d’ici à la fin de 2028 pour c).")],
     "doute": "La phrase 3 garde « parfois » et « efficacement » de la source. L'alinéa c) n'est pas repris alors que son échéance l'est."},
    {"id": "fdr4", "type": "feuille de route", "doc": E26, "section": ("roadmap", "axes"),
     "passages": [
         P(E26, "Nous avons constaté qu’il y avait peu de coordination", "(points 48 à 53).", after="Conclusions et recommandations 100 Dans l’ensemble, nous concluons"),
         P(E26, "Recommandation n° 1 – Analyser comment recenser", "D’ici la fin 2026.", after="Conclusions et recommandations 100 Dans l’ensemble, nous concluons"),
         P(E26, "Recommandation n° 2 – Recenser, analyser", "D’ici la fin 2026.", after="Conclusions et recommandations 100 Dans l’ensemble, nous concluons")],
     "phrases": [
         ("v", 0, "Nous avons constaté qu’il y avait peu de coordination entre le FAMI et le Fonds social européen (FSE) lors de la période 2014-2020."),
         ("a", 1, "La Commission devrait, en coopération avec les États membres et dans le cadre des compétences respectives de chaque partie, analyser comment:",
          "recenser les déficits de financement et les synergies possibles entre les sources disponibles de financement des parcours d’intégration des ressortissants de pays tiers"),
         ("a", 2, "En coopération avec les États membres, la Commission devrait:",
          "collecter, analyser et diffuser des informations tant sur les bonnes pratiques que sur les défis à relever pour adapter le soutien du FAMI à l’intégration de groupes spécifiques, ainsi que sur d’autres sujets qui revêtent une importance croissante dans le domaine de l’intégration"),
         ("v", 1, "D’ici la fin 2026.")],
     "doute": "Axe 1 (coordination des fonds) et axe 2 (bonnes pratiques) : le rattachement des recommandations aux axes est mon choix, "
              "la Cour ne parle pas d'« axes ». Exemple de test (document SR-2024-26)."},
    # ---------------------------------------------------------------- termes de référence (5)
    {"id": "tdr0", "type": "termes de référence", "doc": C25, "section": ("tor", "livrables"),
     "passages": [
         P(C25, "Livrables attendus", "etc.).", after="5.2 UO Design"),
         P(C25, "Compétences attendues", "(respect du RGAA, sobriété, etc.).", after="5.2 UO Design")],
     "phrases": [
         ("v", 0, "Prototype ou service en production intégrant les recommandations UX, dans le format précisé par le bénéficiaire."),
         ("v", 0, "Documentation des actions entreprises et notamment scénarisation d’interfaces et parcours utilisateurs (storyboards, user journeys, personas, etc.).")],
     "doute": "C'est un CCTP, pas des termes de référence : la section « Livrables attendus » d'une unité d'œuvre joue le rôle du « livrables » d'un TdR. "
              "Aucun vrai TdR à licence vérifiée n'a été trouvé."},
    {"id": "tdr1", "type": "termes de référence", "doc": C25, "section": ("tor", "contexte"),
     "passages": [
         P(C25, "Cet accord-cadre interministériel s’inscrit dans le contexte", "créer des services qui répondent mieux aux besoins des utilisateurs."),
         P(C25, "3.1 Objet L’accord-cadre a pour objet", "l’approche produit agile piloté par l’impact.")],
     "phrases": [
         ("v", 0, "Cet accord-cadre interministériel s’inscrit dans le contexte de la priorité de la feuille de route du numérique de l’État et vise à faciliter l’adoption de « l’approche produit » au sein des administrations publiques."),
         ("v", 0, "L’objectif de l’approche produit est simple : créer des services qui répondent mieux aux besoins des utilisateurs."),
         ("v", 1, "L’accord-cadre a pour objet la réalisation de prestations de conception, de déploiement et d’amélioration continue de services numériques conçus selon l’approche produit agile piloté par l’impact.")],
     "doute": "Contexte d'un accord-cadre (priorité de la feuille de route du numérique), pas contexte et justification d'une mission : "
              "aucun « constat du diagnostic » dans le passage. La 3e phrase est un objet, pas du contexte."},
    {"id": "tdr2", "type": "termes de référence", "doc": C25, "section": ("tor", "objectifs"),
     "passages": [
         P(C25, "3.1 Objet L’accord-cadre a pour objet", "du dispositif interministériel."),
         P(C25, "Cet accord-cadre interministériel s’inscrit dans le contexte", "créer des services qui répondent mieux aux besoins des utilisateurs.")],
     "phrases": [
         ("v", 0, "L’accord-cadre a pour objet la réalisation de prestations de conception, de déploiement et d’amélioration continue de services numériques conçus selon l’approche produit agile piloté par l’impact."),
         ("v", 0, "D’une part, la conception, le développement et l’exploitation des produits numériques opérés par la DINUM (hors OPI) et par les incubateurs de services numériques des ministères, ainsi que les missions d’accompagnement de produits réalisées par la DINUM."),
         ("v", 0, "D’autre part, la réalisation des produits numériques des autres entités bénéficiaire, destiné à la conception, au développement et à l’exploitation des produits numériques des administrations, opérateurs et autres entités bénéficiaires du dispositif interministériel.")],
     "doute": "Objet et besoin d'un marché, pas objectif général et objectifs spécifiques d'une mission. Les 2e et 3e phrases sont les deux puces « d'une part / d'autre part » "
              "prises séparément : la phrase de liaison « Le besoin concerne » est perdue. Faute de la source conservée (« bénéficiaire, destiné »)."},
    {"id": "tdr3", "type": "termes de référence", "doc": C21, "section": ("tor", "livrables"),
     "passages": [
         P(C21, "2.5. UO Réversibilité : transfert portant sur un produit numérique à la fin du marché Prestation", "un bilan de transfert de compétences.")],
     "phrases": [
         ("v", 0, "L’objectif est d’opérer vers le nouveau prestataire le transfert des compétences techniques et fonctionnelles du produit numérique, par un fonctionnement en biseau avec la nouvelle équipe ou par la préparation de la résilience et de la documentation du service dans le cas où la nouvelle équipe n'est pas encore opérationnelle."),
         ("v", 0, "Cette phase ne doit pas durer plus d’un mois."),
         ("v", 0, "Les livrables attendus sont une documentation mise à jour, des tutoriels, un bilan de transfert de compétences.")],
     "doute": "Exemple de test (document CCTP 2021). La consigne est celle de la section « Livrables » de l'application ; "
              "la 1re phrase est un objectif, pas un livrable."},
    {"id": "tdr4", "type": "termes de référence", "doc": C25, "section": ("tor", "objectifs"),
     "passages": [
         P(C25, "Prestation attendue", "sans interruption de service ni altération du niveau de qualité attendu.", after="5.7 UO Transfert de compétences"),
         P(C25, "Le mode produit, caractérisé par une équipe intégrée", "l’appropriation des solutions développées.", after="5.7 UO Transfert de compétences")],
     "phrases": [
         ("v", 0, "Cette phase a pour objectif d’organiser et de conduire le transfert de compétences en fin de projet au bénéfice de l’administration et/ou d’un tiers désigné par celle-ci."),
         ("v", 0, "Elle inclut également l’assistance technique requise pour assurer la continuité des activités assurées par le titulaire, sans interruption de service ni altération du niveau de qualité attendu."),
         ("v", 1, "Le mode produit, caractérisé par une équipe intégrée, favorise le transfert de compétences du titulaire vers l’administration.")],
     "doute": "Objectifs d'une unité d'œuvre (transfert de compétences), pas objectif général et objectifs spécifiques d'une mission."},
    # ---------------------------------------------------------------- cahier des charges (5)
    {"id": "cdc0", "type": "cahier des charges", "doc": ROCH, "section": ("cdc", "perimetre"),
     "passages": [
         P(ROCH, "Le CCAS de Rochefort", "à assurer une veille sociale tout au long de l'année.", after="ARTICLE 1"),
         P(ROCH, "Le service s'adresse aux personnes dépendantes", "dispositif de coffre à clés sécurisé.", after="ARTICLE 2")],
     "phrases": [
         ("v", 0, "Le titulaire s’engage à livrer, en liaison froide, les repas commandés aux personnes dépendantes domiciliées sur le territoire d’intervention du Pôle Maintien à Domicile du CCAS et à assurer une veille sociale tout au long de l’année."),
         ("a", 1, "Le service s'adresse aux personnes dépendantes :",
          "de 65 ans et plus et/ou en situation de handicap et titulaires d'une carte d'invalidité au taux minimal de 80%")],
     "doute": "Un cahier des charges de service (portage de repas), pas de projet numérique. La phrase 2 est assemblée (amorce + puce)."},
    {"id": "cdc1", "type": "cahier des charges", "doc": ROCH, "section": ("cdc", "contraintes"),
     "passages": [
         P(ROCH, "Planning de livraison", "selon le planning suivant :", after="ARTICLE 4"),
         P(ROCH, "Il doit établir les signalements", "avant 14 h 00.", after="ARTICLE 5")],
     "phrases": [
         ("v", 0, "La journée alimentaire doit être livrée entre 8h00 et 12h00."),
         ("v", 1, "Il doit établir les signalements correspondants et les communiquer au CCAS via un outil de suivi (portail internet, courrier électronique sécurisé...) le jour même de la prestation avant 14 h 00.")],
     "doute": "Le tableau des jours limites de commande est perdu à l'extraction : il n'est pas dans le passage."},
    {"id": "cdc2", "type": "cahier des charges", "doc": ROCH, "section": ("cdc", "non_fonctionnelles"),
     "passages": [
         P(ROCH, "Principe de la liaison froide", "pas de risque pour la santé.", after="ARTICLE 4"),
         P(ROCH, "Il effectue le transport et la livraison des repas", "produits d’origine animale et denrées alimentaires en contenant.", after="ARTICLE 6")],
     "phrases": [
         ("v", 0, "Le portage de repas est effectué en liaison froide, c’est-à-dire lorsque la conservation des repas entre leur élaboration et leur consommation est assuré par le froid (maintien entre 0 et 3 degrés)."),
         ("v", 0, "La chaine du froid ne doit pas être interrompue."),
         ("v", 1, "Il effectue le transport et la livraison des repas dans le respect de la limite de température de +3°C, avec tolérance jusqu’à +5°C, fixée suite à l’analyse des dangers, et ce, dans le cadre de l’article 3 de l’arrêté du 21 décembre 2009 relatif aux règles sanitaires applicables aux activités de commerce de détail, d’entreposage et de transport de produits d’origine animale et denrées alimentaires en contenant.")],
     "doute": "Exigence de conservation des aliments, pas de performance logicielle. L'exception du passage (« il est admis de les soustraire à ces températures pour des périodes de courte durée… ») "
              "n'est pas reprise : « La chaine du froid ne doit pas être interrompue » y paraît plus absolu qu'à la source. À corriger en ajoutant l'exception."},
    {"id": "cdc3", "type": "cahier des charges", "doc": CSEC, "section": ("cdc", "non_fonctionnelles"),
     "passages": [
         P(CSEC, "Dès la prise de poste", "(10 minutes) (SECU_SPT_002).", after="Phase de démarrage")],
     "phrases": [
         ("v", 0, "Appliquer sans délai les mises à jour du poste de travail (OS, applications)."),
         ("v", 0, "Choisir des mots de passe longs (≥ 20 caractères), complexes et uniques par service, avec activation systématique du 2FA lorsque disponible."),
         ("v", 0, "Mettre en place un mécanisme automatique de verrouillage de la session après une certain période d’inactivité (10 minutes).")],
     "doute": "Exemple de test (annexe sécurité). Les phrases sont des impératifs (« Choisir… ») et non « Le système doit… » comme le demande la consigne de l'application ; "
              "la consigne demande aussi des identifiants NFR-1…, absents ici. La source contient une faute (« une certain période »), conservée. "
              "Les repères (SECU_…) du texte source restent dans le passage."},
    {"id": "cdc4", "type": "cahier des charges", "doc": C25, "section": ("cdc", "contraintes"),
     "passages": [
         P(C25, "Efficacité des infrastructures :", "doivent être fournies et justifiées.", after="4.2 Hébergement"),
         P(C25, "Si le titulaire ne gère pas directement", "par son propre fournisseur.", after="4.2 Hébergement")],
     "phrases": [
         ("v", 0, "Le titulaire doit optimiser l'efficacité énergétique de ses infrastructures d'hébergement, en visant des indicateurs de performance tels que le PUE (Power Usage Effectiveness), le CUE (Carbon Usage Effectiveness) et le WUE (Water Usage Effectiveness)."),
         ("v", 0, "Des valeurs cibles pour ces indicateurs doivent être fournies et justifiées."),
         ("v", 1, "Si le titulaire ne gère pas directement les infrastructures d'hébergement, il doit s'assurer que son propre fournisseur d'hébergement applique les recommandations précédentes.")],
     "doute": "Contraintes environnementales d'hébergement, que la consigne « techniques, réglementaires, budgétaires et de délai » couvre mal."},
    # ---------------------------------------------------------------- divergences entre deux sources (5)
    {"id": "div0", "type": "divergence entre deux sources", "doc": R27, "section": ("custom", "Divergences entre la recommandation et la réponse", CONSIGNE_DIVERGENCE),
     "passages": [
         P(R27, "Afin que les États membres mettent en œuvre des sanctions efficaces", "(Quand? Fin 2026)"),
         P(R27, "La Commission accepte partiellement cette recommandation.", "juridiquement défendable devant la Cour de justice de l’Union européenne.")],
     "phrases": [
         ("v", 0, "Afin que les États membres mettent en œuvre des sanctions efficaces, proportionnées et dissuasives en cas de non-respect des obligations de déclaration prévues dans la DAC 6, la Commission devrait engager une procédure d’infraction lorsqu’il existe des éléments de preuve suffisants qu'un État membre applique un système de sanctions manifestement inapproprié en réaction aux violations des dispositions de la DAC 6."),
         ("v", 1, "La Commission accepte partiellement cette recommandation."),
         ("v", 1, "La décision d’engager une procédure d’infraction contre un État membre pour quelque motif que ce soit repose sur une analyse détaillée, dans chaque cas individuel, de la question et de la législation en cause.")],
     "doute": "C'est une divergence de position (recommandation / acceptation partielle), pas une contradiction factuelle. "
              "La consigne est écrite par l'assistant."},
    {"id": "div1", "type": "divergence entre deux sources", "doc": R27, "section": ("custom", "Divergences entre la recommandation et la réponse", CONSIGNE_DIVERGENCE),
     "passages": [
         P(R27, "Recommandation nº 1 - Clarifier le cadre législatif de l’UE Pour faire en sorte", "mécanismes de règlement des différends."),
         P(R27, "La Commission accepte partiellement la recommandation nº 1 b).", "en accord avec les États membres.")],
     "phrases": [
         ("a", 0, "Pour faire en sorte que les États membres appliquent la législation de l’UE de manière uniforme, la Commission devrait:",
          "examiner la nécessité de modifier la DAC 6 sur la base du résultat de l’évaluation en cours"),
         ("v", 1, "La Commission accepte partiellement la recommandation nº 1 b)."),
         ("v", 1, "Toutefois, il ne saurait être préjugé des futures propositions législatives; celles-ci doivent être adaptées aux situations spécifiques, en accord avec les États membres.")],
     "doute": "Même document que div0 (réponses au rapport 27/2024) : deux exemples du même document, tous deux en entraînement."},
    {"id": "div2", "type": "divergence entre deux sources", "doc": R27, "section": ("custom", "Divergences entre la recommandation et la réponse", CONSIGNE_DIVERGENCE),
     "passages": [
         P(R27, "Recommandation nº 2 - Améliorer la qualité des déclarations DAC 6 Pour optimiser", "(Quand? Fin 2027)"),
         P(R27, "La Commission accepte partiellement la recommandation, car", "ou de leur conception.")],
     "phrases": [
         ("v", 1, "La Commission accepte partiellement la recommandation, car la modification proposée nécessiterait une modification de la DAC 6 et la Commission ne peut préjuger des futures propositions législatives ou de leur conception.")],
     "doute": "Un seul fait dans la sortie : à voir si l'échantillon est trop pauvre. À écarter si la recommandation de la Cour n'est pas utilisée."},
    {"id": "div3", "type": "divergence entre deux sources", "doc": R2613, "section": ("custom", "Divergences entre la recommandation et la réponse", CONSIGNE_DIVERGENCE),
     "passages": [
         P(R2613, "Recommandation nº 3 — Clarifier la législation et centrer le contrôle du respect des règles sur les affaires ayant un impact important sur le marché unique La Commission devrait:", "D’ici fin 2027."),
         P(R2613, "La Commission accepte partiellement la recommandation nº 3, point a).", "n’a pas l’intention de rouvrir ou de réviser les directives existantes.")],
     "phrases": [
         ("a", 0, "La Commission devrait",
          "lors du réexamen de la directive sur les services en vue d’une proposition législative, et sans préjudice des décisions des colégislateurs, définir plus clairement l’obligation de proportionnalité des nouvelles exigences nationales ainsi que les modalités de leur notification à la Commission", ", "),
         ("v", 1, "La Commission accepte partiellement la recommandation nº 3, point a)."),
         ("v", 1, "Toutefois, à ce stade, la Commission n’a pas l’intention de rouvrir ou de réviser les directives existantes.")],
     "doute": "Exemple de test (réponses au rapport 13/2026)."},
    {"id": "div4", "type": "divergence entre deux sources", "doc": R2613, "section": ("custom", "Divergences entre la recommandation et la réponse", CONSIGNE_DIVERGENCE),
     "passages": [
         P(R2613, "La Commission devrait: a) en coopération avec les États membres, améliorer l’accès électronique", "D’ici fin 2027."),
         P(R2613, "La Commission accepte partiellement la recommandation nº 4, point c).", "selon la solution qui s’avère la plus appropriée dans chaque cas.")],
     "phrases": [
         ("a", 0, "La Commission devrait", "lorsque la task force ne semble pas en mesure de traiter efficacement ces obstacles, faire des propositions législatives si tous les autres moyens se sont révélés inefficaces", ", "),
         ("v", 1, "La Commission accepte partiellement la recommandation nº 4, point c)."),
         ("v", 1, "En vertu des traités, la Commission dispose du droit exclusif d’initiative législative.")],
     "doute": "Exemple de test. Le passage contient les alinéas a), b), c) : seul c) est repris dans la sortie."},
    # ---------------------------------------------------------------- extraction de constats (5)
    {"id": "con0", "type": "extraction de constats", "doc": E28, "section": ("findings",),
     "passages": [
         P(E28, "En ce qui concerne le délai de référence d’un an", "(voir points 29 à 38)."),
         P(E28, "Dans les dossiers complexes", "(voir points 41 à 47).")],
     "constats": [
         (0, "En ce qui concerne le délai de référence d’un an pour le traitement des plaintes, nous avons constaté que dans 38 % des dossiers ouverts entre 2012 et 2023, la Commission ne l’a pas respecté.",
          "Délais de traitement des plaintes", "medium"),
         (0, "Elle a en outre fixé des critères permettant de prioriser les plaintes, mais elle n’a pas publié de lignes directrices quant à la manière d’en interpréter certaines (par exemple «porter gravement atteinte aux intérêts financiers de l’UE» et «manquement systématique au droit de l’UE»).",
          "Critères de priorisation des plaintes", "medium"),
         (1, "Dans la pratique, bien que les lignes directrices ne précisent pas comment décider de la prolongation des dialogues EU Pilot après l’écoulement du délai de neuf mois ni le temps supplémentaire à leur accorder, 65 % de ces dialogues ont été prolongés au terme du délai initial.",
          "Prolongation des dialogues EU Pilot", "medium")],
     "doute": "Thèmes et gravités écrits par l'assistant : la source ne gradue pas ses constats."},
    {"id": "con1", "type": "extraction de constats", "doc": E27, "section": ("findings",),
     "passages": [
         P(E27, "En ce qui concerne l’échange d’informations fiscales prévu par la DAC 6", "(voir points 64 à 66).")],
     "constats": [
         (0, "Toutefois, ils effectuent peu de contrôles qualité des déclarations DAC 6 avant de les télécharger dans le répertoire central européen.",
          "Contrôle qualité des déclarations DAC 6", "medium"),
         (0, "L’un des principaux points faibles du schéma de déclaration réside dans le fait que le champ de données prévu pour indiquer les noms des pays tiers engagés dans un dispositif transfrontière n’est pas obligatoire.",
          "Schéma de déclaration", "medium"),
         (0, "Au moment de notre audit, aucun des États membres visités n’avait infligé la moindre sanction.",
          "Sanctions en cas de non-déclaration", "high")],
     "doute": "Gravité « high » pour l'absence de sanctions : ma lecture, pas celle de la Cour. La 3e phrase est coupée avant la parenthèse (« voir points… »)."},
    {"id": "con2", "type": "extraction de constats", "doc": E26, "section": ("findings",),
     "passages": [
         P(E26, "Nous avons constaté que le cadre législatif établissait", "(points 48 à 53).", after="Conclusions et recommandations 100 Dans l’ensemble, nous concluons")],
     "constats": [
         (0, "Dans certains États membres, le niveau de soutien du FAMI aux mesures d’intégration était faible par rapport à celui provenant des autres sources de financement disponibles.",
          "Niveau de soutien du FAMI", "low"),
         (0, "La valeur ajoutée du FAMI risque d’être limitée par sa complexité administrative.",
          "Complexité administrative", "medium"),
         (0, "Nous avons constaté qu’il y avait peu de coordination entre le FAMI et le Fonds social européen (FSE) lors de la période 2014-2020.",
          "Coordination entre fonds", "medium")],
     "doute": "Exemple de test. « dans certains États membres » et « risque » sont conservés, mais perdus si le modèle abrège. Gravités : mon choix."},
    {"id": "con3", "type": "extraction de constats", "doc": E28, "section": ("findings",),
     "passages": [
         P(E28, "Nous avons relevé que la plupart des cas", "(voir points 59 à 64)."),
         P(E28, "En ce qui concerne les procédures d’infraction, nous avons constaté", "(voir points 48 à 58).")],
     "constats": [
         (1, "En 2023, le traitement de 72 % des cas de non-communication a dépassé le délai de référence d’un an.",
          "Délais de clôture des infractions", "high"),
         (0, "Toutefois, dans 13 affaires, les États membres concernés payaient des amendes depuis des années plutôt que de remédier à leurs manquements au droit de l’Union.",
          "Effet dissuasif des sanctions financières", "high")],
     "doute": "Deux points voisins du même chapitre. L'ordre des constats suit les passages, pas la source."},
    {"id": "con4", "type": "extraction de constats", "doc": E27, "section": ("findings",),
     "passages": [
         P(E27, "La Commission et les États membres ne mesurent guère", "(voir points 85 à 92)."),
         P(E27, "Le groupe «Code de conduite» contribue", "(voir points 75 à 84).")],
     "constats": [
         (0, "La Commission n’ayant pas fixé de valeurs cibles et d’objectifs quantitatifs dans ce domaine, elle ne vérifie pas s’ils sont efficaces.",
          "Suivi de la performance", "high"),
         (1, "Toutefois, dans plusieurs États membres, les périodes approuvées pour le démantèlement de ce type de régimes ont duré beaucoup plus longtemps que les deux ans recommandés par le Conseil.",
          "Durée du démantèlement des régimes", "medium"),
         (1, "Par ailleurs, les États membres font le choix de n’appliquer qu’une petite partie des mesures défensives susceptibles d’être appliquées aux opérations effectuées avec des pays non coopératifs.",
          "Mesures défensives", "medium")],
     "doute": "Gravités écrites par l'assistant."},
]
