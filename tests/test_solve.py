import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.solve import _extract_route, _trim_route, _label, solve_ip
from src.problem import Problem, Solution


def test_extract_route_simple():
    y = {(0, 1): 1, (1, 2): 1, (2, 0): 1}
    route = _extract_route(y, 3, 0)
    assert route == [0, 1, 2, 0], f"Expected [0,1,2,0], got {route}"
    print("  _extract_route simple: OK")


def test_extract_route_with_s_prime():
    y = {(0, 1): 1, (1, 2): 1, (2, 3): 1, (3, 4): 1, (4, 0): 1}
    route = _extract_route(y, 5, 0)
    assert route == [0, 1, 2, 3, 4, 0], f"Expected [0,1,2,3,4,0], got {route}"
    print("  _extract_route with s': OK")


def test_extract_route_disconnected():
    y = {(0, 1): 1, (1, 0): 1, (2, 3): 1, (3, 2): 1}
    route = _extract_route(y, 4, 0)
    assert len(route) >= 2
    assert route[0] == 0 and route[-1] == 0
    print("  _extract_route disconnected: OK")


def test_trim_route():
    route = [0, 3, 4, 0, 1, 2, 0]
    trimmed = _trim_route(route, 0)
    assert trimmed == [0, 1, 2, 0], f"Expected [0,1,2,0], got {trimmed}"
    print("  _trim_route: OK")


def test_trim_route_no_trim():
    route = [0, 1, 2, 0]
    trimmed = _trim_route(route, 0)
    assert trimmed == route
    print("  _trim_route no trim: OK")


def test_label():
    labels = _label([0, 1, 2, 3, 4, 0], n=2, m=1, s_idx=0, s_end=1)
    assert labels == ["s", "s'", "f0", "f1", "b0", "s"]
    print("  _label: OK")


def test_solve_returns_valid_route():
    prob = Problem(
        name="test_validate",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0)],
        weights=[1.0],
        baskets=[(2.0, 0.0, 0.0)],
        assignments=[0],
        capacity=10.0,
    )
    sol = solve_ip(prob, verbose=False)
    assert sol.status == "optimal"
    assert len(sol.route) >= 3
    assert sol.cost > 0
    print(f"  solve single fruit: cost={sol.cost:.4f}, route={' → '.join(_label(sol.route, 1, 1, 0, 1))}")


if __name__ == "__main__":
    test_extract_route_simple()
    test_extract_route_with_s_prime()
    test_extract_route_disconnected()
    test_trim_route()
    test_trim_route_no_trim()
    test_label()
    test_solve_returns_valid_route()
    print("All solve tests passed")
