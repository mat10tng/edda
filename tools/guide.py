#!/usr/bin/env python3
"""Write the agent guide, language/guide.md (reference section 13).

    python3 tools/guide.py [--pointer [--root HOST]]

The guide is generated, never written by hand: every statement in it is
a passage of language/reference.md, found by its section and its first
words, or a sentence of one of Edda's own stories, rendered by the read
view (tools/view.py). Each statement names its source. A passage that
cannot be found stops the script, so the guide cannot drift from the
reference. --pointer prints the one pointer line a host places where
its agents read (section 13), the guide's path in it as the host reads
it: relative to HOST when Edda sits inside or beside it, else absolute;
relative to the current folder without --root. The guide is not
written then.
"""
import argparse
import os
import re
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as checker          # noqa: E402
import view                      # noqa: E402

ROOT = checker.ROOT
REFERENCE = os.path.join(ROOT, "language", "reference.md")
GUIDE = os.path.join(ROOT, "language", "guide.md")
WIDTH = 72


class Missing(Exception):
    """a source the guide needs is not where it should be"""


def section(text, n):
    """the body of section n of the reference"""
    m = re.search(rf"^## {n}\. .*$", text, re.M)
    if not m:
        raise Missing(f"no section {n} in the reference")
    end = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end():m.end() + end.start()] if end else text[m.end():]


def blocks(text, n):
    """the paragraphs and list items of section n, each as one line; code
    blocks and tables are left out"""
    out, cur, fence = [], [], False

    def flush():
        if cur:
            out.append(" ".join(cur))
            cur.clear()
    for line in section(text, n).splitlines():
        bare = line.strip()
        if bare.startswith("```"):
            flush()
            fence = not fence
        elif fence or bare.startswith("|") or not bare:
            flush()
        elif re.match(r"(- |\d+\. )", bare):
            flush()
            cur.append(re.sub(r"^(- |\d+\. )", "", bare))
        else:
            cur.append(bare)
    flush()
    return out


def paragraph(text, n, start):
    """the paragraph or list item of section n that starts with start"""
    found = next((b for b in blocks(text, n) if b.startswith(start)), None)
    if found is None:
        raise Missing(f"no passage starting {start!r} in section {n}")
    return found


def sentences(text, n, start, count=1):
    """count sentences of one paragraph or list item of section n, from
    the one that starts with start"""
    found = next((b for b in blocks(text, n) if start in b), None)
    if found is None:
        raise Missing(f"no sentence starting {start!r} in section {n}")
    parts = re.split(r"(?<=\.)\s+(?=[A-Z`*])", found[found.index(start):])
    return " ".join(parts[:count])


def fenced_after(text, n, start):
    """the lines of the first fenced block after start in section n"""
    body = section(text, n)
    at = body.find(start)
    m = re.search(r"```\n(.+?)\n\s*```", body[at:], re.S) if at >= 0 else None
    if not m:
        raise Missing(f"no fenced block after {start!r} in section {n}")
    return [line.strip() for line in m.group(1).splitlines()]


def table_rows(text, n, header):
    """the rows of the table of section n whose header row is header"""
    lines = section(text, n).splitlines()
    for i, line in enumerate(lines):
        if line.startswith("|") and [c.strip() for c in line.strip("|").split("|")] == header:
            rows = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip("|").split("|")])
            return rows
    raise Missing(f"no table {header} in section {n}")


def wrap(text, indent=""):
    return textwrap.wrap(text, WIDTH, initial_indent=indent, subsequent_indent=indent,
                         break_long_words=False, break_on_hyphens=False)


def story_lines(model, sid, kinds=("story",)):
    """the read view's sentences of story sid, of the kinds named"""
    st = next((s for s in model["stories"] if s["id"] == sid), None)
    if st is None:
        raise Missing(f"no story {sid} in specs/")
    return [s["text"] for s in view.story_sentences(st, model["operations"], model["entities"], model["roles"])
            if s["kind"] in kinds]


def reference():
    with open(REFERENCE) as f:
        return f.read()


def guide_path(root=None):
    """the guide's path as the host at root reads it (section 13):
    relative to root when Edda's repository is inside root or beside it
    (the same folder holds both), else absolute; relative to the current
    folder when root is None"""
    path = os.path.realpath(GUIDE)
    if root is None:
        return os.path.relpath(path, os.path.realpath(os.getcwd()))
    host, edda = os.path.realpath(root), os.path.realpath(ROOT)
    near = edda == host or edda.startswith(host.rstrip(os.sep) + os.sep) or \
        os.path.dirname(edda) == os.path.dirname(host)
    return os.path.relpath(path, host) if near else path


