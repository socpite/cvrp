# Talk Script — Capacitated Picking-Routing MILP

*Audience: research group (MILP / flow formulations assumed). Target ~12–15 min + Q&A.*
*Equation labels below match `main.tex`. Code references are `src/solve.py`.*

---

## 0. One-line framing (30 sec)

> "We have one robot that must pick every fruit and drop each into its assigned basket,
> never carrying more than capacity K at once, minimizing total travel. We solve it exactly
> as a single MILP using a multi-commodity flow formulation."

**Hook for experts:** This is *not* a vanilla CVRP. Three twists:
1. Pickups and deliveries are **paired** (fruit → its specific basket), with **precedence** (pick before drop).
2. Baskets can be **revisited any number of times** (multi-trip) — so it's not a Hamiltonian tour.
3. We get **precedence and assignment for free** from the flow structure — no explicit ordering constraints.

---

## 1. Problem formalization (1–2 min)

Point at the nomenclature + Problem definition.

- Inputs: fruits $\mathcal{F}$ with weights $w_i$, baskets $\mathcal{B}$, assignment $t_i$ (each fruit → one basket), start $\mathbf{s}$, capacity $K$.
- A **picking routing plan** $P=(p_1,\dots,p_T)$, $p_i \in \mathcal F \cup \mathcal B$, such that:
  - each fruit appears exactly once,
  - each fruit's basket appears *after* it (precedence),
  - carried load $\le K$ at all times.
- Objective: minimize path weight $W(P)=\sum d(p_i,p_{i+1})$, Euclidean (or collision-free distance — formulation is metric-agnostic, costs come from a planner).

**Say:** "Capacity makes this genuinely multi-trip — the robot returns to a basket, picks more, comes back. That's the modeling challenge."

---

## 2. Graph abstraction + the closed-tour trick (1 min)

- Vertices $\mathcal V = \{\mathbf s\}\cup\mathcal F\cup\mathcal B$, complete graph, $c_{uv}=d(u,v)$.
- **Trick:** add a copy $\mathbf s'$ of the start → $\tilde{\mathcal V}$. Zero-cost $\mathbf s\!\to\!\mathbf s'$ and $\mathbf s'\!\to\!\mathbf s$ edges; $\mathbf s'$ inherits $\mathbf s$'s distances.
- **Why:** lets us model an open walk start→...→end as a **closed tour** on $\tilde{\mathcal V}$, which makes flow conservation clean. (In code: `s_idx=0`, `s_end=1`, fruits `2..`, baskets after; `_cost_ext` does exactly this cost remapping, `solve.py:50`.)

---

## 3. Variables (1 min)

- $y_{ij}\in\{0,1\}$ — robot traverses edge $(i,j)$. **Integer.**
- $z_{ij}^{(k)}\ge 0$ — **one commodity per basket $k$**: how much load *destined for basket $k$* flows on edge $(i,j)$. **Continuous.**
- Edge load $x_{ij}=\sum_k z_{ij}^{(k)}$.

**Say:** "The key design decision: split load by destination basket into separate commodities. That one move buys us correct assignment *and* precedence."

---

## 4. Constraints — walk through in this order (4–5 min, the core)

### (a) Visiting — degree, only on fruits  [`eq:ip_out_degree`, `eq:ip_in_degree`]
$\sum_j y_{ij}=1,\ \sum_j y_{ji}=1$ **for fruits only.**

**Emphasize:** degree-1 is imposed on **fruits only**, not baskets. Baskets get no degree constraint → can be entered/left multiple times.

### (b) Balance everywhere — Eulerian, not Hamiltonian  [`eq:ip_balance`]
$\sum_j y_{ij}=\sum_j y_{ji}\ \forall i$.

**Say:** "This is an *Eulerian* balance, not a Hamiltonian tour. Combined with degree-1 on fruits and the connectivity flow, the $y$-graph is a closed walk that visits each fruit once and baskets as needed. This is what makes multi-trip routes representable."

### (c) Multi-commodity flow — assignment + precedence  [`eq:ip_commodity_pickup/pass/delivery/basket_pass/depot`]
For commodity $k$:
- at fruit $i$ with $t_i=k$: net inflow $=-w_i$ → it's a **source** emitting $w_i$  (`pickup`)
- at fruit $i$ with $t_i\ne k$: net $=0$ (pass through)  (`pass`)
- at basket $b_k$: net inflow $=\sum_{t_i=k}w_i = w_k^{\text{tot}}$ → the **unique sink** (`delivery`)
- at basket $b_l$, $l\ne k$: net $=0$  (`basket_pass`) ← *the one we just added; without it commodity could teleport between baskets*
- at $\mathbf s,\mathbf s'$: net $=0$  (`depot`)

