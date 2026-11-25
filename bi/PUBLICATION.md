# Publication : préparée, rien n'est publié

> Règles vérifiées sur Microsoft Learn le 22/11/2026 (liens en ligne). Ce qui n'a pas pu l'être est marqué
> **non vérifié**. Aucune étape de cette page n'a été exécutée dans Power BI Service.

## 1. Où a-t-on le droit de publier

L'hypothèse H1 et la contrainte C1 imposent un traitement **100 % sur site**. Power BI Service est hébergé par
Microsoft : y publier des données de mission **contredit H1**, même en accès restreint. Le modèle contient des noms
de clients, de missions et de personnes, même sans aucun texte de livrable.

| Cas | Support | Permis |
|---|---|---|
| Démonstration, données inventées | Power BI Service | oui, après accord du propriétaire du projet |
| Mission réelle | Power BI Desktop sur site, ou Power BI Report Server | oui |
| Mission réelle | Power BI Service | **non**, sauf révision écrite de H1 par le client |
| Toute donnée | « Publier sur le web » | **non**, voir §2 |

[Report Server](https://learn.microsoft.com/en-us/power-bi/report-server/get-started) demande une version de Desktop
optimisée pour lui et une licence pour publier. Sa prise en charge du format PBIP et de ce niveau de PBIR est
**non vérifiée**.

## 2. « Publier sur le web » est interdit

[Cette fonction](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-publish-to-web) rend le rapport
lisible par tout Internet, sans authentification, **y compris le détail que le rapport n'affiche pas**. Elle ne
prend pas en charge la RLS, donc pas ce modèle. Elle ne serait envisageable que pour une copie sans rôle, sur données
inventées, sur décision explicite du propriétaire du projet.

## 3. Compte et licence

- [Inscription](https://learn.microsoft.com/en-us/power-bi/fundamentals/service-self-service-signup-for-power-bi) :
  adresse professionnelle ou scolaire. Gmail et Hotmail ne sont pas acceptés directement. Un essai Microsoft 365
  donne un compte en `onmicrosoft.com`.
- [Licences](https://learn.microsoft.com/en-us/power-bi/fundamentals/service-features-license-type) : la licence
  gratuite ne permet ni de partager ni de publier dans l'espace d'autrui. Il faut **Pro** (ou PPU, qui ne partage
  qu'entre PPU), sauf capacité Premium ou Fabric F64 et plus pour les lecteurs gratuits.
- Droits et licence du compte de l'utilisateur : **non vérifiés**.

## 4. Rôles et sécurité par ligne

Les rôles sont dans le modèle (`CadrageIA.SemanticModel/definition/roles/`, générés par `pbip/modele.py`).

| Rôle | Voit |
|---|---|
| `Consultant` | les projets où il a rédigé un livrable ou lancé une génération, et tout ce qui s'y rattache |
| `Responsable` | les projets où il relit au moins un livrable |
| `Administration` | tout |

Restent communs à tous les rôles, car sans donnée de client : le registre des entraînements, les gabarits de
sections et les types d'erreur.

1. Copier [`acces.exemple.csv`](acces.exemple.csv) en `bi/export/acces.csv` (jamais versionné) : une ligne par
   personne, `utilisateur` = son UPN (`prenom.nom@cabinet.fr`), `user_id` = la colonne de `v_person`.
   **Sans ce fichier, Consultant et Responsable ne voient rien** (refus par défaut). Il n'est lu qu'en source CSV.
2. Dans le Service : modèle sémantique → Sécurité → affecter chaque personne à **un seul** rôle. Les rôles
   [s'additionnent](https://learn.microsoft.com/en-us/power-bi/guidance/rls-guidance), et une personne sans rôle
   ne voit aucune ligne.
3. Donner aux lecteurs le rôle **Lecteur** de l'espace de travail. La RLS
   [ne filtre ni les administrateurs, ni les membres, ni les contributeurs](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security).
4. La RLS ne cache pas les pages.
5. `USERPRINCIPALNAME()` renvoie l'UPN dans le Service. En Desktop, hors domaine, la valeur observée est
   `MACHINE\utilisateur` : c'est elle qu'il faut mettre dans le fichier pour tester en local.

Testé en local sur la démo (connexion au modèle avec chaque rôle) : 46 livrables et 36 missions pour un consultant,
80 et 61 pour un responsable, 177 pour l'administration, soit les comptes de la base. **Non testé dans le Service.**

## 5. Données et actualisation

- `DossierCsv` est un paramètre : `python bi/pbip/build_pbip.py --csv "<dossier>"`, ou *Transformer les données →
  Modifier les paramètres*. Dans le Service, un paramètre
  [se modifie mais ne se crée pas](https://learn.microsoft.com/en-us/power-bi/connect-data/service-parameters).
- Une source hors de portée réseau directe du Service
  [demande une passerelle](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-data). Le cas précis d'un
  CSV sur un poste n'est pas décrit sur la page lue (**non vérifié**).
- Fréquence : 8 actualisations planifiées par jour en capacité partagée, 48 en Premium, PPU ou Fabric.
- Avant chaque actualisation : `python -m app.dw.etl`, puis `python -m app.dw.export_csv --out ../bi/export/`.

## 6. Export du rapport

| Moyen | Page Rapport (masquée) | Usage |
|---|---|---|
| Desktop, Exporter en PDF | **exclue** ([pages masquées non exportées](https://learn.microsoft.com/en-us/power-bi/collaborate-share/end-user-pdf)) | les quatre pages de travail |
| Service, Exporter en PDF | case pour les pages masquées, case « page active seulement » | **non testé** |
| `python -m app.dw.report --out rapport.pdf` | sans objet : mêmes règles, fichier complet | **voie recommandée**, fonctionne hors ligne |

```powershell
cd backend
python -m app.dw.report --out ../rapport.pdf
python -m app.dw.report --client "Nom du client" --out ../revue-client.pdf
python -m app.dw.report --consultant "Nom affiché" --since 2026-10-01 --until 2026-11-20 --out ../revue.docx
```

Le filtre `--client` sert aux revues internes : **aucun de ces fichiers ne se transmet au client**.
Le PDF passe par LibreOffice. Sans lui, choisir une sortie `.docx`.

## 7. Le vrai tableau de bord, dans le Service

Un [tableau de bord](https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards) est une page de
tuiles épinglées, sans segment. Il n'existe pas dans Desktop. Six tuiles à épingler, filtres sur « Tous » :

| Tuile | Page | Alerte proposée |
|---|---|---|
| Taux d'erreur de l'IA | Synthèse | au-dessus de la dernière valeur examinée |
| Livrables | Synthèse | sans alerte |
| Appels au modèle par mois | Synthèse | sans alerte (graphique) |
| Rapports en alerte | Projet | supérieur à 0 |
| Sorties invalides | Qualité de l'IA | supérieur à 0 |
| Modèle adopté | Entraînement | sans alerte (texte) |

Les [alertes](https://learn.microsoft.com/en-us/power-bi/create-reports/service-set-data-alerts) n'existent que sur
cartes, KPI et jauges **numériques**, et demandent Pro hors de « Mon espace de travail ». Les cartes du rapport
portent pour cela des mesures numériques.

## 8. Avant de publier, même la démonstration

- [ ] accord écrit du propriétaire du projet ;
- [ ] mention « [DÉMO] » visible sur chaque visuel qui inclut un projet de démonstration ;
- [ ] aucun `acces.csv` réel ni cache `.pbi/cache.abf` dans ce qui part ;
- [ ] chaque rôle testé avec « Tester en tant que rôle », puis avec un vrai compte Lecteur ;
- [ ] « Publier sur le web » désactivé par l'administrateur du locataire.
