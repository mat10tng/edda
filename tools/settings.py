"""The import: a project's edda.yaml, read once for every tool (reference
sections 9 and 11).

edda.yaml sits at the host root, the folder that holds the spec folder.
Its keys, all optional: edda (the pinned revision), specs (the spec
folder, default specs), stack (the code stack, python), problem_log
(local or off, the local problem log; off when left out),
generated_cases, zone (the business zone, an IANA name; UTC when left
out) and clock_start (the start of the clock of every example that uses
time and gives no starts_at of its own; none when left out). No file:
the spec folder is specs and every setting is off. For this revision a specs/edda.yaml holding only generated_cases is
still read; both files at once are refused. A tool given the spec folder
by name takes the folder above it as the root; given --root as well, the
two must name one root. Every path the host gives (the spec folder, the
log folder .edda when the log is on; covers: and .links paths in
check.py) must resolve,
symlinks followed, inside the root (outside_root). So must every file a
tool opens under the root once edda.yaml or a root is in play (guard):
edda.yaml, each .edda, .edda.vc and .links file and each covered code
file, checked on the path as it is opened (check.open_inside), and the
default log .edda/checks.log (watch.py, trend.py).
"""
import os
import sys
import zoneinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as checker          # noqa: E402

REVISION = 75       # the revision of these tools; edda.yaml may pin it
STACKS = ("python",)
PROBLEM_LOGS = ("local", "off")
GENERATED = {
    "type": "object", "additionalProperties": False, "required": ["on"],
    "properties": {"on": {"type": "boolean"}, "runs": {}, "steps": {}}}
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"edda": {}, "specs": {"type": "string"}, "stack": {}, "problem_log": {},
                         "generated_cases": GENERATED, "zone": {}, "clock_start": {}}}
OLD_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"generated_cases": GENERATED}}
VALIDATOR, OLD_VALIDATOR = checker.Draft202012Validator(SCHEMA), checker.Draft202012Validator(OLD_SCHEMA)
GENERATED_OFF = {"on": False, "runs": 100, "steps": 20}


class Usage(Exception):
    """--root and a spec folder name two roots; args[0] is the one line"""


class Refused(Exception):
    """the settings do not check; lines, each <file>:<line>: <rule>:
    <message>; code, the exit code: 3 for a pin newer than these tools,
    else 1"""

    def __init__(self, lines, code=1):
        super().__init__(lines)
        self.lines, self.code = lines, code


class Settings:
    """root, the host root; folder, the spec folder; file, the edda.yaml
    read or None; generated, the generated_cases setting; pin and stack,
    None when not given; problem_log, local or off; zone, the business
    zone, UTC when not given; clock_start, a time text or None; clock,
    the two as check.project_of takes them; flags, (rule, path, line,
    message); guard, the
    root every file of the host must resolve inside as it is opened, or
    None when neither edda.yaml nor a root is in play (an Edda
    repository without its own edda.yaml, read as before)"""

    def __init__(self, root, folder, file=None, generated=None, pin=None, stack=None, flags=(), guard=None,
                 problem_log="off", zone=checker.ZONE, clock_start=None):
        self.root, self.folder, self.file, self.guard = root, folder, file, guard
        self.problem_log = problem_log
        self.zone, self.clock_start = zone, clock_start
        self.clock = (clock_start, zone)        # as check.project_of takes it
        self.generated = dict(GENERATED_OFF, **(generated or {}))
        self.pin, self.stack, self.flags = pin, stack, list(flags)


def shown(path, line, rule, msg):
    return f"{os.path.relpath(path)}:{line}: {rule}: {msg}"


def inside(root, path):
    """whether path, symlinks followed, is root or inside it"""
    real, top = os.path.realpath(path), os.path.realpath(root)
    return real == top or real.startswith(top.rstrip(os.sep) + os.sep)


def outside_line(path, what, at=None):
    """the outside_root line for a path of the host that resolves outside
    the project root: at its line, at=(file, line), when a line names it,
    else at the path itself"""
    msg = f"{what} resolves outside the project root: {os.path.realpath(path)}"
    if at is not None:
        return shown(at[0], at[1], "outside_root", msg)
    return f"{os.path.relpath(path)}: outside_root: {msg}"


