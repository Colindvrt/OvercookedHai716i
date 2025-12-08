# Overcooked Simplifié - Simulation Multi-Agents
Version simplifiée du jeu Overcooked implémentée en Python avec une architecture MVC, conçue pour simuler et analyser le comportement d'agents autonomes.

## Fonctionnalités Clés

- **Simulation Multi-Agents** : Choisissez le nombre de bots (de 1 à 10) pour voir comment ils collaborent (ou non !).
- **Commandes Dynamiques** : Le flux de commandes s'adapte au nombre de joueurs pour maintenir une pression constante.
- **Statistiques en Temps Réel** : Suivez le score, le temps restant et les commandes en cours directement sur l'interface.
- **Graphismes Améliorés** : Interface moderne avec files d'attente de clients, animations de cuisson et indicateurs visuels.

## Installation

```bash
# Créer l'environnement virtuel avec uv
uv venv

# Activer l'environnement virtuel
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Installer les dépendances
uv pip install -e .
```

## Lancement

```bash
python main.py
```
Au lancement, le jeu vous demandera dans le terminal de saisir le nombre de bots souhaités.

## Simulation et Analyse

Le projet inclut des outils pour lancer des simulations massives et analyser les performances :

```bash
# Lancer une batterie de tests (1 à 10 bots, 100 parties)
python run_simulation.py

# Visualiser les résultats (génère des graphiques)
python visualize_results.py
```

## Contrôles

Le jeu est entièrement autonome (bots), mais vous pouvez observer :
- **Échap** : Quitter le jeu

## Structure du projet

```
overcooked-simple/
├── main.py                 # Point d'entrée du jeu interactif
├── run_simulation.py       # Script de simulation headless
├── visualize_results.py    # Analyse des données de simulation
├── src/
│   ├── model/              # Logique métier (GameModel, Item, Player)
│   ├── view/               # Rendu graphique (GameView, Pygame)
│   └── controller/         # IA et Gestion (AIBot, SharedKnowledge)
├── pyproject.toml
└── README.md
```