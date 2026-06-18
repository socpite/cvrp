"""3D visualization for picking-routing problems and solutions.

Interactive app (``python src/visualize.py``):
    * **Open Input**  -- load a problem (input) JSON and draw it.
    * **Solve**       -- solve the loaded problem with the IP solver.
    * **Open Output** -- load a solution (output) JSON, validate it against the
                         loaded problem, and draw the path.
    * **Save Output** -- write the current route to a solution JSON.
    * **Play / Reset**-- animate the picker moving along the route.

CLI (non-interactive):
    python src/visualize.py --input prob.json [--output sol.json] [--save fig.png]
    # with --output: validate + render that solution.
    # without --output: solve the problem, then render.
"""

import argparse
import os
import sys
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.problem import Problem, Solution
from src.formats import (
    load_problem,
    load_solution,
    route_indices_to_labels,
    save_solution,
    parse_label,
)
from src.solve import solve_ip
from src.validate import validate_route, ValidationResult

COLOR_START = "#2196F3"
COLOR_FRUIT = "#4CAF50"
COLOR_BASKET = "#FF9800"
COLOR_ROUTE = "#E91E63"
COLOR_ROUTE_BAD = "#B00020"
COLOR_FRUIT_BASKET_LINE = "#AAAAAA"
COLOR_DOT = "#FF0000"


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _p(v) -> Tuple[float, float, float]:
    return v if len(v) == 3 else (v[0], v[1], 0.0)


def _pos(prob: Problem, ext_idx: int) -> Tuple[float, float, float]:
    """Position of a solver-extended node index (0,1=start; then fruits; baskets)."""
    n = prob.n_fruits
    if ext_idx <= 1:
        return prob.start
    if ext_idx < 2 + n:
        return prob.fruits[ext_idx - 2]
    return prob.baskets[ext_idx - 2 - n]


def _label_positions(prob: Problem, labels: List[str]) -> List[Tuple[float, float, float]]:
    out = []
    for lab in labels:
        kind, idx = parse_label(lab, prob.n_fruits, prob.n_baskets)
        if kind == "s":
            out.append(_p(prob.start))
        elif kind == "f":
            out.append(_p(prob.fruits[idx]))
        else:
            out.append(_p(prob.baskets[idx]))
    return out


def _get_route_positions(prob: Problem, sol: Solution) -> List[Tuple[float, float, float]]:
    return [_p(_pos(prob, i)) for i in sol.route]


def _set_axes_equal(ax):
    xlim, ylim, zlim = ax.get_xlim3d(), ax.get_ylim3d(), ax.get_zlim3d()
    x_range = abs(xlim[1] - xlim[0]) or 1
    y_range = abs(ylim[1] - ylim[0]) or 1
    z_range = abs(zlim[1] - zlim[0]) or 1
    max_range = max(x_range, y_range, z_range)
    x_mid, y_mid, z_mid = sum(xlim) / 2, sum(ylim) / 2, sum(zlim) / 2
    ax.set_xlim3d(x_mid - max_range / 2, x_mid + max_range / 2)
    ax.set_ylim3d(y_mid - max_range / 2, y_mid + max_range / 2)
    ax.set_zlim3d(z_mid - max_range / 2, z_mid + max_range / 2)


# --------------------------------------------------------------------------- #
# Drawing
# --------------------------------------------------------------------------- #
def _draw_problem(ax, prob: Problem):
    ax.clear()
    sp = _p(prob.start)
    ax.scatter(sp[0], sp[1], sp[2], color=COLOR_START, s=200, marker="s", zorder=5)
    ax.text(sp[0], sp[1], sp[2], "start", fontsize=10)

    for i, (f_pos, w, t) in enumerate(zip(prob.fruits, prob.weights, prob.assignments)):
        fp, bp = _p(f_pos), _p(prob.baskets[t])
        ax.scatter(fp[0], fp[1], fp[2], color=COLOR_FRUIT, s=120, zorder=4)
        ax.text(fp[0], fp[1], fp[2], f"f{i}(w={w:.0f})", fontsize=8)
        ax.plot([fp[0], bp[0]], [fp[1], bp[1]], [fp[2], bp[2]],
                color=COLOR_FRUIT_BASKET_LINE, linestyle=":", linewidth=0.8, alpha=0.5)

    for j, b_pos in enumerate(prob.baskets):
        bp = _p(b_pos)
        ax.scatter(bp[0], bp[1], bp[2], color=COLOR_BASKET, s=200, marker="D", zorder=5)
        ax.text(bp[0], bp[1], bp[2], f"b{j}", fontsize=10)

    ax.set_title(f"{prob.name}  |  n={prob.n_fruits} fruits, m={prob.n_baskets} baskets, K={prob.capacity}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    _set_axes_equal(ax)
    ax.grid(True, alpha=0.3)


def _draw_route_positions(ax, route_pos, valid: bool, label: str):
    if len(route_pos) < 2:
        return
    color = COLOR_ROUTE if valid else COLOR_ROUTE_BAD
    xs = [r[0] for r in route_pos]
    ys = [r[1] for r in route_pos]
    zs = [r[2] for r in route_pos]
    ax.plot(xs, ys, zs, color=color, linewidth=2, alpha=0.8, zorder=3)
    ax.legend(
        handles=[
            plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=COLOR_START, label="Start"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_FRUIT, label="Fruit"),
            plt.Line2D([0], [0], marker="D", color="w", markerfacecolor=COLOR_BASKET, label="Basket"),
            plt.Line2D([0], [0], color=color, label=label),
        ],
        loc="upper right", fontsize=8,
    )


