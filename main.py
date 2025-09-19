import pygame
import sys
from src.controller.game_controller import GameController

def main():
    pygame.init()
    controller = GameController()
    controller.run()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()