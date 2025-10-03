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
            'cooked_patty': (100, 50, 25),
            'raw_patty': (150, 50, 50),
            'burger': (255, 200, 100),
            'text': (255, 255, 255),
            # Couleurs pour le personnage cuisinier
            'chef_skin': (255, 220, 177),
            'chef_uniform': (255, 255, 255),
            'chef_hat': (255, 255, 255),
            'chef_eyes': (50, 50, 50),
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
            # Couleur selon type de station
            color = self.COLORS['station']
            if station.station_type == StationType.STOVE:
                color = (200, 100, 100)
            elif station.station_type == StationType.CUTTING_BOARD:
                color = (150, 150, 100)
            elif station.station_type == StationType.ASSEMBLY:
                color = (100, 150, 100)
            elif station.station_type == StationType.DELIVERY:
                color = (100, 100, 200)
            elif station.station_type == StationType.INGREDIENT_SPAWN:
                color = (150, 100, 150)
            
            pygame.draw.rect(self.screen, color, (station.x - 25, station.y - 25, 50, 50))
            pygame.draw.rect(self.screen, (255, 255, 255), (station.x - 25, station.y - 25, 50, 50), 2)
            
            # Affichage spécifique pour l'assemblage : pile d'ingrédients
            if station.station_type == StationType.ASSEMBLY:
                if getattr(station, "contents", None):
                    for idx, it in enumerate(station.contents):
                        # empilement visuel vers le haut
                        self._draw_item(it, station.x, station.y - 12 - idx * 12)
                if station.item and station.item.item_type == ItemType.BURGER:
                    # burger final un peu plus bas pour le distinguer
                    self._draw_item(station.item, station.x, station.y + 10)
            else:
                # Autres stations : afficher l'item si présent
                if station.item:
                    self._draw_item(station.item, station.x, station.y - 10)
            
            # Indicateur de cuisson sur le fourneau
            if (station.station_type == StationType.STOVE and 
                station.item and station.item.item_type == ItemType.RAW_PATTY and station.cooking_start_time > 0):
                cooking_progress = (time.time() - station.cooking_start_time) / station.cooking_duration
                cooking_progress = min(1.0, max(0.0, cooking_progress))
                bar_width = 40
                bar_height = 6
                bar_x = station.x - bar_width // 2
                bar_y = station.y + 30
                pygame.draw.rect(self.screen, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height))
                pygame.draw.rect(self.screen, (255, 200, 0), (bar_x, bar_y, int(bar_width * cooking_progress), bar_height))
            
            # Ingrédient spawn : petit indicateur fantôme
            if station.station_type == StationType.INGREDIENT_SPAWN and station.ingredient_type:
                item_dummy = type('Item', (), {'item_type': station.ingredient_type, 'chopped': False})()
                self._draw_item(item_dummy, station.x, station.y + 10, alpha=128)
    
    def _draw_tomato(self, x: int, y: int, chopped: bool = False, alpha: int = 255):
        """Dessine une tomate réaliste"""
        if chopped:
            # Tomate coupée : plusieurs rondelles
            for i in range(3):
                offset_x = (i - 1) * 6
                pygame.draw.circle(self.screen, (220, 50, 50), (x + offset_x, y), 5)
                pygame.draw.circle(self.screen, (255, 100, 100), (x + offset_x, y), 3)
        else:
            # Tomate entière : rouge brillant avec reflet
            pygame.draw.circle(self.screen, (220, 50, 50), (x, y), 9)
            pygame.draw.circle(self.screen, (180, 30, 30), (x, y), 9, 1)
            # Tige verte
            pygame.draw.line(self.screen, (50, 150, 50), (x, y - 9), (x, y - 13), 2)
            pygame.draw.circle(self.screen, (50, 150, 50), (x, y - 9), 3)
            # Reflet brillant
            pygame.draw.circle(self.screen, (255, 150, 150), (x - 3, y - 3), 2)
    
    def _draw_lettuce(self, x: int, y: int, chopped: bool = False, alpha: int = 255):
        """Dessine de la salade réaliste"""
        if chopped:
            # Salade coupée : plusieurs morceaux
            pygame.draw.circle(self.screen, (100, 200, 100), (x - 4, y - 2), 4)
            pygame.draw.circle(self.screen, (120, 220, 120), (x + 4, y), 4)
            pygame.draw.circle(self.screen, (80, 180, 80), (x, y + 3), 4)
        else:
            # Feuille de salade : forme ondulée verte
            points = [
                (x - 8, y), (x - 6, y - 6), (x - 2, y - 8),
                (x + 2, y - 8), (x + 6, y - 6), (x + 8, y),
                (x + 6, y + 6), (x, y + 8), (x - 6, y + 6)
            ]
            pygame.draw.polygon(self.screen, (100, 200, 100), points)
            pygame.draw.polygon(self.screen, (80, 180, 80), points, 1)
            # Nervures
            pygame.draw.line(self.screen, (80, 180, 80), (x, y - 6), (x, y + 6), 1)
    
    def _draw_bread(self, x: int, y: int, alpha: int = 255):
        """Dessine du pain réaliste"""
        # Pain en forme de dôme
        pygame.draw.ellipse(self.screen, (210, 180, 140), (x - 10, y - 6, 20, 12))
        pygame.draw.ellipse(self.screen, (180, 150, 110), (x - 10, y - 6, 20, 12), 1)
        # Détails du pain (petites lignes)
        pygame.draw.line(self.screen, (180, 150, 110), (x - 6, y - 2), (x - 3, y - 3), 1)
        pygame.draw.line(self.screen, (180, 150, 110), (x + 3, y - 3), (x + 6, y - 2), 1)
    
    def _draw_patty(self, x: int, y: int, cooked: bool = False, alpha: int = 255):
        """Dessine un steak haché réaliste"""
        if cooked:
            # Steak cuit : brun foncé avec marques de grill
            pygame.draw.ellipse(self.screen, (100, 50, 25), (x - 10, y - 4, 20, 8))
            pygame.draw.ellipse(self.screen, (80, 40, 20), (x - 10, y - 4, 20, 8), 1)
            # Marques de grill
            for i in range(3):
                y_pos = y - 3 + i * 3
                pygame.draw.line(self.screen, (60, 30, 15), (x - 8, y_pos), (x + 8, y_pos), 1)
        else:
            # Steak cru : rose/rouge
            pygame.draw.ellipse(self.screen, (200, 80, 80), (x - 10, y - 4, 20, 8))
            pygame.draw.ellipse(self.screen, (180, 60, 60), (x - 10, y - 4, 20, 8), 1)
            # Texture de viande
            pygame.draw.circle(self.screen, (180, 60, 60), (x - 3, y), 2)
            pygame.draw.circle(self.screen, (180, 60, 60), (x + 4, y - 1), 2)
    
    def _draw_burger(self, x: int, y: int, alpha: int = 255):
        """Dessine un burger complet réaliste"""
        # Pain du haut (dôme)
        pygame.draw.ellipse(self.screen, (210, 180, 140), (x - 12, y - 12, 24, 10))
        pygame.draw.ellipse(self.screen, (180, 150, 110), (x - 12, y - 12, 24, 10), 1)
        # Graines de sésame
        for seed_x in [x - 6, x, x + 6]:
            pygame.draw.circle(self.screen, (240, 230, 200), (seed_x, y - 8), 1)
        
        # Salade (vert qui dépasse)
        pygame.draw.ellipse(self.screen, (100, 200, 100), (x - 14, y - 6, 28, 5))
        
        # Tomate (rouge qui dépasse)
        pygame.draw.ellipse(self.screen, (220, 50, 50), (x - 13, y - 2, 26, 4))
        
        # Steak (brun)
        pygame.draw.ellipse(self.screen, (100, 50, 25), (x - 11, y + 1, 22, 5))
        
        # Pain du bas
        pygame.draw.ellipse(self.screen, (210, 180, 140), (x - 12, y + 5, 24, 6))
        pygame.draw.ellipse(self.screen, (180, 150, 110), (x - 12, y + 5, 24, 6), 1)
    
    def _draw_item(self, item, x: int, y: int, alpha: int = 255):
        """Dessine un item avec son apparence réaliste"""
        chopped = getattr(item, 'chopped', False)
        
        if item.item_type == ItemType.TOMATO:
            self._draw_tomato(x, y, chopped, alpha)
        elif item.item_type == ItemType.LETTUCE:
            self._draw_lettuce(x, y, chopped, alpha)
        elif item.item_type == ItemType.BREAD:
            self._draw_bread(x, y, alpha)
        elif item.item_type == ItemType.RAW_PATTY:
            self._draw_patty(x, y, cooked=False, alpha=alpha)
        elif item.item_type == ItemType.COOKED_PATTY:
            self._draw_patty(x, y, cooked=True, alpha=alpha)
        elif item.item_type == ItemType.BURGER:
            self._draw_burger(x, y, alpha)
        else:
            # Fallback : cercle simple
            color = self.COLORS.get(item.item_type.value, (255, 255, 255))
            pygame.draw.circle(self.screen, color, (x, y), 8)
    
    def _draw_chef_character(self, x: int, y: int):
        """Dessine un personnage cuisinier avec tête, corps et toque"""
        # Corps (rectangle blanc pour la veste de cuisinier)
        body_rect = pygame.Rect(x - 12, y - 5, 24, 20)
        pygame.draw.rect(self.screen, self.COLORS['chef_uniform'], body_rect)
        pygame.draw.rect(self.screen, (200, 200, 200), body_rect, 2)  # Contour
        
        # Tête (cercle couleur peau)
        head_center = (x, y - 18)
        pygame.draw.circle(self.screen, self.COLORS['chef_skin'], head_center, 10)
        
        # Yeux (deux petits points noirs)
        left_eye = (x - 4, y - 19)
        right_eye = (x + 4, y - 19)
        pygame.draw.circle(self.screen, self.COLORS['chef_eyes'], left_eye, 2)
        pygame.draw.circle(self.screen, self.COLORS['chef_eyes'], right_eye, 2)
        
        # Sourire (petit arc)
        mouth_points = [
            (x - 4, y - 14),
            (x, y - 12),
            (x + 4, y - 14)
        ]
        pygame.draw.lines(self.screen, self.COLORS['chef_eyes'], False, mouth_points, 1)
        
        # Toque de cuisinier (chapeau blanc)
        # Base de la toque (rectangle)
        hat_base = pygame.Rect(x - 10, y - 28, 20, 5)
        pygame.draw.rect(self.screen, self.COLORS['chef_hat'], hat_base)
        
        # Haut de la toque (ellipse gonflée)
        hat_top = pygame.Rect(x - 8, y - 40, 16, 15)
        pygame.draw.ellipse(self.screen, self.COLORS['chef_hat'], hat_top)
        pygame.draw.ellipse(self.screen, (200, 200, 200), hat_top, 1)  # Contour
        
        # Jambes (deux petites lignes)
        pygame.draw.line(self.screen, (100, 100, 100), (x - 6, y + 15), (x - 6, y + 25), 3)
        pygame.draw.line(self.screen, (100, 100, 100), (x + 6, y + 15), (x + 6, y + 25), 3)
    
    def _draw_players(self, players: List):
        """Dessine tous les joueurs"""
        for _, player in enumerate(players):
            # Dessiner le personnage cuisinier au lieu d'un simple cercle
            self._draw_chef_character(player.x, player.y)
            
            # Si le joueur tient un item, l'afficher au-dessus de sa tête
            if player.held_item:
                self._draw_item(player.held_item, player.x, player.y - 45)
    
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
        
        # Instructions
        instructions = [
            "ESPACE: Ramasser/Poser/Assembler",
            "C: Découper (sur planche)",
            "Flèches: Se déplacer",
            "B: Toggle Bot"
        ]
        for i, instruction in enumerate(instructions):
            text = self.small_font.render(instruction, True, self.COLORS['text'])
            self.screen.blit(text, (580, 10 + i * 20))