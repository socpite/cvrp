import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generator import all_small_tests, random_instance
from src.solve import solve_ip
from src.visualize import show, save


def test_all_small():
    problems = all_small_tests()
    all_ok = True
    for prob in problems:
        print(f"\n{'='*60}")
        print(f"Solving: {prob.name}")
        print(f"  Fruits: {prob.n_fruits}, Baskets: {prob.n_baskets}, "
              f"Capacity: {prob.capacity}")
        print(f"  Weights: {prob.weights}, Assignments: {prob.assignments}")
        print(f"  Total weight: {prob.total_weight:.1f}")

        sol = solve_ip(prob, verbose=True)

        print(f"  Status: {sol.status}")
        if sol.route:
            print(f"  Cost: {sol.cost:.4f}")

            out = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "output", f"{prob.name}.png")
            save(prob, sol, out)
        else:
            all_ok = False

    print(f"\n{'='*60}")
    print(f"All tests passed: {all_ok}")
    return all_ok


if __name__ == "__main__":
    test_all_small()
