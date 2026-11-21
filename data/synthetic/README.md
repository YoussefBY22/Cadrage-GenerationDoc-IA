# Corpus synthétique

Corpus **entièrement fictif**, généré par `backend/eval/corpus/generate.py` (aucun LLM, aucun réseau).
Les sorties ne sont pas versionnées : on les régénère, toujours identiques pour une même graine.

```powershell
cd backend
python -m eval.corpus.generate --seed 7 --out eval/corpus/out
```

Contenu : 3 institutions fictives (Valmont, Arvel, Lorvanie) ; pour chacune un diagnostic (TXT, DOCX, PDF,
même contenu, 10 pages), une note de priorités (DOCX) et un compte rendu d'atelier (PPTX) ; 5 documents
piégés (`traps/`, canari `ZX-CANARI-7`) ; `gold.json` (faits, constats, dépendances, requêtes, pièges,
sujets sans preuve). Chaque fait a une phrase-marqueur unique, retrouvée par texte et non par identifiant.
