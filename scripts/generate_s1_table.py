# -*- coding: utf-8 -*-
"""generate_s1_table.py
Builds supplementary/src/S1_table.tex from supplementary/S1_cited_sources.csv and
supplementary/src/sn-bibliography.bib. Compile with wrap_S1.tex (xelatex x2).
"""
import csv, re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV  = ROOT / "supplementary" / "S1_cited_sources.csv"
BIB  = ROOT / "supplementary" / "src" / "sn-bibliography.bib"
OUT  = ROOT / "supplementary" / "src" / "S1_table.tex"

def parse_bib(text):
    entries = {}
    for m in re.finditer(r'@\w+\{\s*([^,\s]+),', text):
        key, start = m.group(1), m.end()
        nxt = re.search(r'\n@\w+\{', text[start:])
        body = text[start: start + nxt.start()] if nxt else text[start:]
        fields = {}
        for f in re.finditer(r'(\w+)\s*=\s*', body):
            name, i = f.group(1).lower(), f.end()
            if i >= len(body): continue
            if body[i] == '{':
                depth, j = 0, i
                while j < len(body):
                    depth += (body[j] == '{') - (body[j] == '}')
                    j += 1
                    if depth == 0: break
                val = body[i + 1: j - 1]
            elif body[i] == '"':
                j = body.find('"', i + 1); val = body[i + 1: j]
            else:
                m2 = re.match(r'[^,\n]+', body[i:]); val = m2.group(0).strip()
            fields.setdefault(name, ' '.join(val.split()))
        entries[key] = fields
    return entries

def clean(s, limit=None):
    s = re.sub(r'\\url\{[^}]*\}', '', s)
    if limit and len(s) > limit:
        s = s[:limit].rstrip()
        s = re.sub(r'\\\\[A-Za-z]*$', '', s)
        s += '}' * max(0, s.count('{') - s.count('}')) + '\\ldots{}'
    s = re.sub(r'(?<!\\)([&%#_])', r'\\\1', s)
    return s

def first_author(a):
    if not a: return '(institutional)'
    first = re.split(r'\s+and\s+', a)[0]
    if first.startswith('{') and first.endswith('}'): sur = first[1:-1]
    elif ',' in first: sur = first.split(',')[0]
    else: sur = first.split()[-1]
    more = len(re.split(r'\s+and\s+', a)) > 1
    return clean(sur) + (r' et~al.' if more else '')

def venue(f):
    for k in ('journal', 'booktitle', 'howpublished', 'publisher', 'institution', 'school'):
        if f.get(k): return clean(f[k], 48)
    return '---'

rows = list(csv.DictReader(CSV.open(encoding='utf-8-sig')))
bib = parse_bib(BIB.read_text(encoding='utf-8'))
missing = [r['key'] for r in rows if r['key'] not in bib]
if missing: sys.exit(f"keys missing in bib: {missing}")
rows.sort(key=lambda r: r['key'].lower())
lines = []
for i, r in enumerate(rows, 1):
    f = bib[r['key']]
    cit = f"{first_author(f.get('author', ''))} ({clean(f.get('year', 'n.d.'))}), ``{clean(f.get('title', ''), 80)}''"
    route = r['route'].strip() or '---'
    anchor = 'yes' if route == 'A' else ''
    dag = r'$\dagger$' if r['archival'].strip() == 'N' else ''
    lines.append(f"{i} & \\texttt{{{clean(r['key'])}}} & {cit} & {venue(f)} & {r['category']} & {r['in_orig']} & {route} & {anchor} & {dag} \\\\")
OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f"wrote {OUT} ({len(rows)} rows)")