**What to say (honest version — do NOT claim precedence is enforced):**
> "The commodity flow gives each fruit's weight a destination basket and bounds the load on each *arc*. Important caveat: these are **static arc flows**, decoupled from the *order* the robot traverses arcs. So they bound the per-edge load but do **not** by themselves force fruit-before-basket. This makes the IP a **relaxation** — see the correctness slide."

⚠️ **Do not** say "precedence is free / implicit." That argument is false: a basket can sit on an arc the robot crosses *before* its fruits are picked, and the static flow still 'delivers' across it. Counterexample `test4`: the model visits basket `b0` before fruits `f0,f1`. This is why the per-edge capacity ≠ physically carried load once a basket is revisited (multi-trip).

### (d) Capacity — couples flow to routing  [`eq:ip_capacity`]
$\sum_k z_{ij}^{(k)} \le K\,y_{ij}$.

**Two jobs in one constraint:** (i) total load on any edge $\le K$; (ii) **forcing**: if no load $\Rightarrow$ fine, but any positive flow forces $y_{ij}=1$ (you pay the travel cost), and $y_{ij}=0 \Rightarrow$ zero flow. This is the linking constraint.

---

## 5. Subtour elimination — single-commodity connectivity flow (2 min)  [`eq:w_source … eq:w_link`]

Problem: degree + balance alone allow **disconnected subtours** not containing the depot.

Fix: a **separate single-commodity flow** $w_{ij}\in[0,|\tilde{\mathcal V}|]$:
- $\mathbf s$ emits $n$ units; each **fruit consumes exactly 1**; baskets are conservative; $\mathbf s'$ absorbs $n$.
- Linked to routing: $w_{ij}\le |\tilde{\mathcal V}|\,y_{ij}$.

**Say:** "This is a Gavish–Graves-style single-commodity flow SEC. Since every fruit must receive one unit and units originate only at $\mathbf s$, every fruit is reachable from the depot through used edges → no depot-free subtour can survive. Polynomial number of constraints, unlike exponential DFJ cuts — so we just hand the whole model to the solver, no lazy callbacks needed."

Contrast if asked: DFJ subtour cuts are exponential and need separation; this is compact ($O(|E|)$ extra vars/constraints) at the cost of a weaker LP relaxation.

---

## 6. Correctness — it's a RELAXATION, not exact (60 sec, say this clearly)

Point at Prop. *Relaxation and Lower Bound*. Honest statement:
- **Lower bound (always holds):** every real picking plan maps to a feasible $(y,z,w)$ of equal cost ⇒ the IP optimum $z^\star \le W(\mathrm P^\star)$ is a valid lower bound.
- **Exact only without basket revisits:** when no basket/depot node is traversed more than once, arc-flow = carried load and the Euler traversal is unique ⇒ feasible optimal plan.
- **Multi-trip breaks it:** arc flows are static (no traversal order), so a feasible $(y,z,w)$ can correspond to a $y$-graph with **no** capacity/precedence-feasible traversal. The recovered route is a *candidate* that must be **validated** (`src/validate.py`).

**Root cause:** this is the CVRP two-commodity flow device (Baldacci et al. 2004), whose exactness relies on each **customer** visited exactly once. We relaxed the degree constraint on baskets to allow multi-trip — that's exactly what we gave up. (CVRP still revisits its single depot $M$ times, one per vehicle; revisits there are benign because load resets at the depot. Revisiting an intermediate *basket* is not.)

**Evidence:** `test4` (the chosen arc set has a *unique* Euler traversal — the invalid one, basket before its fruits); `large_25f_4b` (peak carried load 12.2 vs K=6). So the reported `cost`/`bounds` are lower bounds, not achievable route costs.

---

## 7. Solving + scaling (1–2 min)

- It's a MILP → branch-and-cut in Gurobi (`solve.py:solve_ip`), `MIPGap 1e-6`, time limit.
- Binaries: $y$ on $O(N^2)$ edges, $N=2+n+m$. Continuous: $z$ is $O(m\,N^2)$, plus $w$ on $O(N^2)$.
- Route is recovered by extracting the Eulerian circuit from $y$ and trimming (`_extract_route`, `_trim_route`).
- **Results (measured just now):** all 6 small instances solve to **proven optimum, gap 0%, in < 0.05 s** each (single B&B node — root cuts close it). Largest small model: 56 binaries / 168 continuous / 152 rows. For $n=20$–$30$, $m=3$–$4$ run with a time limit and report the solver's optimality gap. *(Run `tests/test_large.py` for those numbers.)*

