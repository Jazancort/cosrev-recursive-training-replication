#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_modes.py — Gate verifier for COSREV-D-26-01510 v2
Usage:
  python verify_modes.py                      # marked + clean builds, full report
  python verify_modes.py --compare old.pdf    # also produce sync-diff.txt vs old PDF
  python verify_modes.py --strict             # require FINAL mode to compile cleanly

Exit code:
  0 — no FAIL (PENDs allowed in non-strict mode)
  1 — at least one FAIL, or --strict and FINAL does not compile

Gate criteria (item 1 baseline):
  • CLEAN and MARKED compile without LaTeX errors
  • No undefined citations or references in CLEAN
  • FINAL mode fails (proves the pending-flag mechanism works)
  • Zero literal numbers in .tex source (all via counts.tex macros)
  • PDF Subject metadata contains the git commit hash
"""

import argparse, collections, csv, difflib, hashlib, json, os, pathlib
import re, subprocess, sys, unicodedata
from collections import defaultdict

ROOT  = pathlib.Path(__file__).resolve().parent
MSDIR = ROOT / "Recursive_Training_Failures_in_Large_Language_Models__A_Unified_Taxonomy__Security_Analysis__and_Governance_Framework___Julio_Azancort"
MAIN  = "sn-article"
BIB   = MSDIR / "sn-bibliography.bib"
S1    = ROOT / "supplementary" / "S1.csv"
LOGJ  = ROOT / "search" / "search_log.json"
MANIFEST = ROOT / "supplementary" / "MANIFEST.txt"
SYNCMD   = ROOT / "SYNC.md"
ENV = dict(os.environ,
           max_print_line="10000",
           error_line="254",
           half_error_line="238")

FINDINGS = []  # (level, item, check, detail)

def add(level, item, check, detail):
    FINDINGS.append((str(level), str(item), str(check), str(detail)))

def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd or MSDIR, capture_output=True,
                          text=True, errors="replace", env=ENV)

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()

def rd(p):
    return pathlib.Path(p).read_text(encoding="utf-8", errors="replace")


# ══════════════════════════════════════════════════════════════════════════════
# BUILD
# ══════════════════════════════════════════════════════════════════════════════

MODES = {
    "marked": "",
    "clean":  r"\def\CLEAN{}",
    "final":  r"\def\FINAL{}",
}

def build(mode, commit):
    job = f"{MAIN}-{mode}"
    pre = (MODES[mode] +
           r"\def\gitcommit{" + commit + r"}" +
           r"\input{" + MAIN + "}")
    tex_cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
               f"-jobname={job}", pre]
    bib_cmd = ["bibtex", job]

    for step in (tex_cmd, bib_cmd, tex_cmd, tex_cmd):
        r = run(step)
        if step[0] == "bibtex":
            if r.returncode >= 2:
                return job, False, r.stdout[-600:]
        elif r.returncode != 0:
            return job, False, r.stdout[-1500:]
    return job, True, ""


# ══════════════════════════════════════════════════════════════════════════════
# LOG INSPECTION
# ══════════════════════════════════════════════════════════════════════════════

PEND_RE = re.compile(
    r"Package revision Warning: PENDING (\w+) \(item ([^)]*)\) on input line (\d+)")
PERR_RE = re.compile(
    r"Package revision Error: Unresolved (\w+) \(item ([^)]*)\) at line (\d+)")

def check_log(job, mode):
    log_path = MSDIR / f"{job}.log"
    if not log_path.exists():
        add("FAIL", 1, f"log:{mode}", "log file missing"); return 0
    log = rd(log_path)

    if mode == "clean":
        # Collect pending flags
        pend = sorted(set(PEND_RE.findall(log)), key=lambda x: int(x[2]))
        for kind, item, line in pend:
            add("PEND", item or "?", f"\\{kind}", f"line {line}")

        # Undefined citations / references
        for m in re.finditer(r"(Citation|Reference) `([^']+)' .*?undefined", log):
            add("FAIL", 1, f"undefined-{m.group(1).lower()}", m.group(2))

        # Labels changed → need another pass
        if "Label(s) may have changed" in log:
            add("FAIL", 1, "rerun", "labels changed after last pass")

        # Overfull hboxes > 5pt
        over = [float(x) for x in re.findall(r"Overfull \\hbox \(([\d.]+)pt too wide", log)]
        big = sum(o > 5 for o in over)
        if big:
            add("WARN", 9, "overfull", f"{big} boxes > 5pt (worst: {max(over):.1f}pt)")

        return len(pend)

    if mode == "final":
        m = PERR_RE.search(log)
        if m:
            add("INFO", m.group(2), "final-blocked",
                f"first pending flag at line {m.group(3)} (mode FINAL works correctly)")
        else:
            add("FAIL", 1, "final-no-error",
                "mode FINAL compiled without error — pending-flag mechanism broken")

    return 0


# ══════════════════════════════════════════════════════════════════════════════
# PDF INSPECTION
# ══════════════════════════════════════════════════════════════════════════════

RUNHEAD_RE = re.compile(
    r"Azancort Neto et al\.:.*?Page \d+ of \d+"
    r"|Recursive Training(?:.*?)(?=\n)", re.I)

def pdf_text(pdf, strip_headers=False):
    r = run(["pdftotext", "-enc", "UTF-8", pdf, "-"], cwd=None)
    t = r.stdout
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"(\w)-\n\s*(\w)", r"\1\2", t)   # remove hyphenation
    t = re.sub(r"\s+", " ", t)
    return RUNHEAD_RE.sub(" ", t) if strip_headers else t

def pdfinfo(pdf):
    r = run(["pdfinfo", pdf], cwd=None)
    out = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


# Pattern lists: (item_owner, name, regex, flags)
FAIL_PATTERNS = [
    (2,  "placeholder-count",
     r"\b(?:identified|includ\w*)\s+[NXY]\s+(?:evidence\s+)?(?:studies|sources)\b", re.I),
    (1,  "undefined-ref",        r"\?\?", 0),
    (1,  "revision-language",
     r"(?<![/.])\bv[12]\b(?![./\d])|not carried over|corrected formal results"
     r"|claims-table|\bMC\d+\b", re.I),
    (1,  "internal-id",          r"\(A\d{1,2}\)", 0),
    (1,  "pending-text",
     r"under preparation"
     r"|to be verified"
     r"|requires? verification"
     r"|see protocol"
     r"|deferred to the update search"
     r"|author note"
     r"|renamed per"
     r"|\bTODO\b|\bFIXME\b", re.I),
    (1,  "markup-leakage",       r"\[deleted\]|\[v1:|\[INTERNAL|PENDING", 0),
    (2,  "bib-internal-note",    r"Non-archival:\s*(?:preprint|workshop|not\b)|key formerly", re.I),
    (4,  "kappa-in-pdf",         r"κ\s*=|\bkappa\b|inter-rater", re.I),
]

WARN_PATTERNS = [
    (5,  "crisis-term",          r"recursive training crisis"),
    (5,  "unified-term",         r"\bunified\b|unification"),
    (3,  "only-if-suff",         r"\bonly if\b"),
    (5,  "structural-overuse",
     r"\bstructural(?:ly)?\b"),
    (5,  "absolute-claim",
     r"mathematically certain|formally tight|all existing|no engineering intervention"
     r"|structurally identical|political will|every formal bound|catastrophic"),
    (5,  "strong-verb",          r"\bconfirm(?:s|ed)?\b|\bdemonstrat(?:e|es|ed)\b"),
    (1,  "word-repeated",        r"\b(\w{4,})\s+\1\b"),
]

def ctx(t, m, w=70):
    return "…" + t[max(0, m.start()-w):m.end()+w].strip() + "…"

def check_pdf(pdf, commit):
    t = pdf_text(pdf)

    for item, name, rx, fl in FAIL_PATTERNS:
        for m in list(re.finditer(rx, t, fl))[:5]:
            add("FAIL", item, f"pdf:{name}", ctx(t, m))

    for item, name, rx in WARN_PATTERNS:
        ms = list(re.finditer(rx, t, re.I))
        if ms:
            add("WARN", item, f"pdf:{name}", f"{len(ms)}× ; ex.: {ctx(t, ms[0], 40)}")

    info = pdfinfo(pdf)
    pages = int(info.get("Pages", 0))
    pp = [(int(x), int(y)) for x, y in re.findall(r"Page (\d+) of (\d+)", t)]
    ys = {y for _, y in pp}
    if pp and (len(ys) != 1 or next(iter(ys)) != pages or any(x > y for x, y in pp)):
        add("FAIL", 9, "pagination",
            f"footer 'Page x of y' inconsistent with {pages} pages PDF")

    subj = info.get("Subject", "")
    if commit not in subj:
        add("FAIL", 1, "provenance",
            f"PDF Subject={subj!r}, expected to contain commit={commit!r}")

    return t


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE .TEX INSPECTION
# ══════════════════════════════════════════════════════════════════════════════

def strip_comments(s):
    return "\n".join(re.sub(r"(?<!\\)%.*", "", l) for l in s.splitlines())

def tex_files():
    seen, todo = [], [MSDIR / f"{MAIN}.tex"]
    while todo:
        f = todo.pop()
        if f in seen or not f.exists():
            continue
        seen.append(f)
        for m in re.finditer(r"\\(?:input|include)\{([^}]+)\}",
                              strip_comments(rd(f))):
            n = m.group(1)
            if not n.endswith(".tex"):
                n += ".tex"
            todo.append(MSDIR / n)
    return seen

LITERAL_COUNT_RE = re.compile(
    r"\b1,633\b|1\{,\}633"
    r"|\b(?:797|594|576|865|161)\b"
    r"|\b(?:62|87)\s+(?:evidence\s+)?(?:studies|included)"
    r"|N\s*=\s*62",
    re.I
)
OLD_MARKER_RE = re.compile(
    r"\(preprint\)|\[T,~?preprint\]|\[E,~?workshop\]|p~?=~?preprint|\[T,E,p\]"
)

def check_sources():
    n_flags = 0
    for f in tex_files():
        if f.name in ("counts.tex",):
            continue
        src = strip_comments(rd(f))
        for i, line in enumerate(src.splitlines(), 1):
            # Skip macro definition lines
            if re.search(r"(?:new|provide|renew)command|DeclareRobustCommand", line):
                continue
            # Count warn/fnwarn/internal flags and check they have item number
            for m in re.finditer(r"\\(warn|fnwarn|internal)\b(\{[^}]*\})?", line):
                n_flags += 1
                arg = m.group(2) or ""
                if not arg or arg in ("{}", "{ }"):
                    add("FAIL", 1, "flag-no-owner",
                        f"{f.name}:{i} \\{m.group(1)} with no item number")
            # Check for literal numbers that should use macros
            if LITERAL_COUNT_RE.search(line):
                add("FAIL", 1, "literal-count",
                    f"{f.name}:{i} — use counts.tex macro")
            if OLD_MARKER_RE.search(line):
                add("WARN", 2, "old-marker",
                    f"{f.name}:{i} — standardise to \\nrv{{}}")
    return n_flags


# ══════════════════════════════════════════════════════════════════════════════
# BIBLIOGRAPHY + S1 CROSS-CHECK
# ══════════════════════════════════════════════════════════════════════════════

def bib_entries():
    entries = {}
    text = rd(BIB) if BIB.exists() else ""
    for m in re.finditer(
            r"@(\w+)\s*\{?\s*([^,\s{]+)\s*,\s*([\s\S]*?)(?=\n@|\Z)", text):
        etype = m.group(1).lower()
        if etype in ("comment", "string", "preamble"):
            continue
        key, body = m.group(2), m.group(3)
        doi = re.search(r"\bdoi\s*=\s*[{\"]([^}\"]+)", body, re.I)
        tit = re.search(r"\btitle\s*=\s*\{([\s\S]*?)\}\s*[,\n]", body, re.I)
        entries[key] = (
            doi.group(1).lower().strip() if doi else None,
            re.sub(r"[^a-z0-9]", "", tit.group(1).lower())[:60] if tit else None,
        )
    return entries

def cited_keys(job):
    aux = MSDIR / f"{job}.aux"
    if not aux.exists():
        return set()
    keys = set()
    for m in re.finditer(r"\\citation\{([^}]*)\}", rd(aux)):
        keys |= {k.strip() for k in m.group(1).split(",")}
    return keys

def check_bib_s1(job, pdf_text_content):
    keys = cited_keys(job)
    if not keys:
        add("FAIL", 2, "bib-aux", f"{job}.aux missing or empty")
        return

    bib = bib_entries()

    # Duplicate detection by DOI and by normalised title (only among cited keys)
    for idx, label in enumerate(("DOI", "title")):
        seen = defaultdict(list)
        for k in keys:
            v = bib.get(k, (None, None))[idx]
            if v:
                seen[v].append(k)
        for v, ks in seen.items():
            if len(ks) > 1:
                add("FAIL", 2, f"bib-duplicate-{label}", str(sorted(ks)))

    # Internal notes that should not appear in .bbl
    bbl_path = MSDIR / f"{job}.bbl"
    if bbl_path.exists():
        bbl = rd(bbl_path)
        for rx in (r"to (?:be )?verif\w*", r"formerly", r"renamed",
                   r"author note", r"Non-archival", r"full author list"):
            for m in re.finditer(rx, bbl, re.I):
                snippet = bbl[max(0, m.start()-80):m.end()+20].replace("\n", " ")
                add("FAIL", 2, "bbl-internal-note", snippet)

    # S1 cross-check
    if S1.exists():
        s1_keys = {l.split(",")[0].strip()
                   for l in rd(S1).splitlines()[1:] if l.strip()}
        for k in sorted(keys - s1_keys):
            if k:
                add("FAIL", 2, "cited-not-in-S1", k)
        for k in sorted(s1_keys - keys):
            if k:
                add("FAIL", 2, "S1-not-cited", k)
    else:
        add("FAIL", 2, "S1-missing", "supplementary/S1.csv not found")

    # counts.tex freshness
    counts = MSDIR / "counts.tex"
    if counts.exists() and S1.exists() and LOGJ.exists():
        h = hashlib.sha256(S1.read_bytes() + LOGJ.read_bytes()).hexdigest()[:16]
        if f"inputs-sha256={h}" not in rd(counts):
            add("FAIL", 1, "counts-stale", "run make_counts.py")
    else:
        add("FAIL", 1, "counts-files", "counts.tex / S1.csv / search_log.json missing")

    # Supplementary material declared in PDF vs MANIFEST
    ids = set(re.findall(r"Supplementary (?:Material|Table)\s*(S\d+)",
                         pdf_text_content))
    have = set(rd(MANIFEST).split()) if MANIFEST.exists() else set()
    for s in sorted(ids - have):
        add("FAIL", 9, "supp-missing", s)
    if re.search(r"appendix-a2-supplementary|Table A2", pdf_text_content):
        add("FAIL", 1, "old-supp-name", "replace 'Table A2'/filename with \\SuppStudies")


# ══════════════════════════════════════════════════════════════════════════════
# SYNC DIFF
# ══════════════════════════════════════════════════════════════════════════════

def sync_diff(old_pdf, new_pdf, out_name="sync-diff.txt"):
    def sentences(t):
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if len(s.strip()) > 20]

    a = sentences(pdf_text(old_pdf, strip_headers=True))
    b = sentences(pdf_text(new_pdf, strip_headers=True))
    d = list(difflib.unified_diff(a, b, old_pdf, new_pdf, lineterm="", n=1))
    out_path = ROOT / out_name
    out_path.write_text("\n".join(d), encoding="utf-8")
    hunks = sum(1 for l in d if l.startswith("@@"))
    add("INFO", 1, "sync-diff",
        f"{hunks} hunk(s) written to {out_name}; classify each in SYNC.md")


# ══════════════════════════════════════════════════════════════════════════════
# SUBMISSION READINESS CHECK  (item 9)
# ══════════════════════════════════════════════════════════════════════════════

REQUIRED_SECTIONS_9 = [
    "CRediT authorship contribution statement",
    "Declaration of competing interest",
    "Data and code availability",
    "Declaration of generative AI and AI-assisted technologies in the writing process",
]

def check_submission(pdf_text_content):
    """Item 9: submission-package readiness."""
    t = pdf_text_content
    src_all = "\n".join(strip_comments(rd(f)) for f in tex_files())

    # Abstract word count (CSR: 50–200)
    ab = _section_text(t, r"\bAbstract\b", r"(?:\d+\s*\.\s*)?Introduction")
    if ab:
        nw = len(re.findall(r"\b[\w'']+\b", ab))
        if not (50 <= nw <= 200):
            add("FAIL", 9, "abstract", f"{nw} palavras — CSR: 50–200")
        if re.search(r"\[\d+\]", ab):
            add("FAIL", 9, "abstract", "citação numérica no resumo")

    # Keywords count (CSR: ≤6)
    kw_m = re.search(r"Keywords\s*:?(.*?)(?=\d+\.\s*Introduction|\Z)", t, re.S | re.I)
    if kw_m:
        kws = [k.strip() for k in re.split(r"[,;•]", kw_m.group(1)) if k.strip()]
        if len(kws) > 6:
            add("FAIL", 9, "keywords", f"{len(kws)} palavras-chave — CSR: ≤6")

    # Required Elsevier sections
    for sec in REQUIRED_SECTIONS_9:
        if sec not in t:
            add("FAIL", 9, "declarações", f"falta: {sec}")

    # AI declaration must appear before References
    ai_idx = t.find("Declaration of generative AI")
    ref_idx = t.rfind("References")
    if ai_idx >= 0 and ref_idx >= 0 and ai_idx > ref_idx:
        add("FAIL", 9, "declarações", "declaração de IA vem depois das Referências")

    # Forbidden Springer-style sections (must use Elsevier)
    for rx, why in [
        (r"Conflict of interest:|Consent for publication|Materials availability",
         "declaração no formato Springer — substituir pelo padrão Elsevier"),
        (r"\[TOOL NAME|AI-TOOL-NAME", "nome da ferramenta de IA em aberto"),
        (r"zenodo\.XXXXX|zenodo\.XXXXXXX", "DOI do Zenodo em aberto"),
        (r"ROR identifier", "ROR como processo — remover"),
        (r"No custom software was developed", "declaração de código desactualizada"),
    ]:
        if re.search(rx, t, re.I):
            add("FAIL", 9, "submissão", why)

    # Warn about gmail (institutional preferred)
    if re.search(r"gmail\.com", src_all, re.I):
        add("WARN", 9, "submissão", "e-mail Gmail — considere usar e-mail institucional")

    # Supplementary files declared in text must be in MANIFEST
    supp_ids = set(re.findall(r"Supplementary(?:\s+Material)?\s+(S\d+)", t))
    if MANIFEST.exists():
        have = set(re.findall(r"S\d+", rd(MANIFEST)))
        for sid in sorted(supp_ids - have):
            add("FAIL", 9, "supp-missing", f"{sid} citado no texto mas ausente do MANIFEST")
    else:
        if supp_ids:
            add("FAIL", 9, "supp-missing", "MANIFEST.txt ausente")

    # Required submission files
    for fname in ("highlights.txt",):
        if not (ROOT / fname).exists():
            add("FAIL", 9, "pacote", f"ausente: {fname}")
    if not (ROOT / "v2" / "analysis" / "cover-letter-blocks.md").exists():
        add("WARN", 9, "pacote", "cover-letter-blocks.md ausente")


# ══════════════════════════════════════════════════════════════════════════════
# CONCLUSION CHECK  (item 7)
# ══════════════════════════════════════════════════════════════════════════════

QUALIFIERS_7 = {
    "A1 sample size":  r"fixed (?:per-generation )?sample size",
    "A1 unbiased":     r"unbiased",
    "A3 untested":     r"untested",
    "A4 one study":    r"\bone\b[^.]{0,50}(?:study|fine-tuning)",
    "A5 anchor":       r"\banchor\b",
    "A6 sibling":      r"\bsibling\b",
    "A8 thirteen":     r"\bthirteen\b",
}

def _section_text(text, start_rx, end_rx):
    """Extract text between two regex anchors."""
    m1 = re.search(start_rx, text, re.I)
    if not m1:
        return ""
    rest = text[m1.end():]
    m2 = re.search(end_rx, rest, re.I)
    return rest[:m2.start()] if m2 else rest[:4000]

def check_conclusion(pdf_text_content):
    """Item 7: abstract / conclusion coherence."""
    t = pdf_text_content

    ab = _section_text(t, r"\bAbstract\b", r"(?:\d+\s*\.\s*)?Introduction")
    co = _section_text(t, r"(?:\d+\s*\.\s*)?Conclusion", r"Acknowledg")

    if not ab:
        add("FAIL", 7, "abstract", "Abstract not found in PDF text")
    if not co:
        add("FAIL", 7, "conclusion", "Conclusion not found in PDF text")
        return

    # Qualifiers must be present in both abstract and conclusion
    for name, rx in QUALIFIERS_7.items():
        for label, chunk in (("abstract", ab), ("conclusion", co)):
            if chunk and not re.search(rx, chunk, re.I):
                add("FAIL", 7, "qualificador",
                    f"{name} ausente no {label} (registro 7.1)")

    # Five evidence-type labels must appear in the conclusion
    for lab in ("[T]", "[E]", "[X]", "[C]", "[N]"):
        if co and lab not in co:
            add("FAIL", 7, "rótulos",
                f"{lab} ausente na Conclusão (R1 #10)")

    # Word count
    nw = len(co.split()) if co else 0
    if co and not (200 <= nw <= 380):
        add("WARN", 7, "tamanho",
            f"Conclusão com {nw} palavras (expected 200–360)")

    # Forbidden content in conclusion
    for rx, why in [
        (r"(?:^|\.\s)(?:Fifth|Sixth|Seventh)[, ]", "ordinais órfãos"),
        (r"single reviewer|one author\s+carried|validation set|Semantic Scholar",
         "repete §7.4"),
        (r"Three empirical priorities|\(c\)\s+Under what",
         "prioridades antigas (mover p/ §7.5)"),
        (r"\bpolitical will\b|\bcrisis\b|structural paradox",
         "retórica antiga"),
    ]:
        if co and re.search(rx, co, re.I):
            add("FAIL", 7, "conclusão", f"{why}")

    # highlights.txt
    hl_path = ROOT / "highlights.txt"
    if hl_path.exists():
        items = [l.strip() for l in rd(hl_path).splitlines() if l.strip()]
        if not (3 <= len(items) <= 5):
            add("FAIL", 7, "highlights", f"{len(items)} itens (esperado 3–5)")
        for h in items:
            if len(h) > 85:
                add("FAIL", 7, "highlights", f"{len(h)} caract. (>85): {h[:60]}…")
    else:
        add("FAIL", 7, "highlights", "highlights.txt ausente no root")

    # Future work must be in §7.5, not scattered elsewhere
    src_all = "\n".join(strip_comments(rd(f)) for f in tex_files())
    concl_src = src_all.split(r"\section{Conclusion}")[-1] if r"\section{Conclusion}" in src_all else ""
    if "Five directions" in concl_src:
        add("FAIL", 7, "§7.4", "'Five directions' ainda na §7.4 — mover p/ §7.5")


# ══════════════════════════════════════════════════════════════════════════════
# GOVERNANCE CHECK  (item 6)
# ══════════════════════════════════════════════════════════════════════════════

def check_governance(pdf_text_content):
    """Item 6: verify governance section coherence."""
    t = pdf_text_content
    src = "\n".join(strip_comments(rd(f)) for f in tex_files())

    # 1. G1..G13 each appear as table rows
    rows = re.findall(r"^\s*G(\d{1,2})\s*&", src, re.M)
    expected = list(range(1, 14))
    if sorted(map(int, rows)) != expected:
        add("FAIL", 6, "G-rows",
            f"tabela de instrumentos: linhas encontradas={sorted(map(int,rows))}")

    # 2. G# mentioned in body prose (outside tables)
    # Strip table environments from PDF text for this check
    body = re.sub(r"G\d{1,2}\s*&", "", t)  # remove table cells
    for g in range(1, 14):
        if not re.search(rf"\bG{g}\b", body):
            add("WARN", 6, "G-prosa",
                f"G{g} não é citado na prosa fora da tabela")

    # 3. Trade-offs: the 5 conflicts from R1 #9 must be present
    tr_idx = t.find("Trade-offs")
    tr = t[tr_idx: tr_idx + 4000] if tr_idx >= 0 else ""
    for keyword, label in [("erasure", "privacidade/apagamento"),
                            ("licen",   "licenças"),
                            ("poison",  "dados envenenados"),
                            ("stale",   "dados obsoletos"),
                            ("storage", "armazenamento")]:
        if keyword.lower() not in tr.lower():
            add("FAIL", 6, "trade-offs",
                f"falta conflito '{label}' no parágrafo de Trade-offs (R1 #9)")

    # 4. Legal claims / normative issues
    gov_fail = [
        (r"mandates conformity assessments and risk classification for AI systems deployed across",
         "Art. 27 aplica-se apenas a certos deployers, não a todos os sistemas na UE"),
        (r"presumes systemic risk when.*compute|compute.*presumes systemic",
         "Art. 51(2): presunção de high-impact capabilities, não de systemic risk"),
        (r"Article~?(?:50|53)\([12d]\)[^.]{0,200}\[N\]",
         "fato legal do AI Act rotulado [N]"),
        (r"must include:|is the minimum condition for escaping|equips the next generation.*governance",
         "normativo absoluto sem [N]"),
        (r"\baccumulation mandate\b(?!\")",
         "termo substituído por G4/retention-and-renewal; só permitido entre aspas"),
        (r"Regional collective bargaining|AI data labor standards",
         "instrumento removido da tabela — não deve aparecer na prosa"),
        (r"tab:gov_instruments",
         "Tab. 8 antiga (tab:gov_instruments) ainda referida"),
    ]
    for rx, why in gov_fail:
        for m in re.finditer(rx, t, re.I):
            add("FAIL", 6, "governança", f"{why}: {ctx(t, m, 40)}")


# ══════════════════════════════════════════════════════════════════════════════
# RHETORIC CHECK  (item 5)
# ══════════════════════════════════════════════════════════════════════════════

RHETORIC_FAIL_PDF = [  # checked against CLEAN PDF text
    (5, r"recursive training crisis",
     "termo eliminado (R1 #10) — use 'failures' or 'concern' without 'crisis'"),
    (5, r"structural paradox|structurally (?:invisible|blind|identical|significant|exceed)"
        r"|structural (?:bifurcation|amplification|asymmetry|property|risk at the model)\b",
     "'structural*' fora do sentido definido em §5.4 'structural vulnerability'"),
    (5, r"directly poisons|is not incidental|closing a feedback loop in which",
     "laço causal afirmado sem evidência empírica (R1 #8)"),
    (5, r"confirms the hypothesi[sz]ed pathway|confirms.{0,40}structural",
     "modelo estilizado não confirma via empírica"),
    (5, r"drives four measurable|four measurable transformations",
     "Xu 2025a é observacional, não confirma 'drives'"),
    (5, r"perceive active degradation|skill deterioration reported",
     "survey mede preocupação, não deterioração observada"),
    (5, r"routinely upload unpublished data",
     "não sustentado por Nordling — remover ou citar literalmente"),
    (5, r"institutional adoption of AI tools that have not been formally",
     "definição errada de shadow AI (uso não sancionado, não 'institutional adoption')"),
    (5, r"inherited wholesale|inherits all the.{0,40}vulnerabilit",
     "absoluto sem fonte"),
    (5, r"\[E\s*\+\s*C\]",
     "rótulo [E+C] definido e nunca usado — remover"),
    (5, r"correspond to Stage.?B knowledge collapse in the generating",
     "Zhou não mede Stage B"),
    (5, r"has consistently found that the distance.{0,60}grows",
     "atribuição indevida a Amodei"),
    (5, r"There is no verification framework that is neutral",
     "absoluto; substituir por [C]"),
    (5, r"self-amplifying systemic condition",
     "não demonstrado; remover ou marcar [C]"),
]

_STRUCTURAL_OK = re.compile(
    r"structural vulnerabilit|structurally\s+\w+\s+(?:behaviour|format|behavior)",
    re.I
)

def check_rhetoric(pdf_text_content):
    """Item 5: rhetoric calibration checks on the CLEAN PDF."""
    t = pdf_text_content
    for item, rx, why in RHETORIC_FAIL_PDF:
        for m in list(re.finditer(rx, t, re.I))[:3]:
            add("FAIL", item, "retórica", f"{why}: {ctx(t, m, 40)}")

    # structural* outside the defined sense
    for m in re.finditer(r"\bstructural(?:ly)?\b", t, re.I):
        window = t[max(0, m.start()-80): m.start()+80]
        if not _STRUCTURAL_OK.search(window):
            # Only WARN, not FAIL (many legitimate uses remain during cleanup)
            add("WARN", 5, "structural-scope",
                f"'structural*' possibly outside defined sense: {ctx(t, m, 40)}")
            break  # Only report first to avoid flood

    # Strong verbs without [T] in window
    for m in re.finditer(
            r"\b(?:demonstrat(?:e|es|ed)|confirm(?:s|ed)?(?!\s+to\s+))\b", t, re.I):
        window = t[m.start(): m.start() + 200]
        if not re.search(r"\[T\]|Theorem|\bprove", window, re.I):
            add("WARN", 5, "verbo-forte",
                f"'demonstrates/confirms' without [T] nearby: {ctx(t, m, 50)}")


# ══════════════════════════════════════════════════════════════════════════════
# METHOD COHERENCE CHECK  (item 4)
# ══════════════════════════════════════════════════════════════════════════════

METHOD_FAIL_PDF = [  # checked against CLEAN PDF text
    (4, r"κ\s*=\s*0\.[0-9]|inter-rater|Cohen'?s? kappa",
     "κ / inter-rater agreement in PDF (B2) — remove from Conclusion"),
    (4, r"gold validation set",
     "internal term 'gold validation set' — use §7.4 with \\Nvalset macro"),
    (4, r"scope comparison is under preparation|under preparation\.",
     "§1.2 incomplete — must have Related Reviews table with no \\warn{4}"),
    (4, r"(?<!\w)see protocol\b|update search",
     "reference to internal protocol — remove from manuscript"),
    (9, r"No custom software was developed",
     "search scripts exist (item 9) — update Code availability"),
]

SOURCES_EXPECTED = ("Scopus", "IEEE", "OpenAlex", "arXiv", "OpenReview")

def check_method(pdf_text_content):
    """Item 4: verify method coherence in the compiled CLEAN PDF."""
    t = pdf_text_content
    for item, rx, why in METHOD_FAIL_PDF:
        for m in list(re.finditer(rx, t, re.I))[:3]:
            add("FAIL", item, "method", f"{why}: {ctx(t, m, 40)}")

    # Each source must appear at least twice (§1.1 and A1)
    for base in SOURCES_EXPECTED:
        n = len(re.findall(re.escape(base), t))
        if n < 2:
            add("WARN", 4, "method-bases",
                f"{base} appears {n}× in PDF (expected ≥ 2: §1.1 and A1)")

    # Method limitations must NOT be repeated in the Conclusion
    concl_idx = t.rfind("Conclusion")
    if concl_idx > 0:
        concl = t[concl_idx:concl_idx + 6000]
        if re.search(r"single reviewer|one author carried out", concl, re.I):
            add("WARN", 4, "method-duplication",
                "method limitation (single reviewer) repeated in Conclusion")


# ══════════════════════════════════════════════════════════════════════════════
# FORMAL COHERENCE CHECK  (item 3)
# ══════════════════════════════════════════════════════════════════════════════

# Patterns that this item must eliminate from the .tex source.
# Checked against stripped-comment text; \deleted{} blocks are excluded.
FORMAL_FAIL = [
    (r"\bonly if\b",
     "only-if (Xu gives sufficiency; necessity established only for constant sample)"),
    (r"every formal bound|ceases to apply",
     "absolute anchor claim (B4) — use new §3.6 text"),
    (r"Every mitigation with\s+a formal guarantee",
     "absolute anchor claim in Abstract (B4)"),
    (r"degradation is guaranteed under full replacement(?! with a fixed)",
     "missing 'with a fixed sample size'"),
    (r"Theorem~?6 of~?\\cite\{xu2025",
     "wrong Xu theorem number — should be Theorem~3 (growth condition)"),
    (r"fraction-\$?k",
     "symbol k undefined (§4.2) — paraphrase as 'poisoned share'"),
    (r"single model family",
     "TCE: two model families (LLaMA-3.2-1B and Gemma-3); update §3.2"),
    (r"rate determined by the magnitude of the bias",
     "Yi et al.: bias sets the long-run limit, not the rate of convergence"),
    (r"six primary(?! strategies and one).*strateg",
     "count mismatch (B10) — 5 strategies + 1 instrument + 2 qualifying findings"),
    (r"alongside the \\added\{six\}",
     "watermarking §: 'six' → 'five'"),
    (r"uniform-on-support for.*T_\{\\mathrm\{s\}\}\{=\}1",
     "Marchi (B5): T_s=1 → finite drift (martingale), not uniform-on-support"),
    (r"\\sum_\{t=1\}\^\{N\}.*log p.*x_t",
     "Eq.(3) uses N/t — change to L/ℓ"),
    (r"\\label\{subsec:random_walk\}",
     "§2.5 should be merged into Result~5 (remove subsection)"),
    (r"\\textbf\{Agreement on pure-synthetic",
     "§2.6: title should specify 'with a fixed sample size'"),
    (r"contraction mapping property\\warn\{3\}",
     "contraction mapping is confirmed in Yi et al. — remove \\warn{3}"),
]

def _strip_deleted(src):
    """Remove \\deleted{...} blocks (handles up to 2 nesting levels)."""
    out = re.sub(r"\\deleted\{(?:[^{}]|\{[^{}]*\})*\}", "", src)
    return re.sub(r"\\deleted\{(?:[^{}]|\{[^{}]*\})*\}", "", out)

def check_formal():
    """Item 3: verify that formal-coherence anti-patterns are absent."""
    for f in tex_files():
        src = strip_comments(rd(f))
        src = _strip_deleted(src)
        for rx, why in FORMAL_FAIL:
            for m in re.finditer(rx, src, re.I):
                line = src[:m.start()].count("\n") + 1
                add("FAIL", 3, "formal",
                    f"{f.name}:{line} — {why}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Gate verifier for COSREV-D-26-01510")
    ap.add_argument("--compare", metavar="OLD.pdf",
                    help="Compare new clean PDF vs OLD.pdf; write sync-diff.txt")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 if FINAL mode compiles without error (submission gate)")
    args = ap.parse_args()

    commit = git("rev-parse", "--short", "HEAD") or "nocommit"
    if git("status", "--porcelain"):
        commit += "-dirty"
        add("WARN", 1, "git-dirty", "working tree has uncommitted changes")

    # Build all three modes
    ok = {}
    pdf_txt = ""  # will be populated after PDF checks below
    for mode in ("marked", "clean", "final"):
        job, ok[mode], tail = build(mode, commit)
        if not ok[mode] and mode != "final":
            lines = (tail.strip().splitlines() or ["error"])
            add("FAIL", 1, f"build:{mode}", lines[-1])
        check_log(job, mode)

    # Source check
    n_src = check_sources()

    # Formal coherence check (item 3)
    check_formal()

    # Method coherence check (item 4)
    if pdf_txt:
        check_method(pdf_txt)

    # Rhetoric check (item 5)
    if pdf_txt:
        check_rhetoric(pdf_txt)

    # Governance check (item 6)
    if pdf_txt:
        check_governance(pdf_txt)

    # Conclusion / abstract check (item 7)
    if pdf_txt:
        check_conclusion(pdf_txt)

    # Submission readiness check (item 9)
    if pdf_txt:
        check_submission(pdf_txt)

    # PDF checks (clean mode)
    clean_pdf = MSDIR / f"{MAIN}-clean.pdf"
    pdf_txt = ""
    if clean_pdf.exists():
        pdf_txt = check_pdf(str(clean_pdf), commit)
        check_bib_s1(f"{MAIN}-clean", pdf_txt)
    else:
        add("FAIL", 1, "clean-pdf-missing", str(clean_pdf))

    if args.compare:
        sync_diff(args.compare, str(clean_pdf))

    # Reconcile flag count (source vs log)
    n_pend_log = sum(1 for f in FINDINGS if f[0] == "PEND")
    if n_pend_log != n_src:
        add("WARN", 1, "flag-count-mismatch",
            f"source={n_src} vs log={n_pend_log} "
            f"(possible double-count in caption, or flag inside \\deleted)")

    # ── Report ───────────────────────────────────────────────────────────────
    by_item = defaultdict(list)
    for lv, it, ch, de in FINDINGS:
        by_item[it].append((lv, ch, de))

    def sort_key(x):
        return (not x.isdigit(), int(x) if x.isdigit() else 0)

    for it in sorted(by_item, key=sort_key):
        print(f"\n=== item {it} ===")
        for lv, ch, de in sorted(by_item[it]):
            print(f"  [{lv:4}] {ch}: {de}")

    out_json = ROOT / "verify-report.json"
    out_json.write_text(
        json.dumps(FINDINGS, ensure_ascii=False, indent=1), encoding="utf-8")

    n_fail = sum(f[0] == "FAIL" for f in FINDINGS)
    n_pend = sum(f[0] == "PEND" for f in FINDINGS)
    final_ok = ok.get("final", False)

    print(f"\n{'='*60}")
    print(f"FAIL={n_fail}  PEND={n_pend}  "
          f"build={commit}  "
          f"FINAL={'compiles (pending-flag broken!)' if final_ok else 'blocked (correct)'}")

    if n_fail or (args.strict and final_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
