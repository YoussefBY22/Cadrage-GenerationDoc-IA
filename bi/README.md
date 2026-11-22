# Rapport de pilotage Power BI

Le rapport sert les deux acteurs de l'application, le **consultant** qui rédige et le **responsable** qui valide :
constat, 3 recommandations, prédiction de la charge, et un rapport à imprimer.
Qui voit quoi, et pourquoi : [docs/14](../docs/14-acteurs-dashboard.md).

> **Valeurs inventées.** Les chiffres du jeu de démonstration (`python -m app.dw.demo --seed 42`) sont fictifs : ils
> montrent le pilotage possible et ne jugent aucun modèle réel. Le rapport l'affiche sur chaque page.

![Synthèse](../docs/img/powerbi-synthese.png)

| Page | Pour qui | Capture |
|---|---|---|
| Synthèse | les deux acteurs, direction du cabinet | [voir](../docs/img/powerbi-synthese.png) |
| Production | consultant | [voir](../docs/img/powerbi-production.png) |
| Validation | responsable | [voir](../docs/img/powerbi-validation.png) |
| Administration | profil technique | [voir](../docs/img/powerbi-administration.png) |
| Rapport (masquée, par bouton) | impression | [voir](../docs/img/powerbi-rapport.png) |

Indicateurs : [`KPI.md`](KPI.md). Contenu des pages : [`pages.md`](pages.md). Mise en ligne, préparée et non
faite : [`PUBLICATION.md`](PUBLICATION.md). Fichiers produits :
[rapport interne](exemples/rapport-pilotage-demo.pdf), [rapport client](exemples/rapport-client-demo.pdf).

## Confidentialité (contrainte C1)

- Power BI **Desktop** tourne en local. **Ne pas publier** sur Power BI Service, hébergé par Microsoft.
- L'entrepôt `dw` ne contient ni phrases ni passages des clients ([07 §1](../docs/07-entrepot-bi.md)), et le rôle
  `bi_reader` n'a accès qu'à ce schéma.

## Ouvrir le rapport

1. Produire les données (les 14 CSV : un export antérieur à ce modèle ne se charge pas) :

   ```powershell
   cd backend
   $env:STORAGE_URL = "sqlite:///./data/demo-bi.db"  # une base neuve : la démo ne se régénère pas
   python -m app.dw.demo --seed 42
   python -m app.dw.export_csv --out ../bi/export/
   ```

2. Régler le dossier des CSV (chemin absolu), ce qui régénère le projet :

   ```powershell
   python bi/pbip/build_pbip.py --csv "C:\chemin\vers\bi\export"
   ```

   Sans régénérer : dans Power BI, *Transformer les données → Modifier les paramètres → DossierCsv*.

3. Ouvrir `bi/pbip/CadrageIA.pbip`. Le cache de données n'est pas versionné : cliquer **Refresh now**, puis
   **Apply changes** si le bandeau « pending changes » s'affiche. Ce bandeau apparaît à la première ouverture d'un
   projet sans cache et ne modifie pas les fichiers.

Dans Power BI Desktop, les boutons de navigation se suivent avec **Ctrl + clic**.

### Avec de vraies données

- CSV : `python -m app.dw.etl`, puis le même export. Sur un entrepôt antérieur à la correction des refus :
  recharger avec `--full`.
- PostgreSQL, en lecture seule : `psql -f db/dw/roles.sql` (changer le mot de passe), puis dans les paramètres
  `Source` = `PostgreSQL`, `PgServer`, `PgDatabase`. Importer avec `bi_reader`. **Ce chemin n'a pas été testé dans
  Power BI Desktop** (pilote Npgsql, port 5432 à exposer en local seulement).
- Export anglais (`--locale en`) : paramètre `CultureCsv` = `en-US`. Non testé dans Power BI Desktop.

## Modifier le rapport

Le projet PBIP est **généré**. Ne pas enregistrer depuis Power BI : la génération suivante écraserait la modification.

