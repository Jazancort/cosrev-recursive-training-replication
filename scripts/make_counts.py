# -*- coding: utf-8 -*-
"""
make_counts.py
Generates counts.tex — the single source of truth for all numerical claims
in COSREV-D-26-01510 that could change across revisions.

Sources (never edit counts.tex by hand):
  supplementary/S1.csv   — columns: key,category,route,in_orig,archival
  search/search_log.json — fields documented in search_log.json itself

Usage:
  python make_counts.py
  python make_counts.py --check   # exits non-zero if arithmetic is off
"""

import argparse, collections, csv, hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
S1   = ROOT / "supplementary" / "S1.csv"
LOG  = ROOT / "search" / "search_log.json"
OUT  = ROOT / "Recursive_Training_Failures_in_Large_Language_Models__A_Unified_Taxonomy__Security_Analysis__and_Governance_Framework___Julio_Azancort" / "counts.tex"


# ── helpers ─────────────────────────────────────────────────────────────────

def fmt(n):
    """1633 → 1{,}633 (LaTeX-safe thousand separator)."""
    return "{:,}".format(int(n)).replace(",", "{,}")

def macro(name, value):
    return r"\newcommand{" + "\\" + name + "}{" + str(value) + "}"

def opt(name, v, item=4):
    """Field that may be null — unknown values expand to \\warn{item}."""
    return macro(name, r"\warn{" + str(item) + "}" if v is None else fmt(v))


# ── load and validate inputs ─────────────────────────────────────────────────

def load():
    if not S1.exists():
        sys.exit(f"ERROR: {S1} not found. Run generate_s1.py first.")
    if not LOG.exists():
        sys.exit(f"ERROR: {LOG} not found.")

    rows = list(csv.DictReader(S1.open(encoding="utf-8")))
    if not rows:
        sys.exit("ERROR: S1.csv is empty.")

    # Check for required columns
    required = {"key", "category", "route", "in_orig", "archival"}
    missing = required - set(rows[0].keys())
    if missing:
        sys.exit(f"ERROR: S1.csv missing columns: {sorted(missing)}")

    # Check for duplicate keys
    keys = [r["key"].strip() for r in rows]
    dups = [k for k, c in collections.Counter(keys).items() if c > 1]
    if dups:
        sys.exit(f"ERROR: S1.csv duplicate keys: {dups}")

    # Validate category codes
    cat = collections.Counter(r["category"].strip() for r in rows)
    bad_cat = set(cat) - {"E", "P", "C", "L"}
    if bad_cat:
        sys.exit(f"ERROR: S1.csv invalid category codes: {bad_cat}")

    # Validate route codes (only for in_orig=no entries)
    rev_rows = [r for r in rows if r.get("in_orig", "").strip().lower() == "no"]
    valid_routes = {"A", "S", "CH", "R", ""}
    bad_route = {r["route"].strip() for r in rev_rows if r["route"].strip() not in valid_routes}
    if bad_route:
        sys.exit(f"ERROR: S1.csv invalid route codes for revision entries: {bad_route}")

    log = json.loads(LOG.read_text(encoding="utf-8"))
    return rows, rev_rows, cat, log


# ── arithmetic check ─────────────────────────────────────────────────────────

def check_arithmetic(log):
    S = log["sources"]
    # Use in_window values if retrieved is null
    total_in = sum(
        (v["retrieved"] - v["out_of_window"]) if (v.get("retrieved") is not None and v.get("out_of_window") is not None)
        else v.get("in_window", 0)
        for v in S.values()
    )
    expected = total_in - log["duplicates"]
    screened = log["screened"]
    ok = (expected == screened)
    if not ok:
        print(
            f"WARNING A1: sum(in_window)={total_in} - {log['duplicates']}(dup) "
            f"= {expected} ≠ {screened}(screened). "
            f"Populate 'retrieved' and 'out_of_window' in search_log.json to resolve. "
            f"\\warn{{4}} will fire in manuscript.", file=sys.stderr
        )
    return ok


# ── generate counts.tex ───────────────────────────────────────────────────────

