import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from src.problem import Problem, Solution
from src.visualize import _pos, _get_route_positions


def test_pos_maps_indices():
    prob = Problem(
        name="test",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        weights=[1.0, 1.0],
        baskets=[(3.0, 0.0, 0.0)],
        assignments=[0, 0],
        capacity=10.0,
    )
    # Index mapping: 0=s, 1=s', 2=f0, 3=f1, 4=b0
    assert _pos(prob, 0) == (0.0, 0.0, 0.0)
    assert _pos(prob, 1) == (0.0, 0.0, 0.0)
    assert _pos(prob, 2) == (1.0, 0.0, 0.0)
    assert _pos(prob, 3) == (2.0, 0.0, 0.0)
    assert _pos(prob, 4) == (3.0, 0.0, 0.0)
    print("  _pos: OK")


def test_get_route_positions():
    prob = Problem(
        name="test",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        weights=[1.0, 1.0],
        baskets=[(3.0, 0.0, 0.0)],
        assignments=[0, 0],
        capacity=10.0,
    )
    sol = Solution(problem=prob, route=[0, 1, 2, 3, 4, 0], cost=10.0, status="optimal")
    positions = _get_route_positions(prob, sol)
    expected = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (3.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    ]
    assert positions == expected, f"Expected {expected}, got {positions}"
    print("  _get_route_positions: OK")


def test_route_positions_2d_fallback():
    prob = Problem(
        name="test",
        start=(0.0, 0.0),
        fruits=[(1.0, 0.0)],
        weights=[1.0],
        baskets=[(2.0, 0.0)],
        assignments=[0],
        capacity=10.0,
    )
    sol = Solution(problem=prob, route=[0, 1, 2, 3, 0], cost=4.0, status="optimal")
    positions = _get_route_positions(prob, sol)
    for p in positions:
        assert len(p) == 3, f"Expected 3D fallback, got {p}"
    assert positions[0] == (0.0, 0.0, 0.0)
    assert positions[2] == (1.0, 0.0, 0.0)
    print("  _get_route_positions 2D fallback: OK")


def test_empty_route():
    prob = Problem(
        name="test", start=(0.0, 0.0, 0.0),
        fruits=[], weights=[], baskets=[], assignments=[], capacity=10.0,
    )
    sol = Solution(problem=prob, route=[], cost=0.0, status="optimal")
    positions = _get_route_positions(prob, sol)
    assert positions == []
    print("  empty route: OK")


if __name__ == "__main__":
    test_pos_maps_indices()
    test_get_route_positions()
    test_route_positions_2d_fallback()
    test_empty_route()
    print("All visualize tests passed")
