# Maquette des 5 pages (07 §7)

Charte EY : jaune `#FFE600` (accent), anthracite `#2E2E38`, gris `#747480` `#C4C4CD` `#F6F6FA`, Segoe UI, sans logo ; libellés en français ; en haut de chaque page un
segment **Données de démonstration** (`is_demo`) et, en démo, le texte « Valeurs inventées — démonstration ».

## 1. Vue d'ensemble
| Visuel | Champs |
|---|---|
| Cartes (4) | `TPV` · `Acceptation sans modif` · `Temps gagné (h)` · livrables approuvés = `DISTINCTCOUNT(v_outcome[deliverable_id])` |
| Courbe | axe `Dates[Semaine]`, valeur `TPV` |
| Segments | `Missions[client_name]`, `v_generation[type_code]` |

## 2. Qualité et vérification
| Visuel | Champs |
|---|---|
| Barres empilées | axe `v_citations[issue_code]`, valeur nombre de lignes, légende `severity` |
| Matrice | lignes `v_generation[section_title]`, valeur `TPV`, **mise en forme conditionnelle** (rouge < 0,6 · neutre · accent ≥ 0,8) |
| Histogramme | axe `v_generation[type_code]`, valeur `Fidélité chiffres` |

## 3. Comparaison des modèles (A/B/C/D)
| Visuel | Champs |
|---|---|
| Histogramme groupé | axe `Modèles[config_label]`, valeurs `TPV`, `Citations valides`, `Taux refus` |
| Nuage de points | X `Latence p95 (s)`, Y `TPV`, taille = nombre de générations, détail `config_label` |
| Table | `config_label`, `TPV`, `Δ TPV vs B`, `Latence p95 (s)` |

## 4. Relecture
| Visuel | Champs |
|---|---|
| Entonnoir | brouillon → en relecture → approuvé, à partir de `v_review_funnel` (soumis : `submissions > 0` ; approuvés : `approved_date_key` renseignée) |
| Carte | délai médian = `MEDIAN(v_review_funnel[delay_hours])` |
| Carte | taux de refus en relecture = `DIVIDE(SUM(v_review_funnel[rejections]), SUM(v_review_funnel[submissions]))` |
| Barres | 10 sections les plus réécrites : `AVERAGE(v_outcome[edit_ratio])` par `section_title` |

## 5. Usage et sécurité
| Visuel | Champs |
|---|---|
| Colonnes | axe `v_generation[month]`, légende mission, valeur nombre de générations |
| Barres | `v_security[mission_name]`, valeur `SUM(injection_alert_count)` |
| Anneau | `v_security[mime]`, nombre de documents |

> Le délai médian et le taux de refus en relecture sont des mesures **à créer sur place** (formules ci-dessus) ; elles ne
> figurent pas dans `measures.dax`, qui reprend uniquement 07 §6. **[À VÉRIFIER]**
