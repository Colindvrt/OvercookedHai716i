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
    ingredient_type: Optional[ItemType] = None
    contents: List[Item] = field(default_factory=list)

@dataclass
class Order:
    items_needed: List[ItemType]
    time_remaining: float = 60.0

class GameModel:
    def __init__(self):
        self.players: List[Player] = [Player(100, 100)]
        self.stations: List[Station] = []
        self.orders: List[Order] = []
        self.score = 0
        self.game_time = 300.0
        self.start_time = time.time()
        
        self._setup_kitchen()
        self._generate_order()
    
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
            # Choisir un type de plat au hasard
            possible_orders = [ItemType.BURGER, ItemType.PIZZA]
            chosen = random.choice(possible_orders)
            order = Order([chosen])
            self.orders.append(order)
            print(f"Nouvelle commande: {chosen.value.upper()}")
    
    def update(self, delta_time: float):
        """Met à jour le modèle de jeu"""
        # Mise à jour du temps des commandes
        for order in self.orders[:]:
            order.time_remaining -= delta_time
            if order.time_remaining <= 0:
                print(f"Commande expirée: {order.items_needed[0].value}")
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
        if station.item and station.item.item_type in [ItemType.BURGER, ItemType.PIZZA]:
            if not player.held_item:
                player.held_item = station.item
                station.item = None
            return
        
        # Si le joueur pose un ingrédient
        if player.held_item:
            held = player.held_item
            
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
            # Reprendre le dernier ingrédient
            if station.contents:
                last = station.contents.pop()
                player.held_item = last
    
    def _check_recipe_completion(self, station: Station):
        """Vérifie si les ingrédients forment un plat complet"""
        types = {item.item_type for item in station.contents}
        
        # Burger: pain + steak cuit + tomate coupée + salade coupée
        if (ItemType.BREAD in types and 
            ItemType.COOKED_PATTY in types and
            any(i.item_type == ItemType.TOMATO and i.chopped for i in station.contents) and
            any(i.item_type == ItemType.LETTUCE and i.chopped for i in station.contents)):
            station.item = Item(ItemType.BURGER)
            station.contents.clear()
            print("Burger assemblé!")
        
        # Pizza: pain + tomate coupée + fromage
        elif (ItemType.BREAD in types and
              any(i.item_type == ItemType.TOMATO and i.chopped for i in station.contents) and
              ItemType.CHEESE in types):
            station.item = Item(ItemType.PIZZA)
            station.contents.clear()
            print("Pizza assemblée!")
        
        
    
    def _handle_delivery(self, player: Player):
        """Gère la livraison des plats"""
        if not player.held_item:
            return
        
        delivered_item = player.held_item.item_type
        
        # Chercher une commande correspondante
        for order in self.orders[:]:
            if delivered_item in order.items_needed:
                self.orders.remove(order)
                self.score += 100
                player.held_item = None
                print(f"Livraison réussie: {delivered_item.value.upper()} (+100 points)")
                return
        
        print(f"Aucune commande pour {delivered_item.value}")
    
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
                    print(f"{closest_cutting_board.item.item_type.value.capitalize()} coupé(e)!")