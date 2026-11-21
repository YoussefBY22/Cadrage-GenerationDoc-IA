-- Rôle de lecture seule pour Power BI / Metabase : accès au seul schéma dw (07 §8).
-- À exécuter par un administrateur PostgreSQL ; remplacer le mot de passe avant usage.
-- Testé au lot T1 (pas de PostgreSQL disponible lors du développement).

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bi_reader') THEN
        CREATE ROLE bi_reader LOGIN PASSWORD 'CHANGER_MOI';
    END IF;
END
$$;

-- Aucun accès au schéma public (données opérationnelles, textes clients).
REVOKE ALL ON SCHEMA public FROM bi_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM bi_reader;

GRANT USAGE ON SCHEMA dw TO bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA dw TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA dw GRANT SELECT ON TABLES TO bi_reader;

-- Lecture seule : aucune écriture, y compris sur les tables techniques.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA dw FROM bi_reader;
ALTER ROLE bi_reader SET default_transaction_read_only = on;
