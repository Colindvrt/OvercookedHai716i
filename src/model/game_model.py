from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import time
import random
import pygame

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
    UNCOOKED_PIZZA = "uncooked_pizza"
    SALAD = "salad"

class StationType(Enum):
    INGREDIENT_SPAWN = "ingredient_spawn"
    CUTTING_BOARD = "cutting_board"
    STOVE = "stove"
    ASSEMBLY = "assembly"
    DELIVERY = "delivery"
    FURNACE = "furnace"
    HOLDING = "holding"

@dataclass
class Item:
    item_type: ItemType
    chopped: bool = False
    overcooked: bool = False

@dataclass
class Player:
    x: float
    y: float
    held_item: Optional[Item] = None

@dataclass
class Station:
    x: int
    y: int
    station_type: StationType
    item: Optional[Item] = None
    cooking_start_time: float = 0.0
    cooking_duration: float = 3.0
    overcook_duration: float = 20

    ingredient_type: Optional[ItemType] = None
    contents: List[Item] = field(default_factory=list)

@dataclass
class Order:
    items_needed: List[ItemType]
    time_remaining: float = 60.0
    expired: bool = False
    id: int = 0

class GameModel:
    def __init__(self, num_bots: int = 2):
        self.players: List[Player] = [
            Player(100 + i * 50, 300) for i in range(num_bots)
        ]
        self.stations: List[Station] = []
        self.orders: List[Order] = []
        self.score = 0
        self.game_time = 300.0
        self.start_time = None
        self.next_order_id = 1
        self.completed_orders = []
        self.next_order_time = time.time() + 3.0
        self.game_started = False
        
        self._setup_kitchen()
    
    def _setup_kitchen(self):
        """Configuration dynamique : 1 station par bot"""
        self.stations = []
        # On élargit la cuisine pour faire tenir tout le monde (était 1000)
        width = 1600
        
        # 1. SPAWN POINTS (Fixes)
        spawn_types = [ItemType.TOMATO, ItemType.LETTUCE, ItemType.BREAD, ItemType.RAW_PATTY, ItemType.CHEESE]
        step_spawn = width // (len(spawn_types) + 1)
        for i, ing_type in enumerate(spawn_types):
            self.stations.append(Station((i + 1) * step_spawn, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ing_type))
        
        nb_bots = len(self.players)
        # ✅ NOUVELLE FORMULE : 1 station par bot, comme demandé
        nb_service = nb_bots
        
        # 2. STATIONS DE TRAVAIL (Milieu)
        row2_types = []
        for _ in range(nb_service): row2_types.append(StationType.CUTTING_BOARD)
        for _ in range(nb_service): row2_types.append(StationType.STOVE)
        for _ in range(nb_service): row2_types.append(StationType.FURNACE)
        
        step_row2 = width // (len(row2_types) + 1)
        for i, st_type in enumerate(row2_types):
            self.stations.append(Station((i + 1) * step_row2, 200, st_type))
            
        # 3. ASSEMBLAGE & LIVRAISON (Bas)
        row3_types = []
        for _ in range(nb_service): row3_types.append(StationType.ASSEMBLY)
        row3_types.append(StationType.DELIVERY)
        row3_types.append(StationType.HOLDING)
        
        step_row3 = width // (len(row3_types) + 1)
        for i, st_type in enumerate(row3_types):
            duration = 15.0 if st_type == StationType.HOLDING else 3.0
            self.stations.append(Station((i + 1) * step_row3, 300, st_type, cooking_duration=duration))

    def _generate_order(self):
        possible_orders = [ItemType.BURGER, ItemType.PIZZA, ItemType.SALAD]            
        chosen = random.choice(possible_orders)
        order = Order([chosen], id=self.next_order_id)
        self.next_order_id += 1
        self.orders.append(order)
        print(f"Nouvelle commande #{order.id}: {chosen.value.upper()}")
        
        if not self.game_started:
            self.game_started = True
            self.start_time = time.time()
            print("⏱ Game timer started!")
    
    def update(self, delta_time: float):
        current_time = time.time()
        self.completed_orders = [o for o in self.completed_orders if current_time - o['time'] < 3.0]
        
        # MAINTENIR LE NOMBRE DE COMMANDES = NOMBRE DE BOTS
        target_orders = max(1, len(self.players))
        while len(self.orders) < target_orders:
            self._generate_order()
        
        if self.game_started:
            for order in self.orders[:]:
                if not order.expired:
                    order.time_remaining -= delta_time
                    if order.time_remaining <= 0:
                        order.expired = True
                        penalty = -15
                        self.score += penalty
                        print(f"⏰ Commande expirée: {order.items_needed[0].value} ({penalty}$)")
                        self.orders.remove(order)
                        self.completed_orders.append({'id': order.id, 'type': 'expired', 'time': current_time})
        
        for station in self.stations:
            if (station.station_type in [StationType.STOVE, StationType.FURNACE] and station.item and station.cooking_start_time > 0):
                cooking_time = current_time - station.cooking_start_time
                if cooking_time >= station.cooking_duration and cooking_time < station.overcook_duration:
                    if station.item.item_type == ItemType.RAW_PATTY and station.item.item_type != ItemType.COOKED_PATTY:
                        station.item = Item(ItemType.COOKED_PATTY)
                        print("✅ Steak parfaitement cuit!")
                    elif station.item.item_type == ItemType.UNCOOKED_PIZZA and station.item.item_type != ItemType.PIZZA:
                        station.item = Item(ItemType.PIZZA)
                        print("✅ Pizza cuite à la perfection !")
                elif cooking_time >= station.overcook_duration:
                    if station.item.item_type != ItemType.BURNT_PATTY and station.station_type == StationType.STOVE:
                        station.item = Item(ItemType.BURNT_PATTY, overcooked=True)
                        station.cooking_start_time = 0.0
                    elif station.item.item_type != ItemType.PIZZA and station.station_type == StationType.FURNACE:
                        station.item = Item(ItemType.PIZZA, overcooked=True)
                        station.cooking_start_time = 0.0
            elif (station.station_type == StationType.HOLDING and station.item and not station.item.overcooked and station.cooking_start_time > 0):
                expire_time = current_time - station.cooking_start_time
                if expire_time >= station.cooking_duration:
                    station.item.overcooked = True

    def move_player(self, player_index: int, dx: float, dy: float, is_smooth: bool = False):
        """Déplace un joueur (sans collisions avec les tables)"""
        if 0 <= player_index < len(self.players):
            player = self.players[player_index]
            
            # Distance à parcourir
            step_x = dx if is_smooth else dx * 50
            step_y = dy if is_smooth else dy * 50
            
            # Limites écran (pour ne pas sortir de la fenêtre)
            # On garde une petite marge (25px)
            new_x = max(25, min(1575, player.x + step_x))
            new_y = max(25, min(675, player.y + step_y))
            
            # Application directe sans vérifier les obstacles
            player.x = new_x
            player.y = new_y
    
    def interact_with_station(self, player_index: int):
        if player_index >= len(self.players): return
        player = self.players[player_index]
        closest, min_dist = None, float('inf')
        for station in self.stations:
            dist = abs(player.x - station.x) + abs(player.y - station.y)
            if dist < min_dist and dist <= 75:
                min_dist = dist
                closest = station
        if closest: self._handle_station_interaction(player, closest)
    
    def _handle_station_interaction(self, player: Player, station: Station):
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
        elif station.station_type == StationType.FURNACE:
            if player.held_item and not station.item:
                if player.held_item.item_type == ItemType.UNCOOKED_PIZZA:
                    station.item = player.held_item
                    player.held_item = None
                    station.cooking_start_time = time.time()
            elif station.item and not player.held_item:
                if station.item.item_type == ItemType.PIZZA:
                    player.held_item = station.item
                    station.item = None
                    station.cooking_start_time = 0.0
        elif station.station_type == StationType.HOLDING:
            if player.held_item and not station.item:
                if player.held_item.item_type == ItemType.COOKED_PATTY or \
                   (player.held_item.item_type in [ItemType.TOMATO, ItemType.LETTUCE] and player.held_item.chopped):
                    station.item = player.held_item
                    player.held_item = None
                    station.cooking_start_time = time.time()
            elif station.item and not player.held_item:
                if not station.item.overcooked:
                    player.held_item = station.item
                    station.item = None
                    station.cooking_start_time = 0.0
        elif station.station_type == StationType.ASSEMBLY:
            self._handle_assembly(player, station)
        elif station.station_type == StationType.DELIVERY:
            self._handle_delivery(player)
    
    def _handle_assembly(self, player: Player, station: Station):
        # 1. Si un plat fini est sur la table, on peut le prendre
        if station.item and station.item.item_type in [ItemType.BURGER, ItemType.PIZZA, ItemType.SALAD, ItemType.UNCOOKED_PIZZA]:
            if not player.held_item:
                player.held_item = station.item
                station.item = None
            return
        
        # 2. Si on tient un ingrédient
        if player.held_item:
            held = player.held_item
            
            # Ne pas mettre de déchets ou de plats déjà finis dans le mélange
            if held.item_type in [ItemType.BURGER, ItemType.PIZZA, ItemType.SALAD, ItemType.BURNT_PATTY]:
                return
            
            # Vérifier si l'ingrédient est déjà présent (pas de doublons)
            if not any(i.item_type == held.item_type for i in station.contents):
                # Légumes doivent être coupés
                if held.item_type in [ItemType.TOMATO, ItemType.LETTUCE] and not held.chopped:
                    return
                
                # On ajoute
                station.contents.append(held)
                player.held_item = None
                
                # On vérifie si ça fait une recette
                self._check_recipe_completion(station)
    
    def _check_recipe_completion(self, station: Station):
        types = {item.item_type for item in station.contents}
        has_overcooked = any(getattr(item, 'overcooked', False) for item in station.contents)
        
        # Burger : Ordre indifférent grâce aux Sets
        if (ItemType.BREAD in types and 
            ItemType.COOKED_PATTY in types and
            ItemType.TOMATO in types and # On suppose qu'ils sont coupés car _handle_assembly le vérifie
            ItemType.LETTUCE in types):
            
            station.item = Item(ItemType.BURGER, overcooked=has_overcooked)
            station.contents.clear()
            print("🍔 Burger assemblé!")
        
        # Pizza (Base)
        elif (ItemType.BREAD in types and ItemType.TOMATO in types and ItemType.CHEESE in types):
            station.item = Item(ItemType.UNCOOKED_PIZZA, overcooked=has_overcooked)
            station.contents.clear()
            print("🍕 Pizza non cuite assemblée !")
        
        # Salade
        elif (ItemType.LETTUCE in types and ItemType.TOMATO in types and len(station.contents) == 2):
            station.item = Item(ItemType.SALAD)
            station.contents.clear()
            print("🥗 Salade assemblée!")
    
    def _handle_delivery(self, player: Player):
        if not player.held_item: return
        delivered_type = player.held_item.item_type
        is_overcooked = getattr(player.held_item, 'overcooked', False)

        for order in self.orders[:]:
            if delivered_type in order.items_needed:
                self.orders.remove(order)

                if is_overcooked:
                    # Plat trop cuit = 0$
                    payment = 0
                    print(f"⚠️ Commande trop cuite: {delivered_type.value} (0$)")
                else:
                    base_payment = 15
                    # Bonus 15% si livré dans les 15 premières secondes (60 - 45 = 15)
                    if order.time_remaining >= 45:
                        bonus = base_payment * 0.15
                        payment = int(base_payment + bonus)
                        print(f"⚡ Commande express: {delivered_type.value} (+{payment}$ avec bonus 15%)")
                    else:
                        payment = base_payment
                        print(f"✅ Commande livrée: {delivered_type.value} (+{payment}$)")

                self.score += payment
                player.held_item = None
                self.completed_orders.append({'id': order.id, 'type': 'completed', 'time': time.time()})
                return
        
    def chop_at_station(self, player_index: int):
        if player_index >= len(self.players): return
        player = self.players[player_index]
        closest, min_dist = None, float('inf')
        for station in self.stations:
            if station.station_type == StationType.CUTTING_BOARD:
                dist = abs(player.x - station.x) + abs(player.y - station.y)
                if dist < min_dist and dist <= 75:
                    min_dist = dist
                    closest = station
        if closest and closest.item:
            if closest.item.item_type in [ItemType.TOMATO, ItemType.LETTUCE] and not closest.item.chopped:
                closest.item.chopped = True
                print(f"🔪 {closest.item.item_type.value} coupé!")