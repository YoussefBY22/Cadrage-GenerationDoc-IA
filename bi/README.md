# Tableau de bord Power BI Desktop — pas à pas

> **Valeurs inventées.** Les chiffres du jeu de démonstration (`python -m app.dw.demo`) sont **fictifs** :
> ils servent à vérifier la chaîne et la maquette, pas à juger des modèles.
> Rien n'a été testé dans Power BI cette nuit (T6, demain) : les points **[À VÉRIFIER]** sont à confirmer à l'écran.

## 0. Principe de confidentialité (C1)

- Power BI **Desktop** tourne en local. **Ne pas publier** sur Power BI Service (cloud Microsoft) : contraire à C1.
  Power BI Report Server (sur site) : licence **[À VÉRIFIER]**.
- L'entrepôt `dw` ne contient ni phrases ni passages clients (07 §1) ; le rôle `bi_reader` n'a accès qu'à `dw`.

## 1. Produire les données

```powershell
cd backend
python -m app.dw.demo --seed 42                               # jeu de démonstration (is_demo) + ETL + vues
python -m app.dw.export_csv --out ../bi/export/               # option A : 7 CSV (« ; » et virgule décimale)
python -m app.dw.export_csv --out ../bi/export/ --locale en   # variante « , » et point décimal
```
Avec de vraies données : `python -m app.dw.etl`, puis l'export (ou la connexion PostgreSQL ci-dessous).

## 2. Connexion

**Option A — CSV (sans base, testable partout).** Accueil → Obtenir des données → *Texte/CSV* → choisir les 7 fichiers
de `bi/export/` (`v_generation`, `v_quality_by_model`, `v_review_funnel`, `v_outcome`, `v_citations`, `v_security`,
`v_llm_calls`). Origine du fichier : **UTF-8** ; délimiteur : point-virgule ; paramètres régionaux **français** pour la
virgule décimale (ou régénérer avec `--locale en`). Si des colonnes numériques arrivent en texte, passer par
*Transformer les données*. **[À VÉRIFIER]**

**Option B — PostgreSQL (lecture seule).**
1. Créer le rôle : `psql -f db/dw/roles.sql` (changer le mot de passe) ; `alembic upgrade head`, puis l'ETL.
2. Power BI → Obtenir des données → *Base de données PostgreSQL* → serveur `localhost:5432`, base = `POSTGRES_DB`,
   mode **Importer**, identifiants `bi_reader`. Le pilote **Npgsql** peut être demandé selon la version de Power BI
   Desktop **[À VÉRIFIER]**. Choisir les 7 vues du schéma `dw` (`dw.v_generation`, …).
3. `docker-compose.yml` ne publie pas le port 5432 : l'exposer en local seulement (`127.0.0.1:5432:5432`) le temps de
   la séance, puis le retirer **[À VÉRIFIER]**.

## 3. Modèle de relations

Les vues sont déjà « aplaties » ; il faut trois tables de liaison. Dans *Transformer les données* :

| Nouvelle table | Création | Utilité |
|---|---|---|
| `Missions` | dupliquer `v_generation`, garder `mission_key`, `mission_name`, `client_name`, supprimer les doublons | filtre client / mission commun |
| `Modèles` | dupliquer `v_generation`, garder `model_key`, `provider`, `model_name`, `config_label`, supprimer les doublons | filtre configuration A/B/C/D |
| `Dates` | DAX : `Dates = ADDCOLUMNS(CALENDAR(DATE(2026,1,1), DATE(2026,12,31)), "date_key", YEAR([Date])*10000+MONTH([Date])*100+DAY([Date]), "Semaine", WEEKNUM([Date],21))` | axe de temps commun |

Relations (plusieurs-à-un, filtre de la table de liaison vers les vues) :

| De (plusieurs) | Vers (un) |
|---|---|
| `v_generation`, `v_outcome`, `v_review_funnel`, `v_security`, `v_llm_calls` — colonne `mission_key` | `Missions[mission_key]` |
| `v_generation`, `v_llm_calls`, `v_quality_by_model` — colonne `model_key` | `Modèles[model_key]` |
| `v_generation`, `v_outcome`, `v_llm_calls` — colonne `date_key` | `Dates[date_key]` |
| `v_citations[generation_key]` | `v_generation[generation_key]` |

`v_review_funnel[submitted_date_key]` : relation **inactive** vers `Dates` (activer par `USERELATIONSHIP` au besoin).

## 4. Mesures

Coller chaque bloc de [`measures.dax`](measures.dax) (Accueil → Nouvelle mesure) dans une table `_Mesures` : TPV,
Citations valides, Fidélité chiffres, Taux refus, Acceptation sans modif, Temps gagné (h), Latence p95 (s), Δ TPV vs B.
Formules de référence : `docs/07-entrepot-bi.md` §5. `app/dw/kpi.py` donne les mêmes chiffres à 1e-9 près (test
`tests/dw/test_views.py`) : comparer une carte Power BI à `kpi.py` est le test d'acceptation de demain.

## 5. Les 5 pages

Détail visuel par visuel dans [`pages.md`](pages.md) : 1 Vue d'ensemble · 2 Qualité et vérification ·
3 Comparaison des modèles A/B/C/D · 4 Relecture · 5 Usage et sécurité.
Sur **chaque page** : un segment **« Données de démonstration »** (`is_demo`) visible en haut ; en démo, un bandeau
« Valeurs inventées — démonstration ».

## 6. Charte
Couleurs neutres (gris) + une couleur d'accent ; libellés en français ; aucune donnée client dans les info-bulles.

## 7. Points à vérifier demain (T6)
- [ ] Pilote PostgreSQL / Npgsql, port local, rôle `bi_reader` (aucune table `public` visible).
- [ ] Séparateurs et décimales à l'import CSV (FR et EN).
- [ ] `PERCENTILEX.INC` sur `v_llm_calls[latency_ms]` ; `Latence p95` ≈ `kpi.latency_percentile`.
- [ ] Relations ci-dessus, relation inactive de `v_review_funnel`, mise en forme conditionnelle de la page 2.
- [ ] Les cartes TPV / Acceptation / Temps gagné égalent `kpi.py` (démo, graine 42).
- [ ] Aucune publication sur Power BI Service.
