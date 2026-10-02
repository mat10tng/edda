#!/usr/bin/env python3
"""Generate language/keywords.yaml from the tables in reference.md."""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
md = open(f"{ROOT}/language/reference.md").read()


def q(s):
    s = s.replace("`", "").strip()
    return "'" + s.replace("'", "''") + "'"


def tables(text):
    """yield (section title, header, rows) for every markdown table"""
    section = None
    rows, header = [], None
    for line in text.splitlines() + [""]:
        m = re.match(r"^##+ \d+(\.\d+)?\. (.*)", line)
        if m:
            section = m.group(2).strip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r"-+", c) for c in cells):
                continue
            if header is None:
                header = cells
            else:
                rows.append(cells)
        else:
            if header:
                yield section, header, rows
            rows, header = [], None


keys, forms, words, rules, flags, kinds, styles = [], [], [], [], [], [], []
for section, header, rows in tables(md):
    if header[:3] == ["key", "means", "why"]:
        for r in rows:
            for k in re.findall(r"`([a-z_]+:)`", r[0]):
                keys.append((k, section, r[1], r[2]))
    elif header[:3] == ["form", "means", "from"]:
        for r in rows:
            forms.append((r[0], r[1], r[2]))
    elif header[:3] == ["word", "means", "from"]:
        for r in rows:
            for w in re.findall(r"`([A-Z_ ]+)`", r[0]):
                words.append((w, r[1], r[2]))
    elif header[:3] == ["meaning", "the one way", "not"]:
        for r in rows:
            styles.append((r[0], r[1], r[2]))
    elif header[:3] == ["rule", "when", "message"]:
        target = rules if not rules else flags
        for r in rows:
            target.append((r[0], r[1], r[2]))
    elif header[:2] == ["kind", "template"]:
        for r in rows:
            kinds.append((r[0], r[1]))

# the two rule tables come in order: refusals then flags

out = ["# Edda keyword registry, generated from language/reference.md (revision 30).",
       "# Plain YAML, not a spec file: the .edda subset does not apply here.",
       "# Every key, expression form, style rule, fixed name, checker rule and",
       "# read-view sentence kind, with what it means, why it exists and where it",
       "# comes from. The checker refuses any key not in schema.json, any form not",
       "# here and any second way 7.2 names. Hover text in the views comes",
       "# from means and why. A new entry is added like a rule, with a because.",
       "", "keys:"]
for k, s, m, w in keys:
    out += [f"  - key: {q(k)}", f"    section: {q(s)}", f"    means: {q(m)}", f"    why: {q(w)}"]
out += ["", "forms:"]
for f, m, s in forms:
    out += [f"  - form: {q(f)}", f"    means: {q(m)}", f"    from: {q(s)}"]
out += ["", "one_way:"]
for m, w, n in styles:
    out += [f"  - meaning: {q(m)}", f"    write: {q(w)}", f"    not: {q(n)}"]
out += ["", "words:"]
for w, m, s in words:
    out += [f"  - word: {q(w)}", f"    means: {q(m)}", f"    from: {q(s)}"]
out += ["", "refusals:"]
for r, w, m in rules:
    out += [f"  - rule: {q(r)}", f"    when: {q(w)}", f"    message: {q(m)}"]
out += ["", "flags:"]
for r, w, m in flags:
    out += [f"  - rule: {q(r)}", f"    when: {q(w)}", f"    message: {q(m)}"]
out += ["", "sentences:"]
for k, t in kinds:
    out += [f"  - kind: {q(k)}", f"    template: {q(t)}"]
open(f"{ROOT}/language/keywords.yaml", "w").write("\n".join(out) + "\n")
print(len(keys), "keys", len(forms), "forms", len(styles), "style rules", len(words), "words", len(rules), "refusals", len(flags), "flags", len(kinds), "sentence kinds")
