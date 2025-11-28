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
        if not self.shared_knowledge:
            # Fallback (ancienne logique)
            orders = percepts['active_orders']
            if not orders: return
            self.current_order = min(orders, key=lambda o: o.time_remaining)
            self.current_order_id = self.current_order.id
        else:
            self.shared_knowledge.update_orders(percepts['active_orders'])

            # --- BOT 0 (PREP) ---
            if self.player_index == 0:
                unclaimed_orders = self.shared_knowledge.get_unclaimed_orders()

                # Si sa commande actuelle est toujours valide, il la garde
                if self.current_order_id and self.current_order_id in [o.id for o in unclaimed_orders]:
                     pass # Garde sa commande
                elif self.current_order_id and self.current_order_id in [o.id for o in self.shared_knowledge.current_orders]:
                     pass # Garde sa commande (même si réclamée, c'est par lui)
                else:
                    # Sinon, il prend une nouvelle commande
                    if not unclaimed_orders:
                        self.internal_state = AgentState.IDLE
                        self.current_order = None
                        self.current_order_id = None
                        return

                    target_order = min(unclaimed_orders, key=lambda o: o.time_remaining)
                    
                    if self.shared_knowledge.claim_order(target_order.id, self.player_index):
                        self.current_order = target_order
                        self.current_order_id = target_order.id
                    else:
                        self.internal_state = AgentState.IDLE
                        return
                
                # Si, après tout ça, il n'a pas de commande, il sort
                if not self.current_order:
                    self.internal_state = AgentState.IDLE
                    return
                
                print(f"🎯 Agent {self.player_index} (Prep) réclame la commande #{self.current_order_id}")

            # --- BOT 1 (ASSEMBLER) ---
            elif self.player_index == 1:
                # ✅ Bot 1 ne réclame pas. Il vérifie juste s'il y a du travail.
                if percepts['active_orders']:
                    self.internal_state = AgentState.EXECUTING_RECIPE
                    # Il n'a pas de "current_order", il les traite toutes dans _plan_from_model
                    self.current_order = None 
                    self.current_order_id = None
                    self.current_recipe = None
                else:
                    self.internal_state = AgentState.IDLE
                return # Bot 1 a fini sa sélection
        
        # --- (Suite pour Bot 0 uniquement) ---
        if not self.current_order:
            self.internal_state = AgentState.IDLE
            return
        
        # Identifier la recette (concerne Bot 0)
        if self.current_order and self.current_order.items_needed:
            needed_item = self.current_order.items_needed[0]
            
            # ✅ C'EST ICI QUE 'recipe_key' EST DÉFINI !
            recipe_key = ItemType.PIZZA if needed_item == ItemType.PIZZA else needed_item

            if recipe_key in RECIPES:
                self.current_recipe = RECIPES[recipe_key]
                self.internal_state = AgentState.EXECUTING_RECIPE # ✅ CORRECTION: Bot 0 démarre
                print(f"Agent {self.player_index}: Nouvelle commande #{self.current_order_id} - {self.current_recipe.name}")
                
                if self.shared_knowledge:
                    for ingredient, needs_chopping in self.current_recipe.ingredients:
                        needs_cooking = (ingredient == ItemType.RAW_PATTY)
                        self.shared_knowledge.request_ingredient(
                            ingredient, 
                            needs_chopping=needs_chopping,
                            needs_cooking=needs_cooking,
                            agent_id=self.player_index,
                            order_id=self.current_order_id # Lie l'ingrédient à la commande
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
        p = self._p(m)
        a = self._assembly(m)
        d = self._delivery(m)

        # --- RÔLE 1: BOT 0 (PREP CHEF) ---
        if self.player_index == 0:
            
            # On vérifie d'abord s'il a une commande
            if not self.current_recipe or not self.current_order:
                self._push(Step.WAIT, None, self._step_gap)
                return
            
            # Vérifie si la commande existe toujours
            if self.current_order_id not in [o.id for o in m.orders]:
                self._abandon_current_task(m, {'active_order_ids': [o.id for o in m.orders]})
                return
            
            bot1_player = m.players[1] # Référence au Bot 1
            final_dish_type = self.current_order.items_needed[0] # Le plat final de SA commande
            
            # --- (Début de la logique de prépa du Bot 0) ---
            
            is_dish_being_handled = False
            if a.item and (
                a.item.item_type == self.current_recipe.result or
                a.item.item_type == final_dish_type
            ):
                is_dish_being_handled = True
            
            if bot1_player.held_item and (
                bot1_player.held_item.item_type == self.current_recipe.result or
                bot1_player.held_item.item_type == final_dish_type
            ):
                is_dish_being_handled = True
            
            if final_dish_type == ItemType.PIZZA:
                if self._furnace_with(m, ItemType.UNCOOKED_PIZZA) or self._furnace_with(m, ItemType.PIZZA):
                    is_dish_being_handled = True
            
            if is_dish_being_handled:
                print(f"Agent {self.player_index}: Plat déjà assemblé/pris en charge. J'attends.")
                self._push(Step.WAIT, None, self._step_gap * 2)
                return

            if p.held_item:
                if (p.held_item.item_type in [ItemType.TOMATO, ItemType.LETTUCE] and not p.held_item.chopped):
                    board = self._free_board(m)
                    if board:
                        self._push_with_gap(Step.GO_TO, board)
                        self._push_with_gap(Step.INTERACT, board)
                        self._push_with_gap(Step.CHOP, board)
                    else:
                        self._push(Step.WAIT, None, 0.5)
                    return
                
                elif p.held_item.item_type == ItemType.RAW_PATTY:
                    stove = self._free_stove(m)
                    if stove:
                        self._push_with_gap(Step.GO_TO, stove)
                        self._push_with_gap(Step.INTERACT, stove)
                    else:
                        self._push(Step.WAIT, None, 0.5)
                    return
                
                else:
                    board = self._free_board(m)
                    if board:
                        self._push_with_gap(Step.GO_TO, board)
                        self._push_with_gap(Step.INTERACT, board)
                    else:
                        self._push(Step.WAIT, None, 0.5)
                    return

            # Mains vides: chercher une tâche de préparation
            for ingredient_type, needs_chopping in self.current_recipe.ingredients:
                needs_cooking = (ingredient_type == ItemType.RAW_PATTY)
                
                if not needs_chopping and not needs_cooking:
                    continue 
                    
                effective_ingredient = ItemType.COOKED_PATTY if needs_cooking else ingredient_type
                if self._assembly_has(m, effective_ingredient, chopped=needs_chopping if needs_chopping else None):
                    continue
                
                if needs_cooking:
                    # ✅ VÉRIFICATION AJOUTÉE: Bot 1 tient-il le steak ?
                    if bot1_player.held_item and bot1_player.held_item.item_type == ItemType.COOKED_PATTY:
                        continue 
                    if (self._stove_with(m, ItemType.COOKED_PATTY) or 
                        self._stove_with(m, ItemType.RAW_PATTY) or
                        self._stove_with(m, ItemType.BURNT_PATTY)):
                        continue

                elif needs_chopping:
                    # ✅ VÉRIFICATION AJOUTÉE: Bot 1 tient-il l'ingrédient coupé ?
                    if (bot1_player.held_item and 
                        bot1_player.held_item.item_type == ingredient_type and 
                        bot1_player.held_item.chopped):
                        continue
                    if self._board_with(m, ingredient_type, chopped=True) or self._board_with(m, ingredient_type, chopped=False):
                        continue
                
                spawn = self._spawn(m, ingredient_type)
                if spawn:
                    self._push_with_gap(Step.GO_TO, spawn)
                    self._push_with_gap(Step.INTERACT, spawn)
                return
            
            self._push(Step.WAIT, None, self._step_gap * 2)
            return

        # --- RÔLE 2: BOT 1 (ASSEMBLER / RUNNER) ---
        elif self.player_index == 1:
            
            # (La logique du Bot 1 reste inchangée, elle est déjà correcte)
            
            for order in m.orders:
                final_dish_type = order.items_needed[0]
                recipe_key = ItemType.PIZZA if final_dish_type == ItemType.PIZZA else final_dish_type

                if recipe_key not in RECIPES:
                    continue 
                
                current_recipe = RECIPES[recipe_key] 

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
                            self._place_held_item_on_assembly(m)
                        return 
                    if uncooked_pizza_station and uncooked_pizza_station.cooking_start_time > 0:
                        self._push_with_gap(Step.GO_TO, uncooked_pizza_station)
                        self._push(Step.WAIT, None, 1.0)
                        return 

                # Étape 3: Assemblage des ingrédients
                for ingredient_type, needs_chopping in current_recipe.ingredients:
                    needs_cooking = (ingredient_type == ItemType.RAW_PATTY)
                    effective_ingredient = ItemType.COOKED_PATTY if needs_cooking else ingredient_type
                    
                    if self._assembly_has(m, effective_ingredient, chopped=needs_chopping if needs_chopping else None):
                        continue
                    
                    if not needs_chopping and not needs_cooking:
                        self._plan_ingredient(m, ingredient_type, needs_chopping)
                        return 
                    
                    elif p.held_item is None:
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
                        self._place_held_item_on_assembly(m)
                        return 
            
            if p.held_item is not None:
                self._place_held_item_on_assembly(m)
            else:
                self._push(Step.WAIT, None, self._step_gap * 2)

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

    def _plan_ingredient(self, m: GameModel, ingredient_type: ItemType, needs_chopping: bool):
        """
        Planifie la récupération d'un ingrédient SIMPLE (non-préparé)
        et l'amène à l'assemblage.
        (Utilisé par Bot 1 pour Pain, Fromage)
        """
        p = self._p(m)
        a = self._assembly(m)

        # Si on tient déjà le bon item, on le pose
        if p.held_item and p.held_item.item_type == ingredient_type:
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)
            return

        # Si on tient un mauvais item, on vide les mains (sur l'assemblage)
        if p.held_item:
            self._place_held_item_on_assembly(m) # Utilise la fonction correcte
            return

        # Si on n'a rien, on va chercher l'item
        spawn = self._spawn(m, ingredient_type)
        if spawn:
            self._push_with_gap(Step.GO_TO, spawn)
            self._push_with_gap(Step.INTERACT, spawn)
            # Une fois qu'on le tient, on l'amène à l'assemblage
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)