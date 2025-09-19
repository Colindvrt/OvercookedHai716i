from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import time

class ItemType(Enum):
    TOMATO = "tomato"
    LETTUCE = "lettuce"
    BREAD = "bread"
    COOKED_PATTY = "cooked_patty"
    RAW_PATTY = "raw_patty"
    BURGER = "burger"

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
    cooking_duration: float = 3.0  # 3 secondes pour cuire
    ingredient_type: Optional[ItemType] = None  # Pour les spawn points
    contents: List[Item] = field(default_factory=list)  # pile d’assemblage

@dataclass
class Order:
    items_needed: List[ItemType]
    time_remaining: float = 60.0  # 60 secondes par commande

class GameModel:
    def __init__(self):
        self.players: List[Player] = [Player(100, 100)]
        self.stations: List[Station] = []
        self.orders: List[Order] = []
        self.score = 0
        self.game_time = 300.0  # 5 minutes de jeu
        self.start_time = time.time()
        
        self._setup_kitchen()
        self._generate_order()
    
    def _setup_kitchen(self):
        """Configuration basique de la cuisine"""
        # Spawn points d'ingrédients (ligne du haut)
        self.stations.extend([
            Station(100, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.TOMATO),
            Station(200, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.LETTUCE),
            Station(300, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.BREAD),
            Station(400, 100, StationType.INGREDIENT_SPAWN, ingredient_type=ItemType.RAW_PATTY),
        ])
        
        # Stations de travail (ligne du milieu)
        self.stations.extend([
            Station(150, 200, StationType.CUTTING_BOARD),
            Station(250, 200, StationType.CUTTING_BOARD),
            Station(350, 200, StationType.STOVE),
            Station(450, 200, StationType.STOVE),
        ])
        
        # Stations finales
        # ⬇️ ASSEMBLY descendu encore de 2 cases (de 400 -> 500)
        self.stations.extend([
            Station(250, 300, StationType.ASSEMBLY),
            Station(400, 300, StationType.DELIVERY),
        ])
    
    def _generate_order(self):
        """Génère une nouvelle commande simple"""
        if len(self.orders) < 3:  # Maximum 3 commandes en même temps
            order = Order([ItemType.BURGER])
            self.orders.append(order)
    
    def update(self, delta_time: float):
        """Met à jour le modèle de jeu"""
        # Mise à jour du temps des commandes
        for order in self.orders[:]:
            order.time_remaining -= delta_time
            if order.time_remaining <= 0:
                self.orders.remove(order)
        
        # Génération de nouvelles commandes
        if len(self.orders) < 2:
            self._generate_order()
        
        # Mise à jour des stations (cuisson)
        current_time = time.time()
        for station in self.stations:
            if (station.station_type == StationType.STOVE and 
                station.item and station.item.item_type == ItemType.RAW_PATTY and
                current_time - station.cooking_start_time >= station.cooking_duration):
                station.item = Item(ItemType.COOKED_PATTY)
                station.cooking_start_time = 0.0
    
    def move_player(self, player_index: int, dx: int, dy: int):
        """Déplace un joueur"""
        if 0 <= player_index < len(self.players):
            player = self.players[player_index]
            new_x = max(0, min(750, player.x + dx * 50))  # Limites de la carte
            new_y = max(0, min(550, player.y + dy * 50))
            player.x = new_x
            player.y = new_y
    
    def interact_with_station(self, player_index: int):
        """Gère l'interaction joueur-station (touche ESPACE)"""
        if player_index >= len(self.players):
            return
        
        player = self.players[player_index]
        
        # Trouver la station la plus proche
        closest_station = None
        min_distance = float('inf')
        
        for station in self.stations:
            distance = abs(player.x - station.x) + abs(player.y - station.y)
            if distance < min_distance and distance <= 70:  # Distance d'interaction
                min_distance = distance
                closest_station = station
        
        if closest_station:
            self._handle_station_interaction(player, closest_station)
        else:
            print("Aucune station à proximité")
    
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
                else:
                    print("Cet item ne peut pas être coupé")
            elif station.item and not player.held_item:
                player.held_item = station.item
                station.item = None
        
        elif station.station_type == StationType.STOVE:
            if player.held_item and not station.item:
                if player.held_item.item_type == ItemType.RAW_PATTY:
                    station.item = player.held_item
                    player.held_item = None
                    station.cooking_start_time = time.time()
                else:
                    print("Seule la viande crue peut être cuite")
            elif station.item and not player.held_item:
                player.held_item = station.item
                station.item = None
                station.cooking_start_time = 0.0
            elif station.item:
                cooking_time = time.time() - station.cooking_start_time
                if cooking_time < station.cooking_duration:
                    remaining = station.cooking_duration - cooking_time
                    print(f"Cuisson en cours... {remaining:.1f}s restantes")
        
        elif station.station_type == StationType.ASSEMBLY:
            # Burger multi-ingrédients : pain d’abord, puis steak cuit, tomate coupée, salade coupée
            def burger_ready(contents: List[Item]) -> bool:
                types = {it.item_type for it in contents}
                has_bread = ItemType.BREAD in types
                has_cooked = ItemType.COOKED_PATTY in types
                has_chopped_tomato = any(it.item_type == ItemType.TOMATO and it.chopped for it in contents)
                has_chopped_lettuce = any(it.item_type == ItemType.LETTUCE and it.chopped for it in contents)
                return has_bread and has_cooked and has_chopped_tomato and has_chopped_lettuce

            if station.item and station.item.item_type == ItemType.BURGER:
                if not player.held_item:
                    player.held_item = station.item
                    station.item = None
                return

            if player.held_item:
                held = player.held_item
                if not station.contents:
                    if held.item_type == ItemType.BREAD:
                        station.contents.append(held)
                        player.held_item = None
                    else:
                        print("Posez d'abord le pain")
                        return
                else:
                    if held.item_type == ItemType.COOKED_PATTY:
                        if any(i.item_type == ItemType.COOKED_PATTY for i in station.contents):
                            print("Steak déjà posé")
                            return
                        station.contents.append(held)
                        player.held_item = None
                    elif held.item_type == ItemType.TOMATO:
                        if not held.chopped:
                            print("La tomate doit être coupée")
                            return
                        if any(i.item_type == ItemType.TOMATO for i in station.contents):
                            print("Tomate déjà posée")
                            return
                        station.contents.append(held)
                        player.held_item = None
                    elif held.item_type == ItemType.LETTUCE:
                        if not held.chopped:
                            print("La salade doit être coupée")
                            return
                        if any(i.item_type == ItemType.LETTUCE for i in station.contents):
                            print("Salade déjà posée")
                            return
                        station.contents.append(held)
                        player.held_item = None
                    else:
                        print("Cet ingrédient ne fait pas partie du burger")
                        return

                if burger_ready(station.contents):
                    station.item = Item(ItemType.BURGER)
                    station.contents.clear()

            else:
                if station.contents:
                    last = station.contents.pop()
                    player.held_item = last
        
        elif station.station_type == StationType.DELIVERY:
            if player.held_item and player.held_item.item_type == ItemType.BURGER:
                for order in self.orders[:]:
                    if ItemType.BURGER in order.items_needed:
                        self.orders.remove(order)
                        self.score += 100
                        player.held_item = None
                        return
    
    def chop_at_station(self, player_index: int):
        """Découpe un item sur la planche à découper la plus proche (touche C)"""
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
                # sinon déjà coupé
