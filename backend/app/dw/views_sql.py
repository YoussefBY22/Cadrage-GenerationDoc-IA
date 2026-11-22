"""Les 14 vues de Power BI (07 §4), en SQL portable SQLite / PostgreSQL.

Pas de fonction propre à un moteur : les percentiles et médianes se font en DAX ou dans `kpi.py`.
`{s}` est le préfixe de schéma (« dw. » sur PostgreSQL, vide sur SQLite).
"""

from sqlalchemy import Connection, Engine, text

VIEWS: dict[str, str] = {
    "v_generation": """
SELECT g.generation_key, g.run_id, g.date_key, d.date AS date, d.year, d.month, d.iso_week,
       c.client_name, m.mission_key, m.mission_name, g.model_key, mo.provider, mo.model_name,
       mo.config_label, t.type_code, s.section_code, s.title_fr AS section_title,
       g.status, g.sentences_total, g.sentences_verified, g.sentences_warning,
       g.sentences_failed, g.citations_total, g.citations_valid, g.numbers_cited,
       g.numbers_found, g.passages_retrieved, g.attempts, g.latency_ms, g.tokens_in,
       g.tokens_out, g.is_demo, g.user_key AS author_key,
       CASE WHEN g.sentences_total > 0
            THEN 1.0 * g.sentences_verified / g.sentences_total END AS tpv
FROM {s}fact_section_generation g
JOIN {s}dim_date d ON d.date_key = g.date_key
JOIN {s}dim_mission m ON m.mission_key = g.mission_key
JOIN {s}dim_client c ON c.client_key = m.client_key
JOIN {s}dim_model mo ON mo.model_key = g.model_key
JOIN {s}dim_section s ON s.section_key = g.section_key
JOIN {s}dim_deliverable_type t ON t.type_key = s.type_key
""",
    "v_quality_by_model": """
SELECT g.model_key, mo.provider, mo.model_name, mo.config_label, g.is_demo,
       COUNT(*) AS n_generations,
       SUM(CASE WHEN g.status = 'ok' THEN g.sentences_verified ELSE 0 END) AS sentences_verified,
       SUM(CASE WHEN g.status = 'ok' THEN g.sentences_total ELSE 0 END) AS sentences_total,
       1.0 * SUM(CASE WHEN g.status = 'ok' THEN g.sentences_verified ELSE 0 END)
           / NULLIF(SUM(CASE WHEN g.status = 'ok' THEN g.sentences_total ELSE 0 END), 0) AS tpv,
       1.0 * SUM(g.citations_valid) / NULLIF(SUM(g.citations_total), 0) AS citations_valid_rate,
       CASE WHEN SUM(g.numbers_cited) = 0 THEN 1.0
            ELSE 1.0 * SUM(g.numbers_found) / SUM(g.numbers_cited) END AS number_fidelity,
       1.0 * SUM(CASE WHEN g.status = 'refused' THEN 1 ELSE 0 END) / COUNT(*) AS refusal_rate,
       1.0 * SUM(CASE WHEN g.status = 'invalid' THEN 1 ELSE 0 END) / COUNT(*) AS invalid_rate,
       AVG(1.0 * g.latency_ms) AS avg_latency_ms
FROM {s}fact_section_generation g
JOIN {s}dim_model mo ON mo.model_key = g.model_key
GROUP BY g.model_key, mo.provider, mo.model_name, mo.config_label, g.is_demo
""",
    "v_review_funnel": """
SELECT r.deliverable_id, r.mission_key, r.type_key, r.is_demo,
       MIN(CASE WHEN st.state_code = 'in_review' THEN r.date_key END) AS submitted_date_key,
       MIN(CASE WHEN st.state_code = 'approved' THEN r.date_key END) AS approved_date_key,
       SUM(CASE WHEN st.state_code = 'rejected' THEN 1 ELSE 0 END) AS rejections,
       SUM(CASE WHEN st.state_code = 'in_review' THEN 1 ELSE 0 END) AS submissions,
       MAX(CASE WHEN st.state_code = 'approved' THEN r.hours_since_submission END) AS delay_hours
FROM {s}fact_review r
JOIN {s}dim_state st ON st.state_key = r.to_state_key
GROUP BY r.deliverable_id, r.mission_key, r.type_key, r.is_demo
""",
    "v_outcome": """
SELECT o.outcome_key, o.deliverable_id, o.approved_version, o.date_key, o.mission_key,
       s.section_code, s.title_fr AS section_title, mo.config_label, o.generated_words,
       o.final_words, o.edit_ratio, o.unchanged, o.was_refused, o.minutes_saved_est, o.is_demo,
       s.baseline_minutes, fd.author_key, s.type_key
FROM {s}fact_section_outcome o
LEFT JOIN {s}fact_deliverable fd ON fd.deliverable_id = o.deliverable_id
JOIN {s}dim_section s ON s.section_key = o.section_key
JOIN {s}dim_model mo ON mo.model_key = o.model_key
""",
    "v_citations": """
SELECT cc.citation_key, cc.generation_key, i.issue_code, i.severity, cc.document_key,
       dd.mime AS document_mime, cc.sentence_index, cc.is_valid, cc.support, cc.is_demo
FROM {s}fact_citation_check cc
JOIN {s}dim_issue i ON i.issue_key = cc.issue_key
LEFT JOIN {s}dim_document dd ON dd.document_key = cc.document_key
""",
    "v_security": """
SELECT m.mission_key, m.mission_name, dd.document_key, dd.document_id, dd.mime,
       dd.injection_alert_count, dd.is_demo
FROM {s}dim_document dd
JOIN {s}dim_mission m ON m.mission_key = dd.mission_key
""",
    "v_llm_calls": """
SELECT l.call_key, l.date_key, l.model_key, mo.config_label, l.mission_key, l.call_kind,
       l.latency_ms, l.tokens_in, l.tokens_out, l.success, l.is_demo,
       l.tokens_out * 1000.0 / NULLIF(l.latency_ms, 0) AS tokens_per_second
FROM {s}fact_llm_call l
JOIN {s}dim_model mo ON mo.model_key = l.model_key
""",
    "v_person": """
SELECT u.user_key, u.user_id, u.role, u.user_label, u.is_demo
FROM {s}dim_user u
""",
    "v_deliverable": """
SELECT fd.deliverable_id, fd.mission_key, m.mission_name, fd.client_key, c.client_name,
       fd.type_key, fd.author_key, fd.reviewer_key, fd.state, fd.created_date_key,
       fd.submitted_date_key, fd.approved_date_key, fd.as_of, fd.state_age_hours, fd.idle_hours,
       fd.version, fd.submissions, fd.rejections, fd.returned, fd.reason_code, fd.sections,
       fd.refused_sections, fd.sentences, fd.unchecked_sentences, fd.blocking_open,
       fd.citations_total, fd.citations_invalid, fd.delay_hours, fd.first_blocking,
       fd.first_rejected, fd.risk, fd.risk_low, fd.risk_high, fd.risk_n, fd.is_demo
FROM {s}fact_deliverable fd
JOIN {s}dim_mission m ON m.mission_key = fd.mission_key
JOIN {s}dim_client c ON c.client_key = fd.client_key
""",
    "v_section_current": """
SELECT sc.deliverable_id, sc.section_key, s.section_code, s.title_fr AS section_title,
       sc.sentences, sc.blocking, sc.citations_invalid, sc.refused, sc.priority, sc.is_demo
FROM {s}fact_section_current sc
JOIN {s}dim_section s ON s.section_key = sc.section_key
""",
    "v_action": """
SELECT a.deliverable_id, a.rule_code, a.is_demo
FROM {s}fact_action a
""",
    "v_forecast": """
SELECT f.forecast_key, f.client_key, c.client_name, f.type_key, f.author_key, f.reviewer_key,
       f.as_of, f.queue,
       f.status, f.weeks, f.events, f.origins, f.point, f.low, f.high, f.mae, f.mae_naive,
       f.risk_status, f.risk_brier, f.risk_brier_naive, f.risk_tested, f.is_demo
FROM {s}fact_forecast f
LEFT JOIN {s}dim_client c ON c.client_key = f.client_key
""",
    "v_forecast_point": """
SELECT fp.forecast_key, fp.period_end, fp.actual, fp.point, fp.low, fp.high, fp.is_demo
FROM {s}fact_forecast_point fp
""",
    "v_bench": """
SELECT b.config_label, b.model_name, b.adapter, b.has_retrieval, b.n_sections, b.tpv, b.tpv_low,
       b.tpv_high, b.delta, b.delta_low, b.delta_high, b.decision, b.degraded, b.citation_validity,
       b.number_fidelity, b.attack_success, b.latency_p95_ms, b.simulated, b.is_demo
FROM {s}fact_bench b
""",
}


def _prefix(engine: Engine) -> str:
    return "dw." if engine.dialect.name == "postgresql" else ""


def drop_views(bind: Engine | Connection) -> None:
    _run(bind, [f"DROP VIEW IF EXISTS {{s}}{name}" for name in reversed(VIEWS)])


def create_views(bind: Engine | Connection) -> None:
    """(Re)crée les vues ; idempotent."""
    statements = []
    for name, body in VIEWS.items():
        statements.append(f"DROP VIEW IF EXISTS {{s}}{name}")
        statements.append(f"CREATE VIEW {{s}}{name} AS {body.strip()}")
    _run(bind, statements)


def _run(bind: Engine | Connection, statements: list[str]) -> None:
    engine = bind if isinstance(bind, Engine) else bind.engine
    prefix = _prefix(engine)
    sql = [s.replace("{s}", prefix) for s in statements]
    if isinstance(bind, Engine):
        with bind.begin() as conn:
            for s in sql:
                conn.execute(text(s))
    else:
        for s in sql:
            bind.execute(text(s))
