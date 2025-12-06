"""
Visualisation des résultats de simulation Overcooked Multi-Agent
Génère des graphiques à partir des données de simulation
"""

import json
import matplotlib.pyplot as plt
import numpy as np


def load_results(filename='simulation_results.json'):
    """Charge les résultats depuis le fichier JSON"""
    with open(filename, 'r') as f:
        return json.load(f)


def plot_results(results):
    """Crée des graphiques pour visualiser les résultats"""

    # Extraire les données
    num_bots = [r['num_bots'] for r in results]
    avg_orders = [r['avg_orders_completed'] for r in results]
    avg_money = [r['avg_money_earned'] for r in results]
    avg_delivery_time = [r['avg_delivery_time'] for r in results]
    avg_expired = [r['avg_orders_expired'] for r in results]

    # Créer une figure avec 4 subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('📊 Statistiques Overcooked Multi-Agent', fontsize=16, fontweight='bold')

    # 1. Nombre de commandes complétées
    ax1 = axes[0, 0]
    ax1.plot(num_bots, avg_orders, marker='o', linewidth=2, markersize=8, color='#2ecc71')
    ax1.set_xlabel('Nombre de bots', fontsize=12)
    ax1.set_ylabel('Commandes complétées (moyenne)', fontsize=12)
    ax1.set_title('✅ Commandes complétées par partie', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(num_bots)

    # 2. Argent gagné
    ax2 = axes[0, 1]
    ax2.plot(num_bots, avg_money, marker='s', linewidth=2, markersize=8, color='#f39c12')
    ax2.set_xlabel('Nombre de bots', fontsize=12)
    ax2.set_ylabel('Argent gagné (moyenne)', fontsize=12)
    ax2.set_title('💰 Argent gagné par partie', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(num_bots)

    # 3. Temps de livraison moyen
    ax3 = axes[1, 0]
    ax3.plot(num_bots, avg_delivery_time, marker='^', linewidth=2, markersize=8, color='#3498db')
    ax3.set_xlabel('Nombre de bots', fontsize=12)
    ax3.set_ylabel('Temps de livraison (secondes)', fontsize=12)
    ax3.set_title('⏱️ Temps moyen de livraison', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.set_xticks(num_bots)

    # 4. Commandes expirées vs complétées
    ax4 = axes[1, 1]
    width = 0.35
    x = np.arange(len(num_bots))
    bars1 = ax4.bar(x - width/2, avg_orders, width, label='Complétées', color='#2ecc71')
    bars2 = ax4.bar(x + width/2, avg_expired, width, label='Expirées', color='#e74c3c')
    ax4.set_xlabel('Nombre de bots', fontsize=12)
    ax4.set_ylabel('Nombre de commandes', fontsize=12)
    ax4.set_title('📦 Commandes complétées vs expirées', fontsize=13, fontweight='bold')
    ax4.set_xticks(x)
    ax4.set_xticklabels(num_bots)
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('simulation_results.png', dpi=300, bbox_inches='tight')
    print("📈 Graphiques sauvegardés dans 'simulation_results.png'")
    plt.show()


def print_analysis(results):
    """Affiche une analyse textuelle des résultats"""
    print("\n" + "=" * 80)
    print("🔍 ANALYSE DES RÉSULTATS")
    print("=" * 80)

    # Trouver la configuration optimale
    best_money = max(results, key=lambda r: r['avg_money_earned'])
    best_orders = max(results, key=lambda r: r['avg_orders_completed'])
    best_delivery = min(results, key=lambda r: r['avg_delivery_time'])

    print(f"\n💰 Meilleur gain d'argent: {best_money['num_bots']} bots ({best_money['avg_money_earned']:.1f}$)")
    print(f"📦 Plus de commandes: {best_orders['num_bots']} bots ({best_orders['avg_orders_completed']:.1f} commandes)")
    print(f"⚡ Livraison la plus rapide: {best_delivery['num_bots']} bots ({best_delivery['avg_delivery_time']:.2f}s)")

    # Calculer l'efficacité (argent par bot)
    print("\n💡 Efficacité (argent/bot):")
    for r in results:
        efficiency = r['avg_money_earned'] / r['num_bots']
        print(f"   {r['num_bots']} bot{'s' if r['num_bots'] > 1 else ''}: {efficiency:.1f}$/bot")

    print()


def main():
    """Fonction principale"""
    try:
        results = load_results()
        print_analysis(results)
        plot_results(results)
    except FileNotFoundError:
        print("❌ Fichier 'simulation_results.json' non trouvé.")
        print("   Lancez d'abord 'python3 run_simulation.py'")
    except Exception as e:
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    main()
