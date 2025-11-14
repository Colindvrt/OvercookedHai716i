from enum import Enum, auto
from typing import Optional, List, Tuple, Dict
import time
from src.controller import shared_knowledge
from src.model.game_model import (
    GameModel, StationType, ItemType, Station, Player, Order
)
from src.controller.shared_knowledge import SharedKnowledge, IngredientStatus


# Étapes atomiques
class Step(Enum):
    GO_TO = auto()
    INTERACT = auto()
    CHOP = auto()
    WAIT = auto()

# État interne de l'agent
class AgentState(Enum):
    IDLE = auto()
    EXECUTING_RECIPE = auto()
    DELIVERING = auto()

class Recipe:
    """Définit une recette avec ses ingrédients et leurs préparations"""
    def __init__(self, name: str, result: ItemType, ingredients: List[Tuple[ItemType, bool]]):
        """
        name: nom de la recette
        result: type d'item final produit
        ingredients: liste de (ItemType, needs_chopping)
        """
        self.name = name
        self.result = result
        self.ingredients = ingredients  # [(ItemType, needs_chopping), ...]

# Bibliothèque de recettes
RECIPES = {
    ItemType.BURGER: Recipe(
        name="Burger",
        result=ItemType.BURGER,
        ingredients=[
            (ItemType.BREAD, False),      # pain (pas de découpe)
            (ItemType.RAW_PATTY, False),  # steak (cuisson nécessaire)
            (ItemType.TOMATO, True),      # tomate coupée
            (ItemType.LETTUCE, True),     # salade coupée
        ]
    ),
    ItemType.PIZZA: Recipe(
        name="Pizza",
        result=ItemType.UNCOOKED_PIZZA, # MODIFICATION: Le résultat de l'assemblage est une pizza non cuite
        ingredients=[
            (ItemType.BREAD, False),
            (ItemType.TOMATO, True),
            (ItemType.CHEESE, False),
        ]
    ),
    ItemType.SALAD: Recipe(
        name="Salad",
        result=ItemType.SALAD,
        ingredients=[
            (ItemType.LETTUCE, True),      # salade coupée
            (ItemType.TOMATO, True),      # tomate coupée
        ]
    ),
}

