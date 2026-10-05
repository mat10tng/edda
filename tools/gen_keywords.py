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


keys, forms, words, rules, flags, failures, kinds = [], [], [], [], [], [], []
dims, fixed = {}, {}        # dimension -> allowed values; rule -> its fixed dimensions
for section, header, rows in tables(md):
    if header[:3] == ["key", "means", "why"]:
        for r in rows:
            for k in re.findall(r"`([a-z_]+:)`", r[0]):
                keys.append((k, section, r[1], r[2]))
    elif header[:4] == ["key", "section", "means", "why"]:     # keys inside keys, tagged with their section
        for r in rows:
            for k in re.findall(r"`([a-z_]+:)`", r[0]):
                keys.append((k, r[1], r[2], r[3]))
    elif header[:3] == ["form", "means", "from"]:
        for r in rows:
            forms.append((r[0], r[1], r[2]))
    elif header[:3] == ["word", "means", "from"]:
        for r in rows:
            for w in re.findall(r"`([A-Z_ ]+)`", r[0]):
                words.append((w, r[1], r[2]))
    elif header[:3] == ["rule", "when", "message"]:
        target = rules if not rules else flags if not flags else failures
        for r in rows:
            target.append((r[0], r[1], r[2]))
    elif header[:3] == ["dimension", "values", "set by"]:
        for r in rows:
            dims[r[0]] = re.findall(r"`([^`]+)`", r[1])
    elif header[:6] == ["rule", "went wrong", "sub", "fix", "acts", "level"]:
        for r in rows:
            fixed[r[0].strip("`")] = dict(zip(("category", "sub", "fix", "acts", "level"), r[1:6]))
    elif header[:2] == ["kind", "template"]:
        for r in rows:
            kinds.append((r[0], r[1]))

# the three rule tables come in order: refusals, flags, then the runner's failures

# every rule has its four fixed dimensions, each an allowed value (section 11)
ALLOWED = {"category": "what went wrong", "fix": "fix", "acts": "acts", "level": "level"}
named = [r[0].strip("`") for r in rules + flags + failures]
wrong = [f"no dimensions for {r}" for r in named if r not in fixed]
wrong += [f"dimensions for no rule: {r}" for r in fixed if r not in named]
wrong += [f"{r}: {d} {v[d]!r} is not one of {dims.get(ALLOWED[d])}" for r, v in fixed.items()
          for d in ALLOWED if v[d] not in dims.get(ALLOWED[d], [])]
wrong += [f"{r}: no sub" for r, v in fixed.items() if not v["sub"]]
if wrong:
    raise SystemExit("keywords.yaml not written:\n  " + "\n  ".join(wrong))


KEY = {"what went wrong": "category", "found by": "found_by"}   # the registry's key for a dimension


def dimensions(r):
    return [f"    {d}: {q(v)}" for d, v in fixed[r.strip("`")].items()]


REV = re.search(r"^Revision (\d+)", md, re.M).group(1)
out = [f"# Edda keyword registry, generated from language/reference.md (revision {REV}).",
       "# Plain YAML, not a spec file: the .edda subset does not apply here.",
       "# Every key, expression form, fixed name, checker rule and read-view",
       "# sentence kind, with what it means, why it exists and where it comes",
       "# from. The checker refuses any key not in schema.json and any form not",
       "# here. Hover text in the views comes from means and why. A new row is",
       "# added like a rule, with a because. Each rule, the runner's failures",
       "# included, carries its fixed dimensions (category, sub, fix, acts,",
       "# level); dimensions lists the values each may take.",
       "", "keys:"]
for k, s, m, w in keys:
    out += [f"  - key: {q(k)}", f"    section: {q(s)}", f"    means: {q(m)}", f"    why: {q(w)}"]
out += ["", "forms:"]
for f, m, s in forms:
    out += [f"  - form: {q(f)}", f"    means: {q(m)}", f"    from: {q(s)}"]
out += ["", "words:"]
for w, m, s in words:
    out += [f"  - word: {q(w)}", f"    means: {q(m)}", f"    from: {q(s)}"]
out += ["", "refusals:"]
for r, w, m in rules:
    out += [f"  - rule: {q(r)}", f"    when: {q(w)}", f"    message: {q(m)}"] + dimensions(r)
out += ["", "flags:"]
for r, w, m in flags:
    out += [f"  - rule: {q(r)}", f"    when: {q(w)}", f"    message: {q(m)}"] + dimensions(r)
out += ["", "failures:"]
for r, w, m in failures:
    out += [f"  - rule: {q(r)}", f"    when: {q(w)}", f"    message: {q(m)}"] + dimensions(r)
out += ["", "dimensions:"]
for d, values in dims.items():
    out += [f"  - dimension: {q(KEY.get(d, d))}", "    values: [" + ", ".join(q(v) for v in values) + "]"]
out += ["", "sentences:"]
for k, t in kinds:
    out += [f"  - kind: {q(k)}", f"    template: {q(t)}"]
open(f"{ROOT}/language/keywords.yaml", "w").write("\n".join(out) + "\n")
print(len(keys), "keys", len(forms), "forms", len(words), "words", len(rules), "refusals", len(flags), "flags",
      len(failures), "failures", len(dims), "dimensions", len(kinds), "sentence kinds")
