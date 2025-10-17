import pygame
import time
import math
from typing import List
from src.model.game_model import GameModel, ItemType, StationType

class GameView:
    def __init__(self, width: int = 1000, height: int = 700):  # Increased size
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Overcooked Deluxe - Multi-Recettes")
        
        self.COLORS = {
            'background': (45, 52, 54), 'floor': (240, 235, 216), 'counter': (139, 69, 19),
            'counter_top': (160, 82, 45), 'wall': (108, 117, 125), 'player': (0, 100, 255),
            'station': (100, 100, 100), 'tomato': (255, 0, 0), 'lettuce': (0, 255, 0),
            'bread': (200, 150, 100), 'cooked_patty': (100, 50, 25), 'raw_patty': (150, 50, 50),
            'cheese': (255, 255, 100), 'burger': (255, 200, 100), 'pizza': (255, 180, 50),
            'salad': (150, 255, 150), 'text': (255, 255, 255), 'chef_skin': (255, 220, 177),
            'chef_uniform': (255, 255, 255), 'chef_hat': (255, 255, 255), 'chef_eyes': (50, 50, 50),
            'stove_base': (50, 50, 60), 'stove_top': (70, 70, 80), 'fire': (255, 100, 0),
            'cutting_board': (205, 133, 63), 'metal': (192, 192, 192), 'shadow': (0, 0, 0, 60),
            'furnace': (20, 20, 20), 
        }
        
        self.font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 20)
        self.large_font = pygame.font.Font(None, 42)
        self.animation_time = 0
        self.customers = {}  # Dict with order ID as key
        self.customer_spawn_timer = 0
    
    def render(self, model: GameModel):
        self.animation_time += 0.05
        self._draw_floor()
        self._draw_walls()
        self._draw_counters(model.stations)
        self._draw_enhanced_stations(model.stations)
        self._update_customers(model)
        self._draw_customers()
        self._draw_players(model.players)
        self._draw_modern_ui(model)
        self._draw_particle_effects(model.stations)
        pygame.display.flip()
    
    def _draw_floor(self):
        tile_size = 50
        # Only draw floor in play area
        for x in range(0, self.width, tile_size):
            for y in range(0, 450, tile_size):  # Stop before customer area
                color = (240, 235, 216) if (x // tile_size + y // tile_size) % 2 == 0 else (235, 230, 211)
                pygame.draw.rect(self.screen, color, (x, y, tile_size, tile_size))
                pygame.draw.rect(self.screen, (200, 195, 176), (x, y, tile_size, tile_size), 1)
        
        # Customer counter area - wooden counter look
        pygame.draw.rect(self.screen, (139, 90, 43), (0, 450, self.width, 250))
        # Counter top edge
        pygame.draw.rect(self.screen, (160, 110, 60), (0, 450, self.width, 15))
        # Add some wood texture lines
        for i in range(5, self.width, 40):
            pygame.draw.line(self.screen, (120, 75, 35), (i, 460), (i, self.height), 1)
    
    def _draw_walls(self):
        wall_height = 80
        pygame.draw.rect(self.screen, self.COLORS['wall'], (0, 0, self.width, wall_height))
        for i in range(10):
            s = pygame.Surface((self.width, 1), pygame.SRCALPHA)
            s.fill((0, 0, 0, 30 - i * 3))
            self.screen.blit(s, (0, wall_height + i))
        tile_size = 20
        for x in range(0, self.width, tile_size):
            for y in range(10, wall_height - 10, tile_size):
                pygame.draw.rect(self.screen, (118, 127, 135), (x, y, tile_size-2, tile_size-2))
    
    def _draw_counters(self, stations):
        for cx, cy, cw, ch in [(80, 140, 500, 80), (620, 140, 150, 80)]:
            shadow = pygame.Surface((cw + 10, ch + 10), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 40))
            self.screen.blit(shadow, (cx + 5, cy + 5))
            pygame.draw.rect(self.screen, self.COLORS['counter'], (cx, cy, cw, ch))
            pygame.draw.rect(self.screen, self.COLORS['counter_top'], (cx, cy, cw, 15))
            for i in range(3):
                pygame.draw.line(self.screen, (150, 92, 55), (cx + 10, cy + 5 + i * 3), (cx + cw - 10, cy + 5 + i * 3), 1)
            drawer_y = cy + 30
            pygame.draw.rect(self.screen, (120, 60, 10), (cx + 20, drawer_y, cw - 40, 35))
            pygame.draw.rect(self.screen, (100, 50, 5), (cx + 20, drawer_y, cw - 40, 35), 2)
            pygame.draw.circle(self.screen, (180, 180, 180), (cx + cw // 2, drawer_y + 17), 4)
    
    def _draw_enhanced_stations(self, stations):
        for station in stations:
            if station.station_type == StationType.STOVE:
                self._draw_stove(station)
            elif station.station_type == StationType.FURNACE:
                self._draw_furnace(station)
            elif station.station_type == StationType.CUTTING_BOARD:
                self._draw_cutting_board(station)
            elif station.station_type == StationType.ASSEMBLY:
                self._draw_assembly_station(station)
            elif station.station_type == StationType.DELIVERY:
                self._draw_delivery_station(station)
            elif station.station_type == StationType.INGREDIENT_SPAWN:
                self._draw_ingredient_spawn(station)
    
    def _draw_stove(self, station):
        x, y = station.x, station.y
        shadow = pygame.Surface((70, 70), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 40))
        self.screen.blit(shadow, (x - 32, y - 27))
        pygame.draw.rect(self.screen, self.COLORS['stove_base'], (x - 30, y - 25, 60, 50), border_radius=3)
        pygame.draw.circle(self.screen, self.COLORS['stove_top'], (x, y), 20)
        pygame.draw.circle(self.screen, (50, 50, 50), (x, y), 20, 2)
        
        if station.item and station.item.item_type == ItemType.RAW_PATTY and station.cooking_start_time > 0:
            glow_intensity = int(100 + 155 * abs(math.sin(self.animation_time * 2)))
            pygame.draw.circle(self.screen, (glow_intensity, 20, 0), (x, y), 18)
            for i in range(3):
                flame_y = y + 15 + math.sin(self.animation_time * 3 + i) * 3
                pygame.draw.circle(self.screen, (255, 150, 0), (x - 10 + i * 10, int(flame_y)), 4)
        
        for i in range(3):
            pygame.draw.circle(self.screen, (80, 80, 80), (x - 15 + i * 15, y - 30), 3)
        
        if station.item:
            self._draw_item(station.item, x, y - 5)
            if station.item.item_type == ItemType.RAW_PATTY and station.cooking_start_time > 0:
                cooking_progress = (time.time() - station.cooking_start_time) / station.cooking_duration
                cooking_progress = min(1.0, max(0.0, cooking_progress))
                bar_width, bar_height = 50, 8
                bar_x, bar_y = x - bar_width // 2, y + 35
                pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=4)
                progress_color = (255, 200 - int(100 * cooking_progress), 0)
                pygame.draw.rect(self.screen, progress_color, (bar_x + 2, bar_y + 2, int((bar_width - 4) * cooking_progress), bar_height - 4), border_radius=3)

    def _draw_furnace(self, station):
        x, y = station.x, station.y
        # Carré noir simple
        pygame.draw.rect(self.screen, self.COLORS['furnace'], (x - 30, y - 25, 60, 50), border_radius=5)
        pygame.draw.rect(self.screen, (50, 50, 50), (x - 30, y - 25, 60, 50), 3, border_radius=5)
        
        # Porte du four
        pygame.draw.rect(self.screen, (40, 40, 40), (x - 25, y - 20, 50, 30))
        
        if station.item:
            self._draw_item(station.item, x, y - 5)
            if station.item.item_type == ItemType.UNCOOKED_PIZZA and station.cooking_start_time > 0:
                cooking_progress = (time.time() - station.cooking_start_time) / station.cooking_duration
                cooking_progress = min(1.0, max(0.0, cooking_progress))
                bar_width, bar_height = 50, 8
                bar_x, bar_y = x - bar_width // 2, y + 35
                pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=4)
                progress_color = (255, 150 - int(100 * cooking_progress), 0)
                pygame.draw.rect(self.screen, progress_color, (bar_x + 2, bar_y + 2, int((bar_width - 4) * cooking_progress), bar_height - 4), border_radius=3)

    def _draw_cutting_board(self, station):
        x, y = station.x, station.y
        shadow = pygame.Surface((60, 45), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 40))
        self.screen.blit(shadow, (x - 27, y - 17))
        pygame.draw.rect(self.screen, self.COLORS['cutting_board'], (x - 25, y - 15, 50, 35), border_radius=3)
        pygame.draw.rect(self.screen, (185, 123, 53), (x - 25, y - 15, 50, 35), 2, border_radius=3)
        for i in range(5):
            pygame.draw.line(self.screen, (195, 143, 73), (x - 20, y - 10 + i * 8), (x + 20, y - 10 + i * 8), 1)
        pygame.draw.line(self.screen, (175, 113, 43), (x - 10, y), (x + 5, y + 5), 1)
        pygame.draw.line(self.screen, (175, 113, 43), (x + 8, y - 3), (x + 15, y + 8), 1)
        if station.item:
            pygame.draw.line(self.screen, (192, 192, 192), (x + 15, y - 10), (x + 22, y - 20), 3)
            pygame.draw.line(self.screen, (101, 67, 33), (x + 22, y - 20), (x + 25, y - 25), 2)
            self._draw_item(station.item, x, y)
    
    def _draw_assembly_station(self, station):
        x, y = station.x, station.y
        shadow = pygame.Surface((85, 65), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 40))
        self.screen.blit(shadow, (x - 37, y - 27))
        pygame.draw.rect(self.screen, (200, 200, 200), (x - 35, y - 25, 70, 50), border_radius=5)
        pygame.draw.rect(self.screen, (170, 170, 170), (x - 35, y - 25, 70, 50), 2, border_radius=5)
        pygame.draw.line(self.screen, (230, 230, 230), (x - 30, y - 20), (x + 25, y - 20), 2)
        pygame.draw.line(self.screen, (220, 220, 220), (x - 25, y), (x + 20, y), 1)
        pygame.draw.circle(self.screen, (150, 150, 150), (x - 20, y + 15), 5, 2)
        pygame.draw.circle(self.screen, (150, 150, 150), (x + 20, y + 15), 5, 2)
        pygame.draw.line(self.screen, (150, 150, 150), (x - 20, y + 15), (x + 20, y + 15), 2)
        if hasattr(station, 'contents') and station.contents:
            for idx, item in enumerate(station.contents):
                self._draw_item(item, x, y + 5 - idx * 8, scale=0.9)
        if station.item and station.item.item_type in [ItemType.BURGER, ItemType.PIZZA, ItemType.SALAD, ItemType.UNCOOKED_PIZZA]:
            self._draw_item(station.item, x, y + 5)
            for i in range(3):
                s = pygame.Surface((50, 50), pygame.SRCALPHA)
                pygame.draw.circle(s, (255, 255, 255, 50 - i * 15), (25, 25), 20 - i * 5)
                self.screen.blit(s, (x - 25, y - 20))
    
    def _draw_delivery_station(self, station):
        x, y = station.x, station.y
        pygame.draw.rect(self.screen, (160, 82, 45), (x - 35, y - 20, 70, 40), border_radius=5)
        pygame.draw.rect(self.screen, (139, 69, 19), (x - 35, y - 20, 70, 40), 3, border_radius=5)
        pygame.draw.rect(self.screen, (220, 220, 220), (x - 30, y - 15, 60, 30), border_radius=3)
        pygame.draw.ellipse(self.screen, (192, 192, 192), (x - 15, y - 10, 30, 20))
        pygame.draw.ellipse(self.screen, (150, 150, 150), (x - 15, y - 10, 30, 20), 2)
        pygame.draw.circle(self.screen, (180, 180, 180), (x, y - 10), 3)
        pygame.draw.circle(self.screen, (50, 200, 50), (x, y + 20), 8)
        pygame.draw.line(self.screen, (255, 255, 255), (x - 3, y + 20), (x, y + 23), 2)
        pygame.draw.line(self.screen, (255, 255, 255), (x, y + 23), (x + 5, y + 17), 2)
    
    def _draw_ingredient_spawn(self, station):
        x, y = station.x, station.y
        pygame.draw.rect(self.screen, (230, 230, 250), (x - 30, y - 30, 60, 60), border_radius=5)
        pygame.draw.rect(self.screen, (180, 180, 200), (x - 30, y - 30, 60, 60), 3, border_radius=5)
        pygame.draw.rect(self.screen, (210, 210, 230), (x - 25, y - 25, 50, 50), border_radius=3)
        pygame.draw.rect(self.screen, (180, 180, 200), (x + 10, y, 8, 15), border_radius=2)
        if station.ingredient_type:
            item_dummy = type('Item', (), {'item_type': station.ingredient_type, 'chopped': False})()
            self._draw_item(item_dummy, x, y, scale=0.8)
            label_text = station.ingredient_type.value.capitalize()
            text_surface = self.small_font.render(label_text, True, (100, 100, 100))
            self.screen.blit(text_surface, text_surface.get_rect(center=(x, y + 35)))
    
    def _draw_particle_effects(self, stations):
        for station in stations:
            if (station.station_type == StationType.STOVE and station.item and 
                station.item.item_type == ItemType.RAW_PATTY and station.cooking_start_time > 0):
                for i in range(3):
                    offset = math.sin(self.animation_time * 2 + i) * 5
                    y_pos = station.y - 20 - i * 10 - (self.animation_time % 20) * 2
                    alpha = max(0, 100 - i * 30 - int((self.animation_time % 20) * 5))
                    if alpha > 0:
                        steam = pygame.Surface((20, 20), pygame.SRCALPHA)
                        pygame.draw.circle(steam, (255, 255, 255, alpha), (10, 10), 8)
                        self.screen.blit(steam, (int(station.x + offset - 10), int(y_pos)))
    
    def _update_customers(self, model):
        # Remove customers for completed/expired orders
        for order_id in list(self.customers.keys()):
            if order_id not in [o.id for o in model.orders]:
                completed_info = next((c for c in model.completed_orders if c['id'] == order_id), None)
                if completed_info:
                    if completed_info['type'] == 'overcooked':
                        self.customers[order_id]['leaving'] = True
                        self.customers[order_id]['expression'] = 'overcooked'
                    elif completed_info['type'] == 'expired':
                        self.customers[order_id]['leaving'] = True
                        self.customers[order_id]['expression'] = 'angry'
                    elif completed_info['type'] == 'completed':
                        self.customers[order_id]['leaving'] = True
                        self.customers[order_id]['expression'] = 'happy'
                else:
                    if order_id in self.customers:
                        del self.customers[order_id]
        
        # Calculate spacing for customers based on the current number of orders
        num_orders = len(model.orders)
        available_width = self.width - 300  # Leave margins
        spacing = min(250, available_width // max(num_orders, 1)) if num_orders > 0 else 250
        start_x = 150

        # Add new customers for new orders
        for idx, order in enumerate(model.orders):
            if order.id not in self.customers:
                target_x = start_x + idx * spacing
                self.customers[order.id] = {
                    'x': self.width + 50, 
                    'target_x': target_x, 
                    'y': 550,  # Fixed y position in customer area
                    'waiting': False,
                    'leaving': False, 
                    'animation_offset': 0, 
                    'expression': 'waiting',
                    'order_type': order.items_needed[0] if order.items_needed else None,
                    'order_index': idx
                }
        
        # Update customer positions and expressions
        for order_id, customer in list(self.customers.items()):
            if not customer['leaving']:
                order_idx = next((i for i, o in enumerate(model.orders) if o.id == order_id), -1)
                if order_idx >= 0:
                    customer['order_index'] = order_idx
                    customer['target_x'] = start_x + order_idx * spacing
            
            if customer['leaving']:
                customer['x'] += 4
                if customer['x'] > self.width + 150:
                    if order_id in self.customers:
                        del self.customers[order_id]
            elif not customer['waiting']:
                # Move towards target position
                if abs(customer['x'] - customer['target_x']) > 5:
                    if customer['x'] > customer['target_x']:
                        customer['x'] -= 3
                    else:
                        customer['x'] += 3
                else:
                    customer['x'] = customer['target_x']
                    customer['waiting'] = True
            
            customer['animation_offset'] = math.sin(self.animation_time + order_id) * 2
            
            # Update expression based on order time
            if not customer['leaving'] and order_id in [o.id for o in model.orders]:
                order = next((o for o in model.orders if o.id == order_id), None)
                if order:
                    if order.time_remaining < 10:
                        customer['expression'] = 'angry'
                    elif order.time_remaining < 30:
                        customer['expression'] = 'worried'
                    else:
                        customer['expression'] = 'waiting'
    
    def _draw_customers(self):
        for customer in self.customers.values():
            x, y = customer['x'], int(customer['y'] + customer['animation_offset'])
            expression = customer.get('expression', 'waiting')
            order_type = customer.get('order_type')
            
            # Better customer body - rounded with clothing details
            # Legs
            pygame.draw.rect(self.screen, (50, 50, 100), (x - 8, y + 15, 6, 20), border_radius=3)
            pygame.draw.rect(self.screen, (50, 50, 100), (x + 2, y + 15, 6, 20), border_radius=3)
            # Shoes
            pygame.draw.ellipse(self.screen, (40, 40, 40), (x - 10, y + 33, 8, 6))
            pygame.draw.ellipse(self.screen, (40, 40, 40), (x + 2, y + 33, 8, 6))
            
            # Body - shirt
            pygame.draw.ellipse(self.screen, (100, 150, 200), (x - 15, y - 5, 30, 25))
            # Collar
            pygame.draw.line(self.screen, (80, 120, 160), (x - 5, y - 3), (x - 10, y + 5), 2)
            pygame.draw.line(self.screen, (80, 120, 160), (x + 5, y - 3), (x + 10, y + 5), 2)
            
            # Arms
            pygame.draw.rect(self.screen, (255, 220, 177), (x - 20, y, 8, 15), border_radius=4)
            pygame.draw.rect(self.screen, (255, 220, 177), (x + 12, y, 8, 15), border_radius=4)
            pygame.draw.ellipse(self.screen, (255, 210, 167), (x - 22, y + 12, 10, 8))
            pygame.draw.ellipse(self.screen, (255, 210, 167), (x + 12, y + 12, 10, 8))
            
            # Neck
            pygame.draw.rect(self.screen, (255, 220, 177), (x - 4, y - 8, 8, 6))
            
            # Head
            pygame.draw.circle(self.screen, (255, 220, 177), (x, y - 15), 14)
            
            # Hair
            pygame.draw.arc(self.screen, (80, 50, 30), (x - 14, y - 28, 28, 20), 0, 3.14, 3)
            
            # Eyes
            pygame.draw.circle(self.screen, (255, 255, 255), (x - 5, y - 17), 4)
            pygame.draw.circle(self.screen, (255, 255, 255), (x + 5, y - 17), 4)
            pygame.draw.circle(self.screen, (50, 50, 50), (x - 5, y - 16), 3)
            pygame.draw.circle(self.screen, (50, 50, 50), (x + 5, y - 16), 3)
            
            # Eyebrows and mouth based on expression
            if expression == 'angry' or expression == 'overcooked':
                # Angry eyebrows
                pygame.draw.line(self.screen, (50, 50, 50), (x - 8, y - 21), (x - 2, y - 23), 2)
                pygame.draw.line(self.screen, (50, 50, 50), (x + 2, y - 23), (x + 8, y - 21), 2)
                # Frown
                pygame.draw.arc(self.screen, (50, 50, 50), (x - 6, y - 8, 12, 8), 3.14, 6.28, 2)
            elif expression == 'worried':
                # Worried eyebrows
                pygame.draw.line(self.screen, (50, 50, 50), (x - 8, y - 22), (x - 2, y - 21), 2)
                pygame.draw.line(self.screen, (50, 50, 50), (x + 2, y - 21), (x + 8, y - 22), 2)
                # Straight mouth
                pygame.draw.line(self.screen, (50, 50, 50), (x - 5, y - 9), (x + 5, y - 9), 2)
            elif expression == 'happy':
                # Happy eyebrows
                pygame.draw.arc(self.screen, (50, 50, 50), (x - 8, y - 24, 6, 4), 0, 3.14, 2)
                pygame.draw.arc(self.screen, (50, 50, 50), (x + 2, y - 24, 6, 4), 0, 3.14, 2)
                # Big smile
                pygame.draw.arc(self.screen, (50, 50, 50), (x - 7, y - 14, 14, 10), 0, 3.14, 2)
            else:  # waiting
                # Normal eyebrows
                pygame.draw.arc(self.screen, (50, 50, 50), (x - 8, y - 23, 6, 4), 0, 3.14, 1)
                pygame.draw.arc(self.screen, (50, 50, 50), (x + 2, y - 23, 6, 4), 0, 3.14, 1)
                # Slight smile
                pygame.draw.arc(self.screen, (50, 50, 50), (x - 5, y - 13, 10, 6), 0, 3.14, 2)
            
            # Speech bubble with order
            if not customer['leaving'] and order_type and customer['waiting']:
                # Draw speech bubble
                bubble_x, bubble_y = x, y - 60
                bubble_w, bubble_h = 70, 50
                
                # Bubble shadow
                shadow = pygame.Surface((bubble_w + 5, bubble_h + 5), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, 40))
                self.screen.blit(shadow, (bubble_x - bubble_w//2 + 2, bubble_y - bubble_h//2 + 2))
                
                # Main bubble
                pygame.draw.ellipse(self.screen, (255, 255, 255), 
                                  (bubble_x - bubble_w//2, bubble_y - bubble_h//2, bubble_w, bubble_h))
                pygame.draw.ellipse(self.screen, (200, 200, 200), 
                                  (bubble_x - bubble_w//2, bubble_y - bubble_h//2, bubble_w, bubble_h), 2)
                
                # Small bubble tail
                pygame.draw.circle(self.screen, (255, 255, 255), (x - 10, y - 35), 6)
                pygame.draw.circle(self.screen, (200, 200, 200), (x - 10, y - 35), 6, 2)
                pygame.draw.circle(self.screen, (255, 255, 255), (x - 5, y - 42), 4)
                pygame.draw.circle(self.screen, (200, 200, 200), (x - 5, y - 42), 4, 1)
                
                # Draw the order item in bubble
                item_dummy = type('Item', (), {'item_type': order_type, 'chopped': False})()
                self._draw_item(item_dummy, bubble_x, bubble_y - 5, scale=1.2)
                
                # "One X please" text
                order_names = {
                    ItemType.BURGER: "Burger",
                    ItemType.PIZZA: "Pizza",
                    ItemType.SALAD: "Salad"
                }
                order_text = order_names.get(order_type, "Order")
                text_surface = self.small_font.render(order_text, True, (50, 50, 50))
                self.screen.blit(text_surface, text_surface.get_rect(center=(bubble_x, bubble_y + 15)))
            
            # Show "OVERCOOKED!" message if leaving angry due to overcooked food
            if customer['leaving'] and expression == 'overcooked':
                text_surface = self.font.render("OVERCOOKED!", True, (255, 50, 50))
                self.screen.blit(text_surface, text_surface.get_rect(center=(x, y - 80)))
    
    def _draw_chef_character(self, x, y):
        shadow = pygame.Surface((40, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 60), (0, 0, 40, 10))
        self.screen.blit(shadow, (x - 20, y + 25))
        pygame.draw.rect(self.screen, (50, 50, 50), (x - 8, y + 10, 6, 18), border_radius=3)
        pygame.draw.rect(self.screen, (50, 50, 50), (x + 2, y + 10, 6, 18), border_radius=3)
        body_rect = pygame.Rect(x - 14, y - 8, 28, 22)
        pygame.draw.rect(self.screen, self.COLORS['chef_uniform'], body_rect, border_radius=3)
        pygame.draw.rect(self.screen, (220, 220, 220), body_rect, 2, border_radius=3)
        for by in [y - 3, y + 3]:
            pygame.draw.circle(self.screen, (255, 215, 0), (x, by), 2)
        pygame.draw.rect(self.screen, self.COLORS['chef_uniform'], (x - 20, y - 5, 8, 15), border_radius=2)
        pygame.draw.rect(self.screen, self.COLORS['chef_uniform'], (x + 12, y - 5, 8, 15), border_radius=2)
        pygame.draw.circle(self.screen, self.COLORS['chef_skin'], (x - 18, y + 8), 4)
        pygame.draw.circle(self.screen, self.COLORS['chef_skin'], (x + 18, y + 8), 4)
        pygame.draw.circle(self.screen, self.COLORS['chef_skin'], (x, y - 20), 11)
        pygame.draw.circle(self.screen, (255, 255, 255), (x - 4, y - 21), 3)
        pygame.draw.circle(self.screen, (255, 255, 255), (x + 4, y - 21), 3)
        pygame.draw.circle(self.screen, self.COLORS['chef_eyes'], (x - 4, y - 20), 2)
        pygame.draw.circle(self.screen, self.COLORS['chef_eyes'], (x + 4, y - 20), 2)
        # Better mouth - small smile curve
        pygame.draw.arc(self.screen, (200, 100, 100), (x - 4, y - 17, 8, 5), 0, 3.14, 2)
        pygame.draw.rect(self.screen, self.COLORS['chef_hat'], (x - 12, y - 32, 24, 6), border_radius=2)
        pygame.draw.ellipse(self.screen, self.COLORS['chef_hat'], (x - 10, y - 45, 20, 18))
        pygame.draw.ellipse(self.screen, (220, 220, 220), (x - 10, y - 45, 20, 18), 2)
        pygame.draw.line(self.screen, (220, 220, 220), (x - 5, y - 42), (x - 3, y - 35), 1)
        pygame.draw.line(self.screen, (220, 220, 220), (x + 5, y - 42), (x + 3, y - 35), 1)
    
    def _draw_players(self, players):
        for player in players:
            self._draw_chef_character(player.x, player.y)
            if player.held_item:
                bounce = math.sin(self.animation_time * 3) * 2
                self._draw_item(player.held_item, player.x, int(player.y - 50 + bounce))
    
    def _draw_modern_ui(self, model):
        # Score - Top Left (no timer here)
        panel_width, panel_height = 220, 80
        s = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        s.fill((30, 30, 40, 200))
        self.screen.blit(s, (15, 90))
        pygame.draw.rect(self.screen, (255, 215, 0), pygame.Rect(15, 90, panel_width, panel_height), 3, border_radius=8)
        
        # Score only
        score_text = self.large_font.render(f"${model.score}", True, (255, 215, 0))
        score_rect = score_text.get_rect(center=(15 + panel_width // 2, 130))
        self.screen.blit(score_text, score_rect)
        
        # Timer - Separate panel below score
        timer_panel_height = 70
        s = pygame.Surface((panel_width, timer_panel_height), pygame.SRCALPHA)
        s.fill((30, 30, 40, 200))
        self.screen.blit(s, (15, 185))
        pygame.draw.rect(self.screen, (100, 200, 255), pygame.Rect(15, 185, panel_width, timer_panel_height), 3, border_radius=8)
        
        # Show timer or "Waiting..." message
        if model.game_started and model.start_time:
            time_remaining = max(0, model.game_time - (time.time() - model.start_time))
            timer_text = self.font.render(f"⏱ {int(time_remaining // 60):02d}:{int(time_remaining % 60):02d}", True, (255, 255, 255))
        else:
            timer_text = self.font.render("Waiting...", True, (150, 150, 150))
        timer_rect = timer_text.get_rect(center=(15 + panel_width // 2, 220))
        self.screen.blit(timer_text, timer_rect)
        
        # Orders Panel - Top Right (much clearer, no overlap with ingredients)
        order_names = {
            ItemType.BURGER: ("🍔", "Burger", (255, 200, 100)), 
            ItemType.PIZZA: ("🍕", "Pizza", (255, 180, 50)), 
            ItemType.SALAD: ("🥗", "Salade", (150, 255, 150))
        }
        
        orders_title_y = 90
        title_surface = self.large_font.render("ORDERS", True, (255, 255, 255))
        self.screen.blit(title_surface, (self.width - 270, orders_title_y))
        
        for i, order in enumerate(model.orders):
            panel_x = self.width - 280
            panel_y = 140 + i * 110
            panel_w, panel_h = 260, 100
            
            # Background with shadow
            shadow = pygame.Surface((panel_w + 5, panel_h + 5), pygame.SRCALPHA)
            shadow.fill((0, 0, 0, 80))
            self.screen.blit(shadow, (panel_x + 3, panel_y + 3))
            
            s = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            s.fill((30, 30, 40, 220))
            self.screen.blit(s, (panel_x, panel_y))
            
            item_type = order.items_needed[0] if order.items_needed else None
            if item_type and item_type in order_names:
                emoji, name, color = order_names[item_type]
                border_color = (255, 50, 50) if order.time_remaining < 10 else color
                pygame.draw.rect(self.screen, border_color, (panel_x, panel_y, panel_w, panel_h), 4, border_radius=10)
                
                # Order number and item
                order_num_text = self.font.render(f"Order #{i+1}", True, (200, 200, 200))
                self.screen.blit(order_num_text, (panel_x + 15, panel_y + 12))
                
                # Item icon (larger and clearer)
                item_dummy = type('Item', (), {'item_type': item_type, 'chopped': False})()
                self._draw_item(item_dummy, panel_x + 40, panel_y + 55, scale=1.5)
                
                # Item name
                item_name_text = self.font.render(name, True, (255, 255, 255))
                self.screen.blit(item_name_text, (panel_x + 80, panel_y + 45))
                
                # Timer bar
                time_ratio = max(0, min(1, order.time_remaining / 60.0))
                bar_x, bar_y = panel_x + 15, panel_y + 75
                bar_w, bar_h = panel_w - 30, 15
                
                # Bar background
                pygame.draw.rect(self.screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=8)
                
                # Bar fill with color gradient
                if time_ratio > 0.5:
                    bar_color = (0, 255, 100)
                elif time_ratio > 0.25:
                    bar_color = (255, 200, 0)
                else:
                    bar_color = (255, 50, 50)
                    # Pulse effect when time is critical
                    if order.time_remaining < 10:
                        pulse = int(abs(math.sin(self.animation_time * 4)) * 50)
                        bar_color = (255, pulse, pulse)
                
                pygame.draw.rect(self.screen, bar_color, 
                               (bar_x + 2, bar_y + 2, int((bar_w - 4) * time_ratio), bar_h - 4), 
                               border_radius=6)
                
                # Time remaining text
                time_text = self.small_font.render(f"{int(order.time_remaining)}s", True, (255, 255, 255))
                self.screen.blit(time_text, (bar_x + bar_w - 35, bar_y - 2))
        
        # Controls Panel - Bottom Right
        controls_w, controls_h = 240, 115
        s = pygame.Surface((controls_w, controls_h), pygame.SRCALPHA)
        s.fill((30, 30, 40, 200))
        self.screen.blit(s, (self.width - controls_w - 15, self.height - controls_h - 15))
        pygame.draw.rect(self.screen, (100, 200, 255), 
                        pygame.Rect(self.width - controls_w - 15, self.height - controls_h - 15, 
                                  controls_w, controls_h), 3, border_radius=8)
        
        controls = [
            "SPACE: Pick/Place",
            "C: Chop", 
            "Arrows: Move",
            "B: Toggle Bot",
            "ESC: Quit"
        ]
        
        for i, text in enumerate(controls):
            text_surface = self.small_font.render(text, True, (255, 255, 255))
            self.screen.blit(text_surface, (self.width - controls_w, self.height - controls_h + i * 21))
    
    def _draw_tomato(self, x, y, chopped=False, alpha=255, scale=1.0):
        radius = int(9 * scale)
        if chopped:
            for i in range(3):
                pygame.draw.circle(self.screen, (220, 50, 50), (x + int((i - 1) * 6 * scale), y), int(5 * scale))
                pygame.draw.circle(self.screen, (255, 100, 100), (x + int((i - 1) * 6 * scale), y), int(3 * scale))
        else:
            pygame.draw.circle(self.screen, (220, 50, 50), (x, y), radius)
            pygame.draw.circle(self.screen, (180, 30, 30), (x, y), radius, 1)
            pygame.draw.line(self.screen, (50, 150, 50), (x, y - radius), (x, y - int(13 * scale)), 2)
            pygame.draw.circle(self.screen, (50, 150, 50), (x, y - radius), int(3 * scale))
            pygame.draw.circle(self.screen, (255, 150, 150), (x - int(3 * scale), y - int(3 * scale)), int(2 * scale))
    
    def _draw_lettuce(self, x, y, chopped=False, alpha=255, scale=1.0):
        if chopped:
            pygame.draw.circle(self.screen, (100, 200, 100), (x - int(4 * scale), y - int(2 * scale)), int(4 * scale))
            pygame.draw.circle(self.screen, (120, 220, 120), (x + int(4 * scale), y), int(4 * scale))
            pygame.draw.circle(self.screen, (80, 180, 80), (x, y + int(3 * scale)), int(4 * scale))
        else:
            s = int(8 * scale)
            points = [(x - s, y), (x - int(6 * scale), y - int(6 * scale)), (x - int(2 * scale), y - s),
                     (x + int(2 * scale), y - s), (x + int(6 * scale), y - int(6 * scale)), (x + s, y),
                     (x + int(6 * scale), y + int(6 * scale)), (x, y + s), (x - int(6 * scale), y + int(6 * scale))]
            pygame.draw.polygon(self.screen, (100, 200, 100), points)
            pygame.draw.polygon(self.screen, (80, 180, 80), points, 1)
            pygame.draw.line(self.screen, (80, 180, 80), (x, y - int(6 * scale)), (x, y + int(6 * scale)), 1)
    
    def _draw_bread(self, x, y, alpha=255, scale=1.0):
        w, h = int(20 * scale), int(12 * scale)
        pygame.draw.ellipse(self.screen, (210, 180, 140), (x - w//2, y - h//2, w, h))
        pygame.draw.ellipse(self.screen, (180, 150, 110), (x - w//2, y - h//2, w, h), 1)
    
    def _draw_patty(self, x, y, cooked=False, burnt=False, alpha=255, scale=1.0):
        w, h = int(20 * scale), int(8 * scale)
        if burnt:
            pygame.draw.ellipse(self.screen, (30, 20, 15), (x - w//2, y - h//2, w, h))
            pygame.draw.ellipse(self.screen, (20, 10, 5), (x - w//2, y - h//2, w, h), 1)
            for i in range(3):
                pygame.draw.line(self.screen, (10, 5, 0), (x - int(8 * scale), y - 3 + i * 3), (x + int(8 * scale), y - 3 + i * 3), 1)
        elif cooked:
            pygame.draw.ellipse(self.screen, (100, 50, 25), (x - w//2, y - h//2, w, h))
            pygame.draw.ellipse(self.screen, (80, 40, 20), (x - w//2, y - h//2, w, h), 1)
            for i in range(3):
                pygame.draw.line(self.screen, (60, 30, 15), (x - int(8 * scale), y - 3 + i * 3), (x + int(8 * scale), y - 3 + i * 3), 1)
        else:
            pygame.draw.ellipse(self.screen, (200, 80, 80), (x - w//2, y - h//2, w, h))
            pygame.draw.ellipse(self.screen, (180, 60, 60), (x - w//2, y - h//2, w, h), 1)
    
    def _draw_burger(self, x, y, alpha=255, scale=1.0):
        s = int(scale * 12)
        pygame.draw.ellipse(self.screen, (210, 180, 140), (x - s, y - s, s*2, int(10 * scale)))
        pygame.draw.ellipse(self.screen, (180, 150, 110), (x - s, y - s, s*2, int(10 * scale)), 1)
        for seed_x in [x - int(6 * scale), x, x + int(6 * scale)]:
            pygame.draw.circle(self.screen, (240, 230, 200), (seed_x, y - int(8 * scale)), 1)
        pygame.draw.ellipse(self.screen, (100, 200, 100), (x - int(14 * scale), y - int(6 * scale), int(28 * scale), int(5 * scale)))
        pygame.draw.ellipse(self.screen, (220, 50, 50), (x - int(13 * scale), y - int(2 * scale), int(26 * scale), int(4 * scale)))
        pygame.draw.ellipse(self.screen, (100, 50, 25), (x - int(11 * scale), y + int(1 * scale), int(22 * scale), int(5 * scale)))
        pygame.draw.ellipse(self.screen, (210, 180, 140), (x - s, y + int(5 * scale), s*2, int(6 * scale)))
        pygame.draw.ellipse(self.screen, (180, 150, 110), (x - s, y + int(5 * scale), s*2, int(6 * scale)), 1)
    
    def _draw_cheese(self, x, y, alpha=255, scale=1.0):
        w, h = int(36 * scale), int(28 * scale)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        points = [(int(2 * scale), int(26 * scale)), (int(18 * scale), int(2 * scale)), (int(34 * scale), int(26 * scale))]
        pygame.draw.polygon(s, (255, 215, 0, alpha), points)
        pygame.draw.polygon(s, (200, 170, 0, alpha), points, 1)
        for cx, cy, r in [(int(16 * scale), int(12 * scale), int(3 * scale)), 
                          (int(10 * scale), int(18 * scale), int(2 * scale)), 
                          (int(24 * scale), int(18 * scale), int(2 * scale))]:
            pygame.draw.circle(s, (240, 220, 80, alpha), (cx, cy), r)
        self.screen.blit(s, (x - w//2, y - h//2))
    
    def _draw_pizza(self, x, y, finished=True, alpha=255, scale=1.0):
        radius = int(18 * scale)
        # Pâte
        pygame.draw.circle(self.screen, (240, 200, 140), (x, y), radius)
        pygame.draw.circle(self.screen, (200, 160, 100), (x, y), radius, 1)

        if finished:
            # Pizza cuite (avec fromage fondu et garnitures)
            pygame.draw.circle(self.screen, (200, 50, 50), (x, y), int(14 * scale))
            cheese_surface = pygame.Surface((int(36 * scale), int(36 * scale)), pygame.SRCALPHA)
            pygame.draw.circle(cheese_surface, (255, 230, 120, alpha), (int(18 * scale), int(18 * scale)), int(11 * scale))
            self.screen.blit(cheese_surface, (x - int(18 * scale), y - int(18 * scale)))
            for dx, dy in [(-6, -4), (4, 0), (0, 6), (7, 5), (-7, 3)]:
                pygame.draw.circle(self.screen, (180, 40, 40), (int(x + dx * scale), int(y + dy * scale)), int(3 * scale))
                pygame.draw.circle(self.screen, (220, 90, 90), (int(x + dx * scale + 1), int(y + dy * scale - 1)), int(2 * scale))
        else:
            # Pizza non cuite (juste les ingrédients posés)
            pygame.draw.circle(self.screen, (220, 60, 60), (x, y), int(14 * scale)) # Sauce
            pygame.draw.circle(self.screen, (255, 255, 180), (x, y), int(12 * scale)) # Fromage non fondu
            for dx, dy in [(-6, -4), (4, 0), (0, 6)]:
                pygame.draw.circle(self.screen, (190, 50, 50), (int(x + dx * scale), int(y + dy * scale)), int(3 * scale))
    
    def _draw_item(self, item, x, y, alpha=255, scale=1.0):
        chopped = getattr(item, 'chopped', False)
        if item.item_type == ItemType.TOMATO:
            self._draw_tomato(x, y, chopped, alpha, scale)
        elif item.item_type == ItemType.LETTUCE:
            self._draw_lettuce(x, y, chopped, alpha, scale)
        elif item.item_type == ItemType.BREAD:
            self._draw_bread(x, y, alpha, scale)
        elif item.item_type == ItemType.RAW_PATTY:
            self._draw_patty(x, y, cooked=False, burnt=False, alpha=alpha, scale=scale)
        elif item.item_type == ItemType.COOKED_PATTY:
            self._draw_patty(x, y, cooked=True, burnt=False, alpha=alpha, scale=scale)
        elif item.item_type == ItemType.BURNT_PATTY:
            self._draw_patty(x, y, cooked=False, burnt=True, alpha=alpha, scale=scale)
        elif item.item_type == ItemType.BURGER:
            self._draw_burger(x, y, alpha, scale)
        elif item.item_type == ItemType.CHEESE:
            self._draw_cheese(x, y, alpha, scale)
        elif item.item_type == ItemType.UNCOOKED_PIZZA:
            self._draw_pizza(x, y, finished=False, alpha=alpha, scale=scale)
        elif item.item_type == ItemType.PIZZA:
            self._draw_pizza(x, y, finished=True, alpha=alpha, scale=scale)
        elif item.item_type == ItemType.SALAD:
            self._draw_lettuce(x - 5, y, chopped=True, alpha=alpha, scale=scale)
            self._draw_tomato(x + 5, y, chopped=True, alpha=alpha, scale=scale)
        else:
            color = self.COLORS.get(item.item_type.value, (255, 255, 255))
            pygame.draw.circle(self.screen, color, (x, y), int(8 * scale))
