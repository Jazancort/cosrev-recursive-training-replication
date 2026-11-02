#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim/s4b.py — Numerical check of Result 4 (discrete distribution, Shumailov / Suresh),
             Result 6 (temperature-filtered accumulation, Marchi et al.) and
             Results 1-2 under a fixed input design (Gerstgrasser et al.).

Outputs (written to sim/):
  s4b_results.json  — all numbers referenced in Supplementary S4, sections S4.3-S4.5
  figS4_2.pdf       — three-panel figure
  figS4_2.png       — same at 300 dpi

Run from the repository root:
  uv run python sim/s4b.py

Reference: COSREV-D-26-01510, gate-v3 branch.
"""
import json
import pathlib
import time

import matplotlib.pyplot as plt
import numpy as np

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 20261029
rng = np.random.default_rng(SEED)
t0 = time.time()

OUTDIR = pathlib.Path(__file__).parent


# ── Helpers ────────────────────────────────────────────────────────────────────
def tv(a, b):
    """Total-variation distance (works along last axis)."""
    return 0.5 * np.abs(a - b).sum(-1)


def norm_entropy(q, K):
    """Normalised Shannon entropy H(q) / log(K)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        h = -np.nansum(np.where(q > 0, q * np.log(q), 0.0), -1)
    return h / np.log(K)


# ══════════════════════════════════════════════════════════════════════════════
# C: Discrete distribution with fixed sample size (Result 4, Suresh et al.)
# ══════════════════════════════════════════════════════════════════════════════
K    = 50       # number of outputs
N    = 500      # samples per generation
G    = 100      # generations
R    = 300      # replicates

# Reference distribution: power-law p_k ~ k^{-1.2}
p = np.arange(1, K + 1, dtype=float) ** -1.2
p /= p.sum()

# Initial samples
c0 = rng.multinomial(N, p, size=R)               # shape (R, K)
q_rep    = c0.astype(float) / N                  # replace: empirical distribution
pool_acc = c0.astype(float)                       # accumulate: raw counts

# Statistics per generation
sup_rep, sup_acc = [], []
tv_rep,  tv_acc  = [], []

# Survival analysis: generation at which each output is first lost (replace only)
lost = np.full((R, K), -1, dtype=int)
never_obs = c0 == 0
lost[never_obs] = -2      # never observed at g=0; excluded from survival

def _record(g):
    sup_rep.append((q_rep > 0).sum(1))                              # shape (R,)
    sup_acc.append((pool_acc > 0).sum(1))
    tv_rep.append(tv(q_rep, p))
    tv_acc.append(tv(pool_acc / pool_acc.sum(1, keepdims=True), p))

_record(0)

for g in range(1, G + 1):
    # Replace: draw N samples from the current empirical distribution
    q_rep = rng.multinomial(N, q_rep) / N

    # Accumulate: draw N samples from the current normalised pool
    q_pool = pool_acc / pool_acc.sum(1, keepdims=True)
    pool_acc += rng.multinomial(N, q_pool)

    # Record which outputs just disappeared (replace only)
    newly_lost = (q_rep == 0) & (lost == -1) & ~never_obs
    lost[newly_lost] = g

    _record(g)

sup_rep = np.array(sup_rep)   # shape (G+1, R)
sup_acc = np.array(sup_acc)
tv_rep  = np.array(tv_rep)
tv_acc  = np.array(tv_acc)

# Survival analysis: expected count m_k = N * p_k
m = N * p
# Treat still-surviving outputs as censored at generation G
loss_gen = np.where(lost == -1, G, lost).astype(float)
loss_gen[lost == -2] = np.nan    # exclude unobserved

cens_frac = np.array([
    float((lost[:, k] == -1).sum()) / float((lost[:, k] != -2).sum())
    for k in range(K)
])

# Per-output mean survival time (over replicates where it was observed)
mean_loss = np.array([
    float(np.nanmean(loss_gen[:, k]))
    for k in range(K)
])

# Keep outputs with low censoring (<20%) for correlation
keep = cens_frac < 0.20
r_corr = float(np.corrcoef(m[keep], mean_loss[keep])[0, 1])
coeffs = np.polyfit(m[keep], mean_loss[keep], 1)
slope, intercept = float(coeffs[0]), float(coeffs[1])

# Fraction of (output, replicate) pairs where loss_gen >= m_k
mask_valid = (lost != -1) & (lost != -2)   # uncensored, observed
frac_ge = float(
    (loss_gen[mask_valid] >= np.broadcast_to(m, loss_gen.shape)[mask_valid]).mean()
)


# ══════════════════════════════════════════════════════════════════════════════
# D: Temperature-filtered accumulation in the exact-tracking limit (Result 6)
# ══════════════════════════════════════════════════════════════════════════════
K2  = 20       # outputs
n0  = 200      # initial samples
b   = 10       # batch size per step
S   = 2000     # steps (total synthetic samples = S * b = 20 000)
R2  = 200      # replicates

