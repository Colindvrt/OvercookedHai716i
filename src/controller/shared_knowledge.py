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
    order_id: Optional[int] = None  # ID de la commande associée

class SharedKnowledge:
    """
    Mémoire partagée entre tous les agents.
    Permet la coordination et évite les conflits.
    """
    
    def __init__(self):
        # Commandes actives
        self.current_orders: List[Order] = []
        
        # État des ingrédients nécessaires
        # ✅ Clé = (ItemType, order_id) pour éviter les conflits
        self.ingredients: Dict[tuple, IngredientInfo] = {} 
        
        # Réservations de stations (station -> agent_id)
        self.station_reservations: Dict[tuple, int] = {}  # (x, y) -> agent_id
        
        # Messages entre agents
        self.messages: List[Dict] = []
        
        # Timestamp de dernière mise à jour
        self.last_update = time.time()
        
        # ✅ AJOUTÉ: Commandes réclamées (order_id -> agent_id)
        self.claimed_orders: Dict[int, int] = {}
    
    def update_orders(self, orders: List[Order]):
        """Met à jour la liste des commandes"""
        self.current_orders = orders.copy()
        self.last_update = time.time()
        
        # ✅ AJOUTÉ: Nettoyer les commandes réclamées qui sont terminées
        active_order_ids = {o.id for o in self.current_orders}
        for oid in list(self.claimed_orders.keys()):
            if oid not in active_order_ids:
                del self.claimed_orders[oid]
        
        # ✅ AJOUTÉ: Nettoyer les ingrédients des commandes terminées
        for key in list(self.ingredients.keys()):
            order_id = self.ingredients[key].order_id
            if order_id and order_id not in active_order_ids:
                del self.ingredients[key]

    
    def request_ingredient(self, item_type: ItemType, needs_chopping: bool = False, needs_cooking: bool = False, agent_id: int = 0, order_id: Optional[int] = None):
        """Demande la préparation d'un ingrédient pour une commande spécifique"""
        
        # ✅ Clé unique
        key = (item_type, order_id)
        
        if key not in self.ingredients:
            self.ingredients[key] = IngredientInfo(
                item_type=item_type,
                status=IngredientStatus.NEEDED,
                needs_chopping=needs_chopping,
                needs_cooking=needs_cooking,
                order_id=order_id
            )
            print(f"📋 SharedKnowledge: {item_type.value} demandé pour commande #{order_id}")
    
    def claim_ingredient_preparation(self, item_type: ItemType, order_id: int, agent_id: int) -> bool:
        """Un agent réclame la préparation d'un ingrédient"""
        key = (item_type, order_id)
        if key in self.ingredients:
            info = self.ingredients[key]
            if info.status == IngredientStatus.NEEDED and info.claimed_by is None:
                info.status = IngredientStatus.IN_PREPARATION
                info.claimed_by = agent_id
                print(f"👨‍🍳 Agent {agent_id} prend en charge: {item_type.value} (Commande #{order_id})")
                return True
        return False
    
    def mark_ingredient_ready(self, item_type: ItemType, order_id: int, station: Station, agent_id: int):
        """Marque un ingrédient comme prêt"""
        key = (item_type, order_id)
        if key in self.ingredients:
            info = self.ingredients[key]
            if info.claimed_by == agent_id:
                info.status = IngredientStatus.READY
                info.station = station
                info.ready_time = time.time()
                print(f"✅ {item_type.value} prêt à la station ({station.x}, {station.y})")
    
    def take_ingredient(self, item_type: ItemType, order_id: int, agent_id: int) -> bool:
        """Un agent prend un ingrédient prêt"""
        key = (item_type, order_id)
        if key in self.ingredients:
            info = self.ingredients[key]
            if info.status == IngredientStatus.READY:
                info.status = IngredientStatus.TAKEN
                info.claimed_by = agent_id
                print(f"📦 Agent {agent_id} prend: {item_type.value} (Commande #{order_id})")
                # Une fois pris, on peut le supprimer
                del self.ingredients[key]
                return True
        return False
    
    def clear_ingredient(self, item_type: ItemType, order_id: int):
        """Nettoie un ingrédient de la mémoire (après utilisation)"""
        key = (item_type, order_id)
        if key in self.ingredients:
            del self.ingredients[key]
    
    # ... (les fonctions de réservation de station restent inchangées) ...
    def reserve_station(self, station: Station, agent_id: int, duration: float = 5.0) -> bool:
        key = (station.x, station.y)
        current_time = time.time()
        
        expired = []
        if hasattr(self, 'station_reservations'): # Check au cas où
            for pos, (aid, expiry) in self.station_reservations.items():
                if current_time > expiry:
                    expired.append(pos)
        else:
            self.station_reservations = {}

        for pos in expired:
            del self.station_reservations[pos]
        
        if key not in self.station_reservations or self.station_reservations[key][0] == agent_id:
            self.station_reservations[key] = (agent_id, current_time + duration)
            return True
        return False
    
    def release_station(self, station: Station, agent_id: int):
        key = (station.x, station.y)
        if key in self.station_reservations and self.station_reservations[key][0] == agent_id:
            del self.station_reservations[key]
    
    def is_station_available(self, station: Station, agent_id: int) -> bool:
        key = (station.x, station.y)
        if key not in self.station_reservations:
            return True
        aid, expiry = self.station_reservations[key]
        return aid == agent_id or time.time() > expiry
    
    # ... (les fonctions de message restent inchangées) ...
    def send_message(self, sender_id: int, message_type: str, data: Dict):
        self.messages.append({
            'sender': sender_id,
            'type': message_type,
            'data': data,
            'time': time.time()
        })
        if len(self.messages) > 10:
            self.messages = self.messages[-10:]
    
    def get_messages(self, for_agent_id: int, message_type: Optional[str] = None) -> List[Dict]:
        messages = [m for m in self.messages if m['sender'] != for_agent_id]
        if message_type:
            messages = [m for m in messages if m['type'] == message_type]
        return messages
    
    def get_ingredient_status(self, item_type: ItemType, order_id: int) -> Optional[IngredientStatus]:
        key = (item_type, order_id)
        if key in self.ingredients:
            return self.ingredients[key].status
        return None
    
    def get_ready_ingredients(self, order_id: int) -> List[IngredientInfo]:
        return [info for info in self.ingredients.values() 
                if info.status == IngredientStatus.READY and info.order_id == order_id]
    
    def reset(self):
        """Réinitialise la mémoire partagée"""
        self.current_orders.clear()
        self.ingredients.clear()
        self.station_reservations.clear()
        self.messages.clear()
        self.claimed_orders.clear() # ✅ AJOUTÉ
        print("🔄 SharedKnowledge réinitialisé")

    # ✅ NOUVELLES FONCTIONS (manquantes dans votre fichier)
    
    def claim_order(self, order_id: int, agent_id: int) -> bool:
        """Tente de réclamer une commande. Retourne True si succès."""
        # (Le nettoyage se fait dans update_orders)
        
        if order_id not in self.claimed_orders:
            self.claimed_orders[order_id] = agent_id
            return True
        elif self.claimed_orders[order_id] == agent_id:
            return True # On la possède déjà
        
        return False # Déjà prise par un autre
    
    def get_unclaimed_orders(self) -> List[Order]:
        """Retourne la liste des commandes non réclamées."""
        self.update_orders(self.current_orders) # S'assurer que la liste est à jour
        claimed_ids = set(self.claimed_orders.keys())
        return [o for o in self.current_orders if o.id not in claimed_ids]