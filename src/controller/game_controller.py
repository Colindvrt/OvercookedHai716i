import pygame
import time
from src.model.game_model import GameModel
from src.view.game_view import GameView

class GameController:
    def __init__(self):
        # S'assurer que pygame est initialisé ici si ce n'est pas fait ailleurs
        if not pygame.get_init():
            pygame.init()
        self.model = GameModel()
        self.view = GameView()
        self.clock = pygame.time.Clock()
        self.running = True
        self.last_time = time.time()
    
    def run(self):
        """Boucle principale du jeu"""
        while self.running:
            current_time = time.time()
            delta_time = current_time - self.last_time
            self.last_time = current_time
            
            self._handle_events()
            self.model.update(delta_time)
            self.view.render(self.model)
            
            self.clock.tick(60)  # 60 FPS
    
    def _handle_events(self):
        """Gère les événements d'entrée"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
    
    def _handle_keydown(self, event):
        """Gère les touches pressées"""
        # Mouvement du joueur 1 (flèches)
        if event.key == pygame.K_UP:
            self.model.move_player(0, 0, -1)
        elif event.key == pygame.K_DOWN:
            self.model.move_player(0, 0, 1)
        elif event.key == pygame.K_LEFT:
            self.model.move_player(0, -1, 0)
        elif event.key == pygame.K_RIGHT:
            self.model.move_player(0, 1, 0)
        elif event.key == pygame.K_SPACE:
            self.model.interact_with_station(0)
        elif event.key == pygame.K_c:
            self.model.chop_at_station(0)  # Action pour découper
        elif event.key == pygame.K_ESCAPE:
            self.running = False