def _draw_solution_on_ax(ax, prob: Problem, sol: Solution):
    """Backward-compatible: draw a solver Solution (extended-index route)."""
    _draw_problem(ax, prob)
    route_pos = _get_route_positions(prob, sol)
    _draw_route_positions(ax, route_pos, valid=True,
                          label=f"Route (cost={sol.cost:.1f}, {sol.status})")
    ax.set_title(f"{prob.name}  |  cost={sol.cost:.4f}  |  {sol.status}")


# --------------------------------------------------------------------------- #
# Static render helpers (used by tests / CLI)
# --------------------------------------------------------------------------- #
def show(prob: Problem, sol: Optional[Solution] = None):
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    if sol is not None:
        _draw_solution_on_ax(ax, prob, sol)
    else:
        _draw_problem(ax, prob)
    plt.show()


def save(prob: Problem, sol: Optional[Solution] = None, path: str = "output.png"):
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    if sol is not None:
        _draw_solution_on_ax(ax, prob, sol)
    else:
        _draw_problem(ax, prob)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def save_route(prob: Problem, labels: List[str], res: ValidationResult, path: str):
    """Render a labelled route (validated) to a PNG."""
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")
    _draw_problem(ax, prob)
    route_pos = _label_positions(prob, labels)
    tag = "VALID" if res.ok else "INVALID"
    _draw_route_positions(ax, route_pos, res.ok, f"Route ({tag}, cost={res.computed_cost:.1f})")
    ax.set_title(f"{prob.name}  |  cost={res.computed_cost:.4f}  |  {tag}")
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# File pickers (interactive)
# --------------------------------------------------------------------------- #
_JSON_TYPES = [("JSON files", "*.json"), ("All files", "*.*")]


def _with_tk_root(fn):
    """Run ``fn(parent_or_None)`` with a usable Tk root, creating a hidden one if needed."""
    try:
        import tkinter as tk
        from tkinter import filedialog  # noqa: F401
    except Exception as e:  # pragma: no cover - depends on backend
        print(f"[visualize] file dialog unavailable ({e}); use the --input/--output CLI flags instead.")
        return None
    root = getattr(tk, "_default_root", None)
    created = False
    if root is None:
        root = tk.Tk()
        root.withdraw()
        created = True
    try:
        return fn(root)
    finally:
        if created:
            root.destroy()


def _pick_open(title: str) -> Optional[str]:
    from tkinter import filedialog
    path = _with_tk_root(lambda r: filedialog.askopenfilename(parent=r, title=title, filetypes=_JSON_TYPES))
    return path or None


def _pick_save(title: str) -> Optional[str]:
    from tkinter import filedialog
    path = _with_tk_root(lambda r: filedialog.asksaveasfilename(
        parent=r, title=title, defaultextension=".json", filetypes=_JSON_TYPES))
    return path or None


