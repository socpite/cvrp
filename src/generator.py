from typing import List, Tuple
import numpy as np
from src.problem import Problem


def make_problem(
    name: str,
    start: Tuple[float, float, float],
    fruits: List[Tuple[float, float, float]],
    weights: List[float],
    baskets: List[Tuple[float, float, float]],
    assignments: List[int],
    capacity: float,
) -> Problem:
    return Problem(
        name=name,
        start=start,
        fruits=fruits,
        weights=weights,
        baskets=baskets,
        assignments=assignments,
        capacity=capacity,
    )


def random_instance(
    name: str,
    n_fruits: int,
    n_baskets: int,
    capacity: float,
    seed: int = 0,
    bounds: Tuple[float, float, float, float, float, float] = (0, 0, 0, 10, 10, 5),
) -> Problem:
    rng = np.random.default_rng(seed)
    x0, y0, z0, x1, y1, z1 = bounds

    start = (float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), float(rng.uniform(z0, z1)))

    fruits = [
        (float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), float(rng.uniform(z0, z1)))
        for _ in range(n_fruits)
    ]
    weights = [float(rng.uniform(1.0, capacity * 0.8)) for _ in range(n_fruits)]
    baskets = [
        (float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), float(rng.uniform(z0, z1)))
        for _ in range(n_baskets)
    ]
    assignments = [int(rng.integers(0, n_baskets)) for _ in range(n_fruits)]

    return Problem(
        name=name,
        start=start,
        fruits=fruits,
        weights=weights,
        baskets=baskets,
        assignments=assignments,
        capacity=capacity,
    )


def small_test_1() -> Problem:
    return make_problem(
        name="test1_simple_line",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        weights=[1.0, 1.0],
        baskets=[(3.0, 0.0, 0.0)],
        assignments=[0, 0],
        capacity=10.0,
    )


def small_test_2() -> Problem:
    return make_problem(
        name="test2_two_baskets",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        weights=[1.0, 1.0],
        baskets=[(2.0, 0.0, 0.0), (0.0, 2.0, 0.0)],
        assignments=[0, 1],
        capacity=10.0,
    )


def small_test_3() -> Problem:
    return make_problem(
        name="test3_capacity_forced_multi_trip",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)],
        weights=[3.0, 3.0, 1.0],
        baskets=[(4.0, 0.0, 0.0)],
        assignments=[0, 0, 0],
        capacity=4.0,
    )


def small_test_4() -> Problem:
    return make_problem(
        name="test4_triangle",
        start=(0.0, 0.0, 0.0),
        fruits=[(2.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        weights=[2.0, 2.0],
        baskets=[(0.0, 2.0, 0.0)],
        assignments=[0, 0],
        capacity=5.0,
    )


def small_test_5() -> Problem:
    return make_problem(
        name="test5_two_baskets_capacity",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
        weights=[3.0, 3.0, 3.0, 3.0],
        baskets=[(5.0, 0.0, 0.0), (0.0, 5.0, 0.0)],
        assignments=[0, 0, 1, 1],
        capacity=5.0,
    )


def small_test_6() -> Problem:
    return make_problem(
        name="test6_capacity_one_at_a_time",
        start=(0.0, 0.0, 0.0),
        fruits=[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        weights=[3.0, 3.0],
        baskets=[(3.0, 0.0, 0.0)],
        assignments=[0, 0],
        capacity=3.0,
    )


def all_small_tests() -> List[Problem]:
    return [
        small_test_1(),
        small_test_2(),
        small_test_3(),
        small_test_4(),
        small_test_5(),
        small_test_6(),
    ]


def large_test_a() -> Problem:
    return random_instance(
        "large_20f_3b", n_fruits=20, n_baskets=3, capacity=8.0, seed=42,
        bounds=(0, 0, 0, 20, 20, 10),
    )


def large_test_b() -> Problem:
    return random_instance(
        "large_25f_4b", n_fruits=25, n_baskets=4, capacity=6.0, seed=123,
        bounds=(0, 0, 0, 30, 30, 15),
    )


def large_test_c() -> Problem:
    return random_instance(
        "large_30f_4b", n_fruits=30, n_baskets=4, capacity=7.0, seed=456,
        bounds=(0, 0, 0, 40, 40, 20),
    )


def all_large_tests() -> List[Problem]:
    return [
        large_test_a(),
        large_test_b(),
        large_test_c(),
    ]
