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
    # Liste des tâches obligatoires avant de commencer celle-ci
    dependencies: List[int] = field(default_factory=list)

@dataclass
class TaskList:
    order_id: int
    tasks: deque = field(default_factory=deque)
    group_owners: Dict[int, int] = field(default_factory=dict)

    def get_first_doable_task(self, agent_id: int) -> Optional[Task]:
        # Liste des tâches terminées pour vérifier les pré-requis
        completed_ids = {t.task_id for t in self.tasks if t.completed}

        for task in self.tasks:
            if task.completed: continue
            if task.claimed_by is not None and task.claimed_by != agent_id: continue
            
            # 1. Vérification STRICTE des dépendances
            # Si une tâche requise n'est pas marquée "completed", on ne touche pas à celle-ci
            if task.dependencies and not all(d in completed_ids for d in task.dependencies):
                continue

            # 2. Logique de Groupe (Propriété)
            grp = task.ingredient_group
            if grp > 0:
                owner = self.group_owners.get(grp)
                if owner == agent_id: return task # C'est ma chaîne, je continue
                elif owner is None and task.claimed_by is None:
                    # Personne n'a ce groupe, je peux le prendre si je ne saute pas d'étape
                    # (On vérifie qu'il n'y a pas de tâche non faite avec ID plus petit dans ce groupe)
                    if not any(t.ingredient_group == grp and t.task_id < task.task_id and not t.completed for t in self.tasks):
                        return task
            else:
                # Tâche sans groupe (ex: Livraison)
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

        # ✅ La tâche DELIVER est créée dans chaque _create_*_tasks avec les bonnes dépendances
        if final_dish_type == ItemType.BURGER: self._create_burger_tasks(task_list)
        elif final_dish_type == ItemType.SALAD: self._create_salad_tasks(task_list)
        elif final_dish_type == ItemType.PIZZA: self._create_pizza_tasks(task_list)

        self.task_lists[order.id] = task_list

    def _find_available_assembly(self, stations: List[Station]) -> Optional[tuple]:
        assembly_positions = [(s.x, s.y) for s in stations if s.station_type == StationType.ASSEMBLY]
        assigned = set(self.order_assembly_assignments.values())
        for pos in assembly_positions:
            if pos not in assigned: return pos
        return None

    def get_assigned_assembly(self, order_id: int) -> Optional[tuple]:
        return self.order_assembly_assignments.get(order_id)

    # --- CRÉATION DES TÂCHES ---
    def _create_burger_tasks(self, task_list):
        tid = self._next_task_id
        oid = task_list.order_id

        # Grp 1 : Pain (Base) - DOIT ÊTRE FAIT EN PREMIER
        place_bread_id = tid + 1
        task_list.tasks.append(Task(tid, oid, TaskType.TAKE, ItemType.BREAD, StationType.INGREDIENT_SPAWN, ingredient_group=1))
        task_list.tasks.append(Task(tid+1, oid, TaskType.PLACE, ItemType.BREAD, StationType.ASSEMBLY, ingredient_group=1))

        # Grp 2 : Steak (peut être fait en parallèle)
        place_patty_id = tid + 4
        task_list.tasks.append(Task(tid+2, oid, TaskType.TAKE, ItemType.RAW_PATTY, StationType.INGREDIENT_SPAWN, ingredient_group=2))
        task_list.tasks.append(Task(tid+3, oid, TaskType.COOK, ItemType.RAW_PATTY, StationType.STOVE, ingredient_group=2))
        task_list.tasks.append(Task(tid+4, oid, TaskType.PLACE, ItemType.COOKED_PATTY, StationType.ASSEMBLY, needs_chopping=False, ingredient_group=2, dependencies=[place_bread_id]))

        # Grp 3 : Tomate - ✅ DÉPENDANCE DÈS LE TAKE
        place_tomato_id = tid + 7
        task_list.tasks.append(Task(tid+5, oid, TaskType.TAKE, ItemType.TOMATO, StationType.INGREDIENT_SPAWN, ingredient_group=3, dependencies=[place_bread_id]))
        task_list.tasks.append(Task(tid+6, oid, TaskType.CHOP, ItemType.TOMATO, StationType.CUTTING_BOARD, ingredient_group=3))
        task_list.tasks.append(Task(tid+7, oid, TaskType.PLACE, ItemType.TOMATO, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=3))

        # Grp 4 : Salade + DELIVER (dernier ingrédient = livraison automatique)
        place_lettuce_id = tid + 10
        task_list.tasks.append(Task(tid+8, oid, TaskType.TAKE, ItemType.LETTUCE, StationType.INGREDIENT_SPAWN, ingredient_group=4, dependencies=[place_bread_id]))
        task_list.tasks.append(Task(tid+9, oid, TaskType.CHOP, ItemType.LETTUCE, StationType.CUTTING_BOARD, ingredient_group=4))
        task_list.tasks.append(Task(tid+10, oid, TaskType.PLACE, ItemType.LETTUCE, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=4))
        task_list.tasks.append(Task(tid+11, oid, TaskType.DELIVER, ItemType.BURGER, ingredient_group=4, dependencies=[place_bread_id, place_patty_id, place_tomato_id, place_lettuce_id]))

        self._next_task_id += 12

    def _create_salad_tasks(self, tl):
        tid, oid = self._next_task_id, tl.order_id

        # Salade
        place_lettuce_id = tid + 2
        tl.tasks.append(Task(tid, oid, TaskType.TAKE, ItemType.LETTUCE, StationType.INGREDIENT_SPAWN, ingredient_group=1))
        tl.tasks.append(Task(tid+1, oid, TaskType.CHOP, ItemType.LETTUCE, StationType.CUTTING_BOARD, ingredient_group=1))
        tl.tasks.append(Task(tid+2, oid, TaskType.PLACE, ItemType.LETTUCE, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=1))

        # Tomate + DELIVER (dernier ingrédient = livraison automatique)
        place_tomato_id = tid + 5
        tl.tasks.append(Task(tid+3, oid, TaskType.TAKE, ItemType.TOMATO, StationType.INGREDIENT_SPAWN, ingredient_group=2))
        tl.tasks.append(Task(tid+4, oid, TaskType.CHOP, ItemType.TOMATO, StationType.CUTTING_BOARD, ingredient_group=2))
        tl.tasks.append(Task(tid+5, oid, TaskType.PLACE, ItemType.TOMATO, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=2))
        tl.tasks.append(Task(tid+6, oid, TaskType.DELIVER, ItemType.SALAD, ingredient_group=2, dependencies=[place_lettuce_id, place_tomato_id]))

        self._next_task_id += 7

    def _create_pizza_tasks(self, tl):
        tid, oid = self._next_task_id, tl.order_id
        place_base_id = tid + 1
        place_tomato_id = tid + 4
        place_cheese_id = tid + 6
        cook_pizza_id = tid + 8

        # Grp 1 : Pain (Base) - DOIT ÊTRE FAIT EN PREMIER
        tl.tasks.append(Task(tid, oid, TaskType.TAKE, ItemType.BREAD, StationType.INGREDIENT_SPAWN, ingredient_group=1))
        tl.tasks.append(Task(tid+1, oid, TaskType.PLACE, ItemType.BREAD, StationType.ASSEMBLY, ingredient_group=1))

        # Grp 2 : Tomate - ✅ DÉPENDANCE DÈS LE TAKE
        tl.tasks.append(Task(tid+2, oid, TaskType.TAKE, ItemType.TOMATO, StationType.INGREDIENT_SPAWN, ingredient_group=2, dependencies=[place_base_id]))
        tl.tasks.append(Task(tid+3, oid, TaskType.CHOP, ItemType.TOMATO, StationType.CUTTING_BOARD, ingredient_group=2))
        tl.tasks.append(Task(tid+4, oid, TaskType.PLACE, ItemType.TOMATO, StationType.ASSEMBLY, needs_chopping=True, ingredient_group=2))

        # Grp 3 : Fromage - ✅ DÉPENDANCE DÈS LE TAKE
        tl.tasks.append(Task(tid+5, oid, TaskType.TAKE, ItemType.CHEESE, StationType.INGREDIENT_SPAWN, ingredient_group=3, dependencies=[place_base_id]))
        tl.tasks.append(Task(tid+6, oid, TaskType.PLACE, ItemType.CHEESE, StationType.ASSEMBLY, ingredient_group=3))

        # Grp 4 : Cuisson ET Livraison (MÊME AGENT) - ✅ Attend que tous les ingrédients soient posés
        tl.tasks.append(Task(tid+7, oid, TaskType.TAKE, ItemType.UNCOOKED_PIZZA, StationType.ASSEMBLY, ingredient_group=4, dependencies=[place_tomato_id, place_cheese_id]))
        tl.tasks.append(Task(tid+8, oid, TaskType.COOK, ItemType.UNCOOKED_PIZZA, StationType.FURNACE, ingredient_group=4))
        tl.tasks.append(Task(tid+9, oid, TaskType.DELIVER, ItemType.PIZZA, ingredient_group=4, dependencies=[cook_pizza_id]))

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
            if task.station_pos: self.release_station_at(task.station_pos, agent_id)
            
            # --- AUTO-CLAIM NEXT STEP (Continuity) ---
            # Si on vient de poser un ingrédient final OU de finir de cuire (Pizza), on doit enchaîner
            if task.task_type in [TaskType.PLACE, TaskType.COOK]:
                 tl = self.task_lists.get(task.order_id)
                 if tl:
                     # On cherche la prochaine tâche qui dépend DIRECTEMENT de celle qu'on vient de finir
                     # OU qui dépend de l'ensemble des tâches de PLACE (cas du burger/salade)
                     for next_task in tl.tasks:
                         # Si la tâche suivante est déjà prise, on passe
                         if next_task.claimed_by is not None: continue
                         
                         # Cas 1: Dépendance directe (ex: Pizza crue -> Cuisson)
                         is_direct_dependency = task.task_id in next_task.dependencies
                         
                         # Cas 2: C'est une tâche de récupération/livraison qui attend que tout soit posé
                         # On vérifie si TOUTES ses dépendances sont satisfaites
                         completed_ids = {t.task_id for t in tl.tasks if t.completed}
                         # On ajoute la tâche courante comme complétée (car on est dans complete_task)
                         completed_ids.add(task.task_id)
                         
                         are_dependencies_met = next_task.dependencies and all(d in completed_ids for d in next_task.dependencies)
                         
                         if are_dependencies_met:
                             # Si c'est une tâche logique pour enchaîner
                             if next_task.task_type in [TaskType.TAKE, TaskType.DELIVER, TaskType.COOK]:
                                 self.claim_task(next_task, agent_id)
                                 return # On ne prend qu'une seule tâche suivante

    def release_assembly_for_order(self, order_id: int):
        """Libère la table d'assemblage pour cette commande (plat pris de la table)"""
        if order_id in self.order_assembly_assignments:
            del self.order_assembly_assignments[order_id]

    def cleanup_order_task_list(self, order_id: int):
        # On supprime seulement quand toute la commande est finie/livrée
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

    def get_next_task(self, agent_id: int, agent_pos: Tuple[float, float], stations: List[Station], held_item: Optional[ItemType] = None) -> Optional[Task]:
        # 1. Priorité ABSOLUE : Tâches de livraison ou récupération de plat assemblé
        # On parcourt toutes les tâches pour trouver une livraison en attente
        for order_id in list(self.task_lists.keys()):
            task_list = self.task_lists[order_id]
            for task in task_list.tasks:
                if task.completed: continue
                if task.claimed_by is not None and task.claimed_by != agent_id: continue
                
                # Si c'est une tâche de livraison ou de prise de plat assemblé
                is_deliver = task.task_type == TaskType.DELIVER
                is_take_assembly = (task.task_type == TaskType.TAKE and task.target_station_type == StationType.ASSEMBLY)
                
                if is_deliver or is_take_assembly:
                    # Vérifier si faisable (dépendances)
                    completed_ids = {t.task_id for t in task_list.tasks if t.completed}
                    if task.dependencies and not all(d in completed_ids for d in task.dependencies):
                        continue
                    
                    # Vérifier compatibilité item
                    if held_item:
                        if task.task_type == TaskType.TAKE: continue # On a déjà un truc
                        if task.item_type != held_item: continue
                    
                    # Si on a les mains vides pour un TAKE ou l'item pour un DELIVER
                    return task

        # 2. Si pas de livraison urgente, on cherche n'importe quelle tâche faisable
        # Sans notion de distance, juste la première trouvée
        for order_id in list(self.task_lists.keys()):
            task_list = self.task_lists[order_id]
            task = task_list.get_first_doable_task(agent_id)
            if task:
                # FILTRE: Si on tient un item, on ne peut prendre QUE des tâches qui l'utilisent
                if held_item:
                    if task.task_type == TaskType.TAKE: continue
                    if task.item_type != held_item: continue
                
                return task
        
        return None

    def _estimate_task_position(self, task: Task, stations: List[Station], agent_pos: Tuple[float, float], agent_id: int) -> Optional[Tuple[float, float]]:
        if task.target_station_type == StationType.INGREDIENT_SPAWN:
             for s in stations:
                 if s.station_type == StationType.INGREDIENT_SPAWN and s.ingredient_type == task.item_type:
                     return (s.x, s.y)
                     
        elif task.target_station_type == StationType.ASSEMBLY:
             return self.get_assigned_assembly(task.order_id)
             
        elif task.target_station_type == StationType.DELIVERY:
             for s in stations:
                 if s.station_type == StationType.DELIVERY: return (s.x, s.y)
                 
        elif task.target_station_type in [StationType.CUTTING_BOARD, StationType.STOVE, StationType.FURNACE]:
             # Trouver la station la plus proche disponible
             closest = None
             min_d = float('inf')
             for s in stations:
                 if s.station_type == task.target_station_type:
                     if self.is_station_available(s, agent_id):
                         d = (agent_pos[0] - s.x)**2 + (agent_pos[1] - s.y)**2
                         if d < min_d:
                             min_d = d
                             closest = s
             if closest: return (closest.x, closest.y)
             
        return None

    def is_item_needed(self, item_type: ItemType) -> bool:
        """Vérifie si un item est nécessaire pour une tâche active"""
        for task_list in self.task_lists.values():
            for task in task_list.tasks:
                if not task.completed:
                    # Si une tâche a besoin de cet item (TAKE ou DELIVER ou CHOP/COOK sur place)
                    if task.item_type == item_type:
                        return True
        return False