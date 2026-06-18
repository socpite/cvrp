from typing import Callable, List, Optional

import numpy as np
import gurobipy as gp
from gurobipy import GRB

from src.problem import Problem, Solution


def _validate_problem(prob: Problem) -> None:
    n, m = prob.n_fruits, prob.n_baskets
    if len(prob.weights) != n:
        raise ValueError(f"weights has {len(prob.weights)} entries but there are {n} fruits.")
    if len(prob.assignments) != n:
        raise ValueError(f"assignments has {len(prob.assignments)} entries but there are {n} fruits.")
    if prob.capacity <= 0:
        raise ValueError("capacity must be positive.")
    for i, w in enumerate(prob.weights):
        if w <= 0:
            raise ValueError(f"weights[{i}] must be positive.")
    for i, t in enumerate(prob.assignments):
        if not 0 <= t < m:
            raise ValueError(f"assignments[{i}] = {t} is not a valid basket index.")


def _extract_route(y_vals: dict, n_nodes: int, s_idx: int) -> List[int]:
    adj = {
        i: [v for v in range(n_nodes) if v != i and y_vals.get((i, v), 0) > 0.5]
        for i in range(n_nodes)
    }
    edge_used = {(i, j): False for i in adj for j in adj[i]}
    stack = [s_idx]
    circuit = []
    while stack:
        v = stack[-1]
        out = [u for u in adj[v] if not edge_used[(v, u)]]
        if out:
            u = out[0]
            edge_used[(v, u)] = True
            stack.append(u)
        else:
            circuit.append(stack.pop())
    return list(reversed(circuit))


def _trim_route(route: List[int], s_idx: int) -> List[int]:
    last_s = -1
    for i in range(len(route) - 1):
        if route[i] == s_idx:
            last_s = i
    if last_s > 0:
        return route[last_s:]
    return route


def _label(route: List[int], n: int, m: int, s_idx: int, s_end: int) -> List[str]:
    f_start, b_start = 2, 2 + n
    labels = []
    for idx in route:
        if idx == s_idx:
            labels.append("s")
        elif idx == s_end:
            labels.append("s'")
        elif f_start <= idx < b_start:
            labels.append(f"f{idx - f_start}")
        else:
            labels.append(f"b{idx - b_start}")
    return labels


def _cost_ext(i: int, j: int, cost_mat: np.ndarray,
              s_idx: int, s_end: int, n_orig: int) -> float:
    if i == s_idx:
        if j == s_end:
            return 0.0
        return cost_mat[0, j - 1]
    if i == s_end:
        if j == s_idx:
            return 0.0
        return cost_mat[n_orig - 1, j - 1]
    if j == s_idx:
        if i == s_end:
            return 0.0
        return cost_mat[i - 1, 0]
    if j == s_end:
        if i == s_idx:
            return 0.0
        return cost_mat[i - 1, n_orig - 1]
    return cost_mat[i - 1, j - 1]


def _compact_timed_route(route: List[int], s_end: int) -> List[int]:
    compact = []
    for node in route:
        if compact and compact[-1] == node:
            continue
        compact.append(node)
    while len(compact) > 1 and compact[-1] == s_end and compact[-2] == s_end:
        compact.pop()
    return compact


