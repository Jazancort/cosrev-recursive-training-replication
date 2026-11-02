#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sim/s4a.py — Numerical check of Results 1-2 (Gerstgrasser et al. 2024) and
             Result 5 (Xu et al., preprint).

Results 1-2: ordinary least squares under replacement, accumulation, and
             accumulate-subsample (fixed training budget).
Result 5:   recursive Gaussian mean estimation with growing synthetic samples.

Outputs (written to sim/):
  s4a_results.json  — all numbers referenced in Supplementary S4
  figS4_1.pdf       — two-panel figure for S4
  figS4_1.png       — same at 300 dpi (for review)

Run from the repository root:
  uv run python sim/s4a.py

Reference: COSREV-D-26-01510, gate-v3 branch.
"""
import json
import pathlib
import time

import matplotlib.pyplot as plt
import numpy as np
from scipy.special import zeta

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 20261029
rng = np.random.default_rng(SEED)
t_start = time.time()

OUTDIR = pathlib.Path(__file__).parent

# ── Helpers ────────────────────────────────────────────────────────────────────
def ols(X, y):
    """Ordinary least squares via QR-based lstsq."""
    return np.linalg.lstsq(X, y, rcond=None)[0]


# ── A: linear regression, replacement / accumulation / accumulate-subsample ────
d     = 10     # dimension
N     = 50     # samples per generation
sigma = 1.0    # noise std
G     = 20     # generations
R     = 300    # replicates

theta_star = rng.standard_normal(d) / np.sqrt(d)
E0 = sigma**2 * d / (N - d - 1)

REGIMES = ("replace", "accumulate", "accsub")
err = {k: np.empty((R, G + 1)) for k in REGIMES}

for r in range(R):
    # Generation 0: fit on real data
    X0 = rng.standard_normal((N, d))
    y0 = X0 @ theta_star + sigma * rng.standard_normal(N)
    th = {k: ols(X0, y0) for k in REGIMES}

    # Running accumulate sufficient statistics
    XtX = X0.T @ X0
    Xty = X0.T @ y0

    # Running pool for accsub
    poolX = [X0.copy()]
    pooly = [y0.copy()]

    for k in REGIMES:
        err[k][r, 0] = float(np.sum((th[k] - theta_star) ** 2))

    for g in range(1, G + 1):
        # Draw fresh inputs; labels from the previous model of the same regime
        new_data = {}
        for k in REGIMES:
            X = rng.standard_normal((N, d))
            y = X @ th[k] + sigma * rng.standard_normal(N)
            new_data[k] = (X, y)

        # Replace: fit only on new batch
        th["replace"] = ols(*new_data["replace"])

        # Accumulate: fit on all retained data (sufficient-statistic update)
        Xn, yn = new_data["accumulate"]
        XtX += Xn.T @ Xn
        Xty += Xn.T @ yn
        th["accumulate"] = np.linalg.solve(XtX, Xty)

        # Accumulate-subsample: random subset of size 2N from the growing pool
        poolX.append(new_data["accsub"][0])
        pooly.append(new_data["accsub"][1])
        AX = np.vstack(poolX)
        Ay = np.concatenate(pooly)
        idx = rng.choice(len(Ay), size=min(2 * N, len(Ay)), replace=False)
        th["accsub"] = ols(AX[idx], Ay[idx])

        for k in REGIMES:
            err[k][r, g] = float(np.sum((th[k] - theta_star) ** 2))

gs = np.arange(G + 1)
H2 = np.cumsum(1.0 / np.arange(1, G + 2) ** 2)   # partial sums of 1/i^2

# Mean and 95% CI, normalised by E0
A = {
    k: (err[k].mean(0) / E0,
        1.96 * err[k].std(0, ddof=1) / np.sqrt(R) / E0)
    for k in REGIMES
}

pi2_6 = np.pi ** 2 / 6
accsub_exceeds = int(np.argmax(A["accsub"][0] > pi2_6))   # first g where accsub > pi²/6

# ── B: Gaussian mean estimation with growing synthetic samples ──────────────────
n  = 20      # initial real-data sample size
T  = 200     # iterations
RB = 20_000  # replicates

k_vals = np.arange(1, T, dtype=float)       # k = 1 … T-1
schedules = {
    "constant":    np.ones(T - 1),
    "linear":      k_vals,
    "superlinear": k_vals ** 1.5,
}

B = {}
for name, c in schedules.items():
    nt = np.ceil(c * n).astype(int)          # sample sizes at each iteration
    # Starting estimate: N(0, 1/n)
    th1 = rng.standard_normal(RB) / np.sqrt(n)
    # Each step: mean of nt[t] samples from N(th_{t-1}, 1)
    increments = rng.standard_normal((RB, T - 1)) / np.sqrt(nt)
    # path[:, t] = estimate after step t; path[:, 0] = real-data estimate
    path = np.empty((RB, T))
    path[:, 0] = th1
    path[:, 1:] = th1[:, np.newaxis] + np.cumsum(increments, axis=1)

    # Expected squared error (normalised by n): n * E[(th_t - 0)^2]
    nE_sim   = n * (path ** 2).mean(0)
    nE_exact = np.concatenate([[0.0], np.cumsum(n / nt)]) + 1.0   # 1 + sum n/n_t

    # Probability of improvement: P(|th_T| < |th_1|)
    P = (np.abs(path) < np.abs(th1)[:, np.newaxis]).mean(0)
    P_ci = 1.96 * np.sqrt(P * (1 - P) / RB)

    B[name] = {
        "nt_seq": nt[:5].tolist(),       # first 5 values for reference
        "nE_sim":   nE_sim,
        "nE_exact": nE_exact,
        "P":        P,
        "P_ci":     P_ci,
    }

# Exact P(2) = 1/2 - arcsin(1/sqrt(5)) / pi
P2_exact = 0.5 - np.arcsin(5.0 ** -0.5) / np.pi

# ── Figure (Okabe-Ito palette, print-safe markers) ─────────────────────────────
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

fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(11, 4.2))

# Panel (a): linear regression
style_a = {
    "replace":    ("#D55E00", "o", "Replace"),
    "accumulate": ("#0072B2", "s", "Accumulate"),
    "accsub":     ("#CC79A7", "^", r"Accumulate-subsample ($2N$)"),
}
for k, (col, mk, lab) in style_a.items():
    m, ci = A[k]
    ax_a.plot(gs, m, color=col, marker=mk, ms=3, lw=1.5, label=lab)
    ax_a.fill_between(gs, m - ci, m + ci, color=col, alpha=0.20, lw=0)

ax_a.plot(gs, gs + 1, "k--", lw=1.0, label=r"$g+1$ (Result 1)")
ax_a.plot(gs, H2,     "k:",  lw=1.2, label=r"$\sum_{i\leq g+1}i^{-2}$ (Result 2)")
ax_a.axhline(pi2_6, color="grey", lw=0.8)
ax_a.set_xlabel("Generation $g$")
ax_a.set_ylabel("$E_g / E_0$")
ax_a.set_title("(a) Linear regression (OLS)")
ax_a.legend(fontsize=8, frameon=False)

# Panel (b): Gaussian mean, log-log
Ts = np.arange(1, T + 1)
colors_b = {"constant": "#D55E00", "linear": "#009E73", "superlinear": "#0072B2"}
labels_b = {
    "constant":    r"$c_k=1$ (constant)",
    "linear":      r"$c_k=k$ (linear)",
    "superlinear": r"$c_k=k^{1.5}$ (superlinear)",
}
for name, col in colors_b.items():
    ax_b.loglog(Ts, B[name]["nE_sim"],   color=col, lw=1.5, label=labels_b[name])
    ax_b.loglog(Ts, B[name]["nE_exact"], "k--", lw=0.7)

ax_b.axhline(1.0 + float(zeta(1.5)), color="grey", lw=0.8, ls=":",
             label=r"$1+\zeta(1.5)$")
ax_b.set_xlabel("Iteration $T$")
ax_b.set_ylabel(r"$n\,\mathbb{E}(\hat\theta_T - \theta^\ast)^2$")
ax_b.set_title("(b) Gaussian mean, growing synthetic sample")
ax_b.legend(fontsize=8, frameon=False)

fig.tight_layout()
fig.savefig(OUTDIR / "figS4_1.pdf", bbox_inches="tight")
fig.savefig(OUTDIR / "figS4_1.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# ── JSON output ────────────────────────────────────────────────────────────────
def pick(arr, indices):
    return [round(float(arr[i]), 4) for i in indices]

idx_A = [1, 5, 20]
idx_P = [1, 4, 19, 199]

out = {
    "seed": SEED,
    "runtime_s": round(time.time() - t_start, 1),
    "A": {
        "d": d, "N": N, "R": R,
        "E0": round(float(E0), 4),
        "generations_checked": idx_A,
        "H2_at_checked": pick(H2, idx_A),
        "replace":    {"mean": pick(A["replace"][0],    idx_A),
                       "ci95": pick(A["replace"][1],    idx_A)},
        "accumulate": {"mean": pick(A["accumulate"][0], idx_A),
                       "ci95": pick(A["accumulate"][1], idx_A)},
        "accsub":     {"mean": pick(A["accsub"][0],     idx_A),
                       "ci95": pick(A["accsub"][1],     idx_A)},
        "accsub_exceeds_pi2_6_at_g": accsub_exceeds,
        "pi2_over_6": round(pi2_6, 4),
    },
    "B": {
        "n": n, "T": T, "R": RB,
        "P2_exact": round(float(P2_exact), 4),
        "iterations_checked": [t - 1 for t in [2, 5, 20, 200]],
        **{
            nm: {
                "nE_sim":   pick(B[nm]["nE_sim"],   [1, 9, 49, 199]),
                "nE_exact": pick(B[nm]["nE_exact"], [1, 9, 49, 199]),
                "P":        pick(B[nm]["P"],        [1, 4, 19, 199]),
                "P_ci":     pick(B[nm]["P_ci"],     [1, 4, 19, 199]),
            }
            for nm in schedules
        },
    },
}

out_path = OUTDIR / "s4a_results.json"
out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
print(f"\nRuntime: {out['runtime_s']} s")
print(f"Figures: {OUTDIR}/figS4_1.pdf + figS4_1.png")
print(f"Results: {out_path}")
