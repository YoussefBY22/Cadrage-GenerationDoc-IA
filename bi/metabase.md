# Alternative libre : Metabase (07 §10)

Aucun tableau n'est construit cette nuit : connexion et cinq questions SQL à coller (« Nouvelle → Question SQL »).
Image **non téléchargée** (T6) ; licence **AGPL** (usage interne, image non modifiée) : **à vérifier**
(`docs/LICENCES-LOGICIELS.md`).

## Lancement (demain)
```powershell
docker compose -f docker-compose.yml -f deploy/docker-compose.bi.yml --profile bi up metabase
```
Puis http://127.0.0.1:3000 → créer le compte administrateur local.

## Connexion à la base
PostgreSQL · hôte `db` · port `5432` · base = `POSTGRES_DB` · utilisateur `bi_reader` (`db/dw/roles.sql`) ·
schéma `dw` uniquement (désactiver la synchronisation des autres schémas). **[À VÉRIFIER]**

## Cinq questions (SQL portable)
```sql
-- 1. TPV par configuration
SELECT config_label, n_generations, tpv, citations_valid_rate, refusal_rate
FROM dw.v_quality_by_model ORDER BY tpv DESC;

-- 2. Anomalies de citation par code
SELECT issue_code, COUNT(*) AS n FROM dw.v_citations GROUP BY issue_code ORDER BY n DESC;

-- 3. Acceptation sans modification et temps gagné
SELECT 1.0 * SUM(CASE WHEN unchanged THEN 1 ELSE 0 END) / COUNT(*) AS acceptation_sans_modif,
       SUM(minutes_saved_est) / 60.0 AS heures_gagnees
FROM dw.v_outcome;

-- 4. Délai de relecture et refus par livrable
SELECT deliverable_id, submissions, rejections, delay_hours FROM dw.v_review_funnel ORDER BY delay_hours DESC;

-- 5. Alertes d'injection par mission
SELECT mission_name, SUM(injection_alert_count) AS alertes FROM dw.v_security
GROUP BY mission_name ORDER BY alertes DESC;
```
Sur SQLite (essai local sans PostgreSQL), retirer le préfixe `dw.`. Les percentiles (p95) ne sont pas dans les vues :
utiliser `app/dw/kpi.py` ou DAX.
