from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import time
import random

class ItemType(Enum):
    TOMATO = "tomato"
    LETTUCE = "lettuce"
    BREAD = "bread"
    COOKED_PATTY = "cooked_patty"
    RAW_PATTY = "raw_patty"
    BURNT_PATTY = "burnt_patty"
    CHEESE = "cheese"
    BURGER = "burger"
    PIZZA = "pizza"
    SALAD = "salad"

class StationType(Enum):
    INGREDIENT_SPAWN = "ingredient_spawn"
    CUTTING_BOARD = "cutting_board"
    STOVE = "stove"
    ASSEMBLY = "assembly"
    DELIVERY = "delivery"

@dataclass
class Item:
    item_type: ItemType
    chopped: bool = False
    overcooked: bool = False

@dataclass
class Player:
    x: int
    y: int
    held_item: Optional[Item] = None

@dataclass
class Station:
    x: int
    y: int
    station_type: StationType
    item: Optional[Item] = None
    cooking_start_time: float = 0.0
    cooking_duration: float = 3.0
    overcook_duration: float = 5.0
    ingredient_type: Optional[ItemType] = None
    contents: List[Item] = field(default_factory=list)

@dataclass
class Order:
    items_needed: List[ItemType]
    time_remaining: float = 60.0
    expired: bool = False
    id: int = 0  # Add unique ID for tracking

