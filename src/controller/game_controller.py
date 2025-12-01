import pygame
import time
from src.model.game_model import GameModel
from src.view.game_view import GameView
from src.controller.bot_controller import AIBot  
from src.controller.shared_knowledge import SharedKnowledge

class GameController:
    def __init__(self, num_bots: int = 2): # Ajout du paramètre
        if not pygame.get_init():
            pygame.init()
        
        # On passe le nombre au modèle pour qu'il crée les joueurs
        self.model = GameModel(num_bots=num_bots)
        self.view = GameView()
        self.clock = pygame.time.Clock()
        self.running = True
        self.last_time = time.time()
        
        self.shared_knowledge = SharedKnowledge()
        self.bot_enabled = True
        
        # --- CRÉATION DYNAMIQUE DES BOTS ---
        self.bots = []
        for i in range(num_bots):
            bot = AIBot(player_index=i, shared_knowledge=self.shared_knowledge)
            self.bots.append(bot)
        # -----------------------------------
    
    def run(self):
        """Boucle principale du jeu"""
        while self.running:
            current_time = time.time()
            delta_time = current_time - self.last_time
            self.last_time = current_time
            
            self._handle_events()
            self.model.update(delta_time)
            self.shared_knowledge.update_orders(self.model.orders)
            
            # Mise à jour de TOUS les bots
            if self.bot_enabled:
                for bot in self.bots:
                    bot.update(self.model)
            
            self.view.render(self.model)
            self.clock.tick(60)
    
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False