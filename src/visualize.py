from typing import List, Optional, Tuple
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.problem import Problem, Solution
from src.generator import all_small_tests, all_large_tests, random_instance
from src.solve import solve_ip

COLOR_START = "#2196F3"
COLOR_FRUIT = "#4CAF50"
COLOR_BASKET = "#FF9800"
COLOR_ROUTE = "#E91E63"
COLOR_FRUIT_BASKET_LINE = "#AAAAAA"
COLOR_DOT = "#FF0000"


def _pos(prob: Problem, ext_idx: int) -> Tuple[float, float, float]:
    n, m = prob.n_fruits, prob.n_baskets
    if ext_idx <= 1:
        return prob.start
    if ext_idx < 2 + n:
        return prob.fruits[ext_idx - 2]
    return prob.baskets[ext_idx - 2 - n]


def _set_axes_equal(ax):
    xlim = ax.get_xlim3d()
    ylim = ax.get_ylim3d()
    zlim = ax.get_zlim3d()
    x_range = abs(xlim[1] - xlim[0]) or 1
    y_range = abs(ylim[1] - ylim[0]) or 1
    z_range = abs(zlim[1] - zlim[0]) or 1
    max_range = max(x_range, y_range, z_range)
    x_mid = (xlim[0] + xlim[1]) / 2
    y_mid = (ylim[0] + ylim[1]) / 2
    z_mid = (zlim[0] + zlim[1]) / 2
    ax.set_xlim3d(x_mid - max_range / 2, x_mid + max_range / 2)
    ax.set_ylim3d(y_mid - max_range / 2, y_mid + max_range / 2)
    ax.set_zlim3d(z_mid - max_range / 2, z_mid + max_range / 2)


def _draw_problem(ax, prob: Problem):
    ax.clear()

    def p(v):
        return v if len(v) == 3 else (v[0], v[1], 0.0)

    sp = p(prob.start)
    ax.scatter(sp[0], sp[1], sp[2], color=COLOR_START, s=200, marker="s", zorder=5)
    ax.text(sp[0], sp[1], sp[2], "start", fontsize=10)

    for i, (f_pos, w, t) in enumerate(zip(prob.fruits, prob.weights, prob.assignments)):
        fp = p(f_pos)
        bp = p(prob.baskets[t])
        ax.scatter(fp[0], fp[1], fp[2], color=COLOR_FRUIT, s=120, zorder=4)
        ax.text(fp[0], fp[1], fp[2], f"f{i}(w={w:.0f})", fontsize=8)
        ax.plot([fp[0], bp[0]], [fp[1], bp[1]], [fp[2], bp[2]],
                color=COLOR_FRUIT_BASKET_LINE, linestyle=":", linewidth=0.8, alpha=0.5)

    for j, b_pos in enumerate(prob.baskets):
        bp = p(b_pos)
        ax.scatter(bp[0], bp[1], bp[2], color=COLOR_BASKET, s=200, marker="D", zorder=5)
        ax.text(bp[0], bp[1], bp[2], f"b{j}", fontsize=10)

    ax.set_title(f"{prob.name}  |  n={prob.n_fruits} fruits, m={prob.n_baskets} baskets, K={prob.capacity}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    _set_axes_equal(ax)
    ax.grid(True, alpha=0.3)


def _get_route_positions(prob: Problem, sol: Solution) -> List[Tuple[float, float, float]]:

    def p(v):
        return v if len(v) == 3 else (v[0], v[1], 0.0)
    return [p(_pos(prob, i)) for i in sol.route]


def _draw_solution_on_ax(ax, prob: Problem, sol: Solution):
    _draw_problem(ax, prob)
    route_pos = _get_route_positions(prob, sol)
    xs = [r[0] for r in route_pos]
    ys = [r[1] for r in route_pos]
    zs = [r[2] for r in route_pos]
    ax.plot(xs, ys, zs, color=COLOR_ROUTE, linewidth=2, alpha=0.7, zorder=3)
    ax.legend(
        handles=[
            plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=COLOR_START, label="Start"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_FRUIT, label="Fruit"),
            plt.Line2D([0], [0], marker="D", color="w", markerfacecolor=COLOR_BASKET, label="Basket"),
            plt.Line2D([0], [0], color=COLOR_ROUTE, label=f"Route (cost={sol.cost:.1f}, {sol.status})"),
        ],
        loc="upper right", fontsize=8,
    )
    ax.set_title(f"{prob.name}  |  cost={sol.cost:.4f}  |  {sol.status}")