# --------------------------------------------------------------------------- #
# Interactive app
# --------------------------------------------------------------------------- #
def app(initial_input: Optional[str] = None, initial_output: Optional[str] = None):
    st = {"prob": None, "labels": None, "result": None, "source": None, "save_sol": None}

    plt.rcParams["toolbar"] = "None"
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    fig.subplots_adjust(bottom=0.16, left=0.05, right=0.95, top=0.88)
    status_txt = fig.text(0.5, 0.965, "Open an input file to begin.",
                          ha="center", va="top", fontsize=10, family="monospace")

    # animation state
    anim = {"running": False, "pos": 0.0, "artist": None, "timer": None, "route": None}

    def _set_status(msg: str, color: str = "black"):
        status_txt.set_text(msg)
        status_txt.set_color(color)

    def _stop_anim():
        anim["running"] = False
        if anim["timer"] is not None:
            try:
                anim["timer"].stop()
            except Exception:
                pass
            anim["timer"] = None

    def _remove_dot():
        if anim["artist"] is not None:
            try:
                anim["artist"].remove()
            except Exception:
                pass
            anim["artist"] = None

    def redraw():
        _stop_anim()
        _remove_dot()
        if st["prob"] is None:
            ax.clear()
            ax.set_title("No problem loaded")
            plt.draw()
            return
        _draw_problem(ax, st["prob"])
        if st["labels"]:
            res = st["result"]
            route_pos = _label_positions(st["prob"], st["labels"])
            anim["route"] = route_pos
            tag = "VALID" if (res and res.ok) else "INVALID"
            cost = res.computed_cost if res else 0.0
            _draw_route_positions(ax, route_pos, res.ok if res else True,
                                  f"Route ({st['source']}, {tag}, cost={cost:.1f})")
            ax.set_title(f"{st['prob'].name}  |  {tag}  |  cost={cost:.4f}")
        else:
            anim["route"] = None
        plt.draw()

    def _show_result(prefix: str):
        res = st["result"]
        if res is None:
            return
        color = "#2E7D32" if res.ok else COLOR_ROUTE_BAD
        first = ""
        if not res.ok and res.errors:
            first = "  |  " + res.errors[0]
        elif res.warnings:
            first = "  |  " + res.warnings[0]
        _set_status(f"{prefix}: {('VALID' if res.ok else 'INVALID')}  "
                    f"cost={res.computed_cost:.4f}  peak load={res.max_load:.2f}{first}", color)
        print(f"\n=== {prefix} ===")
        print(res.summary())

    # --- callbacks --------------------------------------------------------- #
    def on_open_input(_):
        path = _pick_open("Open problem (input) JSON")
        if not path:
            return
        try:
            prob = load_problem(path)
        except Exception as e:
            _set_status(f"Failed to load input: {e}", COLOR_ROUTE_BAD)
            return
        st.update(prob=prob, labels=None, result=None, source=None, save_sol=None)
        _set_status(f"Loaded input '{os.path.basename(path)}'  |  "
                    f"n={prob.n_fruits}, m={prob.n_baskets}, K={prob.capacity}, "
                    f"total_w={prob.total_weight:.0f}")
        redraw()

    def on_solve(_):
        if st["prob"] is None:
            _set_status("Open an input file first.", COLOR_ROUTE_BAD)
            return
        _set_status("Solving...", "#E65100")
        plt.draw()
        fig.canvas.flush_events()
        sol = solve_ip(st["prob"], verbose=False)
        labels = route_indices_to_labels(sol.route, st["prob"].n_fruits, st["prob"].n_baskets)
        res = validate_route(st["prob"], labels, sol.cost)
        st.update(labels=labels, result=res, source="solved", save_sol=sol)
        redraw()
        _show_result(f"Solved ({sol.status})")

    def on_open_output(_):
        if st["prob"] is None:
            _set_status("Open an input file first (the output is validated against it).", COLOR_ROUTE_BAD)
            return
        path = _pick_open("Open solution (output) JSON")
        if not path:
            return
        try:
            loaded = load_solution(path)
        except Exception as e:
            _set_status(f"Failed to load output: {e}", COLOR_ROUTE_BAD)
            return
        if loaded.problem and loaded.problem != st["prob"].name:
            print(f"[visualize] note: output is for problem '{loaded.problem}', "
                  f"loaded input is '{st['prob'].name}'.")
        try:
            res = validate_route(st["prob"], loaded.route, loaded.cost)
        except Exception as e:
            _set_status(f"Could not validate output: {e}", COLOR_ROUTE_BAD)
            return
        st.update(labels=loaded.route, result=res, source="loaded", save_sol=None)
        redraw()
        _show_result(f"Loaded '{os.path.basename(path)}'")

    def on_save_output(_):
        if st["save_sol"] is None:
            _set_status("Nothing to save -- press Solve first (only solved routes can be saved).",
                        COLOR_ROUTE_BAD)
            return
        path = _pick_save("Save solution (output) JSON")
        if not path:
            return
        try:
            save_solution(st["save_sol"], path)
        except Exception as e:
            _set_status(f"Failed to save: {e}", COLOR_ROUTE_BAD)
            return
        _set_status(f"Saved solution to '{os.path.basename(path)}'.", "#2E7D32")

    def _anim_tick():
        if not anim["running"] or not anim["route"] or len(anim["route"]) < 2:
            _stop_anim()
            return
        rp = anim["route"]
        anim["pos"] += 0.03
        n_seg = len(rp) - 1
        if anim["pos"] >= n_seg:
            anim["pos"] = 0.0
        seg = int(anim["pos"])
        t = anim["pos"] - seg
        a, b = rp[seg], rp[seg + 1]
        px, py, pz = (a[k] + (b[k] - a[k]) * t for k in range(3))
        if anim["artist"] is None:
            anim["artist"] = ax.plot([px], [py], [pz], "o", color=COLOR_DOT, markersize=14, zorder=10)[0]
        else:
            anim["artist"].set_data([px], [py])
            anim["artist"].set_3d_properties([pz])
        fig.canvas.draw_idle()

    def on_play(_):
        if not anim["route"] or len(anim["route"]) < 2:
            return
        if anim["running"]:
            _stop_anim()
            return
        anim["running"] = True
        anim["timer"] = fig.canvas.new_timer(interval=50)
        anim["timer"].add_callback(_anim_tick)
        anim["timer"].start()

    def on_reset(_):
        _stop_anim()
        anim["pos"] = 0.0
        _remove_dot()
        fig.canvas.draw_idle()

    # --- buttons ----------------------------------------------------------- #
    specs = [
        ("Open Input", on_open_input, "#90CAF9"),
        ("Solve", on_solve, "#FFB74D"),
        ("Open Output", on_open_output, "#A5D6A7"),
        ("Save Output", on_save_output, "#E0E0E0"),
        ("Play", on_play, "#CE93D8"),
        ("Reset", on_reset, "#E0E0E0"),
    ]
    buttons = []  # keep references alive
    w, gap, x0 = 0.13, 0.015, 0.05
    for i, (text, cb, color) in enumerate(specs):
        axb = fig.add_axes([x0 + i * (w + gap), 0.04, w, 0.06])
        btn = Button(axb, text, color=color)
        btn.label.set_fontsize(9)
        btn.on_clicked(cb)
        buttons.append(btn)

    # --- initial state ----------------------------------------------------- #
    if initial_input:
        try:
            st["prob"] = load_problem(initial_input)
            _set_status(f"Loaded input '{os.path.basename(initial_input)}'  |  "
                        f"n={st['prob'].n_fruits}, m={st['prob'].n_baskets}, K={st['prob'].capacity}")
            redraw()
        except Exception as e:
            _set_status(f"Failed to load input: {e}", COLOR_ROUTE_BAD)
    if initial_output and st["prob"] is not None:
        try:
            loaded = load_solution(initial_output)
            st["labels"] = loaded.route
            st["result"] = validate_route(st["prob"], loaded.route, loaded.cost)
            st["source"] = "loaded"
            redraw()
            _show_result(f"Loaded '{os.path.basename(initial_output)}'")
        except Exception as e:
            _set_status(f"Failed to load output: {e}", COLOR_ROUTE_BAD)

    plt.show()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _run_cli(args) -> int:
    prob = load_problem(args.input)
    if args.output:
        loaded = load_solution(args.output)
        res = validate_route(prob, loaded.route, loaded.cost)
        print(res.summary())
        labels = loaded.route
    else:
        sol = solve_ip(prob, time_limit=args.time_limit, verbose=args.verbose)
        labels = route_indices_to_labels(sol.route, prob.n_fruits, prob.n_baskets)
        res = validate_route(prob, labels, sol.cost)
        print(f"Solved: {sol.status}")
        print(res.summary())
        if args.write_output:
            save_solution(sol, args.write_output)
            print(f"Wrote solution to {args.write_output}")

    if args.save:
        save_route(prob, labels, res, args.save)
        print(f"Saved figure to {args.save}")
    elif not args.no_show:
        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection="3d")
        _draw_problem(ax, prob)
        _draw_route_positions(ax, _label_positions(prob, labels), res.ok,
                              f"Route ({'VALID' if res.ok else 'INVALID'}, cost={res.computed_cost:.1f})")
        plt.show()
    return 0 if res.ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize / solve / validate picking-routing instances.")
    parser.add_argument("--input", help="problem (input) JSON; enables non-interactive CLI mode")
    parser.add_argument("--output", help="solution (output) JSON to validate and render")
    parser.add_argument("--write-output", help="when solving, write the solution JSON to this path")
    parser.add_argument("--save", help="save the figure to this PNG instead of showing a window")
    parser.add_argument("--no-show", action="store_true", help="do not open a window (CLI)")
    parser.add_argument("--time-limit", type=float, default=120.0, help="solver time limit (s)")
    parser.add_argument("--verbose", action="store_true", help="verbose solver output")
    cli_args = parser.parse_args()

    if cli_args.input:
        sys.exit(_run_cli(cli_args))
    else:
        app()
