"""
Simulation de statistiques pour Overcooked Multi-Agent
Exécute plusieurs parties en parallèle pour analyser les performances selon le nombre de bots
"""

import time
import multiprocessing as mp
from dataclasses import dataclass
from typing import List, Dict
import statistics
import json

# Import sans initialiser pygame
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'  # Mode headless pour pygame

from src.model.game_model import GameModel
from src.controller.bot_controller import AIBot
from src.controller.shared_knowledge import SharedKnowledge


@dataclass
class GameStats:
    """Statistiques d'une partie"""
    num_bots: int
    orders_completed: int
    orders_expired: int
    money_earned: int
    avg_delivery_time: float  # secondes
    game_duration: float  # secondes


def run_single_game(num_bots: int, game_duration: float = 60.0) -> GameStats:
    """
    Simule une partie complète et retourne les statistiques

    Args:
        num_bots: Nombre de bots
        game_duration: Durée de la partie en secondes

    Returns:
        GameStats avec les statistiques de la partie
    """
    # Créer le modèle et les bots
    model = GameModel(num_bots=num_bots)
    shared_knowledge = SharedKnowledge()
    bots = [AIBot(player_index=i, shared_knowledge=shared_knowledge) for i in range(num_bots)]

    # Variables de tracking
    start_time = time.time()
    last_time = start_time
    delivery_times = []  # Temps de livraison de chaque commande
    order_start_times = {}  # Quand chaque commande a été créée

    # Compteurs persistants (model.completed_orders est nettoyé après 3s)
    total_completed = 0
    total_expired = 0
    seen_order_ids = set()  # Pour éviter de compter 2 fois

    # Boucle de simulation (60 FPS simulés)
    frame_time = 1.0 / 60.0

    while True:
        current_time = time.time()

        # Vérifier si la partie est terminée
        if current_time - start_time >= game_duration:
            break

        delta_time = current_time - last_time
        last_time = current_time

        # Tracker les nouvelles commandes
        for order in model.orders:
            if order.id not in order_start_times:
                order_start_times[order.id] = current_time

        # Update du jeu
        model.update(delta_time)
        shared_knowledge.update_orders(model.orders)

        for bot in bots:
            bot.update(model)

        # Tracker les nouvelles livraisons (avant que model.completed_orders soit nettoyé)
        for completed_order in model.completed_orders:
            order_id = completed_order['id']
            if order_id not in seen_order_ids:
                seen_order_ids.add(order_id)

                if completed_order['type'] == 'completed':
                    total_completed += 1
                    # Calculer le temps de livraison
                    if order_id in order_start_times:
                        delivery_time = completed_order['time'] - order_start_times[order_id]
                        delivery_times.append(delivery_time)
                elif completed_order['type'] == 'expired':
                    total_expired += 1

        # Simuler le temps de frame
        time.sleep(max(0, frame_time - (time.time() - current_time)))

    # Calculer les statistiques finales
    avg_delivery_time = statistics.mean(delivery_times) if delivery_times else 0.0
    actual_duration = time.time() - start_time

    return GameStats(
        num_bots=num_bots,
        orders_completed=total_completed,
        orders_expired=total_expired,
        money_earned=model.score,
        avg_delivery_time=avg_delivery_time,
        game_duration=actual_duration
    )


def run_simulation_for_bots(num_bots: int, num_games: int = 10) -> List[GameStats]:
    """
    Exécute plusieurs parties pour une configuration de bots donnée EN PARALLÈLE

    Args:
        num_bots: Nombre de bots
        num_games: Nombre de parties à simuler

    Returns:
        Liste des statistiques de chaque partie
    """
    num_cores = mp.cpu_count()
    print(f"🤖 Simulation {num_bots} bot{'s' if num_bots > 1 else ''}: {num_games} parties (parallèle sur {num_cores} cœurs)...")

    # Exécuter toutes les parties en parallèle
    with mp.Pool(processes=num_cores) as pool:
        args = [(num_bots,) for _ in range(num_games)]
        stats = pool.starmap(run_single_game, args)

    # Afficher les résultats
    for i, game_stats in enumerate(stats):
        print(f"  Partie {i+1}/{num_games}: {game_stats.orders_completed} commandes, {game_stats.money_earned}$")

    return stats


def aggregate_stats(stats_list: List[GameStats]) -> Dict:
    """Agrège les statistiques de plusieurs parties"""
    if not stats_list:
        return {}

    return {
        'num_bots': stats_list[0].num_bots,
        'num_games': len(stats_list),
        'avg_orders_completed': statistics.mean([s.orders_completed for s in stats_list]),
        'avg_orders_expired': statistics.mean([s.orders_expired for s in stats_list]),
        'avg_money_earned': statistics.mean([s.money_earned for s in stats_list]),
        'avg_delivery_time': statistics.mean([s.avg_delivery_time for s in stats_list]),
        'std_orders_completed': statistics.stdev([s.orders_completed for s in stats_list]) if len(stats_list) > 1 else 0,
        'std_money_earned': statistics.stdev([s.money_earned for s in stats_list]) if len(stats_list) > 1 else 0,
    }


def main():
    """Fonction principale de simulation"""
    print("=" * 80)
    print("🎮 SIMULATION OVERCOOKED MULTI-AGENT")
    print("=" * 80)
    print()

    # Configuration
    min_bots = 1
    max_bots = 10
    num_games_per_config = 10  # Nombre de parties par configuration

    print(f"⚙️  Configuration:")
    print(f"   - Bots: {min_bots} à {max_bots}")
    print(f"   - Parties par configuration: {num_games_per_config}")
    print(f"   - Durée par partie: 60 secondes")
    print(f"   - Total de parties: {(max_bots - min_bots + 1) * num_games_per_config}")
    print()

    # Collecter les statistiques pour chaque configuration
    all_results = []

    for num_bots in range(min_bots, max_bots + 1):
        stats = run_simulation_for_bots(num_bots, num_games_per_config)
        aggregated = aggregate_stats(stats)
        all_results.append(aggregated)
        print()

    # Afficher le résumé final
    print("=" * 80)
    print("📊 RÉSULTATS FINAUX")
    print("=" * 80)
    print()
    print(f"{'Bots':<6} {'Commandes':<12} {'Expirées':<10} {'Argent':<10} {'Temps livraison':<18}")
    print("-" * 80)

    for result in all_results:
        print(f"{result['num_bots']:<6} "
              f"{result['avg_orders_completed']:<12.1f} "
              f"{result['avg_orders_expired']:<10.1f} "
              f"{result['avg_money_earned']:<10.1f}$ "
              f"{result['avg_delivery_time']:<18.2f}s")

    print()

    # Sauvegarder les résultats en JSON
    output_file = 'simulation_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"✅ Résultats sauvegardés dans {output_file}")
    print()


if __name__ == "__main__":
    main()
