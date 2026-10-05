#!/usr/bin/env python3
"""The edda command (reference section 13): one entry point for the tools.

    edda check   [--root DIR] [--model [DIR] | --graph ENTITY.PROPERTY [DIR]]
    edda run     [--root DIR] [--project DIR] [--seed N] [STORY ...]
    edda view    [--lines] [--root DIR | DIR] [STORY ...]
    edda approve NAME --by OPERATOR [--because TEXT] [--at TIME] [--dry-run]
                 [--root DIR] [--folder DIR]
    edda guide   [--pointer [--root HOST]]
    edda trend   [--root DIR] [--log FILE] [--by DIM[,DIM]] [--top N]

Each takes the options its tool in tools/ takes, and --json. The exit
codes are the same for every one: 0 nothing refused and nothing failed
(flags alone are 0), 1 a refusal, a failing example, function row or generated case,
or an approval refused, 2 a usage error, 3 Edda itself failed. Plain,
each prints what its tool prints. With --json it prints one JSON
document on stdout instead (FORMAT, below, names its shape): format,
edda (the revision), command, exit, the command's own fields (FIELDS)
and messages: every line the command said that is not in its fields,
in the order said (a flag or refusal of the settings, the lines of a
usage error, a refusal of the spec, Edda failing, anything on stderr).
With --json a tool prints only what its fields do not hold; what it
prints goes to messages, whatever the outcome. Every folder or file an
option names must be there and of its kind (settings.not_there), else
the one line and exit 2, before anything is done. The old scripts (tools/check.py and
the rest) run through main, so they keep their options and output and
take these exit codes. The checker's run lives here, not in check.py,
whose code is linked to Edda's stories.
"""
import contextlib
import copy
import glob
import importlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FORMAT = 2          # the shape of the --json document; a change to it is a new number: 2 since revision 71
                    # (run's functions)
COMMANDS = ("check", "run", "view", "approve", "guide", "trend")
USAGE = "usage: edda check|run|view|approve|guide|trend [--root DIR] [--json] ..."
FIELDS = {          # each command's own fields, as they are when it stopped before its result
    "check": {"files": [], "problems": [], "counts": {}, "model": None, "graph": None},
    "run": {"functions": [], "stories": [], "failures": [], "counts": {}},
    "view": {"blocks": []},
    "approve": {"name": None, "kind": None, "number": None, "history": None, "version": None,
                "written": False, "refused": None},
    "guide": {"pointer": None, "guide": None, "written": False},
    "trend": {"log": None, "skipped": 0, "total": 0, "first": None, "last": None, "per_day": [], "by": [],
              "groups": [], "rules": []},
}


def check(argv, result=None):
    """the checker's run (reference section 11), the exit code; result, when
    given, gets files, problems and counts. --root names the project, the
    folder holding edda.yaml and the spec folder; Edda's own when left out,
    and only then, and only in plain output, are the fixtures reported"""
    import check as checker
    import settings
    import watch
    args, root = list(argv), None
    if args[:1] == ["--root"] and len(args) >= 2:
        root, args = args[1], args[2:]
        usage = settings.not_there([root])
        if usage:
            print(usage)
            return 2
    if args[:1] == ["--model"] and len(args) <= 2 or args[:1] == ["--graph"] and 2 <= len(args) <= 3:
        return checker.model_main(args, root, result)
    if args:
        print(checker.USAGE)
        return 2
    project, code = settings.open_project(root)
    if project is None:
        return code
    if not os.path.isdir(project.folder):
        print(f"no such folder: {os.path.relpath(project.folder)}")
        return 1
    files = [] if result is not None else None
    if result is not None:
        result["files"] = files     # filled as the files are read, so a failure keeps what was read
    ok, own, own_links = checker.report(project.folder, project.root, project.root, project.guard, files)
    if project.root == checker.ROOT and result is None:
        fixtures(checker)
    seen = [(path, r) for path, layers in own.items() for kind in layers for r in kind]
    seen += [(os.path.join(project.root, shown), r) for shown, refusals, flags in (own_links[0] if own_links else [])
             for r in refusals + flags]
    problems = [dict(watch.problem(rule, path, line, watch.found_by(rule), project.root, checker.load, project.guard),
                     message=msg) for path, (rule, line, msg) in seen]
    problems += [dict(watch.problem(rule, path, line, "reading", project.root, checker.load, project.guard),
                      message=msg) for rule, path, line, msg in project.flags]
    counts = watch.count_line(problems)
    if result is not None:
        result.update(problems=problems, counts=watch.counts(problems))
    elif counts:
        print(counts)
    watch.log(problems, project.root, project.problem_log == "local")
    return 0 if ok else 1


