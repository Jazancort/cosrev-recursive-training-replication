# -*- coding: utf-8 -*-
"""check_dupes_and_breaks.py
usage: uv run python v2/references/scripts/check_dupes_and_breaks.py sn-article.tex [clean.txt]
Generate clean.txt with: pdftotext -layout sn-article.pdf sn-article-clean.txt
"""
import re, sys, pathlib

tex_path = pathlib.Path(sys.argv[1])
tex = tex_path.read_text(encoding="utf-8").splitlines()

# ── 1) Blank lines inside tabular or \added ──────────────────────────────
depth_tab, depth_add = 0, 0
for n, line in enumerate(tex, 1):
    s = line.strip()
    if s.startswith('%'):
        continue
    depth_tab += len(re.findall(r"\\begin\{tabular\*?\}", line)) \
               - len(re.findall(r"\\end\{tabular\*?\}", line))
    if "\\added{" in line:
        depth_add += line.count("{") - line.count("}")
    elif depth_add > 0:
        depth_add += line.count("{") - line.count("}")
        depth_add = max(depth_add, 0)
    if not s and (depth_tab > 0 or depth_add > 0):
        ctx = "tabela" if depth_tab > 0 else "\\added"
        print(f"[BLANK] L{n}: linha em branco dentro de {ctx}")

# ── 2) N-gram duplicate check in PDF text ───────────────────────────────
if len(sys.argv) > 2:
    txt = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8", errors="ignore")
    words = re.findall(r"[A-Za-z][A-Za-z\-']+", txt)
    seen, N, W = {}, 7, 120
    for i in range(len(words) - N):
        g = " ".join(w.lower() for w in words[i:i+N])
        if g in seen and i - seen[g] < W:
            dist = i - seen[g]
            ctx = " ".join(words[i:i+N])
            print(f"[DUP] '{ctx}' (distância {dist} palavras)")
        seen[g] = i
else:
    print("[INFO] Sem ficheiro .txt do PDF — só verificação de linhas em branco")
