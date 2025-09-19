from enum import Enum, auto
from typing import Optional, List, Tuple
import time

from src.model.game_model import (
    GameModel, StationType, ItemType, Station, Player
)

# Étapes atomiques
class Step(Enum):
    GO_TO = auto()
    INTERACT = auto()
    CHOP = auto()
    WAIT = auto()

class AIBot:
    """
    Bot pas-à-pas (une action à la fois) avec délai global entre actions.
    Respect strict: une seule chose en main.
    Recette: pain (sur ASSEMBLY) -> steak cuit -> tomate coupée -> salade coupée -> burger -> livraison
    """

    def __init__(self, player_index: int = 0):
        self.player_index = player_index
        self.queue: List[Tuple[Step, Optional[Station], float]] = []  # (step, station, deadline)
        self._cooldown = 0.7              # anti-spam interact/chop
        self._last_action_ts = 0.0
        self._step_gap = 0.7              # délai global entre TOUTES les actions
        self._gap_until = 0.0
        self._current_objective = None    # 🔧 Ajout pour suivre l'objectif actuel

    # ------------- Helpers accès modèle -------------
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

    # ------------- État assemblage -------------
    def _assembly_has_bread(self, m: GameModel) -> bool:
        a = self._assembly(m)
        return any(i.item_type == ItemType.BREAD for i in a.contents)

    def _assembly_has(self, m: GameModel, it: ItemType) -> bool:
        a = self._assembly(m)
        return any(i.item_type == it for i in a.contents)

    def _assembly_has_chopped(self, m: GameModel, it: ItemType) -> bool:
        a = self._assembly(m)
        return any(i.item_type == it and i.chopped for i in a.contents)

    def _burger_ready_on_assembly(self, m: GameModel) -> bool:
        a = self._assembly(m)
        return a.item is not None and a.item.item_type == ItemType.BURGER

    # ------------- Mouvement / actions -------------
    def _near(self, px: int, py: int, s: Station, dist: int = 70) -> bool:
        return abs(px - s.x) + abs(py - s.y) <= dist

    def _move_towards(self, m: GameModel, target_x: int, target_y: int):
        """Un seul pas (50 px) par appel, comme tes inputs clavier."""
        p = self._p(m)
        dx = 0
        dy = 0
        if p.x < target_x: dx = 1
        elif p.x > target_x: dx = -1
        elif p.y < target_y: dy = 1
        elif p.y > target_y: dy = -1
        if dx != 0 or dy != 0:
            m.move_player(self.player_index, dx, dy)

    def _interact(self, m: GameModel):
        m.interact_with_station(self.player_index)

    def _chop(self, m: GameModel):
        m.chop_at_station(self.player_index)

    # ------------- Queue utils -------------
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
        self._current_objective = None  # 🔧 Reset l'objectif

    def _set_objective(self, objective: str):
        """🔧 Définit l'objectif actuel pour éviter les conflits"""
        self._current_objective = objective

    # ------------- Planification -------------
    def _plan(self, m: GameModel):
        p = self._p(m)
        a = self._assembly(m)
        d = self._delivery(m)

        # 🔧 Priorité absolue : si on a du pain en main et pas sur l'assembly
        if (p.held_item and p.held_item.item_type == ItemType.BREAD and 
            not self._assembly_has_bread(m)):
            self._set_objective("place_bread")
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)
            return

        # Burger en main -> livrer
        if p.held_item and p.held_item.item_type == ItemType.BURGER:
            self._set_objective("deliver_burger")
            self._push_with_gap(Step.GO_TO, d)
            self._push_with_gap(Step.INTERACT, d)
            return

        # Burger prêt -> prendre + livrer
        if self._burger_ready_on_assembly(m):
            self._set_objective("take_and_deliver_burger")
            if p.held_item is None:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
            self._push_with_gap(Step.GO_TO, d)
            self._push_with_gap(Step.INTERACT, d)
            return

        # 🔧 Pain d'abord - logique simplifiée et sécurisée
        if not self._assembly_has_bread(m):
            self._set_objective("get_bread")
            if p.held_item is None:
                bspawn = self._spawn(m, ItemType.BREAD)
                if bspawn:
                    self._push_with_gap(Step.GO_TO, bspawn)
                    self._push_with_gap(Step.INTERACT, bspawn)
                return
            # 🔧 Si on a le pain en main, le poser DIRECTEMENT sur l'assembly
            elif p.held_item.item_type == ItemType.BREAD:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            # 🔧 Si on a autre chose que le pain, le poser intelligemment
            else:
                self._clear_hands_strategically(m, p.held_item.item_type)
                return

        # Steak cuit
        if not self._assembly_has(m, ItemType.COOKED_PATTY):
            self._set_objective("get_cooked_patty")
            if p.held_item and p.held_item.item_type == ItemType.COOKED_PATTY:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            
            if p.held_item is None:
                stove_cooked = self._stove_with(m, ItemType.COOKED_PATTY)
                if stove_cooked:
                    self._push_with_gap(Step.GO_TO, stove_cooked)
                    self._push_with_gap(Step.INTERACT, stove_cooked)
                    return
                
                stove_raw = self._stove_with(m, ItemType.RAW_PATTY)
                if stove_raw and stove_raw.cooking_start_time > 0:
                    self._push_with_gap(Step.GO_TO, stove_raw)
                    remaining = max(0.0, stove_raw.cooking_duration - (time.time() - stove_raw.cooking_start_time))
                    if remaining < 0.5:  # Presque prêt
                        self._push(Step.WAIT, None, remaining + 0.1)
                    return
                
                # Commencer la cuisson
                rspawn = self._spawn(m, ItemType.RAW_PATTY)
                stove = self._free_stove(m)
                if rspawn and stove:
                    self._push_with_gap(Step.GO_TO, rspawn)
                    self._push_with_gap(Step.INTERACT, rspawn)
                    self._push_with_gap(Step.GO_TO, stove)
                    self._push_with_gap(Step.INTERACT, stove)
                return
            else:
                # Poser ce qu'on a en main
                self._clear_hands_strategically(m, p.held_item.item_type)
                return

        # Tomate coupée
        if not self._assembly_has_chopped(m, ItemType.TOMATO):
            self._set_objective("get_chopped_tomato")
            self._handle_chopped_ingredient(m, ItemType.TOMATO)
            return

        # Salade coupée
        if not self._assembly_has_chopped(m, ItemType.LETTUCE):
            self._set_objective("get_chopped_lettuce")
            self._handle_chopped_ingredient(m, ItemType.LETTUCE)
            return

        # Dernier passage à l'assembly pour finaliser
        self._set_objective("finalize_burger")
        if p.held_item:
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)
        else:
            self._push_with_gap(Step.GO_TO, a)
            self._push(Step.WAIT, None, self._step_gap)

    def _clear_hands_strategically(self, m: GameModel, held_type: ItemType):
        """🔧 Fonction pour poser intelligemment l'objet en main"""
        a = self._assembly(m)
        
        if held_type in (ItemType.TOMATO, ItemType.LETTUCE):
            board = self._free_board(m)
            if board:
                self._push_with_gap(Step.GO_TO, board)
                self._push_with_gap(Step.INTERACT, board)
        elif held_type == ItemType.RAW_PATTY:
            stove = self._free_stove(m)
            if stove:
                self._push_with_gap(Step.GO_TO, stove)
                self._push_with_gap(Step.INTERACT, stove)
        elif held_type in (ItemType.COOKED_PATTY, ItemType.BREAD):
            # 🔧 Le steak cuit ET le pain vont directement à l'assembly
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)
        else:
            # Par défaut, attendre un peu
            self._push(Step.WAIT, None, self._step_gap)

    def _handle_chopped_ingredient(self, m: GameModel, ingredient_type: ItemType):
        """🔧 Gère la logique pour les ingrédients à couper"""
        p = self._p(m)
        a = self._assembly(m)
        
        # Si on a déjà l'ingrédient coupé en main
        if (p.held_item and p.held_item.item_type == ingredient_type and 
            p.held_item.chopped):
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)
            return
        
        if p.held_item is None:
            # Chercher l'ingrédient déjà coupé
            ready = self._board_with(m, ingredient_type, chopped=True)
            if ready:
                self._push_with_gap(Step.GO_TO, ready)
                self._push_with_gap(Step.INTERACT, ready)
                return
            
            # Commencer le processus de coupe
            spawn = self._spawn(m, ingredient_type)
            board = self._free_board(m)
            if spawn and board:
                self._push_with_gap(Step.GO_TO, spawn)
                self._push_with_gap(Step.INTERACT, spawn)
                self._push_with_gap(Step.GO_TO, board)
                self._push_with_gap(Step.INTERACT, board)
                self._push_with_gap(Step.CHOP, board)
                self._push_with_gap(Step.INTERACT, board)
            return
        else:
            # Poser ce qu'on a en main
            self._clear_hands_strategically(m, p.held_item.item_type)
            return

    # ------------- Exécution -------------
    def update(self, m: GameModel):
        """Exécute UNE étape à la fois, avec délai global entre TOUTES les actions."""
        if self._assembly(m) is None or self._delivery(m) is None:
            return

        now = time.time()

        # Gap global entre actions
        if now < self._gap_until:
            return

        # 🔧 Vérification de cohérence - ne replanifier que si nécessaire
        if not self.queue or self._should_replan(m):
            self._plan(m)
            if not self.queue:
                return

        step, station, deadline = self.queue[0]

        # WAIT: patienter
        if step == Step.WAIT:
            if now >= deadline:
                self.queue.pop(0)
                self._gap_until = time.time() + self._step_gap
            return

        # Pour GO_TO/INTERACT/CHOP liés à une station : se rapprocher d'abord
        if station is not None:
            p = self._p(m)
            if not self._near(p.x, p.y, station):
                self._move_towards(m, station.x, station.y)
                self._gap_until = time.time() + self._step_gap
                return

        # Anti-spam pour INTERACT/CHOP
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

    def _should_replan(self, m: GameModel) -> bool:
        """🔧 Détermine s'il faut replanifier"""
        p = self._p(m)
        
        # Replanifier si l'objectif actuel n'est plus valide
        if self._current_objective == "place_bread":
            # Si on n'a plus le pain en main ou si il est déjà posé
            return not (p.held_item and p.held_item.item_type == ItemType.BREAD) or self._assembly_has_bread(m)
        
        if self._current_objective == "get_bread":
            # Si le pain est maintenant sur l'assembly
            return self._assembly_has_bread(m)
        
        # Pour les autres objectifs, moins de replanification agressive
        return False