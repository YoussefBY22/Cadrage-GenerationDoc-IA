"""Étiquettes de référentiel d'une initiative : domaine COBIT 2019 ou pratique ITIL 4.

L'étiquette est une aide de lecture proposée par le modèle quand un passage la justifie ; elle ne
remplace jamais une source du client et n'entre pas dans le calcul de priorité. Toute valeur hors
liste est écartée (None) plutôt que conservée : on ne publie pas une étiquette inventée.
"""

from __future__ import annotations

import re

# 40 objectifs COBIT 2019 : 5 EDM, 14 APO, 11 BAI, 6 DSS, 4 MEA.
_COBIT_RANGES = {"EDM": 5, "APO": 14, "BAI": 11, "DSS": 6, "MEA": 4}
COBIT_OBJECTIVES = frozenset(f"{d}{n:02d}" for d, k in _COBIT_RANGES.items() for n in range(1, k + 1))

# 34 pratiques ITIL 4 (14 générales, 17 de gestion des services, 3 techniques).
ITIL_PRACTICES = (
    "Architecture management", "Continual improvement", "Information security management",
    "Knowledge management", "Measurement and reporting", "Organizational change management",
    "Portfolio management", "Project management", "Relationship management", "Risk management",
    "Service financial management", "Strategy management", "Supplier management",
    "Workforce and talent management",
    "Availability management", "Business analysis", "Capacity and performance management",
    "Change enablement", "Incident management", "IT asset management",
    "Monitoring and event management", "Problem management", "Release management",
    "Service catalogue management", "Service configuration management",
    "Service continuity management", "Service design", "Service desk", "Service level management",
    "Service request management", "Service validation and testing",
    "Deployment management", "Infrastructure and platform management",
    "Software development and management",
)
_ITIL_BY_KEY = {p.lower(): p for p in ITIL_PRACTICES}
_COBIT_RE = re.compile(r"\b(EDM|APO|BAI|DSS|MEA)\s*-?\s*(\d{1,2})\b", re.IGNORECASE)


def normalize_domain(label: str | None) -> str | None:
    """« APO12 » ou « COBIT apo-12 » → « COBIT APO12 » ; « ITIL incident management » → « ITIL Incident
    management » ; toute autre valeur → None."""
    if not label or not label.strip():
        return None
    m = _COBIT_RE.search(label)
    if m:
        code = f"{m.group(1).upper()}{int(m.group(2)):02d}"
        return f"COBIT {code}" if code in COBIT_OBJECTIVES else None
    key = re.sub(r"^\s*itil(\s*4)?\s*[:\-]?\s*", "", label.strip(), flags=re.IGNORECASE).lower()
    practice = _ITIL_BY_KEY.get(re.sub(r"\s+", " ", key))
    return f"ITIL {practice}" if practice else None