### Concrete examples (these happen to recover valid routes — show as *successes of the lower bound*, not proof of exactness)

- **Forced multi-trip, one basket** (`test3`, K=4, weights [3,3,1]):
  route `s → f0 → f2 → b0 → f1 → b0 → s`, cost **12.0**, **validated feasible** (peak load 4 = K).
  → robot batches f0+f2 (=4=K), drops at b0, returns for f1. Basket b0 visited twice. Here the relaxation's route *is* schedulable.
- **Two baskets, interleaved multi-trips** (`test5`, K=5): cost **33.62**, validated feasible.
- **Capacity one-at-a-time** (`test6`, K=3): `s → f0 → b0 → f1 → b0 → s`, cost **8.0**, validated feasible.

⚠️ **But the relaxation can also return infeasible routes** — `large_25f_4b` (peak load 12.2 > K=6) and even tiny `test4` (basket-before-fruit). Always run the validator; report the bound separately from feasibility. Do **not** claim "global optimum at gap 0" — gap-0 means optimal *for the relaxation*, i.e. a tight lower bound, not a proven-optimal feasible route.

---

## 8. Limitations / future (45 sec)

- **Soundness (lead with this):** the IP is a relaxation — exact only when baskets aren't revisited. Multi-trip routes need load tied to *traversal order*. Fix: MTZ-style position+load variables with explicit precedence, or per-visit basket copies / a time-expanded graph. This is the main item of future work, and motivates the **state-space / DP search** (hinted in the draft) as the feasibility-correct method.
- Compact SEC ⇒ weaker LP bound; large $n$ will stress branch-and-cut.
- Single robot, static scene, known weights (Assumptions 1–3).
- Multi-commodity $z$ grows with #baskets; could aggregate or use a layered/time-indexed alternative.

---

## Anticipated questions (skim before you go in)

- **"Why not a standard arc-based VRP / DFJ?"** — Multi-trip + paired precedence. DFJ needs exponential cuts; our compact single-commodity flow avoids separation. Multi-commodity handles assignment+precedence without big-M ordering vars.
- **"Why allow baskets unlimited visits — doesn't that blow up the model?"** — No degree constraint on baskets, only balance. It's what *enables* multi-trip; cost is just more $y$ edges, already in the complete graph.
- **"How is precedence enforced? I don't see ordering variables."** — Be honest: it **isn't**. The static arc flow doesn't constrain traversal order, so the model can place a basket before its fruits. That's the relaxation gap; we validate routes a posteriori and treat the IP value as a lower bound. *(Do not give the old "source/sink makes it infeasible" answer — it's wrong.)*
- **"So is your reported cost the optimal route length?"** — It's a **lower bound** on it. Equal to the optimum when the recovered route validates (no basket revisit). Otherwise the true optimum is ≥ our bound.
- **"Capacity is per-edge — does that bound the per-pick load?"** — Only when the arc flow equals carried load, i.e. single-visit. With revisits the per-edge flow can understate the physically carried load (that's the bug — `large_25f_4b`).
- **"Is the LP relaxation tight?"** — Compact SEC is loose; we rely on solver cuts. Separately, even the *integer* model is a relaxation of the routing problem (above).
- **"What's $\mathbf s'$ for?"** — Closes the open start-to-end walk into a tour; zero-cost link, inherits $\mathbf s$ distances.
- **"Continuous $z$ but integer-ish weights — any issue?"** — Weights are real; $z$ is genuinely continuous load, fine.

---

## 30-second elevator version (memorize as fallback)

"One robot, pick-and-deliver with capacity. Complete graph, start-copy to close the tour. Binary
edge vars for the route; one continuous commodity per basket for the load. Degree-1 on fruits,
Eulerian balance everywhere so baskets can be revisited for multi-trips. Each fruit sources its
basket's commodity, the basket absorbs it; per-arc capacity bounds load. A single-commodity n-unit
flow from start kills depot-free subtours compactly. Key caveat: the flows are static, so this is a
**relaxation** — it gives a tight lower bound, exact when baskets aren't revisited, but multi-trip
routes must be validated (and the proper fix ties load to traversal order). Hand it to Gurobi for
the bound in seconds."
