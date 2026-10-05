"""Watching problems (reference section 11, revision 67): the six
dimensions of each problem, the count line and the local log.

Four dimensions are fixed per rule in language/keywords.yaml (category,
sub, fix, acts, level); where is computed from the problem's line and
found by is set by the tool. check.py and run.py append one JSON line
per problem to <project>/.edda/checks.log, the project being the folder
that holds the specs folder; EDDA_LOG=off turns that off and EDDA_LOG=
<file> writes there instead. Writing the log never changes output or an
exit code; the default log is written only if it resolves inside the
project (settings.py, outside_root), else one line on stderr says it was
not written. tools/trend.py reads the log.
"""
import datetime
import json
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXED = ("category", "sub", "fix", "acts", "level")
FIELDS = ("date", "rule", "file", "line") + FIXED + ("where", "found_by", "commit")
DIMENSIONS = FIXED + ("where", "found_by")      # what trend.py groups by

# found by, for the checker's rules; every other checker rule is found by reading
HISTORY = {"bad_version", "bad_pin", "bad_snapshot", "wording_drift", "question_on_approved",
           "stale_link", "unapproved_link"}
ANALYSER = {"dead_refusal", "conflicting_ensure", "empty_ensure", "forbidden_change"}

# where in the spec, from the path of the line in a .edda (the keys of schema.json)
ENTITY_PLACES = {"properties": "entity property", "may_change": "status rules", "always": "always",
                 "may_create": "permissions", "may_read": "permissions", "may_update": "permissions",
                 "may_delete": "permissions"}
OPERATION_PLACES = {"who": "operation who", "refuse": "refuse", "ensure": "ensure", "also_changes": "ensure",
                    "returns": "returns", "ordered_by": "returns"}
EXAMPLE_PLACES = {"given": "example given", "steps": "example step"}
LANGUAGE_TAG = re.compile(r"#\s*edda:\s*language\s*$")

_REGISTRY = []


def registry():
    """(rule -> its fixed dimensions, dimension -> its allowed values), from
    language/keywords.yaml"""
    if not _REGISTRY:
        with open(os.path.join(ROOT, "language", "keywords.yaml")) as f:
            k = yaml.safe_load(f)
        rules = {r["rule"]: {d: r[d] for d in FIXED}
                 for r in (k.get("refusals") or []) + (k.get("flags") or []) + (k.get("failures") or [])}
        _REGISTRY[:] = [rules, {d["dimension"]: d["values"] for d in k.get("dimensions") or []}]
    return _REGISTRY[0], _REGISTRY[1]


def found_by(rule):
    """how the checker found a problem of this rule"""
    return "history" if rule in HISTORY else "analyser" if rule in ANALYSER else "reading"


def place(path):
    """the place in a .edda of a path of keys, or None"""
    if path[:1] == ("roles",) and len(path) >= 2:
        return "role"
    if path[:1] == ("entities",) and len(path) >= 3:
        return ENTITY_PLACES.get(path[2])
    if path[:1] == ("stories",) and len(path) >= 2:
        if len(path) == 2:
            return "story"
        if path[2] == "rules":
            return "story rules"
        if path[2] == "operations":
            return OPERATION_PLACES.get(path[4]) if len(path) >= 5 else None
        if path[2] == "examples":
            return EXAMPLE_PLACES.get(path[4]) if len(path) >= 5 else None
        return "story"
    return None


def where(path, line, load, guard=None):
    """where in the spec a problem at line of the file path is; load is
    check.py's load, for the key path of each line, the file read inside
    guard when given; unknown when it cannot be told. A problem carries a line, not a key, so a place is
    named only when every key and item that starts on the line maps to
    that one place; a line that also holds a key of another place or of
    none (a block in flow form) is unknown, never guessed"""
    if path.endswith(".edda.vc"):
        return "history"
    if path.endswith(".links") or path.endswith(".py"):
        return "code"
    if not path.endswith(".edda") or not line:
        return "unknown"
    try:
        source, _ = load(path, guard)
    except Exception:
        return "unknown"
    places = {place(p) for p, (kline, _) in source.marks.items() if p and kline == line}
    return places.pop() if len(places) == 1 and None not in places else "unknown"


def tagged_language(path, line, guard=None):
    """whether a person tagged the line # edda: language; the file read
    only inside guard when given"""
    try:
        if guard is None:
            f = open(path)
        else:
            from check import open_inside
            f = os.fdopen(open_inside(guard, path))
        with f:
            text = f.read().splitlines()
    except Exception:
        return False
    return bool(line) and 0 < line <= len(text) and bool(LANGUAGE_TAG.search(text[line - 1]))


def problem(rule, path, line, how, folder, load, guard=None):
    """one problem with all six dimensions: path is the file's own path,
    shown relative to folder (the project); guard as for where"""
    fixed = dict(registry()[0].get(rule) or {d: "unknown" for d in FIXED})
    if tagged_language(path, line, guard):
        fixed["acts"] = "language"
    return dict(rule=rule, file=os.path.relpath(path, folder), line=line, **fixed,
                where=where(path, line, load, guard), found_by=how)


def count_line(problems):
    """'3 contradiction, 1 weak check': one count per category with
    problems, in the registry's order; None when there are none"""
    order = registry()[1].get("category") or []
    counts = {}
    for p in problems:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    if not counts:
        return None
    return ", ".join(f"{counts[c]} {c}" for c in sorted(counts, key=lambda c: (order.index(c) if c in order else len(order), c)))


def log_file(folder):
    """where the log goes for the project folder, or None when EDDA_LOG=off"""
    to = os.environ.get("EDDA_LOG", "")
    if to == "off":
        return None
    return to or os.path.join(folder, ".edda", "checks.log")


def commit(folder):
    """the short SHA of the project's commit, or none outside git"""
    try:
        p = subprocess.run(["git", "-C", folder, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return "none"
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else "none"


def log(problems, folder):
    """append one JSON line per problem; nothing when there are none or the
    log is off; a log that cannot be written is left alone, silently. The
    default log must resolve inside folder as it is opened (check.open_inside):
    a log that resolves outside is not written and one line on stderr says
    so; one EDDA_LOG names is the operator's own choice, written as given"""
    try:
        to = log_file(folder)
        if not problems or to is None:
            return
        stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        sha = commit(folder)
        text = "".join(json.dumps({k: (stamp if k == "date" else sha if k == "commit" else p[k]) for k in FIELDS}) + "\n"
                       for p in problems)
        if os.environ.get("EDDA_LOG", ""):
            os.makedirs(os.path.dirname(os.path.abspath(to)), exist_ok=True)
            with open(to, "a") as f:
                f.write(text)
            return
        from check import Outside, open_inside
        os.makedirs(os.path.dirname(to), exist_ok=True)     # .edda, inside the root (settings.log_outside)
        try:
            fd = open_inside(folder, to, os.O_WRONLY | os.O_APPEND | os.O_CREAT)
        except Outside as o:
            print(f"{os.path.relpath(to)}: outside_root: the log resolves outside the project root: {o.args[0]}; "
                  "nothing logged", file=sys.stderr)
            return
        with os.fdopen(fd, "a") as f:
            f.write(text)
    except Exception:
        pass