def log_outside(root):
    """the outside_root line when the log folder .edda of root resolves
    outside it, else None"""
    dot = os.path.join(root, ".edda")
    return None if inside(root, dot) else outside_line(dot, "the log folder .edda")


def not_there(folders=(), files=()):
    """the one usage line (exit 2, section 13) for the first folder or file
    an option names that is not there or not of its kind, else None; each
    tool checks its options with it before it does anything"""
    for path in folders:
        if path is not None and not os.path.isdir(path):
            return f"{'not a folder' if os.path.exists(path) else 'no such folder'}: {path}"
    for path in files:
        if path is not None and not os.path.isfile(path):
            return f"{'not a file' if os.path.exists(path) else 'no such file'}: {path}"
    return None


def whole(v):
    return type(v) is int and v >= 1


def known_zone(v):
    """is v the name of a time zone zoneinfo knows, such as Europe/Oslo"""
    if not isinstance(v, str) or not v:
        return False
    try:
        zoneinfo.ZoneInfo(v)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def problems(path, validator, schema, root):
    """(source, data, found) of one edda.yaml, read inside root: the
    source layer, then its shape and its values"""
    source, data = checker.load(path, root)
    found = source.src
    if not found:
        found = list(source.style) + [("declared_twice", ln, f"declared twice: {k}") for k, ln in source.duplicates]
        found += checker.schema_problems(validator, schema, data, source)
    if not found:
        g = data.get("generated_cases") or {}
        found = [("wrong_type", source.line(("generated_cases", k), False), f"{k} must be a whole number of at least 1")
                 for k in ("runs", "steps") if k in g and not whole(g[k])]
        if "edda" in data and not whole(data["edda"]):
            found.append(("wrong_type", source.line(("edda",), False), "edda must be a whole number of at least 1"))
        specs = data.get("specs")
        if isinstance(specs, str) and (not specs or os.path.isabs(specs) or ".." in specs.replace("\\", "/").split("/")):
            found.append(("wrong_type", source.line(("specs",), False),
                          f"specs must be a folder inside the project, without ..: {specs}"))
        if "stack" in data and data["stack"] not in STACKS:
            found.append(("wrong_type", source.line(("stack",), False), f"stack must be {' or '.join(STACKS)}"))
        if "problem_log" in data and data["problem_log"] not in PROBLEM_LOGS:
            found.append(("wrong_type", source.line(("problem_log",), False),
                          f"problem_log must be {' or '.join(PROBLEM_LOGS)}"))
        if "zone" in data and not known_zone(data["zone"]):
            found.append(("wrong_type", source.line(("zone",), False),
                          f"zone must be a time zone name, such as Europe/Oslo: {data['zone']}"))
        if "clock_start" in data and not checker.time_text(data["clock_start"]):
            found.append(("wrong_type", source.line(("clock_start",), False),
                          f'clock_start must be a time, "YYYY-MM-DD HH:MM" or "YYYY-MM-DD": {data["clock_start"]}'))
    return source, data, found


def refuse(path, found):
    raise Refused([shown(path, line, rule, msg) for rule, line, msg in sorted(set(found), key=lambda p: (p[1], p[0], p[2]))])


def pinned_newer(path, root):
    """refuse, exit 3, when the file pins a revision newer than these tools;
    read before the shape, since a newer revision may have keys this one
    does not know"""
    source, data = checker.load(path, root)
    if source.src or not isinstance(data, dict) or not whole(data.get("edda")) or data["edda"] <= REVISION:
        return
    raise Refused([shown(path, source.line(("edda",), False), "pinned_newer",
                         f"edda.yaml pins revision {data['edda']}; these tools are revision {REVISION}")], code=3)


def glossary_target(folder, root):
    """the target glossary.links names, or None"""
    path = os.path.join(folder, "glossary.links")
    if not os.path.exists(path):
        return None, None
    source, data = checker.load(path, root)
    if source.src or not isinstance(data, dict) or not isinstance(data.get("target"), str):
        return None, None
    return data["target"], path


