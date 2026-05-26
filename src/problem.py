from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union
import numpy as np

Point = Tuple[float, float, float]


@dataclass
class Problem:
    name: str
    start: Point
    fruits: List[Point]
    weights: List[float]
    baskets: List[Point]
    assignments: List[int]
    capacity: float

    @property
    def n_fruits(self) -> int:
        return len(self.fruits)

    @property
    def n_baskets(self) -> int:
        return len(self.baskets)

    @property
    def total_weight(self) -> float:
        return sum(self.weights)

    def dist(self, i: int, j: int) -> float:
        V = [self.start] + self.fruits + self.baskets + [self.start]
        p1 = V[i]
        p2 = V[j]
        return np.linalg.norm([p1[0] - p2[0], p1[1] - p2[1], p1[2] - p2[2]])

    def cost_matrix(self) -> np.ndarray:
        V = [self.start] + self.fruits + self.baskets + [self.start]
        n = len(V)
        C = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                C[i, j] = np.linalg.norm(
                    [V[i][0] - V[j][0], V[i][1] - V[j][1], V[i][2] - V[j][2]]
                )
        return C

    def dim(self) -> int:
        return len(self.start)


@dataclass
class Solution:
    problem: Problem
    route: List[int]
    cost: float
    status: str
    bounds: Optional[Tuple[float, float]] = None
