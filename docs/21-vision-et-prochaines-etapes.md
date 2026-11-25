# 21 — Vision cible et prochaines étapes (clôture de la phase du 25/11/2026)

> Lecteur : toi, un encadrant, un futur développeur. Ce document décrit **où va le produit**, **ce qui manque
> aujourd'hui** et **dans quel ordre le construire**. Rien de ce qui est décrit ici n'est encore codé, sauf mention
> « existe déjà ». État réel et mesures : [`STATUS.md`](STATUS.md), [`19`](19-entrainement-et-tests-reels.md),
> [`20`](20-comprendre-l-apprentissage.md).

## 1. La version cible, du point de vue du consultant

1. **Il dépose tout le dossier du client** : stratégie, rapports d'audit et de diagnostic, documents partagés, KPI,
   en lot (par exemple un zip de 60 fichiers). *Existe déjà en partie : dépôt multiple, rôles de documents
   (diagnostic, stratégie, portefeuille de projets, gabarit), fiche de contexte, chat.*
2. **Contrôle du diagnostic (optionnel)** : avant de s'en servir, l'outil vérifie que le diagnostic est cohérent
   avec les autres documents (chiffres qui se contredisent, documents cités mais absents, recommandations sans
   constat). Le consultant choisit : **faire confiance** au diagnostic tel quel, ou **utiliser l'analyse** pour
   l'annoter. *À construire.*
