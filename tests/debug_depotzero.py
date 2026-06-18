"""Test the proposed fix: force the commodity (load) OUTFLOW from the start nodes
s and s' to be exactly 0 (robot leaves/returns to the depot empty), in addition to
the existing net-zero depot balance. Solve each instance, extract the route, and
validate. Compares against the unmodified model."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import gurobipy as gp
from gurobipy import GRB

from src.formats import load_problem, route_indices_to_labels
from src.solve import _cost_ext, _extract_route, _trim_route
from src.validate import validate_route


def solve(prob, depot_zero_load, time_limit=60):
    n, m = prob.n_fruits, prob.n_baskets
    N = 2 + n + m
    N_orig = 1 + n + m + 1
    s_idx, s_end, f_start, b_start = 0, 1, 2, 2 + n
    edges = [(i, j) for i in range(N) for j in range(N) if i != j]
    cost_mat = prob.cost_matrix()
    ce = np.array([[_cost_ext(i, j, cost_mat, s_idx, s_end, N_orig) for j in range(N)] for i in range(N)])
    total_assigned = [0.0] * m
    for i, t in enumerate(prob.assignments):
        total_assigned[t] += prob.weights[i]

    mdl = gp.Model(); mdl.setParam("OutputFlag", 0); mdl.setParam("TimeLimit", time_limit); mdl.setParam("MIPGap", 1e-6)
    y = mdl.addVars(edges, vtype=GRB.BINARY, name="y")
    x = [mdl.addVars(edges, lb=0, name=f"x{b}") for b in range(m)]
    mdl.setObjective(gp.quicksum(ce[i, j] * y[i, j] for i, j in edges), GRB.MINIMIZE)
    for f in range(f_start, f_start + n):
        mdl.addConstr(gp.quicksum(y[f, j] for j in range(N) if j != f) == 1)
        mdl.addConstr(gp.quicksum(y[i, f] for i in range(N) if i != f) == 1)
    for i in range(N):
        mdl.addConstr(gp.quicksum(y[i, j] for j in range(N) if j != i) == gp.quicksum(y[j, i] for j in range(N) if j != i))
    for b_idx in range(m):
        for f_idx in range(n):
            f = f_start + f_idx
            coeff = -prob.weights[f_idx] if prob.assignments[f_idx] == b_idx else 0.0
            mdl.addConstr(gp.quicksum(x[b_idx][j, f] for j in range(N) if j != f) - gp.quicksum(x[b_idx][f, j] for j in range(N) if j != f) == coeff)
    for b_idx in range(m):
        b = b_start + b_idx
        for bb in range(m):
            coeff = total_assigned[b_idx] if bb == b_idx else 0.0
            mdl.addConstr(gp.quicksum(x[bb][j, b] for j in range(N) if j != b) - gp.quicksum(x[bb][b, j] for j in range(N) if j != b) == coeff)
    for b_idx in range(m):
        for v in (s_idx, s_end):
            mdl.addConstr(gp.quicksum(x[b_idx][j, v] for j in range(N) if j != v) - gp.quicksum(x[b_idx][v, j] for j in range(N) if j != v) == 0)
            if depot_zero_load:
                # proposed fix: NO load leaves the start nodes (robot departs/returns empty)
                mdl.addConstr(gp.quicksum(x[b_idx][v, j] for j in range(N) if j != v) == 0)
    for i, j in edges:
        mdl.addConstr(gp.quicksum(x[b][i, j] for b in range(m)) <= prob.capacity * y[i, j])
    w = mdl.addVars(edges, ub=N, name="w")
    mdl.addConstr(gp.quicksum(w[s_idx, j] for j in range(1, N)) == n)
    for f in range(f_start, f_start + n):
        mdl.addConstr(gp.quicksum(w[j, f] for j in range(N) if j != f) - gp.quicksum(w[f, j] for j in range(N) if j != f) == 1)
    for b in range(b_start, b_start + m):
        mdl.addConstr(gp.quicksum(w[j, b] for j in range(N) if j != b) - gp.quicksum(w[b, j] for j in range(N) if j != b) == 0)
    mdl.addConstr(gp.quicksum(w[j, s_end] for j in range(N) if j != s_end) - gp.quicksum(w[s_end, j] for j in range(N) if j != s_end) == -n)
    for i, j in edges:
        mdl.addConstr(w[i, j] <= N * y[i, j])

    mdl.optimize()
    if mdl.SolCount == 0:
        return None, mdl.Status
    route = _trim_route(_extract_route({(i, j): y[i, j].X for i, j in edges}, N, s_idx), s_idx)
    labels = route_indices_to_labels(route, n, m)
    return labels, mdl.Status


if __name__ == "__main__":
    names = ["test4_triangle", "test1_simple_line", "test3_capacity_forced_multi_trip",
             "test5_two_baskets_capacity", "test6_capacity_one_at_a_time", "large_25f_4b"]
    for name in names:
        prob = load_problem(f"instances/{name}.json")
        tl = 60 if name.startswith("large") else 10
        t0 = time.time()
        labels, status = solve(prob, depot_zero_load=True, time_limit=tl)
        dt = time.time() - t0
        if labels is None:
            print(f"{name:32s}  NO SOLUTION (status {status}) in {dt:.1f}s")
            continue
        res = validate_route(prob, labels)
        print(f"{name:32s}  ok={res.ok!s:5s}  peak={res.max_load:5.2f}/K={prob.capacity:<4g}  cost={res.computed_cost:6.2f}  ({dt:.1f}s)")
        if not res.ok:
            print(f"    -> {res.errors[0]}")
