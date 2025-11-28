from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from enum import Enum
from collections import deque
import time
from src.model.game_model import ItemType, Station, Order, StationType

class TaskType(Enum):
    TAKE = "take"; CHOP = "chop"; COOK = "cook"; PLACE = "place"; DELIVER = "deliver"; WAIT_COOKING = "wait_cooking"

@dataclass
class Task:
    task_id: int; order_id: int; task_type: TaskType; item_type: ItemType
    target_station_type: Optional[StationType] = None
    needs_chopping: bool = False; claimed_by: Optional[int] = None
    completed: bool = False; cooking_start_time: float = 0.0
    station_pos: Optional[Tuple[int, int]] = None; ingredient_group: int = 0
    dependencies: List[int] = field(default_factory=list)

@dataclass
class TaskList:
    order_id: int
    tasks: deque = field(default_factory=deque)
    group_owners: Dict[int, int] = field(default_factory=dict)

    def get_first_doable_task(self, agent_id: int) -> Optional[Task]:
        completed_ids = {t.task_id for t in self.tasks if t.completed}

        for task in self.tasks:
            if task.completed: continue
            if task.claimed_by is not None and task.claimed_by != agent_id: continue
            
            if task.dependencies and not all(d in completed_ids for d in task.dependencies):
                continue

            grp = task.ingredient_group
            if grp > 0:
                owner = self.group_owners.get(grp)
                if owner == agent_id:
                    # 🔥 FIX : Vérifier qu'on a fini TOUTES les tâches précédentes de CE groupe
                    my_tasks_in_group = [t for t in self.tasks if t.ingredient_group == grp and t.claimed_by == agent_id]
                    if any(t.task_id < task.task_id and not t.completed for t in my_tasks_in_group):
                        continue  # On saute cette tâche, il faut finir les précédentes
                    return task
                elif owner is None and task.claimed_by is None:
                    # 🔥 FIX : Un agent ne peut pas prendre un NOUVEAU groupe s'il en possède déjà un autre non terminé
                    my_current_groups = set()
                    for t in self.tasks:
                        if t.claimed_by == agent_id and not t.completed and t.ingredient_group > 0:
                            my_current_groups.add(t.ingredient_group)
                    
                    if my_current_groups:
                        continue  # On a déjà un groupe en cours, on ne peut pas en prendre un autre
                    
                    if not any(t.ingredient_group == grp and t.task_id < task.task_id and not t.completed for t in self.tasks):
                        return task
            else:
                if task.claimed_by is None or task.claimed_by == agent_id: return task
        
        return None