def read(root=None, folder=None):
    """the Settings of the project at root (Edda's own repository when
    None), or of the spec folder named by folder, its root the folder
    above it; raises Refused"""
    given_root = root is not None
    if folder is not None:
        given, folder = folder, os.path.abspath(folder)
        if root is not None and os.path.realpath(root) != os.path.realpath(os.path.dirname(folder)):
            raise Usage(f"--root {root} and the spec folder {given} name two roots; give one")
        root = os.path.dirname(folder)
        named = True
    else:
        root = os.path.abspath(root or checker.ROOT)
        named = False
    path = os.path.join(root, "edda.yaml")
    data, source = {}, None
    guard = root if named or given_root or os.path.lexists(path) else None
    if os.path.exists(path):
        pinned_newer(path, guard)
        source, data, found = problems(path, VALIDATOR, SCHEMA, guard)
        if found:
            refuse(path, found)
    if folder is None:
        folder = os.path.normpath(os.path.join(root, data.get("specs", "specs")))
    if not inside(root, folder):
        at = (path, source.line(("specs",), False)) if "specs" in data and not named else None
        raise Refused([outside_line(folder, "the spec folder", at)])
    dot = log_outside(root) if data.get("problem_log") == "local" else None    # off: nothing is written
    if dot is not None:
        raise Refused([dot])
    old = os.path.join(folder, "edda.yaml")
    if os.path.exists(old) and old != path:     # specs: . is the root itself
        if source is not None:
            raise Refused([shown(old, 1, "two_settings", f"two edda.yaml files; keep {os.path.relpath(path)} "
                                                         "and move generated_cases: into it")])
        guard = root
        _, old_data, found = problems(old, OLD_VALIDATOR, OLD_SCHEMA, guard)
        if found:
            refuse(old, found)
        return Settings(root, folder, old, old_data.get("generated_cases"), guard=guard)
    if source is None:
        return Settings(root, folder, guard=guard)
    stack, flags = data.get("stack"), []
    target, gpath = glossary_target(folder, guard)
    if stack is not None and target is not None and target != stack:
        refuse(path, [("stack_mismatch", source.line(("stack",), False),
                       f"stack is {stack} but {os.path.relpath(gpath)} names target {target}")])
    pin = data.get("edda")
    if pin is not None and pin < REVISION:
        flags.append(("pinned_older", path, source.line(("edda",), False),
                      f"edda.yaml pins revision {pin}; these tools are revision {REVISION}"))
    return Settings(root, folder, path, data.get("generated_cases"), pin, stack, flags, guard,
                    data.get("problem_log", "off"), data.get("zone", checker.ZONE), data.get("clock_start"))


def clock_at(root):
    """(clock_start, zone) of the edda.yaml at root, for a tool given only a
    spec folder (check.project_of); no start and UTC when there is no
    file or it does not check: the tool that reads it reports that"""
    path = os.path.join(root, "edda.yaml")
    if not os.path.isfile(path):
        return None, checker.ZONE
    try:
        _, data, found = problems(path, VALIDATOR, SCHEMA, root)
    except (checker.Outside, OSError, ValueError):     # unreadable here; the settings reader refuses it where it matters
        return None, checker.ZONE
    if found or not isinstance(data, dict):
        return None, checker.ZONE
    return data.get("clock_start"), data.get("zone", checker.ZONE)


def open_project(root=None, folder=None, out=None):
    """read the settings; print each flag line to out (stdout when None) and
    return (Settings, None), or print the refusal and return (None, exit
    code): the usage line (2), the pin's one line (3), or the problems
    under 'the settings do not check:' (1)"""
    out = out or sys.stdout
    try:
        s = read(root, folder)
    except Usage as u:
        print(u.args[0], file=out)
        return None, 2
    except Refused as r:
        if r.code != 1:
            print(r.lines[0], file=out)
        else:
            print("the settings do not check:", file=out)
            for line in r.lines:
                print(f"    {line}", file=out)
        return None, r.code
    for rule, path, line, msg in s.flags:
        print(f"{os.path.relpath(path)}:{line}: flagged: {rule}: {msg}", file=out)
    return s, None
