from dataclasses import dataclass, field
from typing import Dict, Set, Optional, List
from enum import Enum
import time

from src.model.game_model import ItemType, Station, Order

class IngredientStatus(Enum):
    """État d'un ingrédient"""
    NEEDED = "needed"           # On en a besoin
    IN_PREPARATION = "in_prep"  # En cours de préparation
    READY = "ready"             # Prêt à être pris
    TAKEN = "taken"             # Déjà pris par l'assembleur

@dataclass
class IngredientInfo:
    """Information sur un ingrédient"""
    item_type: ItemType
    status: IngredientStatus
    station: Optional[Station] = None
    needs_chopping: bool = False
    needs_cooking: bool = False
    claimed_by: Optional[int] = None  # ID de l'agent qui s'en occupe
    ready_time: float = 0.0
    order_id: Optional[int] = None  # ✅ AJOUTER: ID de la commande associée

class SharedKnowledge:
    """
    Mémoire partagée entre tous les agents.
    Permet la coordination et évite les conflits.
    """
    
    def __init__(self):
        # Commandes actives
        self.current_orders: List[Order] = []
        
        # État des ingrédients nécessaires
        self.ingredients: Dict[ItemType, IngredientInfo] = {}
        
        # Réservations de stations (station -> agent_id)
        self.station_reservations: Dict[tuple, int] = {}  # (x, y) -> agent_id
        
        # Messages entre agents
        self.messages: List[Dict] = []
        
        # Timestamp de dernière mise à jour
        self.last_update = time.time()
    
    def update_orders(self, orders: List[Order]):
        """Met à jour la liste des commandes"""
        self.current_orders = orders.copy()
        self.last_update = time.time()
    
    def request_ingredient(self, item_type: ItemType, needs_chopping: bool = False, needs_cooking: bool = False, agent_id: int = 0, order_id: Optional[int] = None):
        """Demande la préparation d'un ingrédient"""
        # ✅ Créer une clé unique avec l'order_id
        key = (item_type, order_id) if order_id else item_type
        
        if key not in self.ingredients:
            self.ingredients[key] = IngredientInfo(
                item_type=item_type,
                status=IngredientStatus.NEEDED,
                needs_chopping=needs_chopping,
                needs_cooking=needs_cooking,
                order_id=order_id
            )
            print(f"📋 SharedKnowledge: {item_type.value} demandé pour commande #{order_id}")
    
    def claim_ingredient_preparation(self, item_type: ItemType, agent_id: int) -> bool:
        """Un agent réclame la préparation d'un ingrédient"""
        if item_type in self.ingredients:
            info = self.ingredients[item_type]
            if info.status == IngredientStatus.NEEDED and info.claimed_by is None:
                info.status = IngredientStatus.IN_PREPARATION
                info.claimed_by = agent_id
                print(f"👨‍🍳 Agent {agent_id} prend en charge: {item_type.value}")
                return True
        return False
    
    def mark_ingredient_ready(self, item_type: ItemType, station: Station, agent_id: int):
        """Marque un ingrédient comme prêt"""
        if item_type in self.ingredients:
            info = self.ingredients[item_type]
            if info.claimed_by == agent_id:
                info.status = IngredientStatus.READY
                info.station = station
                info.ready_time = time.time()
                print(f"✅ {item_type.value} prêt à la station ({station.x}, {station.y})")
    
    def take_ingredient(self, item_type: ItemType, agent_id: int) -> bool:
        """Un agent prend un ingrédient prêt"""
        if item_type in self.ingredients:
            info = self.ingredients[item_type]
            if info.status == IngredientStatus.READY:
                info.status = IngredientStatus.TAKEN
                info.claimed_by = agent_id
                print(f"📦 Agent {agent_id} prend: {item_type.value}")
                return True
        return False
    
    def clear_ingredient(self, item_type: ItemType):
        """Nettoie un ingrédient de la mémoire (après utilisation)"""
        if item_type in self.ingredients:
            del self.ingredients[item_type]
    
    def reserve_station(self, station: Station, agent_id: int, duration: float = 5.0) -> bool:
        """Réserve une station pour un agent"""
        key = (station.x, station.y)
        current_time = time.time()
        
        # Nettoyer les réservations expirées
        expired = []
        for pos, (aid, expiry) in self.station_reservations.items():
            if current_time > expiry:
                expired.append(pos)
        for pos in expired:
            del self.station_reservations[pos]
        
        # Vérifier si la station est libre ou déjà réservée par cet agent
        if key not in self.station_reservations or self.station_reservations[key][0] == agent_id:
            self.station_reservations[key] = (agent_id, current_time + duration)
            return True
        return False
    
    def release_station(self, station: Station, agent_id: int):
        """Libère une station"""
        key = (station.x, station.y)
        if key in self.station_reservations and self.station_reservations[key][0] == agent_id:
            del self.station_reservations[key]
    
    def is_station_available(self, station: Station, agent_id: int) -> bool:
        """Vérifie si une station est disponible pour un agent"""
        key = (station.x, station.y)
        if key not in self.station_reservations:
            return True
        aid, expiry = self.station_reservations[key]
        return aid == agent_id or time.time() > expiry
    
    def send_message(self, sender_id: int, message_type: str, data: Dict):
        """Envoie un message aux autres agents"""
        self.messages.append({
            'sender': sender_id,
            'type': message_type,
            'data': data,
            'time': time.time()
        })
        # Garder seulement les 10 derniers messages
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]
    
    def get_messages(self, for_agent_id: int, message_type: Optional[str] = None) -> List[Dict]:
        """Récupère les messages pour un agent"""
        messages = [m for m in self.messages if m['sender'] != for_agent_id]
        if message_type:
            messages = [m for m in messages if m['type'] == message_type]
        return messages
    
    def get_ingredient_status(self, item_type: ItemType) -> Optional[IngredientStatus]:
        """Obtient le statut d'un ingrédient"""
        if item_type in self.ingredients:
            return self.ingredients[item_type].status
        return None
    
    def get_ready_ingredients(self) -> List[IngredientInfo]:
        """Liste tous les ingrédients prêts"""
        return [info for info in self.ingredients.values() 
                if info.status == IngredientStatus.READY]
    
    def reset(self):
        """Réinitialise la mémoire partagée"""
        self.current_orders.clear()
        self.ingredients.clear()
        self.station_reservations.clear()
        self.messages.clear()
        print("🔄 SharedKnowledge réinitialisé")