def generate(rows, rev_rows, cat, log, arith_ok):
    S = log["sources"]

    # Route counts — for evidence studies only
    route_E = collections.Counter(
        r["route"].strip() for r in rows
        if r["category"].strip() == "E" and r.get("in_orig", "").strip().lower() == "no"
    )

    # All revision routes (including non-E for §1.1 paragraph)
    route_all = collections.Counter(
        r["route"].strip() for r in rev_rows
    )

    nonarch = sum(r["archival"].strip().upper() == "N" for r in rows)
    in_orig_yes = sum(r["in_orig"].strip().lower() == "yes" for r in rows)
    in_orig_no  = sum(r["in_orig"].strip().lower() == "no"  for r in rows)

    # Consistency check: included_S must equal route_E["S"]
    if log.get("included_S") is not None and log["included_S"] != route_E.get("S", 0):
        sys.exit(
            f"INCONSISTENCY: search_log.json says {log['included_S']} included via structured search, "
            f"but S1.csv has {route_E.get('S', 0)} evidence studies with route=S."
        )

    h = hashlib.sha256(S1.read_bytes() + LOG.read_bytes()).hexdigest()[:16]
    screen_flag = "" if arith_ok else r"\warn{4}"

    # Per-source macros
    source_lines = []
    for name, v in S.items():
        safe = name.replace(" ", "").replace("-", "")
        source_lines += [
            opt(f"Nret{safe}",  v.get("retrieved")),
            opt(f"Nout{safe}",  v.get("out_of_window")),
            macro(f"Nin{safe}",  fmt(v.get("in_window", 0))),
        ]

    # Total counts
    total_ret  = sum(v["retrieved"] for v in S.values()) if all(v.get("retrieved") is not None for v in S.values()) else None
    total_out  = sum(v["out_of_window"] for v in S.values()) if all(v.get("out_of_window") is not None for v in S.values()) else None
    total_in   = sum(v.get("in_window", 0) for v in S.values())

    val = log.get("validation", {})

    lines = [
        f"% GENERATED by make_counts.py — DO NOT EDIT",
        f"% inputs-sha256={h}",
        "%",
        "% ── Source counts (from S1.csv) ────────────────────────────────",
        macro("Ncited",      fmt(len(rows))),
        macro("Nevidence",   fmt(cat["E"])),
        macro("Nposition",   fmt(cat["P"])),
        macro("Ncontext",    fmt(cat["C"])),
        macro("Nlegal",      fmt(cat.get("L", 0))),
        macro("Nstudies",    fmt(cat["E"] + cat["P"] + cat["C"])),
        "%",
        "% ── Revision route counts ──────────────────────────────────────",
        macro("NrouteS",     fmt(route_all.get("S",  0))),
        macro("NrouteCH",    fmt(route_all.get("CH", 0))),
        macro("NrouteR",     fmt(route_all.get("R",  0))),
        macro("NrouteA",     fmt(route_all.get("A",  0))),
        "%",
        "% ── Evidence-study route counts (category E only) ──────────────",
        macro("NrouteES",    fmt(route_E.get("S",  0))),
        macro("NrouteECH",   fmt(route_E.get("CH", 0))),
        macro("NrouteER",    fmt(route_E.get("R",  0))),
        "%",
        "% ── Original vs revision split ─────────────────────────────────",
        macro("NorigYes",    fmt(in_orig_yes)),
        macro("NorigNo",     fmt(in_orig_no)),
        "%",
        "% ── Non-archival (dagger) ───────────────────────────────────────",
        macro("Nnonarchival", fmt(nonarch)),
        macro("NnonarchE",    fmt(sum(r["archival"].strip().upper() == "N" for r in rows if r["category"].strip() == "E"))),
        # NreplNone: count E-category studies with replication="N" (confirmed no independent replication)
        # Blank = not yet audited; only confirmed "N" entries count.
        macro("NreplNone",    fmt(sum(r.get("replication","").strip().upper() == "N" for r in rows if r["category"].strip() == "E"))) if any(r.get("replication","").strip() for r in rows) else r"\newcommand{\NreplNone}{\warn{7}}  % need replication column in S1.csv",
        r"\newcommand{\NinsearchR}{2} % route-R ∩ structured search: peterson(2404.03502) + wright(2510.04226) — confirmed by match_insearch.py",
        "%",
        "% ── Search counts (from search_log.json) ───────────────────────",
        macro("Nsources",     fmt(len(S))),
        macro("cutoffdate",   log.get("cutoff", r"\warn{4}")),
        opt("NrecTotal",  total_ret),
        opt("Noutwindow", total_out),
        macro("NinTotal",    fmt(total_in)),
        macro("Ndup",        fmt(log["duplicates"])),
        macro("Nscreened",   fmt(log["screened"]) + screen_flag),
        opt("Nfulltext",     log.get("fulltext")),
        macro("NincludedS",   fmt(route_E.get("S", 0))),
        "%",
        "% ── Validation set ─────────────────────────────────────────────",
        opt("Nvalset",     val.get("size")),
        opt("Nvalfound",   val.get("retrieved")),
        macro("Nvalmissed", fmt(val.get("not_retrieved", 0))),
        "%",
        "% ── Other method parameters ─────────────────────────────────────",
        # Nstoprule omitted: saturation criterion used (no fixed N); sentence rewritten in §3
        "%",
        "% ── Query counts per source ─────────────────────────────────────",
    ] + [
        macro(f"Nq{name.replace(' ','').replace('-','')}", fmt(v.get("queries", 0)))
        for name, v in S.items()
    ] + [
        "%",
        "% ── Per-source record counts ─────────────────────────────────────",
    ] + source_lines

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return h


# ── main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="Exit non-zero if arithmetic in search_log is off")
    args = ap.parse_args()

    rows, rev_rows, cat, log = load()
    arith_ok = check_arithmetic(log)
    h = generate(rows, rev_rows, cat, log, arith_ok)

    route_E = collections.Counter(
        r["route"].strip() for r in rows
        if r["category"].strip() == "E" and r.get("in_orig", "").strip().lower() == "no"
    )
    print(f"counts.tex written ({len(rows)} sources, "
          f"E={cat['E']} P={cat['P']} C={cat['C']} L={cat.get('L',0)}, "
          f"routes(all): S={sum(r['route'].strip()=='S' for r in rev_rows)} "
          f"CH={sum(r['route'].strip()=='CH' for r in rev_rows)} "
          f"R={sum(r['route'].strip()=='R' for r in rev_rows)} "
          f"A={sum(r['route'].strip()=='A' for r in rev_rows)}, "
          f"sha={h})")

    if args.check and not arith_ok:
        sys.exit(1)