def solve_ip(prob: Problem, time_limit: float = 120.0, verbose: bool = False,
             progress_cb: Optional[Callable[[float, float, str], None]] = None) -> Solution:
    """Solve the picking-routing problem as an ordered, time-indexed MILP.

    The paper's compact multi-commodity arc-flow model is a lower-bound
    relaxation when baskets may be revisited. This implementation enforces the
    route semantics directly: every fruit is picked once, delivery can occur
    only at the assigned basket after pickup, and capacity is checked on the
    carried set after each route position.
    """
    _validate_problem(prob)

    n, m = prob.n_fruits, prob.n_baskets
    n_nodes = 2 + n + m
    n_orig = 1 + n + m + 1
    s_idx = 0
    s_end = 1
    f_start, b_start = 2, 2 + n

    horizon = max(1, 2 * n + 1)
    slots = range(horizon + 1)
    steps = range(horizon)
    nodes = range(n_nodes)
    arcs = [(i, j) for i in nodes for j in nodes]

    cost_mat = prob.cost_matrix()
    cost_mat_ext = np.array([
        [_cost_ext(i, j, cost_mat, s_idx, s_end, n_orig) for j in nodes]
        for i in nodes
    ])

    model = gp.Model(f"cap_picking_{prob.name}")
    if not verbose:
        model.setParam("OutputFlag", 0)
    model.setParam("TimeLimit", time_limit)
    model.setParam("MIPGap", 1e-6)

    visit = model.addVars(slots, nodes, vtype=GRB.BINARY, name="visit")
    move = model.addVars(steps, arcs, vtype=GRB.BINARY, name="move")
    delivered = model.addVars(range(n), slots, vtype=GRB.BINARY, name="delivered")

    model.setObjective(
        gp.quicksum(cost_mat_ext[i, j] * move[t, i, j] for t in steps for i, j in arcs),
        GRB.MINIMIZE,
    )

    for t in slots:
        model.addConstr(gp.quicksum(visit[t, i] for i in nodes) == 1, name=f"one_node_{t}")

    model.addConstr(visit[0, s_idx] == 1, name="start_at_s")
    model.addConstr(visit[horizon, s_end] == 1, name="end_at_s_prime")
    for t in range(1, horizon + 1):
        model.addConstr(visit[t, s_idx] == 0, name=f"no_return_to_s_{t}")
    for t in steps:
        model.addConstr(visit[t, s_end] <= visit[t + 1, s_end], name=f"s_prime_absorbs_{t}")

    for f_idx in range(n):
        fruit = f_start + f_idx
        model.addConstr(
            gp.quicksum(visit[t, fruit] for t in slots) == 1,
            name=f"fruit_once_{f_idx}",
        )

    for t in steps:
        for i in nodes:
            model.addConstr(
                gp.quicksum(move[t, i, j] for j in nodes) == visit[t, i],
                name=f"move_out_{t}_{i}",
            )
        for j in nodes:
            model.addConstr(
                gp.quicksum(move[t, i, j] for i in nodes) == visit[t + 1, j],
                name=f"move_in_{t}_{j}",
            )
        for i in nodes:
            if i != s_end:
                model.addConstr(move[t, i, i] == 0, name=f"no_self_loop_{t}_{i}")

    for f_idx in range(n):
        fruit = f_start + f_idx
        basket = b_start + prob.assignments[f_idx]
        model.addConstr(delivered[f_idx, 0] == 0, name=f"not_delivered_initially_{f_idx}")
        for t in range(1, horizon + 1):
            picked_by_t = gp.quicksum(visit[tau, fruit] for tau in range(t + 1))
            model.addConstr(
                delivered[f_idx, t] >= delivered[f_idx, t - 1],
                name=f"delivery_monotone_{f_idx}_{t}",
            )
            model.addConstr(
                delivered[f_idx, t] <= picked_by_t,
                name=f"deliver_after_pick_{f_idx}_{t}",
            )
            model.addConstr(
                delivered[f_idx, t] - delivered[f_idx, t - 1] <= visit[t, basket],
                name=f"deliver_only_at_basket_{f_idx}_{t}",
            )
        model.addConstr(delivered[f_idx, horizon] == 1, name=f"delivered_by_end_{f_idx}")

    for t in slots:
        load = gp.quicksum(
            prob.weights[f_idx] * (
                gp.quicksum(visit[tau, f_start + f_idx] for tau in range(t + 1))
                - delivered[f_idx, t]
            )
            for f_idx in range(n)
        )
        model.addConstr(load <= prob.capacity, name=f"capacity_{t}")

    if progress_cb is not None:
        def gurobi_cb(model, where):
            if where == GRB.Callback.MIP:
                obj = model.cbGet(GRB.Callback.MIP_OBJBST)
                bnd = model.cbGet(GRB.Callback.MIP_OBJBND)
                if obj >= GRB.INFINITY or np.isinf(obj):
                    gap = float("inf")
                elif obj != 0:
                    gap = abs(obj - bnd) / (abs(obj) + 1e-10) * 100
                else:
                    gap = float("inf")
                progress_cb(obj, bnd, f"{gap:.1f}%")
            elif where == GRB.Callback.MESSAGE:
                msg = model.cbGet(GRB.Callback.MSG_STRING)
                if "%" in msg and "inf" not in msg:
                    progress_cb(0, 0, msg.strip())
        model.optimize(gurobi_cb)
    else:
        model.optimize()

    status_str = {
        GRB.OPTIMAL: "optimal",
        GRB.TIME_LIMIT: "time_limit",
        GRB.INFEASIBLE: "infeasible",
        GRB.UNBOUNDED: "unbounded",
    }.get(model.Status, f"status_{model.Status}")

    if model.SolCount > 0:
        route = []
        for t in slots:
            node = max(nodes, key=lambda i: visit[t, i].X)
            route.append(node)
        route = _compact_timed_route(route, s_end)
        cost = sum(cost_mat_ext[route[k], route[k + 1]] for k in range(len(route) - 1))
        lb_obj = model.ObjBound
        if verbose:
            print(f"  Route: {' -> '.join(_label(route, n, m, s_idx, s_end))}")
        return Solution(problem=prob, route=route, cost=cost, status=status_str,
                        bounds=(lb_obj, cost))

    return Solution(problem=prob, route=[], cost=float("inf"), status=status_str)
