"""Standardized JSON I/O for picking-routing problems and solutions.

Input (problem) format -- ``*.json``::

    {
      "name": "test1",
      "start": [0.0, 0.0, 0.0],
      "fruits": [[1, 0, 0], [2, 0, 0]],
      "weights": [1.0, 1.0],
      "baskets": [[3, 0, 0]],
      "assignments": [0, 0],
      "capacity": 10.0
    }

Output (solution) format -- ``*.json``::

    {
      "problem": "test1",
      "route": ["s", "f0", "f1", "b0", "s"],
      "cost": 6.0,
      "status": "optimal",
      "bounds": [6.0, 6.0]
    }

Routes are expressed with stable labels, independent of the solver's internal
node indexing:

* ``"s"``   -- the start/depot node,
* ``"f<i>"`` -- the ``i``-th fruit (0-based),
* ``"b<j>"`` -- the ``j``-th basket (0-based).
"""

import json
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.problem import Problem, Solution

Point = Tuple[float, float, float]


# --------------------------------------------------------------------------- #
# Label utilities
# --------------------------------------------------------------------------- #
def parse_label(label: str, n_fruits: int, n_baskets: int) -> Tuple[str, Optional[int]]:
    """Parse a route label into ``(kind, index)``.

    ``kind`` is one of ``"s"``, ``"f"``, ``"b"``; ``index`` is ``None`` for the
    start node. Raises ``ValueError`` on an unrecognized or out-of-range label.
    """
    s = label.strip()
    if s in ("s", "s'", "start", "S"):
        return ("s", None)
    if not s or s[0] not in ("f", "b"):
        raise ValueError(f"Unrecognized route label {label!r} (expected 's', 'f<i>', or 'b<j>').")
    kind = s[0]
    try:
        idx = int(s[1:])
    except ValueError:
        raise ValueError(f"Malformed route label {label!r}: expected an integer after '{kind}'.")
    limit = n_fruits if kind == "f" else n_baskets
    if not 0 <= idx < limit:
        raise ValueError(f"Route label {label!r} out of range (valid {kind} indices: 0..{limit - 1}).")
    return (kind, idx)


def route_indices_to_labels(route: List[int], n_fruits: int, n_baskets: int) -> List[str]:
    """Convert a solver route (extended node indices) to canonical labels.

    The solver's extended indexing is ``0 = s``, ``1 = s'`` (start copy),
    ``2..2+n`` fruits, then baskets. Both ``s`` and ``s'`` map to ``"s"``, and
    consecutive duplicate labels (e.g. an ``s -> s'`` hop) are collapsed.
    """
    f_start = 2
    b_start = 2 + n_fruits
    out: List[str] = []
    for idx in route:
        if idx in (0, 1):
            lab = "s"
        elif f_start <= idx < b_start:
            lab = f"f{idx - f_start}"
        else:
            lab = f"b{idx - b_start}"
        if out and out[-1] == lab:
            continue
        out.append(lab)
    return out


# --------------------------------------------------------------------------- #
# Problem (input) I/O
# --------------------------------------------------------------------------- #
def _as_point(v) -> Point:
    if len(v) not in (2, 3):
        raise ValueError(f"Coordinate must have 2 or 3 components, got {v!r}.")
    t = tuple(float(c) for c in v)
    return t if len(t) == 3 else (t[0], t[1], 0.0)


def problem_to_dict(prob: Problem) -> dict:
    return {
        "name": prob.name,
        "start": list(prob.start),
        "fruits": [list(f) for f in prob.fruits],
        "weights": list(prob.weights),
        "baskets": [list(b) for b in prob.baskets],
        "assignments": list(prob.assignments),
        "capacity": prob.capacity,
    }


def problem_from_dict(d: dict) -> Problem:
    required = ("start", "fruits", "weights", "baskets", "assignments", "capacity")
    missing = [k for k in required if k not in d]
    if missing:
        raise ValueError(f"Problem file is missing required field(s): {', '.join(missing)}.")

    fruits = [_as_point(f) for f in d["fruits"]]
    baskets = [_as_point(b) for b in d["baskets"]]
    weights = [float(w) for w in d["weights"]]
    assignments = [int(a) for a in d["assignments"]]

    if len(weights) != len(fruits):
        raise ValueError(f"weights has {len(weights)} entries but there are {len(fruits)} fruits.")
    if len(assignments) != len(fruits):
        raise ValueError(f"assignments has {len(assignments)} entries but there are {len(fruits)} fruits.")
    for i, a in enumerate(assignments):
        if not 0 <= a < len(baskets):
            raise ValueError(f"assignments[{i}] = {a} is not a valid basket index (0..{len(baskets) - 1}).")
    if float(d["capacity"]) <= 0:
        raise ValueError("capacity must be positive.")

    return Problem(
        name=str(d.get("name", "unnamed")),
        start=_as_point(d["start"]),
        fruits=fruits,
        weights=weights,
        baskets=baskets,
        assignments=assignments,
        capacity=float(d["capacity"]),
    )


def save_problem(prob: Problem, path: str) -> None:
    with open(path, "w") as fh:
        json.dump(problem_to_dict(prob), fh, indent=2)


def load_problem(path: str) -> Problem:
    with open(path) as fh:
        return problem_from_dict(json.load(fh))


# --------------------------------------------------------------------------- #
# Solution (output) I/O
# --------------------------------------------------------------------------- #
@dataclass
class LoadedSolution:
    problem: Optional[str]
    route: List[str]
    cost: Optional[float]
    status: Optional[str]
    bounds: Optional[Tuple[float, float]]


def solution_to_dict(sol: Solution) -> dict:
    prob = sol.problem
    d = {
        "problem": prob.name,
        "route": route_indices_to_labels(sol.route, prob.n_fruits, prob.n_baskets),
        "cost": sol.cost,
        "status": sol.status,
    }
    if sol.bounds is not None:
        d["bounds"] = list(sol.bounds)
    return d


def save_solution(sol: Solution, path: str) -> None:
    with open(path, "w") as fh:
        json.dump(solution_to_dict(sol), fh, indent=2)


def load_solution(path: str) -> LoadedSolution:
    with open(path) as fh:
        d = json.load(fh)
    if "route" not in d:
        raise ValueError("Solution file is missing the required 'route' field.")
    route = [str(x) for x in d["route"]]
    bounds = tuple(d["bounds"]) if d.get("bounds") is not None else None
    return LoadedSolution(
        problem=d.get("problem"),
        route=route,
        cost=d.get("cost"),
        status=d.get("status"),
        bounds=bounds,
    )
