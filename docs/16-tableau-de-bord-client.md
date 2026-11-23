# 16 — Tableau de bord client

> **Spécification, rien n'est construit.** Les champs et la publication figée qu'elle exige n'existent pas encore
> (§6). Aucune valeur ne s'affiche sans champ qui la produit. Les maquettes ne contiennent que des emplacements.

## 1. Lecteur et décisions

Le lecteur est la **direction de la société cliente**. Le tableau de bord du cabinet reste inchangé et ne lui est
jamais transmis.

| # | Décision | Lue dans |
|---|---|---|
| 1 | accepter, refuser ou reporter une recommandation | À décider |
| 2 | nommer un responsable et une échéance | Prochaines échéances |
| 3 | arbitrer un retard ou un report | En retard, Reportées |
| 4 | débloquer une dépendance | Bloquées |
| 5 | réagir à une priorité sans action | Priorités couvertes |
| 6 | demander la vérification de ce qui est déclaré fait | À vérifier |

Le client décide de ses actions. **Seul un consultant nommé publie.** Les saisies se font dans l'application,
Power BI les affiche.

## 2. Règles d'affichage

1. Page 1 : libellés de **3 mots au plus**, aucun texte explicatif.
2. Points principaux : **3 au plus**, un titre de **80 caractères au plus**, rédigé et validé par le consultant.
3. Synthèse : bandeau compact de la feuille de route par période, sous les KPI. Le détail est en page 2.
4. Période choisie à la publication : trimestre, semestre ou année. Sans dates : phases ordonnées, sans calendrier.
5. Champ vide : « À renseigner », **jamais 0**. Un KPI dont le champ n'existe pas est masqué.
6. « Destiné au client » et nom de la société sur **chaque page et dans le nom du fichier**.
7. Seuils (30 jours, 2 reports par défaut) : paramètres du client, non affichés.
8. Titres nominaux, au plus 4 KPI en tête, aucun filtre de client.
9. Anthracite et gris, jaune en accent, rouge toujours doublé d'un mot. Ni logo ni nom de cabinet.

## 3. Maquettes

`n`, `x`, `y` et les chevrons sont des emplacements.

### Page 1 : Synthèse

```
+------------------------------------------------------------------------+
| CADRAGE  Synthèse              DESTINÉ AU CLIENT · <société> · <date>  |
+-----------------+-----------------+-----------------+------------------+
| Recommandations | À décider       | Réalisées       | En retard        |
|        n        |        n        |      x / y      |        n         |
|                 |                 | À vérifier : n  | Reportées : n    |
+-----------------+-----------------+-----------------+------------------+
| Feuille de route                                                       |
|   <période 1>     |   <période 2>     |   <période 3>    | <période 4> |
|   n actions  ###  |   n actions  ##   |   n actions  #   | n actions   |
+-----------------------------------+------------------------------------+
| Points principaux                 | Décisions attendues                |
| ! <titre validé, 80 car.>         | <recommandation>              n j  |
| ! <titre validé, 80 car.>         | <recommandation>              n j  |
| ! <titre validé, 80 car.>         | <recommandation>              n j  |
+-----------------------------------+------------------------------------+
| Priorités couvertes               | Prochaines échéances               |
| 1 <priorité>               x / y  | jj/mm <action>        <fonction>   |
| 2 <priorité>         Sans action  | jj/mm <action>        <fonction>   |
+-----------------------------------+------------------------------------+
| n diagnostics · version <v> · <consultant qui publie>                  |
+------------------------------------------------------------------------+
```

### Page 2 : Feuille de route

```
+------------------------------------------------------------------------+
| CADRAGE  Feuille de route      DESTINÉ AU CLIENT · <société> · <date>  |
+--------------------------+-----+-----+-----+-----+----------+----------+
| Priorité / action        | P1  | P2  | P3  | P4  | Resp.    | État     |
| 1 <priorité>             |     |     |     |     |          |          |
|   <action A>             | ### | ##  |     |     | <fonct.> | En cours |
|   <action B>  après A    |     |  ## | ### |     | <fonct.> | À faire  |
| 2 <priorité>             |     |     |     |     |          |          |
|   <action C>  après X    |     |     | ### | ### | <fonct.> | Bloquée  |
| Projet existant X        | ### | ### |     |     | <fonct.> | En cours |
+--------------------------+-----+-----+-----+-----+----------+----------+
| À renseigner : n                                     | aujourd'hui     |
+------------------------------------------------------------------------+
```

