import pygame
import sys
from src.controller.game_controller import GameController

def main():
    # --- Début de la modification ---
    try:
        user_input = input("Entrez le nombre de bots (par défaut 2) : ")
        if user_input.strip() == "":
            num_bots = 2
        else:
            num_bots = int(user_input)
    except ValueError:
        print("Entrée invalide. Lancement avec 2 bots par défaut.")
        num_bots = 2
    
    # Limites de sécurité (entre 1 et 10 bots par exemple)
    num_bots = max(1, min(10, num_bots))
    print(f"Lancement du jeu avec {num_bots} bots !")
    # --- Fin de la modification ---

    pygame.init()
    # On passe le nombre de bots au contrôleur
    controller = GameController(num_bots=num_bots)
    controller.run()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()