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

    ⚠ Mouvement: le bot se place désormais **SOUS** la case cible (ancre: y + 50px) avant d'interagir.
    """

    def __init__(self, player_index: int = 0):
        self.player_index = player_index
        self.queue: List[Tuple[Step, Optional[Station], float]] = []  # (step, station, deadline)
        self._cooldown = 0.0         # anti-spam pour INTERACT/CHOP (demandé)
        self._last_action_ts = 0.0
        self._step_gap = 0.4            # délai global entre TOUTES les actions (déplacements inclus)
        self._gap_until = 0.0

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

    # ------------- Ancre "SOUS la case" -------------
    def _anchor(self, s: Station) -> Tuple[int, int]:
        """
        Renvoie le point-cible où se placer AVANT d'interagir: sous la case (y + 50).
        On clamp dans l'aire de jeu (0..750, 0..550) par sécurité.
        """
        ax = s.x
        ay = min(550, s.y + 50)  # 1 case (50px) sous la station
        return ax, ay

    # ------------- Proximité / Mouvement / Actions -------------
    def _near(self, px: int, py: int, s: Station, tol: int = 10) -> bool:
        """Considère 'arrivé' si l'on est proche de l'ANCRE (s.x, s.y+50) à ±10px."""
        ax, ay = self._anchor(s)
        return abs(px - ax) <= tol and abs(py - ay) <= tol

    def _move_towards(self, m: GameModel, target_x: int, target_y: int):
        """Un seul pas (50 px) par appel, comme les inputs clavier."""
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
        """
        Fait UN déplacement vers l'ancre sous la station s.
        Retourne True si un pas a été fait, False si déjà à l'ancre.
        """
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

    # ------------- Planification -------------
    def _plan(self, m: GameModel):
        p = self._p(m)
        a = self._assembly(m)
        d = self._delivery(m)

        # Burger en main -> livrer
        if p.held_item and p.held_item.item_type == ItemType.BURGER:
            self._push_with_gap(Step.GO_TO, d)
            self._push_with_gap(Step.INTERACT, d)
            return

        # Burger prêt -> prendre + livrer
        if self._burger_ready_on_assembly(m):
            if p.held_item is None:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
            self._push_with_gap(Step.GO_TO, d)
            self._push_with_gap(Step.INTERACT, d)
            return

        # Pain d'abord
        if not self._assembly_has_bread(m):
            if p.held_item is None:
                bspawn = self._spawn(m, ItemType.BREAD)
                self._push_with_gap(Step.GO_TO, bspawn)
                self._push_with_gap(Step.INTERACT, bspawn)  # ramasser pain
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)      # poser pain
                return
            if p.held_item.item_type == ItemType.BREAD:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            # Libérer les mains logiquement
            held = p.held_item.item_type
            if held in (ItemType.TOMATO, ItemType.LETTUCE):
                board = self._free_board(m)
                if board:
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                return
            if held == ItemType.RAW_PATTY:
                stove = self._free_stove(m)
                if stove:
                    self._push_with_gap(Step.GO_TO, stove)
                    self._push_with_gap(Step.INTERACT, stove)
                return
            if held == ItemType.COOKED_PATTY:
                self._push(Step.WAIT, None, self._step_gap)
                return

        # Steak cuit
        if not self._assembly_has(m, ItemType.COOKED_PATTY):
            if p.held_item and p.held_item.item_type == ItemType.COOKED_PATTY:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            if p.held_item is None:
                stove_cooked = self._stove_with(m, ItemType.COOKED_PATTY)
                if stove_cooked:
                    self._push_with_gap(Step.GO_TO, stove_cooked)
                    self._push_with_gap(Step.INTERACT, stove_cooked)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                    return
                stove_raw = self._stove_with(m, ItemType.RAW_PATTY)
                if stove_raw and stove_raw.cooking_start_time > 0:
                    self._push_with_gap(Step.GO_TO, stove_raw)
                    remaining = max(0.0, stove_raw.cooking_duration - (time.time() - stove_raw.cooking_start_time))
                    self._push(Step.WAIT, None, min(0.5, remaining))
                    return
                rspawn = self._spawn(m, ItemType.RAW_PATTY)
                stove = self._free_stove(m)
                if rspawn and stove:
                    self._push_with_gap(Step.GO_TO, rspawn)
                    self._push_with_gap(Step.INTERACT, rspawn)
                    self._push_with_gap(Step.GO_TO, stove)
                    self._push_with_gap(Step.INTERACT, stove)
                return
            # déposer ce qu'on tient
            held = p.held_item.item_type
            if held in (ItemType.TOMATO, ItemType.LETTUCE):
                board = self._free_board(m)
                if board:
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                return
            if held == ItemType.RAW_PATTY:
                stove = self._free_stove(m)
                if stove:
                    self._push_with_gap(Step.GO_TO, stove)
                    self._push_with_gap(Step.INTERACT, stove)
                return
            if held == ItemType.BREAD:
                self._push(Step.WAIT, None, self._step_gap)
                return

        # Tomate coupée
        if not self._assembly_has_chopped(m, ItemType.TOMATO):
            if p.held_item and p.held_item.item_type == ItemType.TOMATO and p.held_item.chopped:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            if p.held_item is None:
                ready = self._board_with(m, ItemType.TOMATO, chopped=True)
                if ready:
                    self._push_with_gap(Step.GO_TO, ready)
                    self._push_with_gap(Step.INTERACT, ready)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                    return
                tspawn = self._spawn(m, ItemType.TOMATO)
                board = self._free_board(m)
                if tspawn and board:
                    self._push_with_gap(Step.GO_TO, tspawn)
                    self._push_with_gap(Step.INTERACT, tspawn)
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                    self._push_with_gap(Step.CHOP, board)
                    self._push_with_gap(Step.INTERACT, board)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                return
            held = p.held_item.item_type
            if held == ItemType.LETTUCE:
                board = self._free_board(m)
                if board:
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                return
            if held == ItemType.COOKED_PATTY:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            if held == ItemType.RAW_PATTY:
                stove = self._free_stove(m)
                if stove:
                    self._push_with_gap(Step.GO_TO, stove)
                    self._push_with_gap(Step.INTERACT, stove)
                return

        # Salade coupée
        if not self._assembly_has_chopped(m, ItemType.LETTUCE):
            if p.held_item and p.held_item.item_type == ItemType.LETTUCE and p.held_item.chopped:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            if p.held_item is None:
                ready = self._board_with(m, ItemType.LETTUCE, chopped=True)
                if ready:
                    self._push_with_gap(Step.GO_TO, ready)
                    self._push_with_gap(Step.INTERACT, ready)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                    return
                lspawn = self._spawn(m, ItemType.LETTUCE)
                board = self._free_board(m)
                if lspawn and board:
                    self._push_with_gap(Step.GO_TO, lspawn)
                    self._push_with_gap(Step.INTERACT, lspawn)
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                    self._push_with_gap(Step.CHOP, board)
                    self._push_with_gap(Step.INTERACT, board)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
                return
            held = p.held_item.item_type
            if held == ItemType.TOMATO:
                board = self._free_board(m)
                if board:
                    self._push_with_gap(Step.GO_TO, board)
                    self._push_with_gap(Step.INTERACT, board)
                return
            if held == ItemType.COOKED_PATTY:
                self._push_with_gap(Step.GO_TO, a)
                self._push_with_gap(Step.INTERACT, a)
                return
            if held == ItemType.RAW_PATTY:
                stove = self._free_stove(m)
                if stove:
                    self._push_with_gap(Step.GO_TO, stove)
                    self._push_with_gap(Step.INTERACT, stove)
                return

        # Dernier passage à l'assembly pour finaliser (si nécessaire)
        if p.held_item:
            self._push_with_gap(Step.GO_TO, a)
            self._push_with_gap(Step.INTERACT, a)
        else:
            self._push_with_gap(Step.GO_TO, a)
            self._push(Step.WAIT, None, self._step_gap)

    # ------------- Exécution -------------
    def update(self, m: GameModel):
        """Exécute UNE étape à la fois, avec délai global entre TOUTES les actions."""
        if self._assembly(m) is None or self._delivery(m) is None:
            return

        now = time.time()

        # Gap global entre actions
        if now < self._gap_until:
            return

        # Planification si rien en attente
        if not self.queue:
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

        # Pour GO_TO/INTERACT/CHOP liés à une station :
        if station is not None:
            # Se rapprocher de **l'ancre sous la case**
            if self._move_to_anchor_step(m, station):
                self._gap_until = time.time() + self._step_gap
                return
            # On est à l'ancre; on peut continuer.

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

            # Cas spécial : si on vient de prendre le pain au spawn, forcer la pose à l'ASSEMBLY
            if station and station.station_type == StationType.INGREDIENT_SPAWN and station.ingredient_type == ItemType.BREAD:
                p = self._p(m)
                if p.held_item and p.held_item.item_type == ItemType.BREAD:
                    self._reset_queue()
                    a = self._assembly(m)
                    self._push_with_gap(Step.GO_TO, a)
                    self._push_with_gap(Step.INTERACT, a)
            return

        if step == Step.CHOP:
            self._chop(m)
            self._last_action_ts = time.time()
            self.queue.pop(0)
            self._gap_until = time.time() + self._step_gap
            return
