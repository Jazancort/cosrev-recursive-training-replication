<div align="center">

# Recursive Training on Model-Generated Data — Supplementary Materials

[![License: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-green.svg)](https://creativecommons.org/licenses/by/4.0/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23887128.svg)](https://doi.org/10.5281/zenodo.23887128)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![GitHub release](https://img.shields.io/github/v/release/Jazancort/cosrev-recursive-training-replication?color=orange)](https://github.com/Jazancort/cosrev-recursive-training-replication/releases)

Supplementary code, data and pre-compiled PDFs for the paper:

**Recursive Training on Model-Generated Data: A Critical Integrative Review of Failure Regimes, Adversarial Interactions and Governance**

Azancort Neto, J.L. · Ferreira de Carvalho, A.C.P.L. · Francês, C.R.L.

*Computer Science Review*, Elsevier, 2026 · COSREV-D-26-01510

</div>

---

## Contents at a glance

| # | File | What it is |
|---|---|---|
| **S1** | `supplementary/S1_cited_sources.csv` | 101 cited sources — category, entry route, archival status, replication status |
| **S1** | `supplementary/S1_cited_sources.pdf` | Formatted table version of S1 |
| **S2** | `supplementary/S2_search_protocol.pdf` | Full search strings, per-source counts and record flow |
| **S3** | `supplementary/S3_theorem_cards.pdf` | Theorem cards for the six formal results |
| **S4** | `supplementary/S4_numerical_checks.pdf` | Numerical checks of formal results in their own models |
| | `sim/s4a.py`, `sim/s4b.py` | Simulation scripts (reproduce S4 figures and tables) |
| | `sim/s4*_results.json` | Raw simulation outputs (seed 20261029) |
| | `search_log.json` | Per-source retrieval counts, deduplication and validation metrics |
| | `scripts/` | Manuscript verification and analysis scripts |

---

## Overview

This review synthesises the literature on what happens when generative models are trained on model-generated data, across four research questions:

- **RQ1** — Under which data-management conditions do formal results predict degradation or stability?
- **RQ2** — What evidence supports each mitigation, and in which settings?
- **RQ3** — How do adversarial threats interact with recursive training?
- **RQ4** — Through which sociotechnical pathways might failures feed back into training data?

We screened 1,633 records from five sources (29 October 2026 cutoff), assessed 664 full texts, and synthesised 61 evidence studies labelled by type (theorem / empirical / extrapolation / conceptual / normative). The review covers six formal results on training-regime dependence, an evidence matrix of five mitigation strategies, a data-integrity security analysis, four sociotechnical pathways, and a 13-instrument governance proposal.

---

## Supplementary details

### S1 — Cited sources (`S1_cited_sources.csv`)

101 rows, 7 columns:

| Column | Values |
|---|---|
| `key` | BibTeX key |
| `category` | `E` evidence · `P` position · `C` context · `L` legal/normative |
| `route` | `S` structured search · `A` anchor · `CH` citation chasing · `R` revision |
| `in_orig` | `Y/N` — in the original v1 submission |
| `archival` | `Y/N` — archival peer-reviewed version at cutoff date |
| `replication` | `none` · `partial` · `independent` · `n/a` |
| `overlap` | Author overlap with other included studies |

### S2 — Search protocol

Complete search strings as executed in each of the five sources (Scopus, IEEE Xplore, OpenAlex, arXiv, OpenReview), date filters, per-source record counts, duplicate-removal procedure, and the full record flow from retrieval to inclusion.

### S3 — Theorem cards

For each of the six formal results (Results 1–6, Table 2 of the main text): source and version consulted, model class, data regime, loss function, asymptotic variable, collapse criterion, main assumptions, and the "does not imply" caveat stated in the review.

### S4 — Numerical checks

Simulation scripts that reproduce each formal result in its own model:

| Script | Results checked | Runtime |
|---|---|---|
| `sim/s4a.py` | 1, 2, 5 (fresh inputs — linear regression + Gaussian mean) | 4.8 s |
| `sim/s4b.py` | 1, 2 (fixed design), 4 (discrete), 6 (temperature-filtered) | 3.6 s |

All runs use seed `20261029` and produce the tables and figures in S4_numerical_checks.pdf.

---

## Quick start

Requirements: Python 3.10–3.12 · [`uv`](https://docs.astral.sh/uv/getting-started/installation/) · POSIX or Windows

```bash
git clone https://github.com/Jazancort/cosrev-recursive-training-replication.git
cd cosrev-recursive-training-replication
uv sync
```

Run the numerical checks:

```bash
uv run python sim/s4a.py   # Results 1, 2, 5
uv run python sim/s4b.py   # Results 1, 2, 4, 6
```

Both scripts write their output to `sim/s4a_results.json` / `sim/s4b_results.json` and regenerate the figures in `sim/figS4_1.pdf` and `sim/figS4_2.pdf`.

---

## Recompiling the supplementary PDFs

LaTeX sources are in `supplementary/src/`. Requires XeLaTeX and BibTeX.

```bash
cd supplementary/src

# S2 — Search protocol
xelatex wrap_S2.tex && xelatex wrap_S2.tex

# S3 — Theorem cards
xelatex wrap_S3.tex && xelatex wrap_S3.tex

# S4 — Numerical checks (needs BibTeX for citations)
xelatex wrap_S4.tex && bibtex wrap_S4 && xelatex wrap_S4.tex && xelatex wrap_S4.tex
```

Pre-compiled PDFs are already in `supplementary/`.

---

## Verification scripts

| Script | What it does |
|---|---|
| `scripts/verify_modes.py` | Two-mode static check of the main manuscript (marked / clean) |
| `scripts/make_counts.py` | Regenerate `counts.tex` macros from `S1.csv` + `search_log.json` |
| `scripts/match_insearch.py` | Verify which route-R sources also appear in the structured search |
| `scripts/check_dupes_and_breaks.py` | Check for duplicate paragraphs and LaTeX line-break issues |
| `scripts/reconcile_sources.py` | Reconcile cited sources between v1 and v2 of the manuscript |

---

## Project structure

```
cosrev-recursive-training-replication/
├── supplementary/
│   ├── S1_cited_sources.csv        # Cited sources table (machine-readable)
│   ├── S1_cited_sources.pdf        # Formatted version of S1
│   ├── S2_search_protocol.pdf      # Search protocol (compiled)
│   ├── S3_theorem_cards.pdf        # Theorem cards (compiled)
│   ├── S4_numerical_checks.pdf     # Numerical checks (compiled)
│   └── src/                        # LaTeX sources for S2–S4
│       ├── wrap_S2.tex             # Standalone wrapper for S2
│       ├── wrap_S3.tex             # Standalone wrapper for S3
│       ├── wrap_S4.tex             # Standalone wrapper for S4
│       ├── appendix-search.tex     # S2 content
│       ├── S3.tex                  # S3 content
│       ├── S4.tex                  # S4 content
│       ├── counts.tex              # Manuscript count macros
│       └── sn-bibliography.bib    # Bibliography
├── scripts/                        # Verification and analysis scripts
├── sim/
│   ├── s4a.py                      # Simulation: Results 1, 2, 5
│   ├── s4b.py                      # Simulation: Results 1, 2, 4, 6
│   ├── s4a_results.json            # Raw outputs (seed 20261029)
│   ├── s4b_results.json
│   ├── figS4_1.pdf                 # Figure S4.1
│   └── figS4_2.pdf                 # Figure S4.2
├── search_log.json                 # Search log with per-source counts
├── pyproject.toml                  # Python dependencies (uv)
├── uv.lock
├── CITATION.cff
├── .zenodo.json
├── LICENSE
└── README.md
```

---

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
  note    = {COSREV-D-26-01510, under review}
}
```

---

## License

Code (`scripts/`, `sim/*.py`): [MIT](LICENSE).
Supplementary text and data (`supplementary/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