def pointer(root=None):
    """the pointer line, as section 13 gives it, with the guide's path"""
    line = fenced_after(reference(), 13, "**The pointer line**")[0]
    if "<guide>" not in line:
        raise Missing("no <guide> in the pointer line of section 13")
    return line.replace("<guide>", guide_path(root))


def guide():
    """the text of language/guide.md"""
    text = reference()
    revision = re.search(r"^Revision (\d+)", text, re.M).group(1)
    model = checker.model_of(os.path.join(ROOT, "specs"))
    out = []

    def para(words):
        out.extend(wrap(words) + [""])

    def quote(words, source):
        out.extend(wrap(words, "> ") + [">"] + wrap(f"-- {source}", "> ") + [""])

    def code(lines):
        out.extend(["```"] + lines + ["```", ""])

    def told(sid, kinds=("story",)):
        for line in story_lines(model, sid, kinds):
            quote(line, f"story {sid}, as the read view says it")

    out += ["# The Edda guide", ""]
    para(f"Generated by tools/guide.py from Edda's own stories and the "
         f"language reference, revision {revision}. Do not edit it; run "
         f"python3 tools/guide.py to write it again. Each passage names "
         f"its source.")

    out += ["## For agents", ""]
    out += ["### Write the stories from the customer's words", ""]
    quote(paragraph(text, 1, "**Who writes, who reads.**"), "reference section 1")
    quote(sentences(text, 10, "`.edda` is current; the agent edits it."), "reference section 10")

    out += ["### Never write a .edda.vc", ""]
    quote(sentences(text, 10, "`.edda` is current; the agent edits it.", 2)
          .split(". ", 1)[1], "reference section 10")
    told("EDDA-005", ("story", "note"))

    out += ["### Run the check and act on who acts", ""]
    quote(paragraph(text, 13, "**`edda.yaml`** at its root"), "reference section 13")
    code(fenced_after(text, 13, "**`edda.yaml`** at its root"))
    quote(sentences(text, 13, "An agent runs the check after each change"), "reference section 13")
    told("EDDA-001")
    quote(sentences(text, 11, "`acts`: `agent`, the agent fixes it alone;"), "reference section 11")
    person = [r[0] for r in table_rows(text, 11, ["rule", "went wrong", "sub", "fix", "acts", "level"])
              if r[4] == "person"]
    out += wrap("Rules a person acts on, from the table of dimensions "
                "(reference section 11): " + ", ".join(person) + ".") + [""]

    out += ["### Mark the code that does a story", ""]
    quote(sentences(text, 9, "The code carries `# <STORY-ID>@<n>`", 2), "reference section 9")

    out += ["### Done", ""]
    quote(paragraph(text, 11, "**Done.**"), "reference section 11")

    out += ["## For people", ""]
    told("EDDA-004")
    told("EDDA-007")
    told("EDDA-006")
    quote(sentences(text, 13, "The operator approves with"), "reference section 13")
    quote(paragraph(text, 13, "**The pointer line**"), "reference section 13")
    quote(paragraph(text, 13, "Where it goes is the host's choice"), "reference section 13")

    body = "\n".join(out).rstrip("\n") + "\n"
    wide = [line for line in body.splitlines() if len(line) >= 80]
    if wide:
        raise Missing(f"a line of 80 characters or more: {wide[0]}")
    if not body.isascii():
        raise Missing("the guide is not ASCII: " + next(line for line in body.splitlines() if not line.isascii()))
    return body


def main(argv):
    ap = argparse.ArgumentParser(description="write language/guide.md, or print the pointer line")
    ap.add_argument("--pointer", action="store_true", help="print the pointer line; write nothing")
    ap.add_argument("--root", help="with --pointer: the host, which the guide's path is given for")
    a = ap.parse_args(argv)
    if a.root is not None and not a.pointer:
        print("--root goes with --pointer")
        return 2
    if a.root is not None and not os.path.isdir(a.root):
        print(f"no such folder: {a.root}")
        return 1
    try:
        if a.pointer:
            print(pointer(a.root))
            return 0
        text = guide()
    except Missing as e:
        print(f"guide not written: {e}")
        return 1
    with open(GUIDE, "w") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(GUIDE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