class GameModel:
    def __init__(self):
        self.players: List[Player] = [Player(100, 100)]
        self.stations: List[Station] = []
        self.orders: List[Order] = []
        self.score = 0
        self.game_time = 300.0
        self.start_time = None  # Will be set when first order arrives
        self.next_order_id = 0  # Track order IDs
        self.completed_orders = []  # Track recently completed orders
        self.next_order_time = time.time() + 3.0  # First order in 3 seconds
        self.game_started = False  # Track if game has started
        
        self._setup_kitchen()
        # Don't generate order immediately - wait for timer
    
    def _setup_kitchen(self):
        """Configuration de la cuisine avec tous les ingrédients"""
        # Spawn points (ligne du haut)
        self.stations.extend([
            Station(100, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.TOMATO),
            Station(200, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.LETTUCE),
            Station(300, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.BREAD),
            Station(400, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.RAW_PATTY),
            Station(500, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.CHEESE),
        ])
        
        # Stations de travail (ligne du milieu)
        self.stations.extend([
            Station(150, 200, StationType.CUTTING_BOARD),
            Station(250, 200, StationType.CUTTING_BOARD),
            Station(350, 200, StationType.STOVE),
            Station(450, 200, StationType.STOVE),
        ])
        
        # Stations finales
        self.stations.extend([
            Station(250, 300, StationType.ASSEMBLY),
            Station(400, 300, StationType.DELIVERY),
        ])
    
    def _generate_order(self):
        """Génère une nouvelle commande aléatoire"""
        if len(self.orders) < 3:
            possible_orders = [ItemType.BURGER, ItemType.PIZZA]
            chosen = random.choice(possible_orders)
            order = Order([chosen], id=self.next_order_id)
            self.next_order_id += 1
            self.orders.append(order)
            print(f"Nouvelle commande #{order.id}: {chosen.value.upper()}")
            
            # Start the game timer when first order arrives
            if not self.game_started:
                self.game_started = True
                self.start_time = time.time()
                print("⏱ Game timer started!")
            
            # Schedule next order with random delay (between 15-30 seconds)
            self.next_order_time = time.time() + random.uniform(15.0, 30.0)
    
    def update(self, delta_time: float):
        """Met à jour le modèle de jeu"""
        current_time = time.time()
        
        # Clean up old completed orders
        self.completed_orders = [o for o in self.completed_orders if current_time - o['time'] < 3.0]
        
        # Check if it's time to generate a new order
        if current_time >= self.next_order_time and len(self.orders) < 3:
            self._generate_order()
        
        # Only update order timers if game has started
        if self.game_started:
            # Mise à jour du temps des commandes
            for order in self.orders[:]:
                if not order.expired:
                    order.time_remaining -= delta_time
                    if order.time_remaining <= 0:
                        order.expired = True
                        self.score -= 20
                        print(f"⏰ Commande expirée: {order.items_needed[0].value} (-20$)")
                        self.orders.remove(order)
                        # Mark as expired for animation
                        self.completed_orders.append({
                            'id': order.id,
                            'type': 'expired',
                            'time': current_time
                        })
        
        # Mise à jour des stations (cuisson et sur-cuisson)
        for station in self.stations:
            if (station.station_type == StationType.STOVE and 
                station.item and station.item.item_type == ItemType.RAW_PATTY and
                station.cooking_start_time > 0):
                
                cooking_time = current_time - station.cooking_start_time
                
                # Cuit parfaitement
                if cooking_time >= station.cooking_duration and cooking_time < station.overcook_duration:
                    if station.item.item_type != ItemType.COOKED_PATTY:
                        station.item = Item(ItemType.COOKED_PATTY)
                        print("✅ Steak parfaitement cuit!")
                
                # Trop cuit / brûlé
                elif cooking_time >= station.overcook_duration:
                    if station.item.item_type != ItemType.BURNT_PATTY:
                        station.item = Item(ItemType.BURNT_PATTY, overcooked=True)
                        print("🔥 Steak brûlé! (Overcooked)")
                        station.cooking_start_time = 0.0
    
    def move_player(self, player_index: int, dx: int, dy: int):
        """Déplace un joueur"""
        if 0 <= player_index < len(self.players):
            player = self.players[player_index]
            new_x = max(0, min(750, player.x + dx * 50))
            new_y = max(0, min(550, player.y + dy * 50))
            player.x = new_x
            player.y = new_y
    
    def interact_with_station(self, player_index: int):
        """Gère l'interaction joueur-station"""
        if player_index >= len(self.players):
            return
        
        player = self.players[player_index]
        
        # Trouver la station la plus proche
        closest_station = None
        min_distance = float('inf')
        
        for station in self.stations:
            distance = abs(player.x - station.x) + abs(player.y - station.y)
            if distance < min_distance and distance <= 70:
                min_distance = distance
                closest_station = station
        
        if closest_station:
            self._handle_station_interaction(player, closest_station)
    
    def _handle_station_interaction(self, player: Player, station: Station):
        """Gère l'interaction spécifique avec une station"""
        if station.station_type == StationType.INGREDIENT_SPAWN:
            if not player.held_item and station.ingredient_type:
                player.held_item = Item(station.ingredient_type)
        
        elif station.station_type == StationType.CUTTING_BOARD:
            if player.held_item and not station.item:
                if player.held_item.item_type in [ItemType.TOMATO, ItemType.LETTUCE]:
                    station.item = player.held_item
                    player.held_item = None
            elif station.item and not player.held_item:
                player.held_item = station.item
                station.item = None
        
        elif station.station_type == StationType.STOVE:
            if player.held_item and not station.item:
                if player.held_item.item_type == ItemType.RAW_PATTY:
                    station.item = player.held_item
                    player.held_item = None
                    station.cooking_start_time = time.time()
            elif station.item and not player.held_item:
                player.held_item = station.item
                station.item = None
                station.cooking_start_time = 0.0
        
        elif station.station_type == StationType.ASSEMBLY:
            self._handle_assembly(player, station)
        
        elif station.station_type == StationType.DELIVERY:
            self._handle_delivery(player)
    
    def _handle_assembly(self, player: Player, station: Station):
        """Gère l'assemblage multi-recettes"""
        # Si un plat fini est prêt, le prendre
        if station.item and station.item.item_type in [ItemType.BURGER, ItemType.PIZZA, ItemType.SALAD]:
            if not player.held_item:
                player.held_item = station.item
                station.item = None
                # Check if overcooked
                if getattr(player.held_item, 'overcooked', False):
                    print("⚠️ Picked up overcooked dish - cannot be served!")
            return
        
        # Si le joueur pose un ingrédient
        if player.held_item:
            held = player.held_item
            
            # Special case: if holding a finished dish and assembly has contents, dispose of old contents
            if held.item_type in [ItemType.BURGER, ItemType.PIZZA, ItemType.SALAD]:
                if station.contents:
                    print("🗑️ Clearing partial ingredients from assembly station")
                    station.contents.clear()
                return
            
            # Ne pas accepter de viande brûlée
            if held.item_type == ItemType.BURNT_PATTY:
                print("❌ Viande brûlée, impossible de l'utiliser!")
                return
            
            # Premier ingrédient : doit être le pain (base)
            if not station.contents:
                if held.item_type == ItemType.BREAD:
                    station.contents.append(held)
                    player.held_item = None
                return
            
            # Ajouter l'ingrédient s'il n'est pas déjà présent
            if not any(i.item_type == held.item_type for i in station.contents):
                # Vérifier si l'ingrédient doit être coupé
                if held.item_type in [ItemType.TOMATO, ItemType.LETTUCE] and not held.chopped:
                    return
                
                station.contents.append(held)
                player.held_item = None
                
                # Vérifier si une recette est complète
                self._check_recipe_completion(station)
        else:
            # Reprendre le dernier ingrédient (allows salvaging partial work)
            if station.contents:
                last = station.contents.pop()
                player.held_item = last
                print(f"📦 Picked up {last.item_type.value} from assembly")
    
    def _check_recipe_completion(self, station: Station):
        """Vérifie si les ingrédients forment un plat complet"""
        types = {item.item_type for item in station.contents}
        
        # Vérifier si un item est overcook
        has_overcooked = any(getattr(item, 'overcooked', False) for item in station.contents)
        
        # Burger: pain + steak cuit + tomate coupée + salade coupée
        if (ItemType.BREAD in types and 
            ItemType.COOKED_PATTY in types and
            any(i.item_type == ItemType.TOMATO and i.chopped for i in station.contents) and
            any(i.item_type == ItemType.LETTUCE and i.chopped for i in station.contents)):
            burger = Item(ItemType.BURGER)
            burger.overcooked = has_overcooked
            station.item = burger
            station.contents.clear()
            if has_overcooked:
                print("🍔 Burger assemblé (mais trop cuit!)")
            else:
                print("🍔 Burger assemblé!")
        
        # Pizza: pain + tomate coupée + fromage
        elif (ItemType.BREAD in types and
              any(i.item_type == ItemType.TOMATO and i.chopped for i in station.contents) and
              ItemType.CHEESE in types):
            pizza = Item(ItemType.PIZZA)
            pizza.overcooked = has_overcooked
            station.item = pizza
            station.contents.clear()
            if has_overcooked:
                print("🍕 Pizza assemblée (mais trop cuite!)")
            else:
                print("🍕 Pizza assemblée!")
        
        # Salade: salade coupée + tomate coupée
        elif (any(i.item_type == ItemType.LETTUCE and i.chopped for i in station.contents) and
              any(i.item_type == ItemType.TOMATO and i.chopped for i in station.contents) and
              len(station.contents) == 2):
            station.item = Item(ItemType.SALAD)
            station.contents.clear()
            print("🥗 Salade assemblée!")
    
    def _handle_delivery(self, player: Player):
        """Gère la livraison des plats"""
        if not player.held_item:
            return
        
        delivered_item = player.held_item
        delivered_type = delivered_item.item_type
        is_overcooked = getattr(delivered_item, 'overcooked', False)
        
        # Chercher une commande correspondante
        for order in self.orders[:]:
            if delivered_type in order.items_needed:
                self.orders.remove(order)
                
                # Calculer le score selon qualité et timing
                time_bonus = max(0, int(order.time_remaining / 2))
                
                if is_overcooked:
                    # Penalize overcooked food
                    penalty = 10
                    self.score -= penalty
                    player.held_item = None
                    print(f"😡 OVERCOOKED! {delivered_type.value.upper()} refusé (-{penalty}$)")
                    # Mark as overcooked for animation
                    self.completed_orders.append({
                        'id': order.id,
                        'type': 'overcooked',
                        'time': time.time()
                    })
                else:
                    base_price = 15
                    total = base_price + time_bonus
                    self.score += total
                    player.held_item = None
                    print(f"😄 Livraison parfaite: {delivered_type.value.upper()} (+{total}$ = {base_price}$ + {time_bonus}$ bonus)")
                    # Mark as completed for animation
                    self.completed_orders.append({
                        'id': order.id,
                        'type': 'completed',
                        'time': time.time()
                    })
                return
        
        print(f"❌ Aucune commande pour {delivered_type.value}")
    
    def chop_at_station(self, player_index: int):
        """Découpe un item sur la planche à découper"""
        if player_index >= len(self.players):
            return
        
        player = self.players[player_index]
        closest_cutting_board = None
        min_distance = float('inf')
        
        for station in self.stations:
            if station.station_type == StationType.CUTTING_BOARD:
                distance = abs(player.x - station.x) + abs(player.y - station.y)
                if distance < min_distance and distance <= 70:
                    min_distance = distance
                    closest_cutting_board = station
        
        if closest_cutting_board and closest_cutting_board.item:
            if closest_cutting_board.item.item_type in [ItemType.TOMATO, ItemType.LETTUCE]:
                if not closest_cutting_board.item.chopped:
                    closest_cutting_board.item.chopped = True
                    print(f"🔪 {closest_cutting_board.item.item_type.value.capitalize()} coupé(e)!")