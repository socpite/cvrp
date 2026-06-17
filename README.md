# Capacitated Picking-Routing IP Solver

An integer-programming solver (Gurobi) for a **capacitated fruit-picking routing problem**: a
single picker starts at a depot, visits every *fruit*, and must deliver each fruit's weight to its
assigned *basket*, never carrying more than a fixed capacity at once. The objective is to minimize
the total 3D Euclidean travel distance of the route.

The formulation, the model variants explored, and notes on the underlying theory live in
`state_space_backup.tex` and `baldacci2004.pdf`.

## Problem definition

A `Problem` (see `src/problem.py`) is described by:

| Field         | Meaning                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| `start`       | Depot coordinate `(x, y, z)` — route begins and ends here.              |
| `fruits`      | List of fruit coordinates; each must be visited.                        |
| `weights`     | Weight of each fruit (parallel to `fruits`).                            |
| `baskets`     | List of basket (drop-off) coordinates.                                  |
| `assignments` | For each fruit, the index of the basket it must be delivered to.        |
| `capacity`    | Maximum weight the picker can carry simultaneously.                     |

The solver returns a `Solution` with the visiting `route` (node indices), the total `cost`, the
Gurobi `status`, and the `(lower_bound, upper_bound)` objective bounds.

## Requirements

- **Python 3.12** (the project venv targets 3.12; newer versions such as 3.14 are not used here).
- **Gurobi 13.x** via the `gurobipy` package. Gurobi requires a license — this project was set up
  with a free [academic license](https://www.gurobi.com/academia/academic-program-and-licenses/).
  Activate yours with `grbgetkey <your-key>` once, after installing.
- `numpy` and `matplotlib` for geometry and 3D visualization.

Exact direct dependencies are listed in `requirements.txt`.

## Setup

This repo was developed with [`uv`](https://docs.astral.sh/uv/). Either tool works.

### Option A — uv (recommended, matches the existing `.venv`)

```bash
# Create a Python 3.12 virtual environment in ./.venv
uv venv --python 3.12

# Install dependencies
uv pip install -r requirements.txt
```

`uv` runs commands inside `.venv` automatically when you prefix them with `uv run` (see below), so
you do not have to activate the environment manually.

### Option B — plain venv + pip

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # bash/zsh
#   or: source .venv/bin/activate.fish   (fish shell)
pip install -r requirements.txt
```

### Gurobi license

`gurobipy` ships the solver binaries, but you still need a valid license file (`gurobi.lic`).
For the academic named-user license:

```bash
grbgetkey <key-from-gurobi-portal>     # run once on a university network
```

Verify everything is working:

```bash
uv run python -c "import gurobipy as gp; gp.Model(); print('Gurobi OK')"
```

## Project layout

```
src/
  problem.py      Problem / Solution dataclasses, distance + cost-matrix helpers
  solve.py        solve_ip(): builds and solves the Gurobi MIP, extracts the route
  generator.py    Hand-built small test instances + random instance generator
  visualize.py    3D matplotlib rendering: show(), save(), and an interactive browse()
tests/
  test_small.py   Solve all 6 small instances, save a PNG per instance to output/
  test_large.py   Solve the 3 larger random instances (20-30 fruits)
  test_solve.py   Unit tests for route-extraction helpers (no solver needed)
  test_visualize.py  Unit tests for index->coordinate mapping
  debug_extract.py   Scratch script for inspecting a raw model build
output/           Rendered PNGs (git-ignored)
```

> **Imports use the `src.` package prefix** (e.g. `from src.solve import solve_ip`). Always run
> scripts from the repository root so that `src` is importable. The test files also insert the repo
> root onto `sys.path`, so running them directly works too.

## Running

All commands below assume you are in the repository root. Prefix with `uv run` (Option A) or
activate the venv first (Option B); the examples use `uv run`.

### Solve and render the small instances

Solves all six small instances, prints the route/cost for each, and writes a PNG per instance into
`output/`:

```bash
uv run python tests/test_small.py
```

### Solve the larger instances

Solves the three larger random instances (20-30 fruits) with a 300s time limit each:

```bash
uv run python tests/test_large.py
```

### Run the unit tests

`test_visualize.py` exercises pure helpers and needs no Gurobi license. `test_solve.py` covers the
route-extraction helpers **and** runs one tiny end-to-end solve, so it does require a working
Gurobi license:

```bash
uv run python tests/test_visualize.py   # no license needed
uv run python tests/test_solve.py       # needs a Gurobi license
```

### Interactive 3D viewer

Launches a matplotlib window to browse instances, solve them on demand, and animate the picker
moving along the route:

```bash
uv run python src/visualize.py
```

Controls:

| Input                         | Action                                              |
| ----------------------------- | --------------------------------------------------- |
| Left / Right arrows           | Previous / next instance                            |
| `s`                           | Solve the current instance                          |
| `r`                           | Reset (clear the solution)                          |
| Spacebar                      | Play / pause the route animation                    |
| **Solve IP** button           | Solve the current instance                          |
| **Random** button             | Generate and add a random instance                  |
| **Play / Reset** buttons      | Control the animated picker dot                     |

> The viewer needs an interactive matplotlib backend (a display / GUI). On a headless machine use
> `save()` / `test_small.py` to write PNGs instead.

## Using the solver from your own code

```python
from src.generator import random_instance      # or make_problem(...)
from src.solve import solve_ip
from src.visualize import save

prob = random_instance("demo", n_fruits=10, n_baskets=2, capacity=8.0, seed=7)

sol = solve_ip(prob, time_limit=120.0, verbose=True)
print(sol.status, sol.cost, sol.route)

save(prob, sol, "output/demo.png")             # render the solution to a PNG
```

`solve_ip` parameters:

- `time_limit` (seconds, default `120.0`) — Gurobi `TimeLimit`.
- `verbose` (default `False`) — when `True`, Gurobi logs to stdout and the extracted route is
  printed.
- `progress_cb` — optional callback `(obj, bound, gap_str)` invoked during the search (used by the
  interactive viewer to display live progress).

## Troubleshooting

- **`ModuleNotFoundError: No module named 'src'`** — run from the repository root, not from inside
  `src/` or `tests/`.
- **Gurobi license / `GurobiError: No license`** — install a license with `grbgetkey`, or check
  that `GRB_LICENSE_FILE` points at a valid `gurobi.lic`.
- **The viewer opens no window / `UserWarning: FigureCanvasAgg is non-interactive`** — you are on a
  headless backend; use `test_small.py` (which calls `save()`) to produce PNGs instead.
