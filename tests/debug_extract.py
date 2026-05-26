import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generator import small_test_2, small_test_3, small_test_6
from src.solve import solve_ip
from src.solve import _extract_route, _label
import gurobipy as gp
from gurobipy import GRB
import numpy as np


def debug_problem(prob):
    print(f"\n=== {prob.name} ===")
    n, m = prob.n_fruits, prob.n_baskets
    N = 1 + n + m + 1
    s_idx, s_end = 0, 1 + n + m
    f_start, b_start = 1, 1 + n
    edges = [(i, j) for i in range(N) for j in range(N) if i != j]
    cost_mat = prob.cost_matrix()

    total_assigned = [0.0] * m
    for i, t in enumerate(prob.assignments):
        total_assigned[t] += prob.weights[i]

    model = gp.Model()
    model.setParam("OutputFlag", 0)
    model.setParam("TimeLimit", 30)

    y = model.addVars(edges, vtype=GRB.BINARY, name="y")
    x = model.addVars(edges, lb=0, name="x")
    model.setObjective(gp.quicksum(cost_mat[i, j] * y[i, j] for i, j in edges), GRB.MINIMIZE)

    for f in range(f_start, f_start + n):
        model.addConstr(gp.quicksum(y[f, j] for j in range(N) if j != f) == 1)
        model.addConstr(gp.quicksum(y[i, f] for i in range(N) if i != f) == 1)
    for i in range(N):
        model.addConstr(gp.quicksum(y[i, j] for j in range(N) if j != i) ==
                        gp.quicksum(y[j, i] for j in range(N) if j != i))
    model.addConstr(gp.quicksum(y[s_idx, j] for j in range(1, N)) == 1)
    model.addConstr(gp.quicksum(y[i, s_end] for i in range(N - 1)) == 1)

    for f_idx in range(n):
        f = f_start + f_idx
        lhs = gp.quicksum(x[j, f] for j in range(N) if j != f) - gp.quicksum(x[f, j] for j in range(N) if j != f)
        model.addConstr(lhs == -prob.weights[f_idx])
    for b_idx in range(m):
        b = b_start + b_idx
        lhs = gp.quicksum(x[j, b] for j in range(N) if j != b) - gp.quicksum(x[b, j] for j in range(N) if j != b)
        model.addConstr(lhs == total_assigned[b_idx])
    for node in [s_idx, s_end]:
        lhs = gp.quicksum(x[j, node] for j in range(N) if j != node) - gp.quicksum(x[node, j] for j in range(N) if j != node)
        model.addConstr(lhs == 0)
    for i, j in edges:
        model.addConstr(x[i, j] <= prob.capacity * y[i, j])

    w = model.addVars(edges, ub=N, name="w")
    model.addConstr(gp.quicksum(w[s_idx, j] for j in range(1, N)) == n)
    for f in range(f_start, f_start + n):
        lhs = gp.quicksum(w[j, f] for j in range(N) if j != f) - gp.quicksum(w[f, j] for j in range(N) if j != f)
        model.addConstr(lhs == 1)
    for b in range(b_start, b_start + m):
        lhs = gp.quicksum(w[j, b] for j in range(N) if j != b) - gp.quicksum(w[b, j] for j in range(N) if j != b)
        model.addConstr(lhs == 0)
    lhs = gp.quicksum(w[j, s_end] for j in range(N) if j != s_end) - gp.quicksum(w[s_end, j] for j in range(N) if j != s_end)
    model.addConstr(lhs == 0)
    for i, j in edges:
        model.addConstr(w[i, j] <= N * y[i, j])

    for f_idx in range(n):
        f = f_start + f_idx
        basket = b_start + prob.assignments[f_idx]
        r = model.addVars(edges, ub=1, name=f"r{f_idx}")
        lhs = gp.quicksum(r[j, f] for j in range(N) if j != f) - gp.quicksum(r[f, j] for j in range(N) if j != f)
        model.addConstr(lhs == -1)
        lhs = gp.quicksum(r[j, basket] for j in range(N) if j != basket) - gp.quicksum(r[basket, j] for j in range(N) if j != basket)
        model.addConstr(lhs == 1)
        for v in range(N):
            if v == f or v == basket:
                continue
            lhs = gp.quicksum(r[j, v] for j in range(N) if j != v) - gp.quicksum(r[v, j] for j in range(N) if j != v)
            model.addConstr(lhs == 0)
        for i, j in edges:
            model.addConstr(r[i, j] <= y[i, j])

    model.optimize()
    if model.SolCount == 0:
        print("No solution found")
        return

    used = sorted([(i, j) for i, j in edges if y[i, j].X > 0.5])
    print(f"Used edges ({len(used)}): {used}")

    V = [prob.start] + prob.fruits + prob.baskets + [prob.start]
    total_cost = sum(cost_mat[i, j] for i, j in used)
    print(f"Total cost: {total_cost:.4f} (model: {model.ObjVal:.4f})")
    for i, j in used:
        d = np.linalg.norm([V[i][0]-V[j][0], V[i][1]-V[j][1]])
        print(f"  {_label([i], n, m)[0]:>2} -> {_label([j], n, m)[0]}: {d:.4f}")

    route = _extract_route({(i, j): y[i, j].X for i, j in edges}, N, s_idx, s_end)
    labels = _label(route, n, m)
    print(f"Route ({len(route)} nodes): {' -> '.join(labels)}")


debug_problem(small_test_2())
debug_problem(small_test_3())
debug_problem(small_test_6())
