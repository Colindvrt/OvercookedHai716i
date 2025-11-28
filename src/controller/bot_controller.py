from enum import Enum, auto
from typing import Optional, List, Tuple, Dict
import time
import math
from src.model.game_model import GameModel, StationType, ItemType, Station, Player, Order
from src.controller.shared_knowledge import SharedKnowledge, Task, TaskType

class Step(Enum):
    GO_TO = auto()
    INTERACT = auto()
    CHOP = auto()
    WAIT = auto()

class AIBot:
    def __init__(self, player_index: int = 0, shared_knowledge: Optional[SharedKnowledge] = None):
        self.player_index = player_index
        self.shared_knowledge = shared_knowledge
        self.current_task: Optional[Task] = None
        self.queue: List[Tuple[Step, Optional[Station], float]] = []
        self._cooldown = 0.0
        self._last_action_ts = 0.0
        self._step_gap = 0.20
        self._gap_until = 0.0
        self._speed = 150.0
        self._last_update_time = time.time()

    def _p(self, m: GameModel) -> Player:
        return m.players[self.player_index]

    def _check_task_completion(self, m: GameModel, task: Task) -> bool:
        p = m.players[self.player_index]

        if task.task_type == TaskType.TAKE:
            return p.held_item is not None and p.held_item.item_type == task.item_type

        elif task.task_type == TaskType.CHOP:
            if p.held_item and p.held_item.item_type == task.item_type and p.held_item.chopped:
                return True
            return False

        elif task.task_type == TaskType.COOK:
            target_item = ItemType.COOKED_PATTY if task.item_type == ItemType.RAW_PATTY else ItemType.PIZZA
            return p.held_item is not None and p.held_item.item_type == target_item
        
        elif task.task_type == TaskType.PLACE:
            if p.held_item is not None: return False 
            assembly = self._assembly(m)
            if assembly:
                for item in assembly.contents:
                    if item.item_type == task.item_type:
                        if task.needs_chopping and not item.chopped: continue
                        return True
                
                if assembly.item and assembly.item.item_type == task.item_type:
                    return True

                if assembly.item:
                    it = assembly.item.item_type
                    if it == ItemType.UNCOOKED_PIZZA:
                        if task.item_type in [ItemType.BREAD, ItemType.TOMATO, ItemType.CHEESE]: return True
                    
                    elif it == ItemType.BURGER:
                        if task.item_type in [ItemType.BREAD, ItemType.COOKED_PATTY, ItemType.TOMATO, ItemType.LETTUCE]: return True
                    
                    elif it == ItemType.SALAD:
                        if task.item_type in [ItemType.LETTUCE, ItemType.TOMATO]: return True

            return False

        elif task.task_type == TaskType.DELIVER:
            for order in m.orders:
                if order.id == task.order_id:
                    return False
            return True

        return False
    
    def _assembly(self, m: GameModel) -> Optional[Station]:
        if self.current_task:
            assigned_pos = self.shared_knowledge.get_assigned_assembly(self.current_task.order_id)
            if assigned_pos:
                for s in m.stations:
                    if (s.x, s.y) == assigned_pos: return s
        for s in m.stations:
            if s.station_type == StationType.ASSEMBLY: return s
        return None

    def _delivery(self, m: GameModel) -> Optional[Station]:
        for s in m.stations:
            if s.station_type == StationType.DELIVERY: return s
        return None

    def _spawn(self, m: GameModel, it: ItemType):
        for s in m.stations:
            if s.station_type == StationType.INGREDIENT_SPAWN and s.ingredient_type == it: return s
        return None

    def _free_board(self, m: GameModel):
        for s in m.stations:
            if s.station_type == StationType.CUTTING_BOARD and s.item is None:
                if self.shared_knowledge.is_station_available(s, self.player_index): return s
        return None

    def _free_stove(self, m: GameModel):
        for s in m.stations:
            if s.station_type == StationType.STOVE and s.item is None:
                if self.shared_knowledge.is_station_available(s, self.player_index): return s
        return None
        
    def _free_furnace(self, m: GameModel):
        for s in m.stations:
            if s.station_type == StationType.FURNACE and s.item is None:
                 if self.shared_knowledge.is_station_available(s, self.player_index): return s
        return None

    def _stove_with(self, m: GameModel, it: ItemType):
        for s in m.stations:
            if s.station_type == StationType.STOVE and s.item and s.item.item_type == it: return s
        return None
        
    def _furnace_with(self, m: GameModel, it: ItemType):
        for s in m.stations:
            if s.station_type == StationType.FURNACE and s.item and s.item.item_type == it: return s
        return None

    def update(self, m: GameModel):
        current_time = time.time()
        dt = current_time - self._last_update_time
        self._last_update_time = current_time

        if self.shared_knowledge:
            for order in m.orders:
                if order.id not in self.shared_knowledge.task_lists:
                    self.shared_knowledge.create_task_list_for_order(order, m.stations)
            
            for order_id in list(self.shared_knowledge.task_lists.keys()):
                if not any(o.id == order_id for o in m.orders):
                    self.shared_knowledge.cleanup_order_task_list(order_id)
                    if self.current_task and self.current_task.order_id == order_id:
                        self.current_task = None
                        self.queue.clear()
                        self._clear_hands(m)

        # 🔥 FIX : Libérer la tâche actuelle si elle est complétée (sinon on reste bloqué dessus)
        if self.current_task:
            if self._check_task_completion(m, self.current_task):
                self.shared_knowledge.complete_task(self.current_task, self.player_index)
                self.current_task = None
                self.queue.clear()

        # Chercher une nouvelle tâche si nécessaire
        if not self.current_task:
            p = m.players[self.player_index]
            held_type = p.held_item.item_type if p.held_item else None
            
            next_task = self.shared_knowledge.get_next_task(self.player_index, held_item_type=held_type)
            
            if next_task:
                self.shared_knowledge.claim_task(next_task, self.player_index)
                self.current_task = next_task
            elif held_type is not None and not self.queue:
                self._clear_hands(m)
        
        # Exécuter la tâche actuelle
        if self.current_task and not self.queue:
            self._execute_task(m, self.current_task)

        if not self.queue: return
        step, station, deadline = self.queue[0]
        
        if step == Step.GO_TO and station:
            p = m.players[self.player_index]
            target_x, target_y = station.x, min(675, station.y + 50)
            diff_x, diff_y = target_x - p.x, target_y - p.y
            distance = math.sqrt(diff_x**2 + diff_y**2)
            
            if distance < 5.0:
                m.move_player(self.player_index, diff_x, diff_y, is_smooth=True)
                self.queue.pop(0)
                self._gap_until = time.time() + 0.1 
            else:
                if distance > 0:
                    move_x = (diff_x / distance) * self._speed * dt
                    move_y = (diff_y / distance) * self._speed * dt
                    m.move_player(self.player_index, move_x, move_y, is_smooth=True)
            return

        if current_time < self._gap_until: return

        if step == Step.WAIT:
            if current_time >= deadline:
                self.queue.pop(0)
                self._gap_until = time.time() + self._step_gap
            return

        if step in [Step.INTERACT, Step.CHOP] and (current_time - self._last_action_ts) > self._cooldown:
            if step == Step.INTERACT:
                m.interact_with_station(self.player_index)
            elif step == Step.CHOP:
                m.chop_at_station(self.player_index)
            
            self._last_action_ts = time.time()
            self.queue.pop(0)
            self._gap_until = time.time() + self._step_gap

    def _push(self, step, station=None, wait=0.0):
        if step == Step.WAIT: self.queue.append((Step.WAIT, None, time.time() + wait))
        else: self.queue.append((step, station, 0.0))

    def _execute_task(self, m: GameModel, task: Task):
        if self.queue: return
        p = m.players[self.player_index]

        if task.task_type == TaskType.TAKE:
            if p.held_item and p.held_item.item_type == task.item_type: return
            
            if task.target_station_type == StationType.INGREDIENT_SPAWN:
                s = self._spawn(m, task.item_type)
                if s:
                    self._push(Step.GO_TO, s)
                    self._push(Step.INTERACT, s)
            elif task.target_station_type == StationType.ASSEMBLY:
                s = self._assembly(m)
                if s and s.item and s.item.item_type == task.item_type:
                    # 🔥 IMPORTANT : Se débarrasser de ce qu'on tient AVANT
                    if p.held_item:
                        self._clear_hands(m)
                        return
                    self._push(Step.GO_TO, s)
                    self._push(Step.INTERACT, s)
                else:
                    # Pizza pas encore assemblée, on attend
                    self._push(Step.WAIT, None, 0.5)

        elif task.task_type == TaskType.CHOP:
            if p.held_item and p.held_item.chopped: return
            board = self._free_board(m)
            if board:
                if self.shared_knowledge.reserve_station(board, self.player_index):
                    task.station_pos = (board.x, board.y)
                    self._push(Step.GO_TO, board)
                    self._push(Step.INTERACT, board)
                    self._push(Step.CHOP, board)
                    self._push(Step.INTERACT, board)
                else: self._push(Step.WAIT, None, 0.5)
            else: self._push(Step.WAIT, None, 0.5)

        elif task.task_type == TaskType.COOK:
            if task.item_type == ItemType.RAW_PATTY:
                cooked = self._stove_with(m, ItemType.COOKED_PATTY)
                if cooked:
                    if p.held_item: self._clear_hands(m)
                    self._push(Step.GO_TO, cooked)
                    self._push(Step.INTERACT, cooked)
                    return
                raw = self._stove_with(m, ItemType.RAW_PATTY)
                if raw:
                    self._push(Step.WAIT, None, 0.5)
                    return
                stove = self._free_stove(m)
                if stove and p.held_item and p.held_item.item_type == ItemType.RAW_PATTY:
                    if self.shared_knowledge.reserve_station(stove, self.player_index):
                        task.station_pos = (stove.x, stove.y)
                        self._push(Step.GO_TO, stove)
                        self._push(Step.INTERACT, stove)
                    else: self._push(Step.WAIT, None, 0.5)

            elif task.item_type == ItemType.UNCOOKED_PIZZA:
                cooked_furnace = self._furnace_with(m, ItemType.PIZZA)
                if cooked_furnace:
                    if p.held_item is None:
                        self._push(Step.GO_TO, cooked_furnace)
                        self._push(Step.INTERACT, cooked_furnace)
                    else: self._clear_hands(m)
                    return
                cooking_furnace = self._furnace_with(m, ItemType.UNCOOKED_PIZZA)
                if cooking_furnace:
                    self._push(Step.WAIT, None, 0.5)
                    return
                if p.held_item and p.held_item.item_type == ItemType.UNCOOKED_PIZZA:
                    furnace = self._free_furnace(m)
                    if furnace:
                        if self.shared_knowledge.reserve_station(furnace, self.player_index):
                            task.station_pos = (furnace.x, furnace.y)
                            self._push(Step.GO_TO, furnace)
                            self._push(Step.INTERACT, furnace)
                        else: self._push(Step.WAIT, None, 0.5)
                    else: self._push(Step.WAIT, None, 0.5)
                else:
                    # 🔥 Si on n'a pas la pizza crue en main, on attend qu'elle soit assemblée
                    self._push(Step.WAIT, None, 0.5)

        elif task.task_type == TaskType.PLACE:
            p = m.players[self.player_index]
            
            has_item = False
            if p.held_item and p.held_item.item_type == task.item_type:
                if task.needs_chopping:
                    if p.held_item.chopped: has_item = True
                else:
                    has_item = True
            
            if has_item:
                assembly = self._assembly(m)
                if assembly:
                    if self.shared_knowledge.reserve_station(assembly, self.player_index):
                        task.station_pos = (assembly.x, assembly.y)
                        self._push(Step.GO_TO, assembly)
                        self._push(Step.INTERACT, assembly)
                    else: self._push(Step.WAIT, None, 0.5)
            else:
                target_station = self._find_station_with_item(m, task.item_type, task.needs_chopping)
                
                if target_station:
                     if self.shared_knowledge.reserve_station(target_station, self.player_index):
                        self._push(Step.GO_TO, target_station)
                        self._push(Step.INTERACT, target_station)
                     else:
                        self._push(Step.WAIT, None, 0.5)
                else:
                     self._push(Step.WAIT, None, 0.5)

        elif task.task_type == TaskType.DELIVER:
            delivery = self._delivery(m)
            if p.held_item and p.held_item.item_type == task.item_type:
                self._push(Step.GO_TO, delivery)
                self._push(Step.INTERACT, delivery)
            else:
                assembly = self._assembly(m)
                if assembly and assembly.item and assembly.item.item_type == task.item_type:
                    if p.held_item: self._clear_hands(m)
                    self._push(Step.GO_TO, assembly)
                    self._push(Step.INTERACT, assembly)
                    return
                if task.item_type == ItemType.PIZZA:
                    furnace = self._furnace_with(m, ItemType.PIZZA)
                    if furnace:
                        if p.held_item: self._clear_hands(m)
                        self._push(Step.GO_TO, furnace)
                        self._push(Step.INTERACT, furnace)
                        return

    def _clear_hands(self, m):
        s = self._free_board(m)
        if s:
            self._push(Step.GO_TO, s)
            self._push(Step.INTERACT, s)
        
    def _find_station_with_item(self, m: GameModel, item_type: ItemType, needs_chopping: bool) -> Optional[Station]:
        for s in m.stations:
            if s.item and s.item.item_type == item_type:
                if needs_chopping and not s.item.chopped:
                    continue
                if self.shared_knowledge.is_station_available(s, self.player_index):
                    return s
        return None