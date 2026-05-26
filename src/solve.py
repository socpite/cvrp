from typing import Callable, List, Optional, Tuple
import numpy as np
import gurobipy as gp
from gurobipy import GRB
from src.problem import Problem, Solution


def _extract_route(y_vals: dict, n_nodes: int, s_idx: int) -> List[int]:
    adj = {i: [v for v in range(n_nodes) if v != i and y_vals.get((i, v), 0) > 0.5] for i in range(n_nodes)}
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
              s_idx: int, s_end: int, N_orig: int) -> float:
    if i == s_idx:
        if j == s_end:
            return 0.0
        return cost_mat[0, j - 1]
    if i == s_end:
        if j == s_idx:
            return 0.0
        return cost_mat[N_orig - 1, j - 1]
    if j == s_idx:
        if i == s_end:
            return 0.0
        return cost_mat[i - 1, 0]
    if j == s_end:
        if i == s_idx:
            return 0.0
        return cost_mat[i - 1, N_orig - 1]
    return cost_mat[i - 1, j - 1]


def solve_ip(prob: Problem, time_limit: float = 120.0, verbose: bool = False,
             progress_cb: Optional[Callable[[float, float, str], None]] = None) -> Solution:
    n, m = prob.n_fruits, prob.n_baskets
    N = 2 + n + m
    N_orig = 1 + n + m + 1
    s_idx = 0
    s_end = 1
    f_start, b_start = 2, 2 + n

    edges = [(i, j) for i in range(N) for j in range(N) if i != j]
    cost_mat = prob.cost_matrix()
    cost_mat_ext = np.array([[_cost_ext(i, j, cost_mat, s_idx, s_end, N_orig)
                              for j in range(N)] for i in range(N)])

    total_assigned = [0.0] * m
    for i, t in enumerate(prob.assignments):
        total_assigned[t] += prob.weights[i]

    model = gp.Model(f"cap_picking_{prob.name}")
    if not verbose:
        model.setParam("OutputFlag", 0)
    model.setParam("TimeLimit", time_limit)
    model.setParam("MIPGap", 1e-6)

    y = model.addVars(edges, vtype=GRB.BINARY, name="y")
    x = [model.addVars(edges, lb=0, name=f"x{b}") for b in range(m)]

    model.setObjective(gp.quicksum(cost_mat_ext[i, j] * y[i, j] for i, j in edges), GRB.MINIMIZE)

    for f in range(f_start, f_start + n):
        model.addConstr(gp.quicksum(y[f, j] for j in range(N) if j != f) == 1, name=f"out_{f}")
        model.addConstr(gp.quicksum(y[i, f] for i in range(N) if i != f) == 1, name=f"in_{f}")

    for i in range(N):
        model.addConstr(
            gp.quicksum(y[i, j] for j in range(N) if j != i) ==
            gp.quicksum(y[j, i] for j in range(N) if j != i),
            name=f"bal_{i}",
        )

    for b_idx in range(m):
        for f_idx in range(n):
            f = f_start + f_idx
            t = prob.assignments[f_idx]
            coeff = -prob.weights[f_idx] if t == b_idx else 0.0
            lhs = gp.quicksum(x[b_idx][j, f] for j in range(N) if j != f) - gp.quicksum(x[b_idx][f, j] for j in range(N) if j != f)
            model.addConstr(lhs == coeff, name=f"load{b_idx}_f{f}")

    for b_idx in range(m):
        b = b_start + b_idx
        for bb in range(m):
            coeff = total_assigned[b_idx] if bb == b_idx else 0.0
            lhs = gp.quicksum(x[bb][j, b] for j in range(N) if j != b) - gp.quicksum(x[bb][b, j] for j in range(N) if j != b)
            model.addConstr(lhs == coeff, name=f"load{bb}_b{b}")

    for b_idx in range(m):
        for v in [s_idx, s_end]:
            lhs = gp.quicksum(x[b_idx][j, v] for j in range(N) if j != v) - gp.quicksum(x[b_idx][v, j] for j in range(N) if j != v)
            model.addConstr(lhs == 0, name=f"load{b_idx}_{v}")

    for i, j in edges:
        model.addConstr(gp.quicksum(x[b][i, j] for b in range(m)) <= prob.capacity * y[i, j], name=f"cap_{i}_{j}")

    for f_idx in range(n):
        f = f_start + f_idx
        basket = b_start + prob.assignments[f_idx]
        model.addConstr(y[basket, f] == 0, name=f"no_back_{f_idx}")

    w = model.addVars(edges, ub=N, name="w")
    model.addConstr(gp.quicksum(w[s_idx, j] for j in range(1, N)) == n, name="wsrc")
    for f in range(f_start, f_start + n):
        lhs = gp.quicksum(w[j, f] for j in range(N) if j != f) - gp.quicksum(w[f, j] for j in range(N) if j != f)
        model.addConstr(lhs == 1, name=f"wf{f}")
    for b in range(b_start, b_start + m):
        lhs = gp.quicksum(w[j, b] for j in range(N) if j != b) - gp.quicksum(w[b, j] for j in range(N) if j != b)
        model.addConstr(lhs == 0, name=f"wb{b}")
    model.addConstr(gp.quicksum(w[j, s_end] for j in range(N) if j != s_end) - gp.quicksum(w[s_end, j] for j in range(N) if j != s_end) == -n, name="wsnk")
    for i, j in edges:
        model.addConstr(w[i, j] <= N * y[i, j], name=f"wl{i}_{j}")

    if progress_cb is not None:
        def gurobi_cb(model, where):
            if where == GRB.Callback.MIP:
                obj = model.cbGet(GRB.Callback.MIP_OBJ)
                bnd = model.cbGet(GRB.Callback.MIP_OBJBND)
                gap = abs(obj - bnd) / (abs(obj) + 1e-10) * 100 if obj != 0 else float('inf')
                progress_cb(obj, bnd, f"{gap:.1f}%")
            elif where == GRB.Callback.MESSAGE:
                msg = model.cbGet(GRB.Callback.MSG_STRING)
                if "%" in msg and "inf" not in msg:
                    progress_cb(0, 0, msg.strip())
        model.optimize(gurobi_cb)
    else:
        model.optimize()

    status_str = {GRB.OPTIMAL: "optimal", GRB.TIME_LIMIT: "time_limit",
                  GRB.INFEASIBLE: "infeasible", GRB.UNBOUNDED: "unbounded"}.get(
        model.Status, f"status_{model.Status}")

    if model.SolCount > 0:
        y_vals = {(i, j): y[i, j].X for i, j in edges}
        route = _extract_route(y_vals, N, s_idx)
        route = _trim_route(route, s_idx)
        cost = sum(cost_mat_ext[route[k], route[k+1]] for k in range(len(route)-1))
        lb_obj = model.ObjBound
        if verbose:
            print(f"  Route: {' → '.join(_label(route, n, m, s_idx, s_end))}")
        return Solution(problem=prob, route=route, cost=cost, status=status_str,
                        bounds=(lb_obj, cost))

    return Solution(problem=prob, route=[], cost=float("inf"), status=status_str)