### Suivi pas encore renseigné

```
+------------------------------------------------------------------------+
| CADRAGE  Synthèse              DESTINÉ AU CLIENT · <société> · <date>  |
+-----------------------+------------------------+-----------------------+
| Recommandations       | Constats majeurs       | Majeurs couverts      |
|          n            |           n            |        x / y          |
+-----------------------+------------------------+-----------------------+
| Phase 1               | Phase 2                | Phase 3               |
| <action>              | <action>               | <action>              |
+-----------------------+------------------------+-----------------------+
| Échéances : À renseigner          | Avancement : À renseigner          |
+-----------------------------------+------------------------------------+
```

Sans publication, aucun fichier client n'est produit.

## 4. Indicateurs

| KPI | Définition et formule | Champ source | Seuil (paramètre) | Décision |
|---|---|---|---|---|
| Recommandations | initiatives retenues de la dernière publication | initiative : existe ; publication : **à créer** | aucun | 1 |
| À décider | publiées sans décision du client | décision : **à créer** | 30 jours | 1 |
| Réalisées | vérifiées ÷ acceptées, affiché « x / y » | décision, vérification : **à créer** | aucun | 3 |
| À vérifier | déclarées faites, non vérifiées | avancement, vérification : **à créer** | 30 jours | 6 |
| En retard | acceptées, échéance passée, ni déclarées ni vérifiées | échéance, avancement : **à créer** | plus de 0 | 3 |
| Reportées | échéance courante postérieure à l'échéance initiale | deux échéances : **à créer** | 2 reports | 3 |
| Constats majeurs | constats validés de gravité `high`, dans la publication | constat : existe ; publication : **à créer** | aucun | 1 |
| Majeurs couverts | constats majeurs ayant une action retenue ÷ constats majeurs | lien : existe ; action retenue : **à créer** | un non couvert | 1 |
| Priorités couvertes | priorités ayant une action acceptée ÷ priorités validées | priorité, lien, décision : **à créer** | une sans action | 5 |
| Prochaines échéances | 3 premières actions acceptées non réalisées | échéance, responsable : **à créer** | 30 jours | 2 |
| Bloquées | début prévu passé et prérequis non réalisé | lien entre initiatives : existe ; dates, états, projets : **à créer** | plus de 0 | 4 |
| Actions par période | actions retenues dont le début tombe dans la période | début, période : **à créer** | aucun | 2 |
| Diagnostics | documents de ce rôle inclus dans la publication | document : existe ; rôle : **à créer** | aucun | traçabilité |

Refusées, reportées sans date et sans objet ne sont ni « réalisées » ni « en retard ».

## 5. Retiré volontairement

| Retiré | Raison |
|---|---|
| modèle, banc, taux de vérification, alertes d'injection | aucune décision de la direction n'en dépend |
| temps gagné | non mesuré, interne au cabinet |
| file de relecture, renvois, noms des rédacteurs | organisation du cabinet ; seul le consultant qui publie est nommé |
| prédiction | aucun historique du client ne la valide |
| score de priorité | précision trompeuse, le rang suffit |
| avancement global en % | mélangerait déclaré et vérifié |
| brouillons, propositions non retenues | jamais dans le fichier, même masqués |

## 6. Champs à fournir avant de construire

| Champ | Qui saisit | Tant qu'il est vide |
|---|---|---|
| `client_id` stable, porté par le dossier | administrateur | export refusé |
| Publication figée : version, date, consultant, période choisie, actions retenues | consultant nommé | aucun fichier |
| Titre d'un point principal, 80 caractères au plus, validé | consultant | point masqué |
| Identifiant de recommandation stable entre versions | système | suivi masqué |
| Priorité institutionnelle : libellé, rang, source, validation, liens | consultant propose, direction confirme | bloc masqué |
| Projet existant : état, dates, responsable, dépendances | PMO du client, consultant vérifie | lignes absentes |
| Décision : statut, auteur, date, motif | direction | « À renseigner » |
| Responsable (une fonction) | direction | « À renseigner » |
| Début, échéance initiale et courante, motif de report | PMO du client | phases ordonnées, retard masqué |
| Avancement : non démarré, en cours, déclaré fait, avec preuve | responsable de l'action | « À renseigner » |
| Vérification : auteur, date, jamais le déclarant | consultant ou contrôle interne | reste « À vérifier » |
| Rôle du document | déposant, confirmé par le consultant | compteur masqué |
| Seuils du client | direction, saisis par l'administrateur | valeurs par défaut |

