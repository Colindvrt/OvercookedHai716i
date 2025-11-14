import pygame
import time
from src.model.game_model import GameModel
from src.view.game_view import GameView
from src.controller.bot_controller import AIBot  
from src.controller.shared_knowledge import SharedKnowledge

class GameController:
    def __init__(self):
        if not pygame.get_init():
            pygame.init()
        self.model = GameModel()
        self.view = GameView()
        self.clock = pygame.time.Clock()
        self.running = True
        self.last_time = time.time()
        
        # Mémoire partagée
        self.shared_knowledge = SharedKnowledge()
        
        # Bots multi-agents
        self.bot_enabled = True  # ✅ REMETTRE CETTE LIGNE
        self.bot1 = AIBot(player_index=0, shared_knowledge=self.shared_knowledge)
        self.bot2 = AIBot(player_index=1, shared_knowledge=self.shared_knowledge)
    
    def run(self):
        """Boucle principale du jeu"""
        while self.running:
            current_time = time.time()
            delta_time = current_time - self.last_time
            self.last_time = current_time
            
            self._handle_events()
            
            # Mise à jour modèle
            self.model.update(delta_time)
            
            # Mise à jour de la mémoire partagée
            self.shared_knowledge.update_orders(self.model.orders)
            
            # Bots: font les actions automatiquement
            if self.bot_enabled:
                self.bot1.update(self.model)
                self.bot2.update(self.model)  # ✅ AJOUTER LE BOT 2
            
            # Rendu
            self.view.render(self.model)
            self.clock.tick(60)  # 60 FPS
    
    def _handle_events(self):  # ✅ UNE SEULE DÉFINITION
        """Gère les événements d'entrée"""
        for event in pygame.event.get():
            # Quitter via le bouton de la fenêtre
            if event.type == pygame.QUIT:
                self.running = False
            
            # Quitter via la touche ESC (Échap)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False