p2 = np.arange(1, K2 + 1, dtype=float) ** -1.1
p2 /= p2.sum()

D = {}
SNAP_STEPS = {0, 100, 500, 1000, 2000}

for Ts in (0.8, 1.0, 1.25):
    cnt = rng.multinomial(n0, p2, size=R2).astype(float)   # shape (R2, K2)
    q0  = cnt / cnt.sum(1, keepdims=True)

    curve_H = []      # entropy at each step (shape: step, R2)
    snap    = {}
    q1000   = None

    for s in range(S + 1):
        q = cnt / cnt.sum(1, keepdims=True)
        H = norm_entropy(q, K2)
        if s % 20 == 0:
            curve_H.append(H.copy())
        if s in SNAP_STEPS:
            snap[s] = {
                "H_mean":       float(H.mean()),
                "TV_to_q0":     float(tv(q, q0).mean()),
                "top_share":    float(q.max(1).mean()),
                "support":      float((q > 0).sum(1).mean()),
            }
            if s == 1000:
                q1000 = q.copy()

        if s < S:
            # Temperature-scaled sampling: draw b samples from q^{1/T_s}
            w = q ** (1.0 / Ts)
            w /= w.sum(1, keepdims=True)
            cnt += rng.multinomial(b, w)

    tv_1000_2000 = float(tv(q, q1000).mean())

    D[Ts] = {
        "curve_H": np.array(curve_H),   # shape (100, R2) — every 20 steps
        "snap":    snap,
        "TV_1000_2000": tv_1000_2000,
    }


# ══════════════════════════════════════════════════════════════════════════════
# E: Fixed-design OLS (Results 1-2, Gerstgrasser et al.)
# ══════════════════════════════════════════════════════════════════════════════
d    = 10
N3   = 50
sig  = 1.0
G3   = 20
R3   = 300

theta_star = rng.standard_normal(d) / np.sqrt(d)
E0 = sig ** 2 * d / (N3 - d - 1)

err_rep = np.empty((R3, G3 + 1))
err_acc = np.empty((R3, G3 + 1))

for r in range(R3):
    # One fixed input matrix per replicate (same at every generation)
    X  = rng.standard_normal((N3, d))
    Xp = np.linalg.pinv(X)     # Moore-Penrose pseudoinverse

    y0 = X @ theta_star + sig * rng.standard_normal(N3)

    # OLS estimates
    th_rep = Xp @ y0
    th_acc = th_rep.copy()
    y_sum  = y0.copy()

    err_rep[r, 0] = float(np.sum((th_rep - theta_star) ** 2))
    err_acc[r, 0] = float(np.sum((th_acc - theta_star) ** 2))

    for g in range(1, G3 + 1):
        # Replace: labels from the previous replace estimate
        y_r  = X @ th_rep + sig * rng.standard_normal(N3)
        th_rep = Xp @ y_r
        err_rep[r, g] = float(np.sum((th_rep - theta_star) ** 2))

        # Accumulate: OLS on [X; ...; X] with g+1 copies of the same X
        # Equivalent to mean of label vectors (since Xp @ X^T is the projector)
        y_a = X @ th_acc + sig * rng.standard_normal(N3)
        y_sum = y_sum + y_a
        th_acc = Xp @ (y_sum / (g + 1))
        err_acc[r, g] = float(np.sum((th_acc - theta_star) ** 2))

H2   = np.cumsum(1.0 / np.arange(1, G3 + 2) ** 2)

def mean_ci(err):
    m  = err.mean(0) / E0
    ci = 1.96 * err.std(0, ddof=1) / np.sqrt(err.shape[0]) / E0
    return m, ci

mR, cR = mean_ci(err_rep)
mA, cA = mean_ci(err_acc)


# ══════════════════════════════════════════════════════════════════════════════
# Figure (Okabe-Ito palette)
# ══════════════════════════════════════════════════════════════════════════════
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
    "savefig.dpi": 300,
})

OI = {"orange": "#D55E00", "blue": "#0072B2", "green": "#009E73",
      "yellow": "#E69F00", "sky": "#56B4E9"}

fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))

# ── Panel (a): discrete distribution support ──────────────────────────────────
gg = np.arange(G + 1)
for nm, arr, col, mk in (
        ("Replace",    sup_rep, OI["orange"], "o"),
        ("Accumulate", sup_acc, OI["blue"],   "s")):
    lo, hi = np.percentile(arr, [10, 90], axis=1)
    axes[0].plot(gg, arr.mean(1), color=col, marker=mk, markevery=10, ms=4, label=nm)
    axes[0].fill_between(gg, lo, hi, color=col, alpha=0.2, lw=0)

axes[0].set_xlabel("Generation $g$")
axes[0].set_ylabel("Support size")
axes[0].set_title(f"(a) Discrete distribution ($K={K}$, $N={N}$)")
axes[0].legend(fontsize=9, frameon=False)

