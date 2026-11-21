# Comptes rendus de lots

Un fichier `docs/lots/<ID>.md` par lot (≤ 60 lignes), selon `docs/09-plan-execution.md` §1.6.
Ne pas modifier `docs/STATUS.md` ni le glossaire : l'orchestrateur les fusionne.

## Gabarit

```markdown
# Lot <ID> — <titre>

## Fait
- …

## Testé
- `cd backend && ruff check . && pytest -q` → sortie réelle collée ici

## Limites
- …

## Écarts aux contrats de 06
- Aucun / …

## Demandes
- Fichier ou dépendance hors périmètre dont le lot a besoin (et contournement utilisé)

## Pour comprendre
5–8 lignes, avec une analogie.

## 3 questions
1. …
2. …
3. …

## Notions pour le glossaire
- terme : définition courte
```