3. **Feuille de route** : rangée **par axes** (existe déjà), **datée par mois et par sprints** à partir d'une date de
   départ et de durées (aujourd'hui : vagues et horizons indicatifs), avec pour chaque initiative **pourquoi elle
   existe** : constats, recommandations, priorités et passages cités (existe déjà, à rendre plus visible).
4. **Cahier des charges ou TdR pour chaque initiative**, avec :
   - **structure modifiable** : le consultant **importe un sommaire** (le sien ou celui du client) et l'outil rédige
     section par section selon ce sommaire ; *à construire (les gabarits existent, en YAML)* ;
   - **consignes par section** : « améliore la section X », « il manque X, Y, Z », « utilise davantage le
     document Y » ; *à construire (aujourd'hui : générer, proposer quand même, corriger à la main)*.
5. **Chaque action est enregistrée** (section 2) et sert à **améliorer le modèle** (sections 3 et 4).

## 2. Capter les corrections : un historique utile aux humains et à la machine

### Ce qu'on enregistre (un « événement » par action)

| Événement | Exemple | Ce que la machine en tire |
|---|---|---|
| Phrase corrigée à la main | le consultant réécrit une phrase | paire (avant, après) : préférence |
| Référence fausse ou manquante | le vérificateur ou le consultant signale une citation qui ne soutient pas la phrase | exemple négatif ; bon passage si le consultant l'indique |
| Section refusée puis forcée | « proposer quand même » | la consigne et la proposition gardée ou rejetée |
| Consigne de chat | « divise la feuille de route par gouvernance, sécurité, données » | consigne → résultat accepté |
| Consigne de section | « améliore la section X, il manque Y » | consigne + version avant / après |
| Constat validé, rejeté ou corrigé | le consultant décoche un constat | étiquette juste / faux |
| Initiative déplacée, fusionnée, renommée | changement d'axe, de vague | préférence de structure |
| Approbation / renvoi par le responsable | livrable approuvé ou renvoyé avec motif | qualité globale |

*Existe déjà : versions de chaque livrable, différences entre versions, journal d'audit, acquittements motivés,
commentaires, journal des appels au modèle (sans le texte des invites). Il manque : un format d'événement unique,
le lien avec les passages et le modèle utilisé, l'export.*

### Le format : deux lectures d'une même donnée

- **Pour l'humain** : une **frise par dossier et par consultant**, datée (« 25/11 14:32 — Youssef a demandé
  d'améliorer la section Objectifs : il manque les échéances »). Un clic ouvre le détail.
- **Pour la machine** : le détail est un enregistrement **JSON** stocké en base ; l'export produit du **JSONL**
  (une ligne JSON par exemple), le format que lisent les scripts d'entraînement.

Exemple d'événement (le détail derrière une ligne de la frise) :

```json
{
  "id": "evt_01J…", "date": "2026-11-25T14:32:10Z", "consultant": "usr_…", "dossier": "dos_…",
  "type": "section_instruction", "livrable": "dlv_…", "section": "objectifs",
  "consigne": "Améliore cette section : il manque les échéances de chaque objectif.",
  "avant": {"phrases": ["…"], "sources": ["chk_…"]},
  "apres": {"phrases": ["…"], "sources": ["chk_…", "chk_…"]},
  "modele": {"nom": "cadrage-4b-lora", "empreinte": "69530ffa…", "invite_sha256": "…"},
  "verification": {"tpv_avant": 0.5, "tpv_apres": 1.0},
  "statut": "accepte", "revue": {"etat": "a_verifier", "par": null}
}
```

Deux exports, depuis ces événements :
- **SFT** (exemples « consigne → bonne réponse ») : seulement les versions **acceptées** ;
- **préférences** (« pour cette consigne, la réponse B est meilleure que A ») : paires avant / après, pour une
  méthode comme DPO.

Règles : jamais de données d'un client à l'entraînement **sans accord écrit** ; anonymisation des noms et chiffres
sensibles à l'export ; chaque exemple garde sa provenance (dossier, date, modèle).

## 3. Comptes, espace d'administration et nettoyage des données

- **Un espace par consultant** : ses dossiers, son historique, ses corrections. *Existe déjà en partie : comptes,
  rôles (consultant, responsable, administrateur), membres d'un dossier.*
- **L'administrateur** voit l'historique de tous : travaux, corrections, entraînements lancés.
- **Nettoyage assisté par l'IA**, avant tout entraînement :
  - doublons et quasi-doublons fusionnés (le code le fait déjà pour les constats) ;
  - **corrections douteuses signalées** : une correction qui retire une source valide, qui contredit le passage
    cité ou qui ajoute un chiffre absent des documents est marquée « à vérifier par un humain », avec la raison ;
  - un humain valide, corrige ou écarte ; seuls les exemples validés entrent dans le paquet d'entraînement.

## 4. Entraîner à partir de l'usage

### Comment font les grands modèles, et ce qu'on en retient

Les grands modèles (comme Claude) passent par trois grandes étapes : un **pré-entraînement** sur d'énormes volumes
de texte (hors de portée : des milliers de GPU), un **ajustement supervisé** sur des exemples de bonnes réponses,
puis un **apprentissage par préférences** (des humains ou des règles disent quelle réponse est meilleure). Nous
faisons déjà la deuxième étape à petite échelle (QLoRA) ; l'historique des corrections permet la troisième (DPO) sans
matériel géant. L'entraînement reste un **script** (Python) lancé sur un GPU ; l'interface sert à **préparer les
données, lancer, suivre et décider**, pas à remplacer le script.

### Le cycle cible (un clic dans l'application, puis automatique)

| Étape | Qui | Détail |
|---|---|---|
| 1. Export | application | événements validés → paquet JSONL (SFT + préférences), découpé par dossier (jamais le même dossier en entraînement et en test), empreinte SHA-256 |
| 2. Entraînement | serveur interne ou Kaggle | même chaîne qu'aujourd'hui (QLoRA, arrêt anticipé, meilleure version), lancée par le serveur ; Kaggle en secours via son API |
| 3. Test | automatique | banc fixe (rapports jamais vus + vrai rapport) : base, modèle actuel et candidat passent les mêmes tests |
| 4. Décision | humain | le candidat est **adopté seulement s'il fait mieux** ; sinon on garde l'actuel (comme v5 face à v4) |
| 5. Suivi | interface | courbes (erreur de validation, durée, température), résultats par tâche, historique des versions du modèle |

*Existe déjà : scripts d'entraînement en parties, carnets Colab et Kaggle, export GGUF, import Ollama, test par tâche,
registre des modèles avec retour arrière. À construire : export depuis l'historique, lancement depuis l'interface,
banc automatique, tableau de bord d'entraînement.*

### Où entraîner

| Option | Avantages | Limites |
|---|---|---|
| **Serveur interne** (accès par réseau privé, ex. Tailscale, si l'entreprise l'autorise) | données qui ne sortent pas, pas de quota, automatisable | GPU 16-24 Go au moins ; accord de la DSI ; supervision |
| **Kaggle** | gratuit (~30 h de GPU par semaine), API pour lancer un carnet | données publiques ou anonymisées seulement ; sessions de 12 h ; téléchargements manuels aujourd'hui |
| **Colab** | gratuit, simple | quota non publié, coupures |

## 5. Le prochain entraînement (v6) : quoi, comment, et comment savoir s'il est meilleur

**Objectifs** : mieux détecter les **conflits** (11/24 aujourd'hui), mieux **nommer les axes** et les initiatives,
**proposer** des exigences de CdC au lieu de refuser quand le consultant le demande, rédiger les **objectifs et
livrables des TdR** à partir des recommandations.

| Donnée | Source | Volume visé |
|---|---|---|
| Conflits réels | réponses « accepte partiellement / rejette » de la Commission (justification = contrainte) | ≥ 150 |
| Noms d'axes courts | titres de parties des rapports, raccourcis et relus par un humain | ≥ 300 |
| Exigences de CdC | recommandations reformulées en « Le système doit… », relues | ≥ 200 |
| Objectifs / livrables de TdR | recommandations et échéances des rapports | ≥ 200 |
| Corrections réelles | historique de l'application (section 2), si accord | dès qu'il y en a |

Méthode : même chaîne (QLoRA, arrêt anticipé), même découpage par rapport, **mise à jour des consignes TdR « objectifs /
livrables »** dans les gabarits **et** dans le paquet en même temps (le test de cohérence l'exige). Adoption seulement
si v6 bat v4 sur le banc, sans perdre sur le refus et la citation.

## 6. Ordre conseillé

| # | Chantier | Pourquoi d'abord |
|---|---|---|
| 1 | Journal d'événements + frise + export JSONL | sans données d'usage, rien à apprendre ; peu de code, beaucoup de valeur |
| 2 | Consignes par section + chat qui pilote la génération | ce que le consultant attend le plus ; produit des événements riches |
| 3 | Feuille de route datée (date de départ, durées, sprints) | demandé pour présenter la feuille de route au client |
| 4 | CdC sur sommaire importé | adapte l'outil aux habitudes de chaque client |
| 5 | Espace administrateur + nettoyage assisté | prérequis pour entraîner sur des données de plusieurs consultants |
| 6 | Paquet v6 et entraînement | quand 1 et 5 existent |
| 7 | Entraînement lancé depuis l'interface, banc automatique | quand un serveur GPU est disponible |
| 8 | Contrôle du diagnostic | utile mais secondaire |

## 7. Matériel

| Besoin | Minimum | Confortable |
|---|---|---|
| Utiliser l'outil seul | GPU 4 Go (mesuré : ~22 min par feuille de route) | GPU 16 Go, 32 Go de RAM |
| Équipe de consultants | GPU 24 Go, vLLM | GPU 48 Go (modèle 8-14B, fenêtre 32 000 jetons) |
| Entraîner un 4B (QLoRA) | GPU 16 Go (mesuré : T4, 21-43 min) | GPU 24 Go |
| Entraîner un 8-14B | GPU 48 Go | GPU 80 Go |
