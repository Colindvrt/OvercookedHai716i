from dataclasses import dataclass, field
from typing import List, Optional, Tuple
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
    cooking_start_time: float = 0
    cooking_duration: float = 3.0  # 3 secondes pour cuire
    ingredient_type: Optional[ItemType] = None  # Pour les spawn points

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
        
        # Stations finales (ligne du bas)
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
                station.cooking_start_time = 0
    
    def move_player(self, player_index: int, dx: int, dy: int):
        """Déplace un joueur"""
        if 0 <= player_index < len(self.players):
            player = self.players[player_index]
            new_x = max(0, min(750, player.x + dx * 50))  # Limites de la carte
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
            if distance < min_distance and distance <= 70:  # Distance d'interaction augmentée
                min_distance = distance
                closest_station = station
        
        if closest_station:
            print(f"Interaction avec {closest_station.station_type.value} - Distance: {min_distance}")
            self._handle_station_interaction(player, closest_station)
        else:
            print("Aucune station à proximité")
    
    def _handle_station_interaction(self, player: Player, station: Station):
        """Gère l'interaction spécifique avec une station"""
        print(f"Traitement interaction: {station.station_type.value}")
        
        if station.station_type == StationType.INGREDIENT_SPAWN:
            # Prendre un ingrédient si le joueur n'a rien
            if not player.held_item and station.ingredient_type:
                player.held_item = Item(station.ingredient_type)
                print(f"Ramassé: {station.ingredient_type.value}")
        
        elif station.station_type == StationType.CUTTING_BOARD:
            if player.held_item and not station.item:
                # Déposer l'item sur la planche
                if player.held_item.item_type in [ItemType.TOMATO, ItemType.LETTUCE]:
                    station.item = player.held_item
                    player.held_item = None
                    print("Item déposé sur la planche à découper")
                else:
                    print("Cet item ne peut pas être coupé")
            elif station.item and not player.held_item:
                # Prendre l'item de la planche
                player.held_item = station.item
                station.item = None
                print("Item récupéré de la planche")
            elif station.item and player.held_item:
                print("Vous avez déjà quelque chose en main et la planche est occupée")
            else:
                print("Planche vide - posez d'abord un item à couper")
        elif station.station_type == StationType.STOVE:
            if player.held_item and not station.item:
                # Déposer sur le fourneau
                if player.held_item.item_type == ItemType.RAW_PATTY:
                    station.item = player.held_item
                    player.held_item = None
                    station.cooking_start_time = time.time()
                    print("Viande mise à cuire!")
                else:
                    print("Seule la viande crue peut être cuite")
            elif station.item and not player.held_item:
                # Prendre de la cuisinière
                player.held_item = station.item
                station.item = None
                station.cooking_start_time = 0
                print("Item récupéré du fourneau")
            elif station.item:
                # Vérifier l'état de cuisson
                cooking_time = time.time() - station.cooking_start_time
                if cooking_time >= station.cooking_duration:
                    print("La viande est cuite!")
                else:
                    remaining = station.cooking_duration - cooking_time
                    print(f"Cuisson en cours... {remaining:.1f}s restantes")
        
        elif station.station_type == StationType.ASSEMBLY:
            if player.held_item and not station.item:
                station.item = player.held_item
                player.held_item = None
                print(f"Item {station.item.item_type.value} posé à l'assemblage")
            elif station.item and not player.held_item:
                player.held_item = station.item
                station.item = None
                print("Item récupéré de l'assemblage")
            elif (station.item and player.held_item):
                # Essayer d'assembler un burger
                if ((station.item.item_type == ItemType.BREAD and player.held_item.item_type == ItemType.COOKED_PATTY) or
                    (station.item.item_type == ItemType.COOKED_PATTY and player.held_item.item_type == ItemType.BREAD)):
                    station.item = Item(ItemType.BURGER)
                    player.held_item = None
                    print("Burger assemblé!")
                else:
                    print("Ces ingrédients ne peuvent pas être assemblés ensemble")
        
        elif station.station_type == StationType.DELIVERY:
            if player.held_item:
                # Essayer de livrer
                if player.held_item.item_type == ItemType.BURGER:
                    # Chercher une commande correspondante
                    for order in self.orders[:]:
                        if ItemType.BURGER in order.items_needed:
                            self.orders.remove(order)
                            self.score += 100
                            player.held_item = None
                            print("Burger livré! +100 points")
                            return
                    print("Aucune commande pour ce burger")
                else:
                    print("Cet item ne correspond à aucune commande")
            else:
                print("Vous devez porter quelque chose pour livrer")


    
    def chop_at_station(self, player_index: int):
        """Découpe un item sur la planche à découper la plus proche"""
        if player_index >= len(self.players):
            return
        
        player = self.players[player_index]
        
        # Trouver la station de découpe la plus proche
        closest_cutting_board = None
        min_distance = float('inf')
        
        for station in self.stations:
            if station.station_type == StationType.CUTTING_BOARD:
                distance = abs(player.x - station.x) + abs(player.y - station.y)
                if distance < min_distance and distance <= 70:
                    min_distance = distance
                    closest_cutting_board = station
        
        if closest_cutting_board and closest_cutting_board.item:
            # Découper l'item si c'est possible
            if closest_cutting_board.item.item_type in [ItemType.TOMATO, ItemType.LETTUCE]:
                if not closest_cutting_board.item.chopped:
                    closest_cutting_board.item.chopped = True
                    print(f"{closest_cutting_board.item.item_type.value} découpé!")
                else:
                    print("Cet item est déjà découpé")
            else:
                print("Cet item ne peut pas être découpé")
        else:
            print("Aucune planche à découper avec un item à proximité")