class AIBot:
    """
    Agent autonome conforme à la définition de Wooldridge:
    - Perception (see): observe l'environnement via GameModel
    - État interne (I): maintient des informations sur sa tâche actuelle
    - Action-selection (action): décide quoi faire en fonction de l'état et des percepts
    - Goal-directed: poursuit l'objectif de compléter les commandes
    - Social ability: peut interagir avec les stations (environnement)
    
    Environnement:
    - États: positions des joueurs, états des stations, commandes actives
    - Accessible: partiellement (on voit tout mais cuisson = processus temporel)
    - Non-déterministe: la cuisson peut varier
    - Dynamique: les commandes changent, le temps passe
    """

    def __init__(self, player_index: int = 0, shared_knowledge: Optional['shared_knowledge.SharedKnowledge'] = None):
        # Identité de l'agent
        self.player_index = player_index
        self.shared_knowledge = shared_knowledge  # AJOUTER
        
        # État interne (I)
        self.internal_state = AgentState.IDLE
        self.current_recipe: Optional[Recipe] = None
        self.current_order: Optional[Order] = None
        self.current_order_id: Optional[int] = None  # Track order ID
        
        # Plan d'actions (queue)
        self.queue: List[Tuple[Step, Optional[Station], float]] = []
        
        # Timing controls
        self._cooldown = 0.0
        self._last_action_ts = 0.0
        self._step_gap = 0.25
        self._gap_until = 0.0

    # ============ PERCEPTION (see function) ============
    def perceive(self, m: GameModel) -> Dict:
        """
        Fonction 'see' : perçoit l'état de l'environnement
        Retourne un dictionnaire de percepts
        """
        p = self._p(m)
        
        percepts = {
            'player_position': (p.x, p.y),
            'held_item': p.held_item,
            'active_orders': m.orders.copy(),
            'active_order_ids': [o.id for o in m.orders],
            'score': m.score,
            'stations_state': self._perceive_stations(m),
            'assembly_state': self._perceive_assembly(m),
        }
        
        return percepts

    def _perceive_stations(self, m: GameModel) -> Dict:
        """Observe l'état des stations"""
        return {
            'free_boards': [s for s in self._stations(m, StationType.CUTTING_BOARD) if s.item is None],
            'free_stoves': [s for s in self._stations(m, StationType.STOVE) if s.item is None],
            'cooking_stoves': [s for s in self._stations(m, StationType.STOVE) 
                              if s.item and s.item.item_type == ItemType.RAW_PATTY and s.cooking_start_time > 0],
            'items_on_boards': {(s.x, s.y): s.item for s in self._stations(m, StationType.CUTTING_BOARD) if s.item},
        }

    def _perceive_assembly(self, m: GameModel) -> Dict:
        """Observe l'état de la station d'assemblage"""
        a = self._assembly(m)
        if a is None:
            return {'contents': [], 'finished_item': None}
        
        return {
            'contents': a.contents.copy() if hasattr(a, 'contents') else [],
            'finished_item': a.item,
        }

    # ============ ACTION SELECTION (action function) ============
    def action(self, m: GameModel, percepts: Dict) -> None:
        """
        Fonction 'action' : décide de l'action à prendre
        basée sur l'état interne et les percepts
        """
        # Check if current order still exists
        if self.current_order_id is not None:
            if self.current_order_id not in percepts['active_order_ids']:
                # Order expired or was completed by someone else - abandon current task
                print(f"Agent: Commande #{self.current_order_id} expirée/complétée - abandon")
                self._abandon_current_task(m, percepts)
                return
        
        # Mettre à jour l'état interne basé sur les percepts
        self._update_internal_state(percepts)
        
        # Sélectionner la prochaine action basée sur l'état
        if self.internal_state == AgentState.IDLE:
            self._select_order(percepts)
        elif self.internal_state == AgentState.EXECUTING_RECIPE:
            # La planification est gérée par la fonction update()
            # qui appelle _plan_from_model()
            pass
        elif self.internal_state == AgentState.DELIVERING:
            if not self.queue:
                # Retour à IDLE après livraison
                self.internal_state = AgentState.IDLE
                self.current_recipe = None
                self.current_order = None
                self.current_order_id = None

    def _abandon_current_task(self, m: GameModel, percepts: Dict):
        """Abandonne la tâche actuelle et nettoie l'état"""
        self.queue.clear()
        self.internal_state = AgentState.IDLE
        self.current_recipe = None
        self.current_order = None
        self.current_order_id = None
        
        # Si le bot tient un objet, planifie de le poser
        if self._p(m).held_item:
            self._clear_hands(m)

    def _update_internal_state(self, percepts: Dict):
        """Fonction 'next' : met à jour l'état interne"""
        held = percepts['held_item']
        assembly = percepts['assembly_state']
        
        # Si on tient l'item final, passer en mode livraison
        if held and self.current_order and held.item_type == self.current_order.items_needed[0]:
            self.internal_state = AgentState.DELIVERING
        
        # Si la recette est terminée sur l'assemblage
        elif assembly['finished_item'] and self.current_order and \
             assembly['finished_item'].item_type == self.current_order.items_needed[0]:
            self.internal_state = AgentState.DELIVERING

    def _select_order(self, percepts: Dict):
        """Sélectionne une commande à traiter avec coordination"""
        orders = percepts['active_orders']
        if not orders:
            return
        
        if self.shared_knowledge:
            # Récupérer les commandes déjà prises
            claimed_orders = set()
            for msg in self.shared_knowledge.messages:
                if msg['type'] == 'order_claimed' and msg['sender'] != self.player_index:
                    claimed_orders.add(msg['data'].get('order_id'))
            
            # Trouver une commande non réclamée
            available_orders = [o for o in orders if o.id not in claimed_orders]
            
            if available_orders:
                # Prendre la plus urgente parmi les disponibles
                self.current_order = min(available_orders, key=lambda o: o.time_remaining)
            else:
                # Si toutes sont prises, prendre la plus urgente (fallback)
                self.current_order = min(orders, key=lambda o: o.time_remaining)
            
            self.current_order_id = self.current_order.id
            
            # ✅ ANNONCER qu'on prend cette commande
            self.shared_knowledge.send_message(
                self.player_index,
                'order_claimed',
                {'order_id': self.current_order_id}
            )
            print(f"🎯 Agent {self.player_index} réclame la commande #{self.current_order_id}")
        else:
            # Fallback sans coordination
            self.current_order = min(orders, key=lambda o: o.time_remaining)
            self.current_order_id = self.current_order.id
        
        # Identifier la recette et DÉCLARER les ingrédients nécessaires
        if self.current_order and self.current_order.items_needed:
            needed_item = self.current_order.items_needed[0]
            if needed_item in RECIPES:
                self.current_recipe = RECIPES[needed_item]
                self.internal_state = AgentState.EXECUTING_RECIPE
                print(f"Agent {self.player_index}: Nouvelle commande #{self.current_order_id} - {self.current_recipe.name}")
                
                # ✅ DÉCLARER tous les ingrédients nécessaires AVEC L'ID DE LA COMMANDE
                if self.shared_knowledge:
                    for ingredient, needs_chopping in self.current_recipe.ingredients:
                        needs_cooking = (ingredient == ItemType.RAW_PATTY)
                        # Créer une clé unique : ingredient_orderid
                        unique_key = f"{ingredient.value}_{self.current_order_id}"
                        self.shared_knowledge.request_ingredient(
                            ingredient, 
                            needs_chopping=needs_chopping,
                            needs_cooking=needs_cooking,
                            agent_id=self.player_index
                        )
            elif needed_item == ItemType.PIZZA:
                self.current_recipe = RECIPES[ItemType.PIZZA]
                self.internal_state = AgentState.EXECUTING_RECIPE
                print(f"Agent {self.player_index}: Nouvelle commande #{self.current_order_id} - Pizza")
                
                if self.shared_knowledge:
                    for ingredient, needs_chopping in self.current_recipe.ingredients:
                        self.shared_knowledge.request_ingredient(
                            ingredient,
                            needs_chopping=needs_chopping,
                            agent_id=self.player_index
                        )


    # ============ HELPERS ============
    def _p(self, m: GameModel) -> Player:
        return m.players[self.player_index]

    def _stations(self, m: GameModel, t: StationType) -> List[Station]:
        return [s for s in m.stations if s.station_type == t]

    def _one(self, m: GameModel, t: StationType, ingredient_type: Optional[ItemType] = None) -> Optional[Station]:
        for s in self._stations(m, t):
            if ingredient_type is None or s.ingredient_type == ingredient_type:
                return s
        return None

    def _assembly(self, m: GameModel) -> Station:
        return self._one(m, StationType.ASSEMBLY)

    def _delivery(self, m: GameModel) -> Station:
        return self._one(m, StationType.DELIVERY)

    def _spawn(self, m: GameModel, it: ItemType) -> Station:
        return self._one(m, StationType.INGREDIENT_SPAWN, it)

    def _free_board(self, m: GameModel) -> Optional[Station]:
        for b in self._stations(m, StationType.CUTTING_BOARD):
            if b.item is None:
                return b
        boards = self._stations(m, StationType.CUTTING_BOARD)
        return boards[0] if boards else None

    def _free_stove(self, m: GameModel) -> Optional[Station]:
        for s in self._stations(m, StationType.STOVE):
            if s.item is None:
                return s
        stoves = self._stations(m, StationType.STOVE)
        return stoves[0] if stoves else None

    def _stove_with(self, m: GameModel, it: ItemType) -> Optional[Station]:
        for s in self._stations(m, StationType.STOVE):
            if s.item and s.item.item_type == it:
                return s
        return None

    def _board_with(self, m: GameModel, it: ItemType, chopped: bool) -> Optional[Station]:
        for b in self._stations(m, StationType.CUTTING_BOARD):
            if b.item and b.item.item_type == it and bool(b.item.chopped) == chopped:
                return b
        return None
        
    def _free_furnace(self, m: GameModel) -> Optional[Station]:
        for s in self._stations(m, StationType.FURNACE):
            if s.item is None:
                return s
        return self._one(m, StationType.FURNACE) # Retourne le premier trouvé s'il n'y en a pas de libre

    def _furnace_with(self, m: GameModel, it: ItemType) -> Optional[Station]:
        for s in self._stations(m, StationType.FURNACE):
            if s.item and s.item.item_type == it:
                return s
        return None

    def _anchor(self, s: Station) -> Tuple[int, int]:
        ax = s.x
        ay = min(550, s.y + 50)
        return ax, ay

    def _near(self, px: int, py: int, s: Station, tol: int = 10) -> bool:
        ax, ay = self._anchor(s)
        return abs(px - ax) <= tol and abs(py - ay) <= tol

    def _move_towards(self, m: GameModel, target_x: int, target_y: int):
        p = self._p(m)
        dx = 0
        dy = 0
        if p.x < target_x: dx = 1
        elif p.x > target_x: dx = -1
        elif p.y < target_y: dy = 1
        elif p.y > target_y: dy = -1
        if dx != 0 or dy != 0:
            m.move_player(self.player_index, dx, dy)

    def _move_to_anchor_step(self, m: GameModel, s: Station) -> bool:
        ax, ay = self._anchor(s)
        p = self._p(m)
        if not self._near(p.x, p.y, s):
            self._move_towards(m, ax, ay)
            return True
        return False

    def _interact(self, m: GameModel):
        m.interact_with_station(self.player_index)

    def _chop(self, m: GameModel):
        m.chop_at_station(self.player_index)

    def _push(self, step: Step, station: Optional[Station] = None, wait_seconds: float = 0.0):
        if step == Step.WAIT:
            self.queue.append((Step.WAIT, None, time.time() + wait_seconds))
        else:
            self.queue.append((step, station, 0.0))

    def _push_with_gap(self, step: Step, station: Optional[Station] = None):
        self._push(step, station)
        self._push(Step.WAIT, None, self._step_gap)

    def _reset_queue(self):
        self.queue.clear()

    def _assembly_has(self, m: GameModel, it: ItemType, chopped: Optional[bool] = None) -> bool:
        a = self._assembly(m)
        if a is None:
            return False
        if not hasattr(a, 'contents'):
            return False
        
        for item in a.contents:
            if item.item_type == it:
                if chopped is None:
                    return True
                elif chopped and item.chopped:
                    return True
                elif not chopped and not item.chopped:
                    return True
        return False


    # ============ PLANIFICATION DE RECETTE ============
    def _plan_from_model(self, m: GameModel):
        """Planification basée sur la recette active ET LES RÔLES FIXES"""
        if not self.current_recipe or not self.current_order:
            return

        # Vérifie si la commande existe toujours
        if self.current_order_id not in [o.id for o in m.orders]:
            self._abandon_current_task(m, {'active_order_ids': [o.id for o in m.orders]})
            return

        p = self._p(m)
        a = self._assembly(m)
        d = self._delivery(m)
        
        final_dish_type = self.current_order.items_needed[0]
        bot1_player = m.players[1] # ✅ Référence au Bot 1

        # --- RÔLE 1: BOT 0 (PREP CHEF) ---
        if self.player_index == 0:
            
            # ✅ VERIFICATION DE SUR-PREPARATION (Problème 1)
            # On vérifie si le plat est déjà assemblé OU tenu par Bot 1 OU en cuisson
            is_dish_being_handled = False
            if a.item and (
                a.item.item_type == self.current_recipe.result or
                a.item.item_type == final_dish_type
            ):
                is_dish_being_handled = True # Plat assemblé sur la table
            
            if bot1_player.held_item and (
                bot1_player.held_item.item_type == self.current_recipe.result or
                bot1_player.held_item.item_type == final_dish_type
            ):
                is_dish_being_handled = True # Bot 1 tient le plat (ex: UNCOOKED_PIZZA)
            
            if final_dish_type == ItemType.PIZZA:
                if self._furnace_with(m, ItemType.UNCOOKED_PIZZA) or self._furnace_with(m, ItemType.PIZZA):
                    is_dish_being_handled = True # Pizza au four
            
            if is_dish_being_handled:
                print(f"Agent {self.player_index}: Plat déjà assemblé/pris en charge par Bot 1. J'attends.")
                self._push(Step.WAIT, None, self._step_gap * 2)
                return

            # Si mains pleines, vider les mains
            if p.held_item:
                if p.held_item.chopped or p.held_item.item_type == ItemType.COOKED_PATTY:
                    
                    if p.held_item.item_type == ItemType.COOKED_PATTY:
                         # Le steak cuit RESTE sur le four. On le repose si on le tient.
                         stove = self._free_stove(m)
                         if stove:
                             self._push_with_gap(Step.GO_TO, stove)
                             self._push_with_gap(Step.INTERACT, stove)
                         return
                    else: 
                         # ✅ CORRECTIF CONFLIT (Problème 2/3)
                         # Tomate/Salade coupée: ON POSE SUR UNE PLANCHE LIBRE, JAMAIS L'ASSEMBLAGE
                         board = self._free_board(m)
                         if board:
                             self._push_with_gap(Step.GO_TO, board)
                             self._push_with_gap(Step.INTERACT, board)
                             print(f"Agent {self.player_index}: Laisse {p.held_item.item_type.value} coupé sur la planche.")
                         else:
                             # TOUTES LES PLANCHES SONT PLEINES. ON ATTEND.
                             print(f"Agent {self.player_index}: Tient {p.held_item.item_type.value} coupé, mais pas de planche libre. J'attends.")
                             self._push(Step.WAIT, None, self._step_gap)
                         return
                
                else: # On tient un item non préparé, on continue la prépa
                     is_choppable = p.held_item.item_type in [ItemType.TOMATO, ItemType.LETTUCE]
                     self._plan_ingredient(m, p.held_item.item_type, is_choppable)
                     return

            # Mains vides: chercher une tâche de préparation
            for ingredient_type, needs_chopping in self.current_recipe.ingredients:
                needs_cooking = (ingredient_type == ItemType.RAW_PATTY)
                
                # On ne s'occupe QUE de la prépa
                if not needs_chopping and not needs_cooking:
                    continue 
                    
                effective_ingredient = ItemType.COOKED_PATTY if needs_cooking else ingredient_type
                if self._assembly_has(m, effective_ingredient, chopped=needs_chopping if needs_chopping else None):
                    continue
                
                if needs_cooking:
                    if self._stove_with(m, ItemType.COOKED_PATTY) or self._stove_with(m, ItemType.RAW_PATTY):
                        continue
                elif needs_chopping:
                    if self._board_with(m, ingredient_type, chopped=True) or self._board_with(m, ingredient_type, chopped=False):
                        continue
                
                self._plan_ingredient(m, ingredient_type, needs_chopping)
                return
            
            self._push(Step.WAIT, None, self._step_gap * 2)
            return

        # --- RÔLE 2: BOT 1 (ASSEMBLER / RUNNER) ---
        elif self.player_index == 1:
            
            # Étape 1: LIVRAISON
            if p.held_item and p.held_item.item_type == final_dish_type:
                self._push_with_gap(Step.GO_TO, d)
                self._push_with_gap(Step.INTERACT, d)
                return

            ready_dish_station = self._furnace_with(m, final_dish_type) or \
                                (a if a.item and a.item.item_type == final_dish_type else None)
            if ready_dish_station:
                if p.held_item is None:
                    self._push_with_gap(Step.GO_TO, ready_dish_station)
                    self._push_with_gap(Step.INTERACT, ready_dish_station)
                else:
                    # ✅ CORRECTIF CONFLIT (Problème 2/3): Utilise la nouvelle fonction
                    self._place_held_item_on_assembly(m)
                return

            # Étape 2: Cuisson PIZZA
            if final_dish_type == ItemType.PIZZA:
                uncooked_pizza_station = self._furnace_with(m, ItemType.UNCOOKED_PIZZA)
                if p.held_item and p.held_item.item_type == ItemType.UNCOOKED_PIZZA:
                    furnace = self._free_furnace(m)
                    if furnace:
                        self._push_with_gap(Step.GO_TO, furnace)
                        self._push_with_gap(Step.INTERACT, furnace)
                    return
                if a.item and a.item.item_type == ItemType.UNCOOKED_PIZZA:
                    if p.held_item is None:
                        self._push_with_gap(Step.GO_TO, a)
                        self._push_with_gap(Step.INTERACT, a)
                    else:
                        # ✅ CORRECTIF CONFLIT (Problème 2/3): Utilise la nouvelle fonction
                        self._place_held_item_on_assembly(m)
                    return
                if uncooked_pizza_station and uncooked_pizza_station.cooking_start_time > 0:
                    self._push_with_gap(Step.GO_TO, uncooked_pizza_station)
                    self._push(Step.WAIT, None, 1.0)
                    return

            # Étape 3: Assemblage des ingrédients
            for ingredient_type, needs_chopping in self.current_recipe.ingredients:
                needs_cooking = (ingredient_type == ItemType.RAW_PATTY)
                effective_ingredient = ItemType.COOKED_PATTY if needs_cooking else ingredient_type
                
                if self._assembly_has(m, effective_ingredient, chopped=needs_chopping if needs_chopping else None):
                    continue
                
                # Bot 1 s'occupe des items SIMPLES (pain, fromage)
                if not needs_chopping and not needs_cooking:
                    self._plan_ingredient(m, ingredient_type, needs_chopping)
                    return
                
                # Bot 1 s'occupe de RÉCUPÉRER les items préparés
                elif p.held_item is None: # Doit avoir les mains vides
                    ready_station = None
                    if needs_cooking:
                        ready_station = self._stove_with(m, ItemType.COOKED_PATTY)
                    elif needs_chopping:
                        ready_station = self._board_with(m, ingredient_type, chopped=True)
                    
                    if ready_station:
                        self._push_with_gap(Step.GO_TO, ready_station)
                        self._push_with_gap(Step.INTERACT, ready_station)
                        self._push_with_gap(Step.GO_TO, a)
                        self._push_with_gap(Step.INTERACT, a)
                        return
                    else:
                        continue
                else:
                    # ✅ CORRECTIF CONFLIT (Problème 2/3): Utilise la nouvelle fonction
                    self._place_held_item_on_assembly(m)
                    return
            
            # Si on arrive ici, on n'a rien à faire
            if p.held_item is not None:
                # ✅ CORRECTIF CONFLIT (Problème 2/3): Utilise la nouvelle fonction
                self._place_held_item_on_assembly(m)
            else:
                self._push(Step.WAIT, None, self._step_gap * 2)

    def _plan_ingredient(self, m: GameModel, ingredient: ItemType, needs_chopping: bool):
        """Planifie la préparation d'un ingrédient spécifique"""
        p = self._p(m)
        a = self._assembly(m)

        # ✅ VÉRIFIER si on peut claim cet ingrédient
        if self.shared_knowledge:
            ing_status = self.shared_knowledge.get_ingredient_status(ingredient)
            
            # Si l'ingrédient n'est pas encore réclamé ou est réclamé par nous
            if ing_status in [None, IngredientStatus.NEEDED]:
                if not self.shared_knowledge.claim_ingredient_preparation(ingredient, self.player_index):
                    print(f"Agent {self.player_index}: {ingredient.value} déjà réclamé par un autre agent")
                    self._push(Step.WAIT, None, 0.5)
                    return
            elif ing_status == IngredientStatus.IN_PREPARATION:
                ing_info = self.shared_knowledge.ingredients.get(ingredient)
                if ing_info and ing_info.claimed_by != self.player_index:
                    # Un autre agent s'en occupe, ne rien faire
                    print(f"Agent {self.player_index}: {ingredient.value} en préparation par agent {ing_info.claimed_by}")
                    return
        
        # Cas spécial: RAW_PATTY doit être cuit
        needs_cooking = (ingredient == ItemType.RAW_PATTY)
        cooked_version = ItemType.COOKED_PATTY if needs_cooking else ingredient
        
        # Si on tient déjà l'ingrédient préparé
        if p.held_item and p.held_item.item_type == cooked_version:
            if needs_chopping and not p.held_item.chopped:
                # Doit être coupé
                board = self._free_board(m)
                if board:
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                    self._push_with_gap(Step.CHOP, board)
                    self._push_with_gap(Step.INTERACT, board)
                    # ✅ MARQUER COMME PRÊT après découpe
                    if self.shared_knowledge:
                        self.shared_knowledge.mark_ingredient_ready(ingredient, board, self.player_index)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
            else:
                # Prêt à poser sur l'assemblage
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                # ✅ MARQUER COMME PRÊT après dépôt sur assemblage
                if self.shared_knowledge:
                    self.shared_knowledge.mark_ingredient_ready(cooked_version, a, self.player_index)
            return
        
        # Si on tient le bon ingrédient mais non préparé
        if p.held_item and p.held_item.item_type == ingredient:
            if needs_chopping and not p.held_item.chopped:
                board = self._free_board(m)
                if board:
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                    self._push_with_gap(Step.CHOP, board)
                    self._push_with_gap(Step.INTERACT, board)
                    # ✅ MARQUER COMME PRÊT après découpe
                    if self.shared_knowledge:
                        self.shared_knowledge.mark_ingredient_ready(ingredient, board, self.player_index)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                return
        
        # Si mains vides
        if p.held_item is None:
            # Chercher si l'ingrédient est déjà préparé quelque part
            if needs_cooking:
                # Chercher steak cuit
                stove_cooked = self._stove_with(m, ItemType.COOKED_PATTY)
                if stove_cooked:
                    self._push_with_gap(Step.GO_TO, stove_cooked)
                    self._push_with_gap(Step.INTERACT, stove_cooked)
                    # ✅ MARQUER COMME PRÊT après avoir pris le steak cuit
                    if self.shared_knowledge:
                        self.shared_knowledge.mark_ingredient_ready(ItemType.COOKED_PATTY, stove_cooked, self.player_index)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                    return
                
                # Chercher steak en cuisson
                stove_raw = self._stove_with(m, ItemType.RAW_PATTY)
                if stove_raw and stove_raw.cooking_start_time > 0:
                    self._push_with_gap(Step.GO_TO, stove_raw)
                    remaining = max(0.0, stove_raw.cooking_duration - (time.time() - stove_raw.cooking_start_time))
                    self._push(Step.WAIT, None, min(0.5, remaining))
                    # ✅ MARQUER COMME PRÊT quand la cuisson est terminée
                    if remaining <= 0.1 and self.shared_knowledge:
                        self.shared_knowledge.mark_ingredient_ready(ItemType.COOKED_PATTY, stove_raw, self.player_index)
                    return
                
                # Commencer la cuisson
                spawn = self._spawn(m, ItemType.RAW_PATTY)
                stove = self._free_stove(m)
                if spawn and stove:
                    self._push_with_gap(Step.GO_TO, spawn)
                    self._push_with_gap(Step.INTERACT, spawn)
                    self._push_with_gap(Step.GO_TO, stove)
                    self._push_with_gap(Step.INTERACT, stove)
                    # Note: Le steak sera marqué prêt plus tard quand il sera cuit
                return
            
            if needs_chopping:
                # Chercher ingrédient déjà coupé
                ready = self._board_with(m, ingredient, chopped=True)
                if ready:
                    self._push_with_gap(Step.GO_TO, ready)
                    self._push_with_gap(Step.INTERACT, ready)
                    # ✅ MARQUER COMME PRÊT après avoir pris l'ingrédient coupé
                    if self.shared_knowledge:
                        self.shared_knowledge.mark_ingredient_ready(ingredient, ready, self.player_index)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                    return
                
                # Commencer à préparer
                spawn = self._spawn(m, ingredient)
                board = self._free_board(m)
                if spawn and board:
                    self._push_with_gap(Step.GO_TO, spawn)
                    self._push_with_gap(Step.INTERACT, spawn)
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                    self._push_with_gap(Step.CHOP, board)
                    self._push_with_gap(Step.INTERACT, board)
                    # ✅ MARQUER COMME PRÊT après découpe
                    if self.shared_knowledge:
                        self.shared_knowledge.mark_ingredient_ready(ingredient, board, self.player_index)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                return
            
            # Ingrédient simple (pas de préparation)
            spawn = self._spawn(m, ingredient)
            if spawn:
                self._push_with_gap(Step.GO_TO, spawn)
                self._push_with_gap(Step.INTERACT, spawn)
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                # ✅ MARQUER COMME PRÊT après avoir pris l'ingrédient simple
                if self.shared_knowledge:
                    self.shared_knowledge.mark_ingredient_ready(ingredient, spawn, self.player_index)
            return
        
        # Si on tient quelque chose d'autre qui n'est pas lié à la recette, le poser
        if p.held_item:
            held_type = p.held_item.item_type
            # Vérifier si ce qu'on tient fait partie de la recette actuelle
            recipe_ingredients = [ing for ing, _ in self.current_recipe.ingredients] if self.current_recipe else []
            
            if held_type not in recipe_ingredients and held_type != ItemType.COOKED_PATTY:
                # Ce n'est pas pour cette recette, le poser ailleurs
                if held_type in (ItemType.TOMATO, ItemType.LETTUCE):
                    board = self._free_board(m)
                    if board:
                        self._push_with_gap(Step.GO_TO, board)
                        self._push_with_gap(Step.INTERACT, board)
                    return
                elif held_type == ItemType.RAW_PATTY:
                    stove = self._free_stove(m)
                    if stove:
                        self._push_with_gap(Step.GO_TO, stove)
                        self._push_with_gap(Step.INTERACT, stove)
                    return
            else:
                # Fait partie de la recette mais pas le bon moment, attendre
                self._push(Step.WAIT, None, self._step_gap)

    def _clear_hands(self, m: GameModel):
        """Libère les mains en posant l'item tenu"""
        p = self._p(m)
        if not p.held_item:
            return
        
        held = p.held_item.item_type
        
        if held in (ItemType.TOMATO, ItemType.LETTUCE):
            board = self._free_board(m)
            if board:
                self._push_with_gap(Step.GO_TO, board)
                self._push_with_gap(Step.INTERACT, board)
        elif held == ItemType.RAW_PATTY:
            stove = self._free_stove(m)
            if stove:
                self._push_with_gap(Step.GO_TO, stove)
                self._push_with_gap(Step.INTERACT, stove)
        else:
            # Poser sur l'assemblage si possible
            a = self._assembly(m)
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)

    # ============ EXÉCUTION (run function) ============
    def update(self, m: GameModel):
        """
        Fonction principale : perception -> action -> exécution
        Représente un cycle complet de l'agent
        """
        if self._assembly(m) is None or self._delivery(m) is None:
            return

        now = time.time()

        # Respecter le délai entre actions
        if now < self._gap_until:
            return

        # PERCEPTION
        percepts = self.perceive(m)
        
        # ACTION SELECTION
        self.action(m, percepts)
        
        # Planification si nécessaire
        if self.internal_state == AgentState.EXECUTING_RECIPE and not self.queue:
            self._plan_from_model(m)
            if not self.queue:
                return
        
        if self.internal_state == AgentState.DELIVERING and not self.queue:
            d = self._delivery(m)
            self._push_with_gap(Step.GO_TO, d)
            self._push_with_gap(Step.INTERACT, d)

        # EXÉCUTION de l'action planifiée
        if not self.queue:
            return

        step, station, deadline = self.queue[0]

        # WAIT
        if step == Step.WAIT:
            if now >= deadline:
                self.queue.pop(0)
                self._gap_until = time.time() + self._step_gap
            return

        # Mouvement vers la station
        if station is not None:
            if self._move_to_anchor_step(m, station):
                self._gap_until = time.time() + self._step_gap
                return

        # Anti-spam
        if step in (Step.INTERACT, Step.CHOP) and (now - self._last_action_ts) < self._cooldown:
            return

        # Exécuter l'étape
        if step == Step.GO_TO:
            self.queue.pop(0)
            self._gap_until = time.time() + self._step_gap
            return

        if step == Step.INTERACT:
            self._interact(m)
            self._last_action_ts = time.time()
            self.queue.pop(0)
            self._gap_until = time.time() + self._step_gap
            return

        if step == Step.CHOP:
            self._chop(m)
            self._last_action_ts = time.time()
            self.queue.pop(0)
            self._gap_until = time.time() + self._step_gap
            return


    def _place_held_item_on_assembly(self, m: GameModel):
        """
        Action spécifique pour le BOT 1 (Assembleur).
        Planifie de poser l'item tenu sur la station d'assemblage.
        """
        p = self._p(m)
        if not p.held_item:
            return
        
        # Si on tient un plat final, on ne le "vide" pas, on le livre.
        # La logique principale de livraison devrait prendre le dessus.
        if p.held_item.item_type in [ItemType.BURGER, ItemType.PIZZA, ItemType.SALAD, ItemType.UNCOOKED_PIZZA]:
             self._push(Step.WAIT, None, self._step_gap)
             return

        print(f"Agent {self.player_index}: Mains pleines, pose {p.held_item.item_type.value} sur l'assemblage.")
        a = self._assembly(m)
        self._push_with_gap(Step.GO_TO, a)
        self._push_with_gap(Step.INTERACT, a)