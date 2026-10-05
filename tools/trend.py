#!/usr/bin/env python3
"""The problems logged by check.py and run.py over time (reference
section 11).

    python3 tools/trend.py [--root DIR] [--log FILE] [--by DIM[,DIM]] [--top N]

Reads .edda/checks.log in the project (--root, Edda's own when not
named; EDDA_LOG when it names a file, or --log; --root with --log must
name the same log, and .edda must resolve inside the root) and
prints the problems per day, the counts grouped by one dimension or a
pair (category when --by names none), and the rules that come up most.
A dimension is one of category, sub, fix, acts, level, where, found_by.
Every line is checked before it is counted: a line that is not JSON or
not a valid record (a field missing or of the wrong type, a date not in
the log's format, a dimension value the registry does not allow) is
skipped, and one line says how many were. No output line is ever cut:
one that would pass 79 characters goes on over indented lines.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watch    # noqa: E402

WIDTH = 79
DATE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")


def text(v):
    return isinstance(v, str) and v != ""


def dated(v):
    """a date as the log writes it: local time with its offset, to the
    second"""
    if not (isinstance(v, str) and DATE.match(v)):
        return False
    try:
        datetime.datetime.fromisoformat(v)
    except ValueError:
        return False
    return True


def valid(p):
    """whether p is a log record: every field of watch.FIELDS of the right
    type, and each dimension a value the registry allows"""
    if not isinstance(p, dict) or any(k not in p for k in watch.FIELDS):
        return False
    rules, allowed = watch.registry()
    subs = {r["sub"] for r in rules.values()}
    line = p["line"]
    return (dated(p["date"]) and text(p["rule"]) and text(p["file"])
            and text(p["commit"])
            and (line is None or (type(line) is int and line >= 1))
            and isinstance(p["sub"], str) and p["sub"] in subs
            and all(isinstance(p[d], str) and p[d] in allowed.get(d, ())
                    for d in watch.DIMENSIONS if d != "sub"))


def read(path, root=None):
    """the logged problems, and how many lines were skipped: not JSON, or
    not a valid record; root, when given, the project the log must resolve
    inside as it is opened (check.open_inside raises Outside)"""
    problems, bad = [], 0
    if root is None:
        f = open(path)
    else:
        from check import open_inside
        f = os.fdopen(open_inside(root, path))
    with f:
        for line in f:
            if not line.strip():
                continue
            try:
                p = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if valid(p):
                problems.append(p)
            else:
                bad += 1
    return problems, bad


def counted(problems, key):
    """(count, label) for each value of key, most first, then by label"""
    counts = {}
    for p in problems:
        counts[key(p)] = counts.get(key(p), 0) + 1
    return sorted(((n, label) for label, n in counts.items()),
                  key=lambda x: (-x[0], x[1]))


def wrap(head, text, indent=None):
    """head then text, on as many lines as it takes, none over WIDTH and
    nothing left out: each line after the first starts with indent (as
    many spaces as head when none is given), and a break goes after a
    comma if it can, else at a space, else inside a word"""
    indent = " " * len(head) if indent is None else indent
    out, start = [], head
    while len(start) + len(text) > WIDTH:
        room = WIDTH - len(start)
        comma = text.rfind(", ", 0, room + 1)
        space = text.rfind(" ", 0, room + 1)
        if comma > 0:
            piece, text = text[:comma + 1], text[comma + 2:]
        elif space > 0:
            piece, text = text[:space], text[space + 1:]
        else:
            piece, text = text[:room], text[room:]
        out.append(start + piece)
        start = indent
    return out + [start + text]


def lines(rows):
    """'  <count>  <label>' for each row, a long label going on over lines
    indented under it"""
    w = max((len(str(n)) for n, _ in rows), default=1)
    return [s for n, label in rows for s in wrap(f"  {n:>{w}}  ", label)]


def trend(problems, by, top):
    """the report as lines"""
    days = sorted({p["date"][:10] for p in problems})
    out = [f"{len(problems)} problems logged, {days[0]} to {days[-1]}", "",
           "per day:"]
    for day in days:
        on = [p for p in problems if p["date"][:10] == day]
        out += wrap(f"  {day}  {len(on):>5}  ", watch.count_line(on))
    out += ["", "by " + " x ".join(by) + ":"]
    out += lines(counted(problems,
                         lambda p: " x ".join(str(p[d]) for d in by)))
    out += ["", "rules that come up most:"]
    out += lines(counted(problems, lambda p: p["rule"])[:top])
    return out


def say(head, text):
    """print head then text, wrapped as wrap does"""
    print("\n".join(wrap(head, text, "  ")))


def main(argv):
    ap = argparse.ArgumentParser(
        description="the logged problems over time")
    ap.add_argument("--log", help="the log (default .edda/checks.log, "
                                  "or EDDA_LOG)")
    ap.add_argument("--root", help="the project whose log is read: the folder "
                                   "holding edda.yaml (default Edda's own)")
    ap.add_argument("--by", default="category",
                    help="one dimension or two, by a comma: where,fix")
    ap.add_argument("--top", type=int, default=10,
                    help="how many rules to list (default 10)")
    a = ap.parse_args(argv)
    by = [d.strip() for d in a.by.split(",")]
    wrong = [d for d in by if d not in watch.DIMENSIONS]
    if not 1 <= len(by) <= 2 or wrong:
        say("--by takes one dimension or two of: ",
            ", ".join(watch.DIMENSIONS))
        return 2
    root = os.path.abspath(a.root or watch.ROOT)
    import settings     # the log folder stays inside the root (section 9)
    outside = settings.log_outside(root)
    if outside is not None:
        print(outside)
        return 1
    if a.root is not None and a.log is not None and \
            os.path.realpath(a.log) != os.path.realpath(os.path.join(root, ".edda", "checks.log")):
        print(f"--root {a.root} and --log {a.log} name two logs; give one")
        return 2
    path = a.log or watch.log_file(root)
    if path is None:
        print("the log is off (EDDA_LOG=off); name one with --log")
        return 2
    if not os.path.exists(path):
        say("nothing logged yet: ", os.path.relpath(path))
        return 0
    if a.log is None and not os.environ.get("EDDA_LOG", "") or a.root is not None and a.log is not None:
        from check import Outside       # the root's own log, not one the operator named alone
        try:
            problems, bad = read(path, root)
        except Outside as o:
            print(f"{os.path.relpath(path)}: outside_root: the log resolves outside the project root: {o.args[0]}")
            return 1
    else:
        problems, bad = read(path)
    if bad:
        print(f"{bad} lines of the log skipped: not JSON or not a valid "
              "record")
    if not problems:
        say("nothing logged yet: ", os.path.relpath(path))
        return 0
    print("\n".join(trend(problems, by, a.top)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