| Pour changer | Fichier |
|---|---|
| un seuil, une règle, la prédiction | [`pilotage.py`](../backend/app/dw/pilotage.py), puis relancer l'ETL |
| un indicateur, une formule | [`pbip/indicateurs.py`](pbip/indicateurs.py) (génère aussi `KPI.md` et `measures.dax`) |
| une table, un libellé, une relation | [`pbip/modele.py`](pbip/modele.py) |
| une page, un visuel, la barre latérale | [`pbip/rapport.py`](pbip/rapport.py), briques dans [`pbip/pbir.py`](pbip/pbir.py) |
| les couleurs et polices | [`theme/cadrage-ey.json`](theme/cadrage-ey.json) |

Ensuite : fermer Power BI, lancer `python bi/pbip/build_pbip.py`, rouvrir et **regarder chaque page**.

Pièges rencontrés :

- **Thème ignoré en silence** : une seule propriété inconnue (ici `tertiaryBackground`) fait rejeter tout le thème,
  et Power BI revient à ses couleurs bleues.
- **`Formula.Firewall`** : une requête ne peut pas référencer une autre requête et lire une source. Chaque table lit
  donc la vue elle-même, par la fonction `Vue`.
- **« A cyclic reference was encountered during evaluation »**, par intermittence à la première actualisation : le
  chargement parallèle est coupé dans `CadrageIA.SemanticModel/.pbi/editorSettings.json`, qui est versionné.

## Modèle de données

Étoile en français au-dessus des vues de [07 §4](../docs/07-entrepot-bi.md). Les colonnes techniques sont masquées.

| Table | Vue source | Filtrée par |
|---|---|---|
| Livrables | `v_deliverable` | client, type, consultant ; la période seulement dans les mesures de flux |
| Actions | `v_action` | via Livrables |
| Sections courantes | `v_section_current` | via Livrables |
| Sections approuvées | `v_outcome` | période (approbation), client, type, consultant |
| Générations | `v_generation` | période, client, type, consultant |
| Documents | `v_security` | client |
| Prévisions, Série de prévision | `v_forecast`, `v_forecast_point` | le périmètre choisi, lu par clé |
| Banc | `v_bench` | aucun filtre |
| Accès | `acces.csv` (hors entrepôt) | sert aux rôles RLS |

Chaque segment lit une table de choix avec une vraie valeur « Tous », reliée en plusieurs-à-plusieurs : le libellé
ne suit pas la langue de Power BI et la prévision sait quel périmètre lire. Le banc d'essai se charge à part :
`python -m app.dw.bench eval/results/<A>.json <B>.json …` (la démo n'en charge aucun ; un résultat simulé ne s'affiche pas).

## Charte

- Anthracite `#2E2E38`, gris `#747480` et `#C4C4CD`, fond `#F6F6FA`, Segoe UI.
- Jaune `#FFE600` pour ce qu'il faut regarder : page active, total, meilleure valeur.
- Texte gris en `#5F5F6B` (le `#747480` ne fait que 4,28:1 sur le fond).
- Rouge réservé aux alertes, toujours doublé d'un libellé, jamais opposé à un vert.
- Ni logo ni nom de cabinet : le produit s'appelle « Cadrage ».

## Sources de conception

Le tableau règle → source → application, avec ce qui n'a pas pu être vérifié, est dans
[docs/14 §6](../docs/14-acteurs-dashboard.md). Principales sources :

1. Microsoft Learn, [mise en page d'un rapport](https://learn.microsoft.com/en-us/training/modules/power-bi-effective-reports/2-design-layout).
2. Microsoft Learn, [accessibilité des rapports](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-accessibility-creating-reports).
3. Microsoft Learn, [rapport ou tableau de bord](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards).
4. Microsoft Learn, [sécurité par ligne](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security).
5. Microsoft Learn, [format PBIR](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report).
