import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generator import all_large_tests
from src.solve import solve_ip


def run():
    tests = all_large_tests()
    all_ok = True
    for prob in tests:
        print(f"\n{'='*60}")
        print(f"Solving: {prob.name}")
        print(f"  Fruits: {prob.n_fruits}, Baskets: {prob.n_baskets}, Capacity: {prob.capacity}")
        print(f"  Total weight: {prob.total_weight:.1f}")
        start = time.time()
        sol = solve_ip(prob, time_limit=300, verbose=True)
        elapsed = time.time() - start
        ok = sol.status == "optimal"
        print(f"  Status: {sol.status}  |  Cost: {sol.cost:.4f}  |  Time: {elapsed:.1f}s")
        if not ok:
            all_ok = False
    print(f"\n{'='*60}")
    print(f"All large tests passed: {all_ok}")


if __name__ == "__main__":
    run()
