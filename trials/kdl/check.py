#!/usr/bin/env python3
"""Check one folder with Edda's own checker, written in YAML or in KDL.

    python3 trials/kdl/check.py FOLDER --format yaml|kdl

yaml: the folder's .edda files through validate's project_of and check.
kdl: each .kdl translated by kdl2yaml into a temporary folder, the same
checks there, and every problem's line mapped back to its .kdl line.
Prints problems as `file: line: rule: message` (flags as
`file: line: flagged: rule: message`, which, as in validate, do not
fail), appends the run to FOLDER/runs.log as one JSON line, and exits 0
when there is no problem, 1 otherwise."""
import datetime, glob, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
sys.path.insert(0, HERE)
import validate   # noqa: E402
import kdl2yaml   # noqa: E402


def run_checker(folder, names):
    """{name.edda: (problems, flags)} for the .edda files of one folder"""
    P = validate.project_of(folder)
    out = {}
    for name in names:
        src, shape, meaning, history, flags = validate.check(os.path.join(folder, name), P)
        out[name] = (src + shape + meaning + history, flags)
    return out


def check_yaml(folder):
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "*.edda")))
    return names, run_checker(folder, names)


def check_kdl(folder):
    names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "*.kdl")))
    results, maps = {}, {}
    tmp = tempfile.mkdtemp(prefix="edda-kdl-")
    try:
        for name in names:
            text, line_map, problems = kdl2yaml.translate(open(os.path.join(folder, name), encoding="utf-8").read())
            if problems:
                results[name] = (problems, [])
                continue
            maps[name] = line_map
            with open(os.path.join(tmp, name[:-4] + ".edda"), "w", encoding="utf-8") as f:
                f.write(text)
        checked = run_checker(tmp, [n[:-4] + ".edda" for n in maps])
    finally:
        shutil.rmtree(tmp)

    def back(line_map, line):
        return line_map[min(max(line, 1), len(line_map)) - 1] if line_map else 1

    for name, line_map in maps.items():
        problems, flags = checked[name[:-4] + ".edda"]
        results[name] = ([(r, back(line_map, ln), m) for r, ln, m in problems],
                         [(r, back(line_map, ln), m) for r, ln, m in flags])
    return names, results


def main(argv):
    if len(argv) != 3 or argv[1] != "--format" or argv[2] not in ("yaml", "kdl"):
        sys.exit("usage: check.py FOLDER --format yaml|kdl")
    folder, fmt = argv[0], argv[2]
    names, results = (check_yaml if fmt == "yaml" else check_kdl)(folder)
    logged = []
    for name in names:
        problems, flags = results[name]
        problems = sorted(set(problems), key=lambda p: (p[1], p[0], p[2]))
        if not problems:
            print(f"{name} OK")
        for rule, line, msg in problems:
            print(f"{name}: {line}: {rule}: {msg}")
            logged.append({"rule": rule, "file": name, "line": line})
        for rule, line, msg in sorted(set(flags), key=lambda p: (p[1], p[0], p[2])):
            print(f"{name}: {line}: flagged: {rule}: {msg}")
    entry = {"time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
             "format": fmt, "files": names, "problems": logged}
    with open(os.path.join(folder, "runs.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return 0 if not logged else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
