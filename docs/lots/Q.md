# Lot Q — qualité réelle (Ollama) et export PDF

## 1. Refus excessifs : trois itérations de prompt, aucune retenue
Évaluation B réduite réelle (qwen3:4b + bge-m3, `eval/configs/B-gpu.yaml`, 1 institution, 31 sections dont
10 « preuve » et 10 « sans preuve », 1 passe). **Une section = 10 points** sur les taux de refus manqués/faux :
les écarts de ±1 section sont dans le bruit.

| Version | Refus global | Faux refus | Refus manqués | Latence p50 | TPV répondu |
|---|---|---|---|---|---|
| Avant (T2, prompt d'origine, 10 passages) | 65 % | 10 % | 10 % | 18,2 s | 1,000 |
| It. 1 : consigne et règle **après** les passages, étiquettes valides listées, 2 exemples, 10 passages ; refus « seulement si aucun passage ne traite le sujet » | 16 % | 0 % | **50 %** | 20,8 s | 1,000 |
| It. 2 : idem, 8 passages, refus si aucun « fait précis qui répond à la consigne » | 32 % | 0 % | **30 %** | 18,0 s | 0,990 |
| It. 3 : idem, « test de décision » (peut-on recopier une phrase qui répond directement ?) | 26 % | 0 % | **30 %** | 18,2 s | 0,976 |

**Décision : prompts d'origine conservés.** Critère posé : réduire les faux refus sans augmenter les refus
manqués. Les trois itérations suppriment les faux refus (1 section → 0) mais font passer les refus manqués de 1
à 3-5 sections sur 10 : le modèle 4 B répond dès qu'un passage voisin existe. Le gain de latence attendu (8
passages) est faible (≈ 0) car la latence est dominée par la génération, pas par la lecture du prompt.
Pistes non tentées (hors des 3 itérations) : seuil de score de recherche avant l'appel (refuser sans appel
si le meilleur passage est peu pertinent), ou second appel « ce passage répond-il à la consigne ? » ; mesurer sur
la B complète (3 institutions) pour sortir du bruit.

## 2. Export PDF
- `soffice_binary()` : PATH, sinon chemin configuré, sinon `C:\Program Files\LibreOffice\program\soffice.exe`.
- La conversion utilise un profil LibreOffice dans le dossier temporaire (`-env:UserInstallation=file:///…`) et
  `cwd` = dossier temporaire, ce qui évite le blocage de l'accès contrôlé aux dossiers de Windows Defender.
- `pytest -q -m soffice` : 1 test vert avec LibreOffice installé (le test détectait soffice par `shutil.which`
  et se sautait à tort ; il utilise maintenant `soffice_binary()`).
