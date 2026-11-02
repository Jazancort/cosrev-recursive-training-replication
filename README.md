# Supplementary materials for: *Recursive Training on Model-Generated Data*

Supplementary code, data and pre-compiled PDFs for the paper:

> Azancort Neto, J.L.; Ferreira de Carvalho, A.C.P.L.; Francês, C.R.L. (2026).
> **Recursive Training on Model-Generated Data: A Critical Integrative Review of
> Failure Regimes, Adversarial Interactions and Governance.**
> *Computer Science Review*. COSREV-D-26-01510.

## What this repository contains

| Item | File / folder | Description |
|---|---|---|
| **S1** | `supplementary/S1_cited_sources.csv` | 101 cited sources with category, entry route, archival status and replication status |
| **S1** | `supplementary/S1_cited_sources.pdf` | Formatted version of S1 |
| **S2** | `supplementary/S2_search_protocol.pdf` | Search protocol: strings, per-source counts, record flow |
| **S3** | `supplementary/S3_theorem_cards.pdf` | Theorem cards for the six formal results (model, regime, assumptions, main result, does-not-imply) |
| **S4** | `supplementary/S4_numerical_checks.pdf` | Numerical check of Results 1, 2, 4, 5 and 6 in their own models |
| **Simulation scripts** | `sim/s4a.py`, `sim/s4b.py` | Python scripts that reproduce the S4 numerical checks |
| **Simulation outputs** | `sim/s4a_results.json`, `sim/s4b_results.json` | Raw results (seed 20261029) |
| **Search log** | `search_log.json` | Per-source counts, deduplication counts, screening and validation metrics |
| **Verification scripts** | `scripts/` | Python scripts for verifying manuscript consistency |

## Supplementary Contents

### S1 — Cited sources

`S1_cited_sources.csv` lists all 101 cited sources with seven columns:

| Column | Values | Description |
|---|---|---|
| `key` | BibTeX key | Unique identifier |
| `category` | E / P / C / L | Evidence / Position / Context / Legal-normative |
| `route` | S / A / CH / R | Structured search / Anchor / Citation chasing / Revision |
| `in_orig` | Y / N | Whether the source was in the original v1 submission |
| `archival` | Y / N | Archival peer-reviewed version available at cutoff date (29 Oct 2026) |
| `replication` | none / partial / independent / n/a | Independent replication status |
| `overlap` | — | Author overlap with other included studies |

### S2 — Search protocol

Full search strings as executed in each of the five sources (Scopus, IEEE Xplore, OpenAlex, arXiv, OpenReview), date filters, per-source record counts, duplicate-removal procedure and record flow from retrieval to inclusion.

### S3 — Theorem cards

For each of the six formal results (Section 2.1 and Table 2 of the main text): source and version consulted, model class, data regime, loss function, asymptotic variable, collapse criterion, main assumptions, and "does not imply" caveat.

### S4 — Numerical checks

Reproduces formal results in their own models:
- Results 1–2 and 5 (linear regression and Gaussian mean estimation, fresh inputs) — `sim/s4a.py`
- Results 1–2 (fixed design), 4 (discrete distribution) and 6 (temperature-filtered accumulation) — `sim/s4b.py`

All numbers match the tables in the main text. Run time: 4.8 s + 3.6 s on a single CPU core.

## Reproducing the numerical checks

Requirements: Python 3.10–3.12 and `uv` ([installation guide](https://docs.astral.sh/uv/getting-started/installation/)).

```bash
git clone https://github.com/Jazancort/cosrev-recursive-training-replication.git
cd cosrev-recursive-training-replication
uv sync
```

Run S4a (Results 1, 2, 5 — fresh inputs):
```bash
uv run python sim/s4a.py
```

Run S4b (Results 1, 2, 4, 6 — fixed design, discrete, temperature):
```bash
uv run python sim/s4b.py
```

Both scripts write their results to `sim/s4a_results.json` and `sim/s4b_results.json` and reproduce `sim/figS4_1.pdf` and `sim/figS4_2.pdf`.

## Recompiling the supplementary PDFs

The LaTeX sources for S2, S3 and S4 are in `supplementary/src/`. To recompile:

```bash
cd supplementary/src
xelatex wrap_S2.tex && xelatex wrap_S2.tex
xelatex wrap_S3.tex && xelatex wrap_S3.tex
xelatex wrap_S4.tex && bibtex wrap_S4 && xelatex wrap_S4.tex && xelatex wrap_S4.tex
```

The compiled PDFs are already included in `supplementary/`.

## Verification scripts

| Script | Purpose |
|---|---|
| `scripts/verify_modes.py` | Two-mode static check of the main manuscript |
| `scripts/make_counts.py` | Regenerate `counts.tex` from `S1.csv` and `search_log.json` |
| `scripts/match_insearch.py` | Verify which route-R sources were also retrieved in the structured search |
| `scripts/check_dupes_and_breaks.py` | Check for duplicate paragraphs and LaTeX break issues |
| `scripts/reconcile_sources.py` | Reconcile cited sources between v1 and v2 of the manuscript |

## Citation

```bibtex
@article{azancort2026recursive,
  title   = {Recursive Training on Model-Generated Data: A Critical Integrative
             Review of Failure Regimes, Adversarial Interactions and Governance},
  author  = {Azancort Neto, Julio Leite and
             Ferreira de Carvalho, Andr{\'e} Carlos Ponce de Leon and
             Fran\c{c}\^es, Carlos Renato Lisboa},
  journal = {Computer Science Review},
  year    = {2026},
  doi     = {pending}
}
```

## License

Code: MIT.  
Data and supplementary text: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