`duration_weeks` existe déjà et se saisit dans l'interface. Une durée vide reste vide : aucune valeur par défaut ne
devient une date. Tant qu'il n'existe pas de compte client, le consultant saisit la décision avec la référence du
compte rendu.

### Conditions préalables

« Approuvé » ne suffit pas pour publier. Constaté le 22/11/2026 sur `main` (`fb2bfeb`), fonctions appelées en mémoire :

- une source inexistante, acquittée, passe l'approbation puis disparaît de l'export ;
- une recommandation sans source ni constat passe sans signal ;
- les initiatives de la feuille de route ne sont pas vérifiées à l'approbation ;
- un constat non validé peut être cité ;
- une durée vide devient 4 semaines dans le Gantt exporté.

Ces corrections relèvent du lot cœur métier. Elles sont à revérifier avant de construire ce tableau de bord.

## 7. Isolation par client

1. Un export par `client_id`, filtré **à la source**. Le nom du client est un texte libre : jamais une clé.
2. L'export lit la publication figée, pas l'entrepôt `dw`, qui exclut volontairement les textes.
3. Liste blanche de colonnes, sans clé séquentielle ni agrégat multi-client.
4. Modèle Power BI distinct, gabarit sans données, puis **un dossier et un fichier par client**. La RLS ne sert
   jamais d'isolation entre clients.
5. Refus si le client est inconnu ou si démonstration et réel sont mêlés.
6. Nom : `<société>-feuille-de-route-destine-au-client-v<version>`, avec un nom de société assaini.
7. Test : deux clients avec des marqueurs, aucun marqueur de l'un dans les fichiers de l'autre.
8. Remise en PDF, ou sur site dans Desktop ou Report Server. Aucune donnée réelle dans Power BI Service.

## 8. Critères de recette

- chaque valeur affichée remonte à un champ de la publication ;
- une proposition non retenue est absente du jeu de données, pas seulement de la page ;
- champs vides : « À renseigner » ou bloc masqué, aucun 0 fabriqué ;
- sans dates : phases seulement ;
- test de fuite du §7 réussi ;
- les deux pages vues au rendu, pleines, vides et avec les titres les plus longs.

## 9. Sources

Consultées le 22/11/2026.

| Source | Ce qui en est retenu | Lecture |
|---|---|---|
| [Manuel financier de Papouasie-Nouvelle-Guinée, suivi d'audit](https://www.finance.gov.pg/wp-content/uploads/2026/04/FMM-05-14-Monitoring-and-Follow-up.pdf) | responsable, échéance, preuve, vérification avant clôture | texte extrait lu |
| [Cour des comptes, suivi des recommandations 2025](https://www.vie-publique.fr/files/rapport/pdf/300407.pdf) | totale, partielle, non mise en œuvre, refus, sans objet | passages ciblés |
| [OMS, tableau de bord d'audit interne](https://www.who.int/about/office-of-internal-oversight-services/dashboards/internal-audit) | peu de chiffres : clos à la date, en retard | compte rendu de lecture assistée |
| [ACCA, suivi des actions](https://www.accaglobal.com/sg/en/member/sectors/internal-audit/learn/management-actions.html) | déclaré n'est pas vérifié, dates révisées | compte rendu de lecture assistée |
| [ISACA, suivi d'audit](https://www.isaca.org/resources/news-and-trends/isaca-now-blog/2025/follow-up-audits-and-follow-up-process-the-auditors-impact-litmus-tool) | retards et ancienneté | compte rendu de lecture assistée |
| [Protiviti](https://www.protiviti.com/au-en/blogs/why-your-project-dashboards-are-lying-you) (avis de cabinet) | limites des feux tricolores, décisions requises | compte rendu de lecture assistée |
| [Microsoft, multi-client](https://learn.microsoft.com/en-us/power-bi/developer/embedded/embed-multi-tenancy) | un modèle par client | compte rendu de lecture assistée |
| [Microsoft, RLS](https://learn.microsoft.com/en-us/power-bi/guidance/rls-guidance) | filtre des lignes, pas des objets | compte rendu de lecture assistée |
| [Microsoft, gabarits](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-templates) | un gabarit peut garder des valeurs de filtre | compte rendu de lecture assistée |

**Choix du projet, non sourcés** : deux pages, 3 points, 80 caractères, seuils par défaut, ressemblance de palette.
**Non lu** : norme IIA 15.2, IBCS, ISO 24896, méthodes internes des grands cabinets.