# ── Panel (b): temperature-filtered accumulation ──────────────────────────────
xs_raw  = np.arange(S + 1) * b          # sample count at each step
xs_log  = xs_raw[::20][1:]              # every-20th step, skip step 0

colors_d = {0.8: OI["orange"], 1.0: OI["green"], 1.25: OI["blue"]}
for Ts, col in colors_d.items():
    cv = D[Ts]["curve_H"][1:]            # skip step 0 (identical for all)
    lo, hi = np.percentile(cv, [10, 90], axis=1)
    axes[1].semilogx(xs_log, cv.mean(1), color=col,
                     label=f"$T_s = {Ts}$", lw=1.5)
    axes[1].fill_between(xs_log, lo, hi, color=col, alpha=0.2, lw=0)

axes[1].axhline(1.0, color="k", ls="--", lw=0.8, label="Uniform")
axes[1].axhline(float(norm_entropy(p2, K2)), color="grey", ls=":", lw=0.8, label="$H(p)$")
axes[1].set_xlabel("Samples added (log scale)")
axes[1].set_ylabel("$H(q) / \\log K$")
axes[1].set_title("(b) Temperature-filtered accumulation")
axes[1].legend(fontsize=9, frameon=False)

# ── Panel (c): fixed-design OLS ───────────────────────────────────────────────
g3 = np.arange(G3 + 1)
for mm, cc, col, mk, lab in (
        (mR, cR, OI["orange"], "o", "Replace"),
        (mA, cA, OI["blue"],   "s", "Accumulate")):
    axes[2].plot(g3, mm, color=col, marker=mk, ms=3, lw=1.5, label=lab)
    axes[2].fill_between(g3, mm - cc, mm + cc, color=col, alpha=0.20, lw=0)

axes[2].plot(g3, g3 + 1, "k--", lw=1.0, label="$g+1$")
axes[2].plot(g3, H2,     "k:",  lw=1.2, label=r"$\sum_{i \leq g+1} i^{-2}$")
axes[2].set_xlabel("Generation $g$")
axes[2].set_ylabel("$E_g / E_0$")
axes[2].set_title("(c) Fixed-design regression (OLS)")
axes[2].legend(fontsize=9, frameon=False)

fig.tight_layout()
fig.savefig(OUTDIR / "figS4_2.pdf", bbox_inches="tight")
fig.savefig(OUTDIR / "figS4_2.png", dpi=300, bbox_inches="tight")
plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# JSON output
# ══════════════════════════════════════════════════════════════════════════════
def pick(arr, indices):
    return [round(float(arr[i]), 4) for i in indices]


loss_table = {}
for k_idx in (9, 19, 29, 39, 49):
    k_label = k_idx + 1
    loss_table[str(k_label)] = {
        "m_k":       round(float(m[k_idx]), 2),
        "mean_loss": round(float(mean_loss[k_idx]), 2),
        "censored":  round(float(cens_frac[k_idx]), 3),
    }

out = {
    "seed":       SEED,
    "runtime_s":  round(time.time() - t0, 1),
    "C": {
        "K": K, "N": N, "G": G, "R": R,
        "support_replace":    pick(sup_rep.mean(1),  [0, 10, 50, 100]),
        "support_accumulate": pick(sup_acc.mean(1),  [0, 10, 50, 100]),
        "tv_replace":         pick(tv_rep.mean(1),   [0, 10, 50, 100]),
        "tv_accumulate":      pick(tv_acc.mean(1),   [0, 10, 50, 100]),
        "loss_table":         loss_table,
        "corr_loss_vs_m":     round(r_corr, 3),
        "slope":              round(slope, 3),
        "intercept":          round(intercept, 2),
        "frac_loss_ge_m":     round(frac_ge, 3),
    },
    "D": {
        "K": K2, "n0": n0, "b": b, "steps": S, "R": R2,
        **{
            str(Ts): {
                "snap":         D[Ts]["snap"],
                "TV_1000_2000": round(D[Ts]["TV_1000_2000"], 4),
            }
            for Ts in D
        },
    },
    "E": {
        "d": d, "N": N3, "G": G3, "R": R3,
        "E0":  round(float(E0), 4),
        "H2_at_g": {
            "g1":  round(float(H2[1]),  4),
            "g5":  round(float(H2[5]),  4),
            "g20": round(float(H2[20]), 4),
        },
        "replace":    {"mean": pick(mR, [1, 5, 20]), "ci95": pick(cR, [1, 5, 20])},
        "accumulate": {"mean": pick(mA, [1, 5, 20]), "ci95": pick(cA, [1, 5, 20])},
    },
}

out_path = OUTDIR / "s4b_results.json"
out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
print(f"\nRuntime: {out['runtime_s']} s")
print(f"Figures: {OUTDIR}/figS4_2.pdf + figS4_2.png")
print(f"Results: {out_path}")
