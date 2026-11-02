# -*- coding: utf-8 -*-
"""match_insearch.py — cross-reference route-R S1 papers against screened corpus.

Usage:
    uv run python v2/references/scripts/match_insearch.py

Reads:
    v2/supplementary/S1.csv           (keys + routes)
    sn-bibliography.bib               (DOIs, arXiv IDs, titles)
    v2/references/corpus/screening-file-A02.csv  (1,633 screened records)

Output:
    For each route-R paper: match status (doi/arxiv/title/none), screen decision
    Summary: NinsearchR count
"""

import csv, pathlib, re, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[3]  # cosrev-v2/
S1   = ROOT / "v2" / "supplementary" / "S1.csv"
BIB  = ROOT / "v2" / "Recursive_Training_Failures_in_Large_Language_Models__A_Unified_Taxonomy__Security_Analysis__and_Governance_Framework___Julio_Azancort" / "sn-bibliography.bib"
CORP = ROOT / "v2" / "references" / "corpus" / "screening-file-A02.csv"


def norm_title(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)[:80]

def norm_doi(d):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", (d or "").lower().strip())

def norm_arxiv(a):
    """Extract bare arXiv ID, stripping version and URL prefix."""
    a = (a or "").strip().lower()
    # Handle URLs like http://arxiv.org/abs/2307.01850v1
    m = re.search(r"(\d{4}\.\d{4,5})", a)
    return m.group(1) if m else re.sub(r"v\d+$", "", a)


# ── Load bib ────────────────────────────────────────────────────────────────
bib_text = BIB.read_text(encoding="utf-8")
bib = {}
for entry in re.finditer(r"@\w+\s*\{([^,]+),([^@]+)", bib_text, re.S):
    key = entry.group(1).strip()
    body = entry.group(2)
    doi_m   = re.search(r"\bdoi\s*=\s*\{([^}]+)\}", body, re.I)
    arx_m   = re.search(r"\beprint\s*=\s*\{([^}]+)\}", body, re.I)
    tit_m   = re.search(r"\btitle\s*=\s*\{([^}]+)\}", body, re.I)
    bib[key] = {
        "doi":   norm_doi(doi_m.group(1)) if doi_m else "",
        "arxiv": norm_arxiv(arx_m.group(1)) if arx_m else "",
        "title": norm_title(tit_m.group(1)) if tit_m else "",
    }


# ── Load screened corpus ────────────────────────────────────────────────────
screened = list(csv.DictReader(CORP.open(encoding="utf-8")))

# Build lookup indices
by_doi   = {}
by_arxiv = {}
by_title = {}
for r in screened:
    pid = r.get("paperId", "")
    # Try to extract DOI from paperId (Scopus/OpenAlex may have it)
    doi_from_pid = norm_doi(pid) if "doi.org" in pid.lower() else ""
    doi_from_pid2 = norm_doi(r.get("doi", "")) if r.get("doi") else ""
    for d in (doi_from_pid, doi_from_pid2):
        if d:
            by_doi.setdefault(d, []).append(r)
    # arXiv ID from paperId
    arx = norm_arxiv(pid)
    if arx:
        by_arxiv.setdefault(arx, []).append(r)
    # title
    nt = norm_title(r.get("title", ""))
    if nt:
        by_title.setdefault(nt, []).append(r)


# ── Cross-reference route-R papers ─────────────────────────────────────────
s1_rows = list(csv.DictReader(S1.open(encoding="utf-8")))
route_r = [r for r in s1_rows if r.get("route", "").strip() == "R"]

print(f"\n{'KEY':40} {'HOW':8} {'DECISION':15} {'SCREEN_NOTES'}")
print("-" * 100)

hits = []
for r in route_r:
    key  = r["key"].strip()
    info = bib.get(key, {"doi": "", "arxiv": "", "title": ""})
    match, how = None, "none"

    # Try DOI
    if info["doi"] and info["doi"] in by_doi:
        match, how = by_doi[info["doi"]][0], "doi"
    # Try arXiv
    elif info["arxiv"] and info["arxiv"] in by_arxiv:
        match, how = by_arxiv[info["arxiv"]][0], "arxiv"
    # Try title
    elif info["title"] and info["title"] in by_title:
        cands = by_title[info["title"]]
        if len(cands) == 1:
            match, how = cands[0], "title"
        elif len(cands) > 1:
            how = f"AMBIGUOUS({len(cands)})"

    if match:
        hits.append(key)
        dec  = match.get("decision", "").strip() or "(blank)"
        note = match.get("notes", "").strip()[:40] or ""
        print(f"{key:40} {how:8} {dec:15} {note}")
    else:
        # Show what we tried for debugging
        tried = f"doi={info['doi'][:20]!r} arx={info['arxiv']!r} tit={info['title'][:20]!r}"
        print(f"{key:40} {'none':8} {'not-found':15} {tried}")

print("-" * 100)
print(f"\nRoute-R papers: {len(route_r)}")
print(f"Found in corpus (NinsearchR): {len(hits)}")
print(f"Matches: {hits}")

# Flag inconsistencies
print("\n=== CONSISTENCY CHECKS ===")
for r in s1_rows:
    key = r["key"].strip()
    if r.get("route", "").strip() == "S":
        info = bib.get(key, {})
        # S papers should be in corpus
        in_corp = False
        if info.get("doi") and info["doi"] in by_doi:
            in_corp = True
        elif info.get("arxiv") and info["arxiv"] in by_arxiv:
            in_corp = True
        elif info.get("title") and info["title"] in by_title:
            in_corp = True
        if not in_corp:
            print(f"WARN: route=S but NOT found in corpus: {key}")
