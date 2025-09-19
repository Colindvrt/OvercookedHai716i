# Overcooked Simplifié

Version simplifiée du jeu Overcooked implémentée en Python avec une architecture MVC.

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

## Contrôles

- **Flèches directionnelles** : Déplacer le joueur
- **Espace** : Interagir avec une station
- **Échap** : Quitter le jeu

## Gameplay

1. Ramassez des ingrédients aux points de spawn (tomate, salade, pain, viande crue)
2. Coupez les légumes sur les planches à découper
3. Cuisez la viande sur les fourneaux
4. Assemblez les burgers à la station d'assemblage
5. Livrez les commandes à la station de livraison

## Structure du projet

```
overcooked-simple/
├── main.py                 # Point d'entrée
├── src/
│   ├── __init__.py
│   ├── model/              # Modèle (logique métier)
│   │   └── game_model.py
│   ├── view/               # Vue (affichage)
│   │   └── game_view.py
│   └── controller/         # Contrôleur (gestion des entrées)
│       └── game_controller.py
├── pyproject.toml
└── README.md
```