def browse():
    tests = all_small_tests() + all_large_tests()
    current = [0]
    sol = [None]
    dot_pos = [0.0]
    anim_running = [False]
    dot_artist = [None]
    route_pos_cache = None
    timer = [None]

    plt.rcParams["toolbar"] = "None"
    fig = plt.figure(figsize=(12, 7))
    from mpl_toolkits.mplot3d import Axes3D
    ax = fig.add_subplot(111, projection='3d')
    fig.subplots_adjust(bottom=0.22, left=0.22, right=0.95, top=0.95)

    _draw_problem(ax, tests[0])

    sel_buttons = []
    button_ax_list = []

    def build_selector():
        nonlocal sel_buttons, button_ax_list
        for b in sel_buttons:
            try:
                b.ax.remove()
            except Exception:
                pass
        for ba in button_ax_list:
            try:
                ba.remove()
            except Exception:
                pass
        sel_buttons = []
        button_ax_list = []
        n = len(tests)
        btn_height = min(0.04, 0.7 / max(n, 1))
        start_y = 0.9 - btn_height
        for i, t in enumerate(tests):
            ypos = start_y - i * (btn_height + 0.005)
            axb = fig.add_axes([0.02, ypos, 0.18, btn_height])
            btn = Button(axb, t.name, color="#F5F5F5" if i != current[0] else "#E91E63")
            btn.label.set_fontsize(7)
            if i == current[0]:
                btn.label.set_fontweight("bold")
                btn.color = "#E91E63"
            def make_cb(idx):
                def cb(_):
                    set_test(idx)
                return cb
            btn.on_clicked(make_cb(i))
            sel_buttons.append(btn)
            button_ax_list.append(axb)

    def highlight_selector():
        for i, btn in enumerate(sel_buttons):
            if i == current[0]:
                btn.color = "#E91E63"
                btn.label.set_fontweight("bold")
            else:
                btn.color = "#F5F5F5"
                btn.label.set_fontweight("normal")
            btn.ax.set_facecolor(btn.color)

    def stop_anim():
        anim_running[0] = False
        if timer[0] is not None:
            try:
                timer[0].stop()
            except Exception:
                pass
            timer[0] = None

    def set_test(idx):
        nonlocal route_pos_cache
        idx = max(0, min(idx, len(tests) - 1))
        stop_anim()
        _remove_dot()
        current[0] = idx
        sol[0] = None
        route_pos_cache = None
        dot_pos[0] = 0
        prob = tests[idx]
        _draw_problem(ax, prob)
        highlight_selector()
        _update_info()
        plt.draw()

    def _update_info():
        prob = tests[current[0]]
        info_box.set_val(
            f"{prob.name}  |  "
            f"fruits={prob.n_fruits}, baskets={prob.n_baskets}, "
            f"K={prob.capacity}, total_w={prob.total_weight:.0f}"
        )

    build_selector()

    ax_solve = fig.add_axes([0.25, 0.05, 0.12, 0.06])
    solve_btn = Button(ax_solve, "Solve IP", color="#FFB74D")
    def solve_cb(_):
        nonlocal route_pos_cache
        prob = tests[current[0]]
        solve_btn.label.set_text("Solving...")
        solve_btn.active = False
        plt.draw()
        def on_progress(obj, bnd, gap_str):
            info_box.set_val(f"{prob.name}  |  obj={obj:.2f}  bnd={bnd:.2f}  gap={gap_str}")
            fig.canvas.draw_idle()
        result = solve_ip(prob, verbose=False, progress_cb=on_progress)
        sol[0] = result
        route_pos_cache = _get_route_positions(prob, result)
        _draw_solution_on_ax(ax, prob, result)
        solve_btn.label.set_text("Solve IP")
        solve_btn.active = True
        dot_pos[0] = 0
        stop_anim()
        rp = _get_dot_route()
        if rp:
            _create_dot(rp[0])
        _update_info()
        plt.draw()
    solve_btn.on_clicked(solve_cb)

    ax_rand = fig.add_axes([0.38, 0.05, 0.10, 0.06])
    rand_btn = Button(ax_rand, "Random", color="#81C784")
    def rand_cb(_):
        import time
        seed = int(time.time() * 1000) % 10000
        rng = np.random.default_rng(seed)
        n = int(rng.integers(3, 7))
        m = int(rng.integers(1, 4))
        K = float(rng.uniform(3, 8))
        prob = random_instance(f"random_{n}f_{m}b", n, m, K, seed=seed)
        tests.append(prob)
        set_test(len(tests) - 1)
        build_selector()
        highlight_selector()
        plt.draw()
    rand_btn.on_clicked(rand_cb)

    ax_info = fig.add_axes([0.25, 0.88, 0.70, 0.05])
    info_box = TextBox(ax_info, "", initial="")
    info_box.set_active(False)
    _update_info()

    def _get_dot_route():
        nonlocal route_pos_cache
        if route_pos_cache is not None:
            return route_pos_cache
        if sol[0] is not None:
            route_pos_cache = _get_route_positions(tests[current[0]], sol[0])
            return route_pos_cache
        return None

    def _create_dot(p):
        nonlocal dot_artist
        if dot_artist[0] is not None:
            dot_artist[0].remove()
        dot_artist[0] = ax.plot([p[0]], [p[1]], [p[2]], 'o',
                                color=COLOR_DOT, markersize=14, zorder=10)[0]

    def _move_dot_to(p):
        nonlocal dot_artist
        if dot_artist[0] is not None:
            dot_artist[0].set_data([p[0]], [p[1]])
            dot_artist[0].set_3d_properties([p[2]])

    def _remove_dot():
        nonlocal dot_artist
        if dot_artist[0] is not None:
            dot_artist[0].remove()
            dot_artist[0] = None

    def _anim_tick():
        if not anim_running[0]:
            return
        rp = _get_dot_route()
        if not rp or len(rp) < 2:
            stop_anim()
            return
        dot_pos[0] += 0.03
        n_seg = len(rp) - 1
        if dot_pos[0] >= n_seg:
            dot_pos[0] = 0.0
        seg = int(dot_pos[0])
        t = dot_pos[0] - seg
        a, b = rp[seg], rp[seg + 1]
        px = a[0] + (b[0] - a[0]) * t
        py = a[1] + (b[1] - a[1]) * t
        pz = a[2] + (b[2] - a[2]) * t
        _move_dot_to((px, py, pz))
        fig.canvas.draw_idle()

    def toggle_anim(_):
        rp = _get_dot_route()
        if not rp or len(rp) < 2:
            return
        if anim_running[0]:
            stop_anim()
        else:
            n_seg = len(rp) - 1
            if dot_pos[0] >= n_seg:
                dot_pos[0] = 0
            p = rp[int(dot_pos[0])]
            _create_dot(p)
            anim_running[0] = True
            timer[0] = fig.canvas.new_timer(interval=50)
            timer[0].add_callback(_anim_tick)
            timer[0].start()

    ax_play = fig.add_axes([0.50, 0.05, 0.08, 0.06])
    play_btn = Button(ax_play, "Play", color="#CE93D8")
    play_btn.on_clicked(toggle_anim)

    ax_reset = fig.add_axes([0.59, 0.05, 0.08, 0.06])
    reset_btn = Button(ax_reset, "Reset", color="#E0E0E0")
    def reset_anim(_):
        stop_anim()
        dot_pos[0] = 0
        rp = _get_dot_route()
        if rp:
            _create_dot(rp[0])
            fig.canvas.draw_idle()
    reset_btn.on_clicked(reset_anim)

    def on_key(event):
        if event.key == "left":
            set_test(current[0] - 1)
        elif event.key == "right":
            set_test(current[0] + 1)
        elif event.key in ("s", "S"):
            solve_cb(None)
        elif event.key in ("r", "R"):
            prob = tests[current[0]]
            _draw_problem(ax, prob)
            sol[0] = None
            route_pos_cache = None
            _remove_dot()
            stop_anim()
            _update_info()
        elif event.key == " ":
            toggle_anim(None)
    fig.canvas.mpl_connect("key_press_event", on_key)

    highlight_selector()
    plt.show()


def show(prob: Problem, sol: Optional[Solution] = None):
    from mpl_toolkits.mplot3d import Axes3D
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    if sol is not None:
        _draw_solution_on_ax(ax, prob, sol)
    else:
        _draw_problem(ax, prob)
    plt.show()


def save(prob: Problem, sol: Optional[Solution] = None, path: str = "output.png"):
    from mpl_toolkits.mplot3d import Axes3D
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')
    if sol is not None:
        _draw_solution_on_ax(ax, prob, sol)
    else:
        _draw_problem(ax, prob)
    plt.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    browse()