def fixtures(checker):
    """print which layer catches each fixture, for Edda's own repository;
    never counted or logged: their problems are there on purpose"""
    ROOT, load = checker.ROOT, checker.load
    print()
    print("fixtures: which layer catches each file")
    LAYERS = ("source", "shape", "meaning", "history")      # the fourth layer's refusals; its flags are "flagged"
    for folder in sorted(os.listdir(f"{ROOT}/fixtures")):
        FP = checker.project_of(f"{ROOT}/fixtures/{folder}")
        paths = sorted(glob.glob(f"{ROOT}/fixtures/{folder}/*.edda") + glob.glob(f"{ROOT}/fixtures/{folder}/*.edda.vc"))
        found = {path: checker.check(path, FP) for path in paths}
        L = None if any(any(r[:4]) for r in found.values()) else checker.links_of(f"{ROOT}/fixtures/{folder}", FP)
        for path in paths:
            src, shape, meaning, history, flags = found[path]
            refusals = src + shape + meaning + history
            caught = next((name for name, hit in zip(LAYERS, (src, shape, meaning, history)) if hit), None)
            label = ("caught by " + caught) if caught else ("flagged" if flags else "passes")
            print(f"  {folder}/{os.path.basename(path)}: {label}")
            for rule, line, msg in refusals:
                print(f"      {line}: {rule}: {msg}")
            for rule, line, msg in flags:
                print(f"      {line}: flagged: {rule}: {msg}")
            if not refusals and not path.endswith(".vc") and not checker.history_refused(path, FP):
                source, data = load(path)
                for s in checker.status_lines(data, FP, source, L and L[1]):
                    print(f"      {s}")
        for shown, refusals, flags in (L[0] if L else []):     # the link layer, after the four
            print(f"  {shown}: " + ("caught by links" if refusals else "flagged" if flags else "passes"))
            for rule, line, msg in refusals:
                print(f"      {line}: {rule}: {msg}")
            for rule, line, msg in flags:
                print(f"      {line}: flagged: {rule}: {msg}")


def call(command, argv, result=None):
    """run one command, the exit code: argparse's own usage error is 2, and
    any error Edda did not foresee is Edda failing, 3"""
    prog = sys.argv[0]
    if os.path.basename(prog) in ("edda", "edda.py"):       # argparse names the command: usage: edda run ...
        sys.argv[0] = f"edda {command}"
    try:
        if command == "check":
            return check(argv, result)
        return importlib.import_module(command).main(argv, result)
    except SystemExit as e:         # argparse: --help is 0, a usage error 2
        return e.code if isinstance(e.code, int) else 0 if e.code is None else 2
    except Exception as e:          # Edda itself failed
        print(f"edda failed: {type(e).__name__}: {e}")
        return 3
    finally:
        sys.argv[0] = prog


def main(argv):
    """the exit code of edda COMMAND ARGS, printing as section 13 says"""
    as_json = "--json" in argv
    if not argv or argv[0] not in COMMANDS:
        if as_json:
            print(json.dumps({"format": FORMAT, "edda": revision(), "command": None, "exit": 2,
                              "messages": [USAGE]}, indent=2))
        else:
            print(USAGE)
        return 2
    command, rest = argv[0], [x for x in argv[1:] if x != "--json"]
    if not as_json:
        return call(command, rest)
    result, said = {}, io.StringIO()       # stdout and stderr in one, so messages keep their order
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
        code = call(command, rest, result)
    doc = {"format": FORMAT, "edda": revision(), "command": command, "exit": code}
    doc.update(copy.deepcopy(FIELDS[command]))
    doc.update(result)
    doc["messages"] = said.getvalue().splitlines()
    print(json.dumps(doc, indent=2))
    return code


def revision():
    import settings
    return settings.REVISION


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
