"""Feasibility validation for a picking-routing solution against a problem.

Checks that a route (a list of labels, see :mod:`src.formats`) is a valid
picking routing plan for a given :class:`~src.problem.Problem`:

* every fruit is visited exactly once,
* each picked fruit is delivered to its assigned basket (after pickup),
* the carried load never exceeds the capacity ``K`` at any pick,
* (informational) the route starts and ends at the depot, and the reported
  cost matches the recomputed travel distance.
"""

import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.formats import load_problem, load_solution, parse_label
from src.problem import Problem

Point = Tuple[float, float, float]


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    computed_cost: float = 0.0
    reported_cost: Optional[float] = None
    max_load: float = 0.0

    def summary(self) -> str:
        head = "VALID" if self.ok else "INVALID"
        lines = [f"{head}  |  cost={self.computed_cost:.4f}  |  peak load={self.max_load:.2f}"]
        for e in self.errors:
            lines.append(f"  [error]   {e}")
        for w in self.warnings:
            lines.append(f"  [warning] {w}")
        return "\n".join(lines)


def _position(prob: Problem, kind: str, idx: Optional[int]) -> Point:
    if kind == "s":
        return prob.start
    if kind == "f":
        return prob.fruits[idx]
    return prob.baskets[idx]


def _dist(p: Point, q: Point) -> float:
    return float(np.linalg.norm(np.asarray(p, dtype=float) - np.asarray(q, dtype=float)))


def validate_route(
    prob: Problem,
    labels: List[str],
    reported_cost: Optional[float] = None,
    tol: float = 1e-6,
    cost_tol: float = 1e-3,
) -> ValidationResult:
    """Validate ``labels`` as a picking routing plan for ``prob``."""
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Parse all labels first; bail out on any malformed/out-of-range label.
    parsed: List[Tuple[str, Optional[int]]] = []
    for lab in labels:
        try:
            parsed.append(parse_label(lab, prob.n_fruits, prob.n_baskets))
        except ValueError as e:
            errors.append(str(e))
    if errors:
        return ValidationResult(ok=False, errors=errors, warnings=warnings, reported_cost=reported_cost)
    if not parsed:
        return ValidationResult(ok=False, errors=["Route is empty."], reported_cost=reported_cost)

    # 2. Endpoints (informational only).
    if parsed[0] != ("s", None):
        warnings.append("Route does not start at the depot 's'.")
    if parsed[-1] != ("s", None):
        warnings.append("Route does not end at the depot 's'.")

    # 3. Each fruit visited exactly once.
    visits = [0] * prob.n_fruits
    for kind, idx in parsed:
        if kind == "f":
            visits[idx] += 1
    for i, c in enumerate(visits):
        if c == 0:
            errors.append(f"Fruit f{i} is never visited.")
        elif c > 1:
            errors.append(f"Fruit f{i} is visited {c} times (must be exactly once).")

    # 4. Walk the route: pick up at fruits, deliver at the matching basket,
    #    track the carried load and enforce capacity at each pickup.
    carried: dict = {}  # fruit index -> weight
    max_load = 0.0
    for step, (kind, idx) in enumerate(parsed):
        if kind == "f":
            carried[idx] = prob.weights[idx]
            load = sum(carried.values())
            max_load = max(max_load, load)
            if load > prob.capacity + tol:
                errors.append(
                    f"Capacity exceeded after picking f{idx} at step {step}: "
                    f"load {load:.3f} > K {prob.capacity:.3f}."
                )
        elif kind == "b":
            delivered = [fi for fi in carried if prob.assignments[fi] == idx]
            for fi in delivered:
                del carried[fi]

    for fi in sorted(carried):
        errors.append(
            f"Fruit f{fi} is picked but never delivered to its basket "
            f"b{prob.assignments[fi]} afterwards."
        )

    # 5. Recompute travel cost and compare with the reported value.
    cost = sum(
        _dist(_position(prob, *a), _position(prob, *b))
        for a, b in zip(parsed, parsed[1:])
    )
    if reported_cost is not None and abs(cost - reported_cost) > cost_tol:
        warnings.append(
            f"Reported cost {reported_cost:.4f} differs from recomputed cost {cost:.4f}."
        )

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        computed_cost=cost,
        reported_cost=reported_cost,
        max_load=max_load,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate a picking-routing route.")
    parser.add_argument("--input", required=True, help="problem JSON file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--route", nargs="+", help="route labels, e.g. s f0 f1 b0 s")
    group.add_argument("--output", help="solution JSON file containing route/cost")
    parser.add_argument("--reported-cost", type=float, help="optional cost to compare against --route")
    args = parser.parse_args()

    prob = load_problem(args.input)
    if args.output:
        sol = load_solution(args.output)
        labels = sol.route
        reported_cost = sol.cost
    else:
        labels = args.route
        reported_cost = args.reported_cost

    result = validate_route(prob, labels, reported_cost)
    print(result.summary())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(_main())
