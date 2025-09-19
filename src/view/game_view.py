import pygame
import time
from typing import List
from src.model.game_model import GameModel, ItemType, StationType

class GameView:
    def __init__(self, width: int = 800, height: int = 600):
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Overcooked Simplifié")
        
        # Couleurs
        self.COLORS = {
            'background': (50, 50, 50),
            'player': (0, 100, 255),
            'station': (100, 100, 100),
            'tomato': (255, 0, 0),
            'lettuce': (0, 255, 0),
            'bread': (200, 150, 100),
            'patty_raw': (150, 50, 50),
            'patty_cooked': (100, 50, 25),
            'burger': (255, 200, 100),
            'text': (255, 255, 255),
            'order_bg': (0, 0, 0, 128)
        }
        
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
    
    def render(self, model: GameModel):
        """Rend la scène complète"""
        self.screen.fill(self.COLORS['background'])
        
        self._draw_stations(model.stations)
        self._draw_players(model.players)
        self._draw_ui(model)
        
        pygame.display.flip()
    
    def _draw_stations(self, stations: List):
        """Dessine toutes les stations"""
        for station in stations:
            # Station de base
            color = self.COLORS['station']
            if station.station_type == StationType.STOVE:
                color = (200, 100, 100)
            elif station.station_type == StationType.CUTTING_BOARD:
                color = (150, 150, 100)
            elif station.station_type == StationType.ASSEMBLY:
                color = (100, 150, 100)
            elif station.station_type == StationType.DELIVERY:
                color = (100, 100, 200)
            
            pygame.draw.rect(self.screen, color, (station.x - 25, station.y - 25, 50, 50))
            
            # Item sur la station
            if station.item:
                self._draw_item(station.item, station.x, station.y - 10)
            
            # Ingrédient spawn indicator
            if station.station_type == StationType.INGREDIENT_SPAWN and station.ingredient_type:
                item_dummy = type('Item', (), {'item_type': station.ingredient_type, 'chopped': False})()
                self._draw_item(item_dummy, station.x, station.y + 10, alpha=128)
    
    def _draw_item(self, item, x: int, y: int, alpha: int = 255):
        """Dessine un item"""
        color = self.COLORS.get(item.item_type.value, (255, 255, 255))
        
        if alpha < 255:
            # Créer une surface avec alpha pour les indicateurs
            surf = pygame.Surface((15, 15))
            surf.set_alpha(alpha)
            surf.fill(color)
            self.screen.blit(surf, (x - 7, y - 7))
        else:
            pygame.draw.circle(self.screen, color, (x, y), 8)
            
        # Indicateur si l'item est coupé
        if hasattr(item, 'chopped') and item.chopped:
            pygame.draw.circle(self.screen, (255, 255, 255), (x + 5, y - 5), 3)
    
    def _draw_players(self, players: List):
        """Dessine tous les joueurs"""
        for i, player in enumerate(players):
            # Joueur
            pygame.draw.circle(self.screen, self.COLORS['player'], (player.x, player.y), 20)
            
            # Item porté
            if player.held_item:
                self._draw_item(player.held_item, player.x, player.y - 30)
    
    def _draw_ui(self, model: GameModel):
        """Dessine l'interface utilisateur"""
        # Score
        score_text = self.font.render(f"Score: {model.score}", True, self.COLORS['text'])
        self.screen.blit(score_text, (10, 10))
        
        # Temps restant
        time_remaining = max(0, model.game_time - (time.time() - model.start_time))
        time_text = self.font.render(f"Temps: {int(time_remaining)}s", True, self.COLORS['text'])
        self.screen.blit(time_text, (10, 40))
        
        # Commandes
        y_offset = 80
        for i, order in enumerate(model.orders):
            order_text = f"Commande {i+1}: Burger ({int(order.time_remaining)}s)"
            text_surface = self.small_font.render(order_text, True, self.COLORS['text'])
            self.screen.blit(text_surface, (10, y_offset + i * 25))