class SharedKnowledge:
    def __init__(self):
        self.task_lists: Dict[int, TaskList] = {}
        self.station_locks: Dict[tuple, int] = {}
        self.order_assembly_assignments: Dict[int, tuple] = {}
        self._next_task_id = 0

    def update_orders(self, orders: List[Order]): pass

    def create_task_list_for_order(self, order: Order, stations: List[Station]):
        if order.id in self.task_lists: return
        if order.id not in self.order_assembly_assignments:
            assigned_pos = self._find_available_assembly(stations)
            if not assigned_pos: return 
            self.order_assembly_assignments[order.id] = assigned_pos

        task_list = TaskList(order_id=order.id)
        final_dish_type = order.items_needed[0]
        
        if final_dish_type == ItemType.BURGER: self._create_burger_tasks(task_list)
        elif final_dish_type == ItemType.SALAD: self._create_salad_tasks(task_list)
        elif final_dish_type == ItemType.PIZZA: self._create_pizza_tasks(task_list)
        
        task_list.tasks.append(Task(self._next_task_id, order.id, TaskType.DELIVER, final_dish_type, ingredient_group=100))
        self._next_task_id += 1
        self.task_lists[order.id] = task_list

    def _find_available_assembly(self, stations: List[Station]) -> Optional[tuple]:
        assembly_positions = [(s.x, s.y) for s in stations if s.station_type == StationType.ASSEMBLY]
        assigned = set(self.order_assembly_assignments.values())
        for pos in assembly_positions:
            if pos not in assigned: return pos
        return None

    def get_assigned_assembly(self, order_id: int) -> Optional[tuple]:
        return self.order_assembly_assignments.get(order_id)

    def _create_burger_tasks(self, task_list):
        tid = self._next_task_id
        oid = task_list.order_id
        
        place_bread_id = tid + 1
        
        task_list.tasks.append(Task(tid, oid, TaskType.TAKE, ItemType.BREAD, StationType.INGREDIENT_SPAWN, ingredient_group=1))
        task_list.tasks.append(Task(tid+1, oid, TaskType.PLACE, ItemType.BREAD, StationType.ASSEMBLY, ingredient_group=1))
        
        place_patty_id = tid + 4
        task_list.tasks.append(Task(tid+2, oid, TaskType.TAKE, ItemType.RAW_PATTY, StationType.INGREDIENT_SPAWN, ingredient_group=2))
        task_list.tasks.append(Task(tid+3, oid, TaskType.COOK, ItemType.RAW_PATTY, StationType.STOVE, ingredient_group=2))
        task_list.tasks.append(Task(place_patty_id, oid, TaskType.PLACE, ItemType.COOKED_PATTY, StationType.ASSEMBLY, ingredient_group=2))
        
        place_tomato_id = tid + 7
        task_list.tasks.append(Task(tid+5, oid, TaskType.TAKE, ItemType.TOMATO, StationType.INGREDIENT_SPAWN, ingredient_group=3))
        task_list.tasks.append(Task(tid+6, oid, TaskType.CHOP, ItemType.TOMATO, StationType.CUTTING_BOARD, ingredient_group=3))
        task_list.tasks.append(Task(place_tomato_id, oid, TaskType.PLACE, ItemType.TOMATO, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=3, dependencies=[place_bread_id]))
        
        place_lettuce_id = tid + 10
        task_list.tasks.append(Task(tid+8, oid, TaskType.TAKE, ItemType.LETTUCE, StationType.INGREDIENT_SPAWN, ingredient_group=4))
        task_list.tasks.append(Task(tid+9, oid, TaskType.CHOP, ItemType.LETTUCE, StationType.CUTTING_BOARD, ingredient_group=4))
        task_list.tasks.append(Task(place_lettuce_id, oid, TaskType.PLACE, ItemType.LETTUCE, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=4, dependencies=[place_bread_id]))
        
        # 🔥 LA LIVRAISON ATTEND QUE TOUT SOIT POSÉ
        task_list.tasks.append(Task(tid+11, oid, TaskType.DELIVER, ItemType.BURGER, ingredient_group=100, dependencies=[place_patty_id, place_tomato_id, place_lettuce_id]))
        
        self._next_task_id += 12

    def _create_salad_tasks(self, tl):
        tid, oid = self._next_task_id, tl.order_id
        
        place_lettuce_id = tid + 2
        tl.tasks.append(Task(tid, oid, TaskType.TAKE, ItemType.LETTUCE, StationType.INGREDIENT_SPAWN, ingredient_group=1))
        tl.tasks.append(Task(tid+1, oid, TaskType.CHOP, ItemType.LETTUCE, StationType.CUTTING_BOARD, ingredient_group=1))
        tl.tasks.append(Task(place_lettuce_id, oid, TaskType.PLACE, ItemType.LETTUCE, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=1))
        
        place_tomato_id = tid + 5
        tl.tasks.append(Task(tid+3, oid, TaskType.TAKE, ItemType.TOMATO, StationType.INGREDIENT_SPAWN, ingredient_group=2))
        tl.tasks.append(Task(tid+4, oid, TaskType.CHOP, ItemType.TOMATO, StationType.CUTTING_BOARD, ingredient_group=2))
        tl.tasks.append(Task(place_tomato_id, oid, TaskType.PLACE, ItemType.TOMATO, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=2))
        
        # 🔥 LA LIVRAISON ATTEND QUE TOUT SOIT POSÉ
        tl.tasks.append(Task(tid+6, oid, TaskType.DELIVER, ItemType.SALAD, ingredient_group=100, dependencies=[place_lettuce_id, place_tomato_id]))
        
        self._next_task_id += 7

    def _create_pizza_tasks(self, tl):
        tid, oid = self._next_task_id, tl.order_id
        
        place_base_id = tid + 1
        tl.tasks.append(Task(tid, oid, TaskType.TAKE, ItemType.BREAD, StationType.INGREDIENT_SPAWN, ingredient_group=1))
        tl.tasks.append(Task(place_base_id, oid, TaskType.PLACE, ItemType.BREAD, StationType.ASSEMBLY, ingredient_group=1))
        
        place_tomato_id = tid + 4
        tl.tasks.append(Task(tid+2, oid, TaskType.TAKE, ItemType.TOMATO, StationType.INGREDIENT_SPAWN, ingredient_group=2))
        tl.tasks.append(Task(tid+3, oid, TaskType.CHOP, ItemType.TOMATO, StationType.CUTTING_BOARD, ingredient_group=2))
        tl.tasks.append(Task(place_tomato_id, oid, TaskType.PLACE, ItemType.TOMATO, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=2, dependencies=[place_base_id]))
        
        place_cheese_id = tid + 6
        tl.tasks.append(Task(tid+5, oid, TaskType.TAKE, ItemType.CHEESE, StationType.INGREDIENT_SPAWN, ingredient_group=3))
        tl.tasks.append(Task(place_cheese_id, oid, TaskType.PLACE, ItemType.CHEESE, StationType.ASSEMBLY, ingredient_group=3, dependencies=[place_base_id]))
        
        take_pizza_id = tid + 7
        cook_pizza_id = tid + 8
        tl.tasks.append(Task(take_pizza_id, oid, TaskType.TAKE, ItemType.UNCOOKED_PIZZA, StationType.ASSEMBLY, ingredient_group=4, dependencies=[place_tomato_id, place_cheese_id]))
        tl.tasks.append(Task(cook_pizza_id, oid, TaskType.COOK, ItemType.UNCOOKED_PIZZA, StationType.FURNACE, ingredient_group=4))
        
        # 🔥 LA LIVRAISON DOIT ATTENDRE QUE LA CUISSON SOIT FINIE
        tl.tasks.append(Task(tid+9, oid, TaskType.DELIVER, ItemType.PIZZA, ingredient_group=100, dependencies=[cook_pizza_id]))
        
        self._next_task_id += 10

    def claim_task(self, task: Task, agent_id: int):
        task.claimed_by = agent_id
        if task.ingredient_group > 0:
            tl = self.task_lists.get(task.order_id)
            if tl and task.ingredient_group not in tl.group_owners:
                tl.group_owners[task.ingredient_group] = agent_id

    def complete_task(self, task: Task, agent_id: int):
        if task.claimed_by == agent_id:
            task.completed = True
            print(f"✅ Agent {agent_id} termine : {task.task_type.value} {task.item_type.value}")
            if task.station_pos: 
                self.release_station_at(task.station_pos, agent_id)
            
            # 🔥 NOUVEAU : Libérer le groupe si toutes ses tâches sont finies
            tl = self.task_lists.get(task.order_id)
            if tl and task.ingredient_group > 0:
                group_tasks = [t for t in tl.tasks if t.ingredient_group == task.ingredient_group]
                if all(t.completed for t in group_tasks):
                    if task.ingredient_group in tl.group_owners:
                        print(f"🔓 Agent {agent_id} libère le groupe {task.ingredient_group}")
                        del tl.group_owners[task.ingredient_group]

    def cleanup_order_task_list(self, order_id: int):
        if order_id in self.task_lists: del self.task_lists[order_id]
        if order_id in self.order_assembly_assignments: del self.order_assembly_assignments[order_id]

    def reserve_station(self, station: Station, agent_id: int) -> bool:
        key = (station.x, station.y)
        if key not in self.station_locks or self.station_locks[key] == agent_id:
            self.station_locks[key] = agent_id
            return True
        return False

    def release_station_at(self, pos: tuple, agent_id: int):
        if pos in self.station_locks and self.station_locks[pos] == agent_id:
            del self.station_locks[pos]

    def is_station_available(self, station: Station, agent_id: int) -> bool:
        key = (station.x, station.y)
        if key not in self.station_locks: return True
        return self.station_locks[key] == agent_id

    def get_next_task(self, agent_id: int, held_item_type: Optional[ItemType] = None) -> Optional[Task]:
        if held_item_type:
            for order_id in list(self.task_lists.keys()):
                task_list = self.task_lists[order_id]
                
                for task in task_list.tasks:
                    if task.completed: continue
                    
                    is_matching_item = (task.item_type == held_item_type)
                    
                    if is_matching_item:
                        if self._is_task_doable(task_list, task, agent_id):
                            return task
            
            return None

        for order_id in list(self.task_lists.keys()):
            task_list = self.task_lists[order_id]
            
            # 🔍 DEBUG : Afficher les tâches disponibles
            print(f"\n[Agent {agent_id}] Recherche de tâche pour order {order_id}")
            for t in task_list.tasks:
                if not t.completed:
                    deps_ok = not t.dependencies or all(d in {x.task_id for x in task_list.tasks if x.completed} for d in t.dependencies)
                    print(f"  - {t.task_type.value} {t.item_type.value} (grp={t.ingredient_group}, deps_ok={deps_ok}, claimed={t.claimed_by})")
            
            task = task_list.get_first_doable_task(agent_id)
            if task: 
                print(f"✅ [Agent {agent_id}] Tâche trouvée : {task.task_type.value} {task.item_type.value}")
                return task
            else:
                print(f"❌ [Agent {agent_id}] Aucune tâche faisable")
        return None

    def _is_task_doable(self, task_list: TaskList, task: Task, agent_id: int) -> bool:
        if task.completed: return False
        if task.claimed_by is not None and task.claimed_by != agent_id: return False
        
        completed_ids = {t.task_id for t in task_list.tasks if t.completed}
        if task.dependencies and not all(d in completed_ids for d in task.dependencies):
            return False
            
        grp = task.ingredient_group
        if grp > 0:
            owner = task_list.group_owners.get(grp)
            if owner is not None and owner != agent_id: return False
        
        return True