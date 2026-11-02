# -*- coding: utf-8 -*-
"""reconcile_sources.py
usage: uv run python v2/references/scripts/reconcile_sources.py v1.aux v1.bib v2.aux v2.bib
"""
import re, sys, unicodedata, pathlib

def keys(aux_path):
    txt = pathlib.Path(aux_path).read_text(encoding="utf-8", errors="ignore")
    # .aux: \\citation{key1,key2}
    # .tex: \\cite*{key1,key2}
    suffix = pathlib.Path(aux_path).suffix.lower()
    if suffix == ".tex":
        pat = r"\\cite\w*\{([^}]+)\}"
    else:
        pat = r"\\citation\{([^}]+)\}"
    return set(k.strip() for m in re.findall(pat, txt) for k in m.split(","))

def titles(bib_path):
    out = {}
    txt = pathlib.Path(bib_path).read_text(encoding="utf-8", errors="ignore")
    for k, body in re.findall(r"@\w+\s*\{([^,\s]+)\s*,(.*?)\n\}", txt, re.S):
        m = re.search(r"title\s*=\s*[{\"](.+?)[}\"]\s*,", body, re.S | re.I)
        t = unicodedata.normalize("NFKD", m.group(1) if m else "").encode("ascii", "ignore").decode().lower()
        out[k.strip()] = re.sub(r"[^a-z0-9]", "", t)[:60]
    return out

k1  = keys(sys.argv[1])
k2  = keys(sys.argv[3])
t1  = titles(sys.argv[2])
t2  = titles(sys.argv[4])
inv2 = {v: k for k, v in t2.items() if k in k2}

same    = k1 & k2
renamed = {k: inv2[t1[k]] for k in k1 - k2 if t1.get(k) and t1[k] in inv2}
removed = k1 - k2 - set(renamed)

print(f"\nv1 citadas:  {len(k1)}")
print(f"mesma chave: {len(same)}")
print(f"renomeadas:  {len(renamed)}")
print(f"removidas:   {len(removed)}")
print(f"\n=> texto: 'Of the {len(k1)} sources, {len(same)} are retained, {len(renamed)} replaced "
      f"by published/corrected versions, and {len(removed)} removed'")

if renamed:
    print("\nRenomeadas/actualizadas:")
    for a, b in sorted(renamed.items()):
        print(f"  {a} → {b}")
if removed:
    print("\nRemovidas:")
    for k in sorted(removed):
        print(f"  - {k}")
