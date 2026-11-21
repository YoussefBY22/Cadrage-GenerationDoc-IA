# Phase A — Pour comprendre

## Pour comprendre
Imagine un **restaurant**. Le modèle de langage est le **chef**, très talentueux mais imprévisible. Le reste du logiciel est la **salle** : prise de commande, caisse, contrôle qualité. Dans la phase A on construit la salle **sans chef** : à sa place, un **mannequin** (`FakeProvider`) qui répond toujours pareil, pour vérifier que tout le service fonctionne. Le jour où le vrai chef (Ollama) arrive, on le branche sur la **même prise** (`LLMProvider`), sans refaire la salle.

Deuxième idée : la **confidentialité**. On ne se contente pas de promettre qu'on n'envoie rien dehors : un **test automatique** coupe Internet pour tout le code de test, et un autre scanne le code pour refuser les bibliothèques cloud. Si quelqu'un ajoute un jour un appel externe, la CI devient rouge.

Notions : interface, déterminisme, graine, sortie structurée, hallucination (pourquoi on ne fait jamais confiance au chef sans contrôle), test de contrat → voir `docs/03-apprentissage-et-glossaire.md` (§1 et §6).

## Choix importants et alternatives écartées
- **Faux modèle plutôt que petit vrai modèle dans le cloud** : un petit modèle réel varie et demande un gros téléchargement ; un test qui varie ne prouve rien. Écarté : `llama.cpp` + mini-modèle en CI.
- **Réseau Docker `internal` pour la base** plutôt que simple « on ne fait pas d'appel » : une règle d'infrastructure ne dépend pas de la discipline humaine.
- **Test de contrat avec serveur simulé** plutôt que mock Python des fonctions : on teste la vraie requête HTTP (forme du JSON, route), là où les bugs d'intégration apparaissent.
- **Journaux avec empreintes** plutôt que journaux complets : plus difficile à déboguer, mais aucune fuite possible.

## 3 questions pour vérifier ta compréhension
1. Pourquoi le `FakeProvider` renvoie-t-il la même réponse pour le même prompt, et en quoi cela aide-t-il à tester sans GPU ?
2. Que prouve le test « aucune connexion sortante », et que ne prouve-t-il **pas** (pense au conteneur en production) ?
3. Pourquoi ne journalise-t-on pas le texte des prompts, et que met-on à la place ?
