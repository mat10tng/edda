#!/usr/bin/env python3
"""Run the examples of Edda's stories against real code, through the
binding (reference sections 8, 9 and 11).

    python3 tools/run.py [--root DIR] [--project DIR] [--seed N] [STORY ...]

For each story (or each one named), each example: make the given things
through the binding, run each step's call as its actor, then judge each
then item: DONE, refused: "<reason>", or a fact, evaluated over the
parsed ast (the whitelist of section 7.1; never eval). Every call of a
bound operation, a step's or a read inside a fact, is held to the
operation's rules (reference section 6): the refusal the spec gives,
every ensure with OLD, every always-rule and the frame rule. The spec must
check first (tools/check.py). A story whose examples all pass is reported
"examples passed", never "done": done (reference section 11) needs more
than the runner computes. The spec folder and the settings come from
the project's edda.yaml (tools/settings.py); --root names the project,
--project its spec folder; given both, they must name one root. When the edda.yaml turns generated
cases on, each story gets one more line: its generated cases
(tools/generate.py, which needs Hypothesis), under the seed --seed names
or a random one. Exit 0 when no story failed, 1 when one failed, its
generated cases included, or the spec or the settings do not check, 2
for a usage error (a STORY the project does not have, a --root or
--project not there), 3 when Edda itself failed (reference section 13).
The edda command (tools/edda.py) runs this as edda run; with --json it
fills a result and prints only the lines the result does not hold.
"""
import argparse
import ast
import datetime
import glob
import json
import os
import random
import re
import shlex
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as checker          # noqa: E402
import edda_binding as binding   # noqa: E402
import settings                  # noqa: E402
import watch                     # noqa: E402

NOW = [None]        # the clock: its time in the example being run, None when the example uses no time
ZONE = [checker.ZONE]   # the business zone, set by run()


class Duration(tuple):
    """DAYS(n), HOURS(n) or MINUTES(n): (unit, n); it only moves a time (7.1)"""


class Fail(Exception):
    """the example fails here; the message says what was found"""


class NoRow(Fail):
    """a Fail because a client function was called on inputs no row covers
    (section 8): no phase of an example swallows it, so it fails the
    example where it was met"""


class UnsetFail(Fail):
    """a Fail because an unset value was read; while generated cases run
    (UNSET_ENDS) judge passes it on: generation gave no value there"""


class EddaError(Exception):
    """Edda itself failed: a spec the checker should have refused"""


class UnknownStory(EddaError):
    """a STORY named that the project does not have: a usage error, exit 2;
    the line printed is the one of revision 68"""


class RuleBroken(Exception):
    """a bound operation broke a rule of the spec; failures are (file:line,
    None, what was found), the line the rule's own. Not a Fail: it ends
    the step, it is never what a fact found. unjudged, while generated
    cases run, the rules of the call that could not be judged (judged)"""

    def __init__(self, failures, unjudged=()):
        super().__init__(failures)
        self.failures, self.unjudged = failures, list(unjudged)


class SpecRefused(Exception):
    """the spec does not check; args[0] is what the checker says"""


# --- expressions: section 7.1 over the parsed ast ------------------------------

def show(v, deep=True):
    """v as a failure message shows it. A given entity is its kind and
    given name. Another entity shows its own stored fields (its instance
    dict, never a property) one level deep: inside it an entity is its
    kind and given name, or its kind alone; lists likewise. Showing never
    raises"""
    try:
        if isinstance(v, binding.Unset):
            return "unset"
        if isinstance(v, binding.Thing):
            d = dict(dict.items(vars(v)))   # raw: an unset field shows as unset
            name = " ".join(filter(None, (d.get("_entity"), d.get("_given"))))
            if d.get("_given") or not deep:
                return name
            fields = ", ".join(f"{k}: {show(x, False)}" for k, x in d.items()
                               if not k.startswith("_"))
            return f"{d.get('_entity')}{{{fields}}}" if fields else name
        if isinstance(v, str):
            return json.dumps(v)
        if isinstance(v, list):
            return "[" + ", ".join(show(x, deep) for x in v) + "]"
        if v is None:
            return "None"
        return repr(v)
    except Exception as e:
        return f"<unprintable: {type(e).__name__}>"


class Lazy:
    """a value read only when an expression reaches it: an always-rule's
    bare property names, so an unset one fails only when read"""

    def __init__(self, get):
        self.get = get

    def __call__(self):
        return self.get()


def read(obj, attr, text):
    """obj's property attr, read through the binding; text names it in a
    failure. While the frame rule records what a computed property reads
    (derives), the read is recorded, and a computed property is the
    spec's expression on obj"""
    if RECORD[0] is not None and isinstance(obj, binding.Thing):
        v = derives(obj, attr)
        if v is not MISSING:
            return v
    try:
        v = getattr(obj, attr)
    except (binding.NotBound, EddaError):
        raise
    except binding.UnsetRead as u:
        if type(dict.get(object.__getattribute__(obj, "__dict__"), attr)) is binding.Unset:
            raise UnsetFail(f"{text} is unset")    # this read itself
        raise UnsetFail(str(u))          # the binding's property used an unset value
    except Exception as e:      # the binding's property crashed
        raise Fail(f"{text} raised {type(e).__name__}: {e}")
    if isinstance(v, binding.Unset):
        raise UnsetFail(f"{text} is unset")
    return v


def evaluate(text, env):
    return value(ast.parse(text, mode="eval").body, env)


def number(v, what):
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float, datetime.datetime, str)):
        raise Fail(f"{what} on {show(v)}")
    return v


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def ordered(a, b):
    """may a and b be ordered: two numbers, two times or two texts"""
    return (is_number(a) and is_number(b)) or any(isinstance(a, t) and isinstance(b, t) for t in (datetime.datetime, str))


def today(t):
    """TODAY at time t: 00:00 of t's day in the business zone (decision GG)"""
    return checker.resolved(datetime.datetime(t.year, t.month, t.day), ZONE[0])


def moment(v):
    """a value as what it stands for when compared (section 7.2): a time
    as its moment, so the two 02:30s of a doubled hour differ and an hour
    that does not exist is read as zoneinfo reads it; a list element by
    element; any other value as it is. Every comparison of values goes
    through it: ==, !=, <, <=, in, not in, and the frame rule's same"""
    if isinstance(v, datetime.datetime):
        return checker.instant(v, ZONE[0])
    if type(v) is list:
        return [moment(x) for x in v]
    return v


def compare(op, a, b):
    if isinstance(op, (ast.Is, ast.IsNot)):
        return (a is None) == isinstance(op, ast.Is)
    if isinstance(op, (ast.In, ast.NotIn)):
        if not isinstance(b, (list, str)) or (isinstance(b, str) and not isinstance(a, str)):
            raise Fail(f"in of {show(a)} on {show(b)}")
        return (moment(a) in moment(b)) == isinstance(op, ast.In)
    if not isinstance(op, (ast.Eq, ast.NotEq)) and not ordered(a, b):
        raise Fail(f"a comparison of {show(a)} with {show(b)}")
    a, b = moment(a), moment(b)
    if isinstance(op, ast.Eq):
        return a == b
    if isinstance(op, ast.NotEq):
        return a != b
    return {ast.Lt: a < b, ast.Gt: a > b, ast.LtE: a <= b, ast.GtE: a >= b}[type(op)]


def items(gens, elt, env):
    """the values of a comprehension, lazily, so any and all stop early"""
    if not gens:
        yield value(elt, env)
        return
    g = gens[0]
    source = value(g.iter, env)
    if not isinstance(source, list):
        raise Fail(f"{ast.unparse(g.iter)} is no list: {show(source)}")
    for x in source:
        inner = dict(env, **{g.target.id: x})
        if all(value(c, inner) for c in g.ifs):
            yield from items(gens[1:], elt, inner)


def value(n, env):
    if isinstance(n, ast.Constant):
        return n.value
    if isinstance(n, ast.Name):
        if n.id in env:
            v = env[n.id]
            return v() if isinstance(v, Lazy) else v
        if n.id == "RESULT":
            raise Fail("RESULT has no value after a refusal")
        if n.id == "ACTOR":
            raise Fail("ACTOR has no value before any call")
        if n.id in checker.CLOCK:
            if NOW[0] is None:      # the checker's time_uses missed a read: Edda's own failure
                raise EddaError(f"{n.id} was read, but the example has no clock: "
                                "the runner read the clock without a start")
            return NOW[0] if n.id == "NOW" else today(NOW[0])
        if re.fullmatch(checker.NAME, n.id):
            return n.id                         # a choice value
        raise EddaError(f"{n.id} has no value here")
    if isinstance(n, ast.Attribute):
        obj = value(n.value, env)
        if not isinstance(obj, binding.Thing):
            raise Fail(f"{ast.unparse(n.value)} is no entity: {show(obj)}")
        return read(obj, n.attr, ast.unparse(n))
    if isinstance(n, ast.Subscript):
        seq, i = value(n.value, env), value(n.slice, env)
        if not isinstance(seq, list) or isinstance(i, bool) or not isinstance(i, int):
            raise Fail(f"{ast.unparse(n)}: no index {show(i)} on {show(seq)}")
        if not -len(seq) <= i < len(seq):
            raise Fail(f"{ast.unparse(n)}: index out of range, {ast.unparse(n.value)} has {len(seq)}")
        return seq[i]
    if isinstance(n, ast.Compare) and len(n.ops) == 1:
        return compare(n.ops[0], value(n.left, env), value(n.comparators[0], env))
    if isinstance(n, ast.BoolOp):
        for x in n.values:
            v = value(x, env)
            if (not v) if isinstance(n.op, ast.And) else v:
                return v
        return v
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
        return not value(n.operand, env)
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        v = value(n.operand, env)
        if not is_number(v):
            raise Fail(f"- on {show(v)}")
        return -v
    if isinstance(n, ast.BinOp) and type(n.op) in checker.OP_WORD:
        a, b = value(n.left, env), value(n.right, env)
        if isinstance(n.op, ast.Add) and isinstance(a, list) and isinstance(b, list):
            return a + b
        if isinstance(b, Duration) and isinstance(n.op, (ast.Add, ast.Sub)):      # a time moved (7.1)
            if not isinstance(a, datetime.datetime):
                raise Fail(f"{ast.unparse(n)}: {show(a)} is no time")
            try:
                return checker.shift(a, b[0], b[1] if isinstance(n.op, ast.Add) else -b[1], ZONE[0])
            except OverflowError as e:
                raise Fail(f"{ast.unparse(n)}: {e}")
        word = checker.OP_WORD[type(n.op)]
        a, b = number(a, word), number(b, word)
        try:
            return {ast.Add: lambda: a + b, ast.Sub: lambda: a - b,
                    ast.Mult: lambda: a * b, ast.Div: lambda: a / b}[type(n.op)]()
        except (TypeError, ZeroDivisionError) as e:
            raise Fail(f"{ast.unparse(n)}: {e}")
    if isinstance(n, ast.List):
        return [value(e, env) for e in n.elts]
    if isinstance(n, ast.ListComp):
        return list(items(n.generators, n.elt, env))
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        f, args = n.func.id, n.args
        if f == "len" and len(args) == 1:
            v = value(args[0], env)
            if not isinstance(v, (list, str)):
                raise Fail(f"len of {show(v)}")
            return len(v)
        if f in checker.GEN_ONLY and len(args) == 1 and isinstance(args[0], ast.GeneratorExp):
            found = items(args[0].generators, args[0].elt, env)
            if f == "sum":
                total = 0
                for x in found:
                    if not is_number(x):
                        raise Fail(f"sum over {show(x)}")
                    total += x
                return total
            return {"any": any, "all": all}[f](found)
        if f == "TIME" and len(args) == 1:
            return time_of(args[0].value)
        if f in checker.DURATIONS and len(args) == 1:
            k = value(args[0], env)
            if type(k) is not int:
                raise Fail(f"{ast.unparse(n)}: {show(k)} is no whole number")
            return Duration((f, k))
        if f == "OLD" and len(args) == 1 and "OLD" in env:
            return env["OLD"](args[0], env)
        if f in PROJECT[0].functions:
            return function_call(f, [value(a, env) for a in args])
        if f in OPERATIONS:
            # a read inside a fact: as the checker itself, no actor, no permission (section 6)
            try:
                return run_operation(f, None, [value(a, env) for a in args],
                                     {k.arg: value(k.value, env) for k in n.keywords})
            except (Fail, RuleBroken, EddaError, binding.NotBound):
                raise
            except binding.UnsetRead as u:
                raise UnsetFail(str(u))
            except binding.Refused as r:
                raise Fail(f"{ast.unparse(n)} was refused: {show(r.reason)}")
            except Exception as e:      # the code under test crashed
                raise Fail(f"{ast.unparse(n)} raised {type(e).__name__}: {e}")
    raise EddaError(f"not an expression the runner knows: {ast.unparse(n)}")


# --- client functions (section 4) -------------------------------------------------

REAL_FUNCTIONS = [False]    # True while generated cases run: a call goes to the bound function, verified first
FUNCTION_RESULTS = {}       # name -> function_rows(name), worked out once per run
REAL_CALLS = []             # while generated cases run: each call of a real function in this run, (name, inputs,
                            # result or the exception it raised); each run clears it (generate.py)


def row_value(v, t):
    """a row's value as the runner holds it: a quoted time for a TIME a time"""
    if isinstance(v, list):
        return [row_value(x, t) for x in v]
    return time_of(v) if t == "TIME" and isinstance(v, str) else v


def equal(a, b):
    """are two values the same value: a time as its moment, a list element
    by element, yes and no never a number"""
    if type(a) is list and type(b) is list:
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) != isinstance(b, bool) or isinstance(a, datetime.datetime) != isinstance(b, datetime.datetime):
        return False
    return moment(a) == moment(b)


def function_call(name, args):
    """a call of a client function in what the runner evaluates: in an
    example only its rows answer, the result of the row whose inputs are
    these values, and a call no row covers fails; while generated cases
    run, the bound function, whose rows all passed (generate.py skips an
    operation that needs one that did not)"""
    if REAL_FUNCTIONS[0]:
        try:
            got = binding.FUNCTIONS[name](*args)
        except Exception as e:      # the client's code crashed
            REAL_CALLS.append((name, list(args), e))
            raise Fail(f"{name}({', '.join(show(a) for a in args)}) raised {type(e).__name__}: {e}")
        REAL_CALLS.append((name, list(args), got))
        return got
    row = row_for(name, args)
    if row is not None:
        return row_value(row.get("gives"), PROJECT[0].functions[name]["returns"])
    raise NoRow(f"no row for {name}({', '.join(show(a) for a in args)})")


def row_for(name, args):
    """the row of a client function whose inputs are these values, compared
    as values, or None when no row covers them"""
    fn = PROJECT[0].functions[name]
    for row in fn["rows"]:
        given = row.get("given") or {}
        if all(equal(a, row_value(given.get(n), t)) for a, (n, t) in zip(args, fn["inputs"])):
            return row
    return None


def function_rows(name):
    """(status, detail, failures) of a client function's rows run through
    its bound function, binding.FUNCTIONS[name], each row's inputs by
    position: "rows passed", "failing" with a failure (file:line, None,
    found) per row, or "not run" with no binding for it. The function is
    never called inside an example"""
    if name in FUNCTION_RESULTS:
        return FUNCTION_RESULTS[name]
    fn, lines = PROJECT[0].functions[name], RULES["functions"][name]
    real = getattr(binding, "FUNCTIONS", {}).get(name)
    if real is None:
        FUNCTION_RESULTS[name] = ("not run", f"no binding for function {name}", [])
        return FUNCTION_RESULTS[name]
    failures = []
    for row, at in zip(fn["rows"], lines):
        args = [row_value(row["given"][n], t) for n, t in fn["inputs"]]
        want = row_value(row["gives"], fn["returns"])
        call = f"{name}({', '.join(show(a) for a in args)})"
        try:
            got = real(*args)
        except Exception as e:      # the client's code crashed
            failures.append((at, None, f"{call} raised {type(e).__name__}: {e}"))
            continue
        if not equal(got, want):
            failures.append((at, None, f"{call} gives {show(want)}, but the code gave {show(got)}"))
    n = len(fn["rows"])
    FUNCTION_RESULTS[name] = (("failing", f"{len(failures)} of {n} rows failed", failures) if failures
                              else ("rows passed", f"all {n}", []))
    return FUNCTION_RESULTS[name]


# --- the spec ----------------------------------------------------------------

def load_project(folder, guard=None, clock=None):
    """the project (the checker's view of it), its operations as written and
    its stories as (id, story, source, path) in file-name, then file order;
    fills PHRASES; guard, the root every file must resolve inside, or None
    (settings.Settings.guard); clock as for check.project_of"""
    P = checker.project_of(folder, guard, clock)
    refused = []
    for path in sorted(glob.glob(f"{folder}/*.edda") + glob.glob(f"{folder}/*.edda.vc")):
        src, shape, meaning, history, _ = checker.check(path, P)
        refused += [f"{os.path.relpath(path)}:{line}: {rule}: {msg}" for rule, line, msg in src + shape + meaning + history]
    if refused:
        raise SpecRefused(refused)
    operations, stories = {}, []
    PHRASES["entities"].clear()
    PHRASES["roles"].clear()
    RULES["operations"].clear()
    RULES["always"].clear()
    RULES["functions"].clear()
    for path in sorted(glob.glob(f"{folder}/*.edda")):
        source, data = checker.load(path, guard)

        def line(at):
            return f"{os.path.relpath(path)}:{source.line(at)}"
        for section in ("entities", "roles"):
            for name, block in (data.get(section) or {}).items():
                PHRASES[section][name] = block.get("properties") or {}
        for name, fn in (data.get("functions") or {}).items():
            RULES["functions"][name] = [line(("functions", name, "examples", i)) for i, _ in enumerate(fn["examples"])]
        for name, block in (data.get("entities") or {}).items():
            RULES["always"][name] = [(fact_text(f), line(("entities", name, "always", i) + (("fact",) if isinstance(f, dict) else ())))
                                     for i, f in enumerate(block.get("always") or [])]
        for sid, st in (data.get("stories") or {}).items():
            operations.update(st.get("operations") or {})
            stories.append((sid, st, source, path))
            for name, op in (st.get("operations") or {}).items():
                at = ("stories", sid, "operations", name)
                RULES["operations"][name] = {
                    "line": line(at),
                    "refuse": [(r["when"], r["reason"], line(at + ("refuse", i, "when")))
                               for i, r in enumerate(op.get("refuse") or [])],
                    "ensure": [(fact_text(f), line(at + ("ensure", i) + (("fact",) if isinstance(f, dict) else ())))
                               for i, f in enumerate(op.get("ensure") or [])],
                    "also_changes": list(op.get("also_changes") or [])}
    return P, operations, stories


fact_text = checker.fact_text
entity_kinds = checker.entity_kinds
kinds_reached = checker.kinds_reached


def operations_run(P, text, reads, calls):
    """every operation evaluating text makes run, each once: those it
    calls by name (a step's call among them), in the text's order, then
    those the reads it calls and the computed properties it reads make
    run (check.call_paths); reads and calls as walk_reads gives them"""
    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, TypeError, ValueError):
        return []
    named = [n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in P.operations]
    reach = P.call_reach()
    nested = set().union(*(reach.get(x, set()) for x in calls | reads))
    return list(dict.fromkeys(named + sorted(nested)))


def needs(story, P):
    """why a story cannot run yet, or None: no examples, or a missing
    binding: an entity a given makes, or an operation anything the
    runner evaluates makes run (check.evaluated: each step's at:, call
    and then facts, every expression of the called operation, the
    always facts every call is held to; and through them the computed
    properties they read and the reads they call, operations_run).
    The clock is no reason: the checker refuses an example that uses
    time and has no start (no_clock_start)"""
    examples = story.get("examples") or {}
    if not examples:
        return "no examples"
    for ex in examples.values():
        for g in ex.get("given") or []:
            entity = next(k for k in g if k != "with")
            if entity != "actor" and entity not in binding.ENTITIES:
                return f"no binding for entity {entity}"
        for _, text, reads, calls in checker.evaluated(P, ex):
            for o in operations_run(P, text, reads, calls):
                if o not in binding.OPERATIONS:
                    return f"no binding for {o}"
    return None


# --- one example ---------------------------------------------------------------

OPERATIONS = {}     # the project's operations as written, set by run()
PROJECT = [None]    # the checker's view of the project, set by run()
STORIES = {}        # the project's stories as written, by id, set by run()
STORY_FILES = {}    # the .edda file of each story, by id, set by run()
PHRASES = {"entities": {}, "roles": {}}     # property type phrases as written, set by load_project()
RULES = {"operations": {}, "always": {}, "functions": {}}    # each operation's rules, each entity's always-rules
                                                             # and each function's rows, with their lines, set by load_project()
GIVENS = []         # the things the example's givens made, set by run_example()


def optional(phrase):
    return isinstance(phrase, str) and ", OPTIONAL" in phrase


def inputs_of(name, args, kwargs):
    """section 6: the required inputs by position, and every optional one
    by keyword, None when left out"""
    inputs = OPERATIONS[name].get("inputs") or {}
    required = [n for n, t in inputs.items() if not optional(t)]
    return dict(zip(required, args)), dict({n: None for n, t in inputs.items() if optional(t)}, **kwargs)


def permitted(name, actor, args, kwargs):
    """section 3: any of the actor's roles passes any who-line, condition included"""
    required, optionals = inputs_of(name, args, kwargs)
    env = dict(required, **optionals, ACTOR=actor)
    for w in OPERATIONS[name].get("who") or []:
        if w["role"] in actor.roles and ("when" not in w or evaluate(w["when"], env)):
            return True
    return False


def run_operation(name, actor, args, kwargs):
    """the operation's return; raises binding.Refused; actor None is a read
    inside a fact, with no permission check. The call is held to the
    operation's rules (section 6): permission, then the first refuse
    condition that holds, which the code must give, reason for reason,
    or none; a refused call changes nothing; a call not refused makes
    every ensure and always-rule hold and changes no stored location the
    spec does not name. A broken rule raises RuleBroken. While generated
    cases run, a condition before it that cannot be judged also allows
    its own reason, and with none that holds, no refusal; a rule that
    cannot be judged goes in unjudged, raised when nothing failed"""
    if name not in binding.OPERATIONS:     # needs() should have found it first: the story is not run
        raise binding.NotBound(name)
    if actor is not None and not permitted(name, actor, args, kwargs):
        raise binding.Refused(f"{name} is not allowed for {', '.join(actor.roles)}")
    rules = RULES["operations"][name]
    required, optionals = inputs_of(name, args, kwargs)
    scope = dict(required, **optionals)
    if actor is not None:
        scope["ACTOR"] = actor
    unjudged = []
    expected, unknown = refusal(name, rules, scope, unjudged)
    if RECORD[0] is not None and "returns" in OPERATIONS[name]:
        found = []  # what a read gives back derives from what its returns reads,
        try:        # and its order from what ordered_by reads on each item
            found = evaluate(OPERATIONS[name]["returns"], scope)
        except NoRow:
            raise
        except (Fail, binding.UnsetRead):
            pass
        for item in found if type(found) is list else []:
            for o in checker.listing(OPERATIONS[name].get("ordered_by")) if isinstance(item, binding.Thing) else []:
                try:
                    evaluate(o, {k: v for k, v in scope.items() if k == "ACTOR"} | {kind_of(item): item})
                except NoRow:
                    raise
                except (Fail, binding.UnsetRead):
                    pass
    roots = GIVENS + list(scope.values())
    before = snapshot(roots)
    if expected is None:
        scope["OLD"] = old_values(rules["ensure"], scope)
        places, possible = named(name, rules, scope, unjudged)    # before the call too: what it derived from then
    try:
        result = binding.OPERATIONS[name](actor, *args, **optionals)
    except binding.Refused as r:
        due = list(dict.fromkeys([u[1] for u in unknown] + ([expected[1]] if expected else [])))
        if r.reason not in due:
            if not unknown and expected is None:
                raise RuleBroken([(rules["line"], None, f"{name} refused: {show(r.reason)}, but the spec does not refuse")], unjudged)
            should = " or ".join(show(x) for x in due) + ("" if expected else ", or not at all")
            raise RuleBroken([(expected[2] if expected else rules["line"], None,
                               f"{name} should refuse: {should}, but it refused: {show(r.reason)}")], unjudged)
        broken = changed(name, before, set())
        if broken:
            raise RuleBroken([(rules["line"], None, m) for m in broken], unjudged)
        if unjudged:    # which refusal is due is not known; that it changed nothing is
            raise unjudged[0][2]
        raise
    if expected is not None:
        raise RuleBroken([(expected[2], None, f"{name} should refuse: {show(expected[1])}, but it did not refuse")], unjudged)
    broken = []
    for text, at in rules["ensure"]:
        found = judged(text, scope, at, f"{name}: ensure {text}", unjudged)
        if found is not None:
            broken.append((at, None, f"{name}: ensure {text}: found {found}"))
    if not ALWAYS[0]:     # a read inside an always fact keeps its other checks, not these
        ALWAYS[0], saved, RECORD[0] = True, RECORD[0], None
        try:
            for thing in reachable(roots):
                for text, at in RULES["always"].get(kind_of(thing)) or []:
                    on = f"{name}: always {text}, on {show(thing, False)}"
                    found = judged(text, own_scope(thing, kind_of(thing)), at, on, unjudged)
                    if found is not None:
                        broken.append((at, None, f"{on}: found {found}"))
        finally:
            ALWAYS[0], RECORD[0] = False, saved
    more, could = named(name, rules, scope, unjudged)
    places, possible = places | more, possible | could
    broken += [(rules["line"], None, m) for m in changed(name, before, places, possible)]
    if broken:
        raise RuleBroken(broken, unjudged)
    if unjudged:
        raise unjudged[0][2]    # nothing failed, something could not be judged: what the binding cannot give
    return result


def set_clock(t):
    """the one way the clock is set or moved: NOW becomes t, and the
    binding's clock(now), when it has one, hears it before anything is
    read at that time: t a datetime with no zone, the business zone's
    wall clock, or None when there is no clock (section 9)"""
    NOW[0] = t
    hook = getattr(binding, "clock", None)
    if hook is not None:
        hook(t)


def cannot_judge():
    """what the binding cannot give: no binding, an unset value read"""
    return binding.NotBound, binding.UnsetRead, UnsetFail


def refusal(name, rules, scope, unjudged):
    """(the first refuse rule whose condition holds, or None; the refuse
    rules before it whose condition could not be judged). Those are judged
    only while generated cases run, each put in unjudged; otherwise what
    the binding cannot give is raised. Conditions after the first that
    holds are not read: they cannot change the verdict"""
    unknown = []
    for r in rules["refuse"]:
        try:
            if evaluate(r[0], scope):
                return r, unknown
        except cannot_judge() as e:
            if not UNSET_ENDS[0]:
                raise
            unknown.append(r)
            unjudged.append((r[2], f"{name}: refuse when {r[0]}", e))
    return None, unknown


def judged(text, env, at, what, unjudged):
    """judge; while generated cases run, a fact that meets what the binding
    cannot give is not judged: (at, what, the exception) goes in unjudged,
    and None is given, so the call's other rules are still judged"""
    try:
        return judge(text, env)
    except cannot_judge() as e:
        if not UNSET_ENDS[0]:
            raise
        unjudged.append((at, what, e))
        return None


# --- the frame rule and OLD (section 6) -------------------------------------------

MISSING = object()      # a stored property the thing does not hold
RECORD = [None]         # the (id of the thing, property) locations read, while derives records
ALWAYS = [False]        # True while the always facts after a call are judged
UNSET_ENDS = [False]    # True while generated cases run: judge passes an unset read on (tools/generate.py)


def fields(thing):
    """a thing's own dict, raw: an unset value stays unread"""
    return object.__getattribute__(thing, "__dict__")


def kind_of(thing):
    return dict.get(fields(thing), "_entity")


def stored(kind):
    """the stored properties of an entity, as declared: neither computed nor derived"""
    return [p for p, phrase in (PHRASES["entities"].get(kind) or {}).items()
            if isinstance(phrase, str) and not phrase.endswith(", DERIVED")]


def declared(thing):
    """the stored properties of a thing: an entity's, or an actor's from its roles"""
    if kind_of(thing) != "actor":
        return stored(kind_of(thing))
    return list(dict.fromkeys(p for r in dict.get(fields(thing), "roles") or []
                              for p in PHRASES["roles"].get(r) or {}))


def reachable(roots):
    """every entity reachable from roots through stored properties, raw, in
    the order first reached, and every actor among them, not looked into;
    an unset value is not read"""
    out, seen, stack = [], set(), list(reversed(roots))
    while stack:
        x = stack.pop()
        if type(x) is list:
            stack.extend(reversed(x))
            continue
        if not isinstance(x, binding.Thing) or id(x) in seen:
            continue
        if kind_of(x) == "actor":
            seen.add(id(x))
            out.append(x)
            continue
        if kind_of(x) not in PHRASES["entities"]:
            continue
        seen.add(id(x))
        out.append(x)
        d = fields(x)
        stack.extend(reversed([dict.get(d, p) for p in stored(kind_of(x)) if p in d]))
    return out


def frozen(v):
    """a deep, frozen copy that keeps every identity: lists copied, an entity
    or an unset value the same object, a plain value as it is"""
    return [frozen(x) for x in v] if type(v) is list else v


def same(a, b):
    """is the value b the frozen value a: an entity or an unset value by
    identity, a list element by element, a time by its moment (moment),
    any other value by type and value; nothing unset is read"""
    if a is b:
        return True
    if type(a) is list and type(b) is list:
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if type(a) is not type(b) or a is MISSING or type(a) is binding.Unset or isinstance(a, binding.Thing):
        return False
    return moment(a) == moment(b)


def snapshot(roots):
    """every stored property location of every entity reachable from roots,
    and of every actor among them, (thing, property) to its frozen value"""
    return [(t, p, frozen(dict.get(fields(t), p, MISSING))) for t in reachable(roots) for p in declared(t)]


def label(thing):
    d = fields(thing)
    return d.get("_given") or d.get("_entity")


def changed(name, before, places, possible=()):
    """a message for each location in before that changed and is not one of
    places, (id of the thing, property), nor one possible may name, (kind
    of the thing, property or "*" for any): that change is not judged"""
    return [f"{name} changed {label(t)}.{p}, which the spec does not name"
            for t, p, v in before
            if not same(v, dict.get(fields(t), p, MISSING)) and (id(t), p) not in places
            and (kind_of(t), p) not in possible and (kind_of(t), "*") not in possible]


def old_values(ensure, scope):
    """OLD for the ensure facts after the call: each OLD(x) taken now, as a
    frozen copy, for every value of the comprehension variables x is
    inside, and looked up after the call by the text of x and the names it
    uses, each by what the call cannot change (keyed)"""
    table = []
    env = dict(scope, OLD=lambda x, env: value(x, env))     # before the call OLD(x) is x
    for text, _ in ensure:
        gather(ast.parse(text, mode="eval").body, env, scope, table)

    def old(x, env):
        text, names = ast.unparse(x), uses(x, env, scope)
        for t, bound, v in table:
            if t == text and keyed(bound, names):
                if isinstance(v, (Fail, binding.NotBound)):     # x could not be read before the call
                    raise v
                return v
        raise Fail(f"OLD({text}) has no value for " + ", ".join(f"{n} = {show(env[n])}" for n, _ in names)
                   + ": it was not there before the call")
    return old


def uses(x, env, scope):
    """the names x uses that env gives a value, by name, each with its key:
    None for an input or the actor, bound by name for the whole call, so
    a value the call changes still finds its OLD; for a comprehension's
    name the value it takes and a frozen copy of it"""
    found = sorted({n.id for n in ast.walk(x) if isinstance(n, ast.Name)} - {"OLD"})
    return [(n, None if n in scope and env[n] is scope[n] else (env[n], frozen(env[n])))
            for n in found if n in env]


def keyed(before, now):
    """do the names of an OLD(x) taken before the call match those of one
    after: the same names, an input by name alone, a comprehension's name
    by the same value it took before, an entity or a list by identity"""
    if [n for n, _ in before] != [n for n, _ in now]:
        return False
    return all(a is b if a is None or b is None else a[0] is b[0] or same(a[1], b[0])
               for (_, a), (_, b) in zip(before, now))


def gather(n, env, scope, table):
    """into table, (text of x, the names x uses with their keys, its frozen
    value, or a Fail or no binding met reading it) for each OLD(x) in n, inside a comprehension once for
    each value its variables take now; a filter is not applied, so a value
    the call lets in still has its OLD"""
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "OLD":
        x, bound = n.args[0], uses(n.args[0], env, scope)
        text = ast.unparse(x)
        if any(t == text and keyed(b, bound) for t, b, _ in table):
            return
        try:
            v = frozen(value(x, env))
        except NoRow:
            raise
        except Fail as e:
            v = e
        except binding.UnsetRead as u:
            v = UnsetFail(str(u))
        except binding.NotBound as e:   # while generated cases run, only the facts that use it are not judged
            if not UNSET_ENDS[0]:
                raise
            v = e
        table.append((text, bound, v))
        return
    if isinstance(n, (ast.ListComp, ast.GeneratorExp)):
        gather_loop(n.generators, n.elt, env, scope, table)
        return
    for child in ast.iter_child_nodes(n):
        gather(child, env, scope, table)


def gather_loop(gens, elt, env, scope, table):
    if not gens:
        gather(elt, env, scope, table)
        return
    g = gens[0]
    gather(g.iter, env, scope, table)
    try:
        source = value(g.iter, env)
    except NoRow:
        raise
    except (Fail, binding.UnsetRead):
        return
    except binding.NotBound:    # gather(g.iter) above kept it for an OLD there
        if not UNSET_ENDS[0]:
            raise
        return
    for x in source if isinstance(source, list) else []:
        inner = dict(env, **{g.target.id: x})
        for c in g.ifs:
            gather(c, inner, scope, table)
        gather_loop(gens[1:], elt, inner, scope, table)


def named(name, rules, scope, unjudged):
    """the locations the spec names, as (id of the thing, property): the
    left operand of an ensure comparison, len of it, and each also_changes
    path; a computed or derived property named also names the stored
    locations it derives from, on that thing (derives). A path or a
    computed property that meets what the binding cannot give names what
    was read before it; while generated cases run, its part of the frame
    rule goes in unjudged and what its unread rest could name in possible
    (unread). Gives (places, possible)"""
    places, possible = set(), set()
    paths = []
    for text, _ in rules["ensure"]:
        n = ast.parse(text, mode="eval").body
        if isinstance(n, ast.Compare) and len(n.ops) == 1:
            left = n.left
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len" and len(left.args) == 1:
                left = left.args[0]
            paths.append(left)
    paths += [ast.parse(p, mode="eval").body for p in rules["also_changes"]]
    for n in paths:
        if not isinstance(n, ast.Attribute):
            continue
        try:
            thing = value(n.value, scope)
        except cannot_judge() as e:
            unread(e, unjudged, rules["line"], name, n, possible)
            continue
        except NoRow:
            raise
        except Fail:
            continue        # the fact itself fails
        if not isinstance(thing, binding.Thing):
            continue
        places.add((id(thing), n.attr))
        saved, RECORD[0] = RECORD[0], set()
        try:
            try:
                derives(thing, n.attr)
            except cannot_judge() as e:
                unread(e, unjudged, rules["line"], name, n, possible)
            except NoRow:
                raise
            except Fail:
                pass        # what was read before it failed is named
            places |= RECORD[0]
        finally:
            RECORD[0] = saved
    return places, possible


def unread(e, unjudged, at, name, path, possible):
    """a frame rule path of operation name that met what the binding cannot
    give: while generated cases run it goes in unjudged, once, and what
    its unread rest could name goes in possible (could_name); with no
    such bound, any property of a kind it could reach, and the report
    says so. Otherwise no binding is raised, and an unset value names
    nothing more"""
    if not UNSET_ENDS[0]:
        if isinstance(e, binding.NotBound):
            raise e
        return
    what = f"{name}: frame rule, {ast.unparse(path)}"
    bound = could_name(name, path)
    if bound is None:
        kinds = could_reach(name, path)
        bound = {(k, "*") for k in kinds}
        what += f" (no bound on what it names: no change to {', '.join(sorted(kinds))} is judged)"
    possible |= bound
    if all((a, w) != (at, what) for a, w, _ in unjudged):
        unjudged.append((at, what, e))


class Reads(checker.Expr):
    """the checker's typing of an expression, silent, keeping the
    (entity, property) pairs it reads (as computed_cycle does), each
    actor property it reads as ("actor", property), and whether some
    property is read on a value of unknown type (open)"""

    def __init__(self, scope, own=None):
        super().__init__(PROJECT[0], scope, silent=True)
        self.own, self.reads, self.calls, self.open, self.types = own, set(), set(), False, {}

    def visit(self, n, scope):
        t = super().visit(n, scope)
        self.types[id(n)] = t
        return t

    def of(self, text):
        self.src, body = text, ast.parse(text, mode="eval").body
        self.visit(body, self.scope)
        for n in ast.walk(body):
            if isinstance(n, ast.Attribute):
                t = self.types.get(id(n.value))
                kinds = [None] if t is None else checker.alts(t)
                self.open |= None in kinds
                self.reads |= {("actor", n.attr) for a in kinds if checker.is_actor(a)}
        return self


def operation_scope(o):
    """the types an operation's own expressions see: each input and ACTOR,
    as the checker gives them to a read's summary"""
    op = PROJECT[0].operations[o]
    scope = {("var", n): True for n, _, _ in op["inputs"]}
    scope.update({n: t for n, t, _ in op["inputs"]})
    scope["ACTOR"] = ("actor", ("one", frozenset(r for r in op["who"] if isinstance(r, str))))
    return scope


def could_name(name, path):
    """a static over-approximation of what path, in operation name, could
    name: every (entity, property) its text reads, and transitively what
    each computed property it reads reads, every stored property of a
    derived one ((entity, "*")), and what a read it calls reads (its
    refuse conditions, returns and ordered_by); actor properties as
    ("actor", property). None when some property is read on a value of
    unknown type"""
    P = PROJECT[0]
    out, seen = set(), set()
    work = [Reads(operation_scope(name)).of(ast.unparse(path))]
    while work:
        r = work.pop()
        if r.open:
            return None
        for k, p in r.reads - out:
            out.add((k, p))
            ent = P.entities.get(k)
            if ent and p in ent["derived"]:
                out.add((k, "*"))
            elif ent and isinstance(ent["computed"].get(p), str):
                work.append(Reads(dict(ent["props"]), k).of(ent["computed"][p]))
        for o in r.calls - seen:
            seen.add(o)
            op, scope = P.operations[o], operation_scope(o)
            work += [Reads(scope).of(x) for x in op["refuse_when"] + [op["returns"]] if isinstance(x, str)]
            item = {"ACTOR": scope["ACTOR"]}
            rl = checker.as_list(op["returns_type"])
            if rl and checker.is_entity(rl[1]):
                item.update({("var", rl[1][1]): True, rl[1][1]: rl[1]})
            work += [Reads(item).of(x) for x in op["order_exprs"] if isinstance(x, str)]
    return out


def could_reach(name, path):
    """the kinds of thing path, in operation name, could reach: from the
    types of the names it uses and of every read's result, through stored
    properties, "actor" among them; every kind when one of those types is
    unknown"""
    P, scope = PROJECT[0], operation_scope(name)
    roots = [scope.get(n.id) for n in ast.walk(path) if isinstance(n, ast.Name)]
    roots += [op["returns_type"] for op in P.operations.values() if isinstance(op["returns"], str)]
    every = set(P.entities) | {"actor"}
    if any(t is None or None in checker.alts(t) for t in roots):
        return every
    kinds = kinds_reached(P, set().union(*(entity_kinds(t) for t in roots)))
    types = roots + [t for k in kinds for t in P.entities[k]["props"].values()]
    if any(t is None for t in types):
        return every
    return kinds | ({"actor"} if any(holds_actor(t) for t in types) else set())


def holds_actor(t):
    """may a value of type t be an actor, alone or in a list"""
    if checker.is_actor(t):
        return True
    if checker.is_list(t):
        return holds_actor(t[1])
    return checker.is_either(t) and any(holds_actor(a) for a in t[1])


def derives(thing, prop):
    """while recording: thing.prop read. A stored property records its
    location; a derived one (section 11) every stored location of that
    thing; a computed one is its expression evaluated on that thing, so
    its own reads, through other computed properties and the read
    operations it calls, are recorded, and gives that value. Anything
    else gives MISSING, read as usual"""
    kind = kind_of(thing)
    ent = PROJECT[0].entities.get(kind)
    if ent is None:
        if prop in declared(thing):     # an actor's
            RECORD[0].add((id(thing), prop))
        return MISSING
    if prop in stored(kind):
        RECORD[0].add((id(thing), prop))
    elif prop in ent["derived"]:
        RECORD[0].update((id(thing), q) for q in stored(kind))
    elif isinstance(ent["computed"].get(prop), str):
        return evaluate(ent["computed"][prop], own_scope(thing, kind))
    return MISSING


def own_scope(thing, kind):
    """an always-rule's roots: the entity's own properties, each read only
    when the rule reaches it"""
    who = label(thing)
    return {p: Lazy(lambda p=p: read(thing, p, f"{who}.{p}")) for p in PHRASES["entities"].get(kind) or {}}


def holds_things(t):
    """may a value of type t be an entity or an actor, alone or in a list"""
    if checker.is_entity(t) or checker.is_actor(t):
        return True
    if checker.is_list(t):
        return holds_things(t[1])
    return checker.is_either(t) and any(holds_things(a) for a in t[1])


def given_props(g, kind):
    """the declared types of the given's properties"""
    P = PROJECT[0]
    if kind == "actor":
        roles = (g.get("with") or {}).get("roles") or []
        return P.actor_props(("all", frozenset(roles)))
    return P.entities[kind]["props"]


def left_out(phrases, values, name):
    """section 8: a stored property the given leaves out takes its DEFAULT
    (a time as a time, section 4), [] for MANY, None for OPTIONAL; any other is a binding.Unset named
    after the given and the property"""
    out = {}
    for p, phrase in phrases.items():
        m = checker.TYPE_RE.fullmatch(phrase) if isinstance(phrase, str) else None
        if p in values or not m or phrase.endswith(", DERIVED"):
            continue
        if phrase.startswith("DEFAULT "):
            out[p] = as_time(checker.default_value(phrase), checker.type_of_phrase(phrase))
        elif m.group("many"):
            out[p] = []
        elif m.group("optional"):
            out[p] = None
        else:
            out[p] = binding.Unset(f"{name}.{p}")
    return out


def given_phrases(g, kind):
    """the given's property phrases as written; an actor's from its roles in order"""
    if kind != "actor":
        return PHRASES["entities"].get(kind) or {}
    out = {}
    for r in (g.get("with") or {}).get("roles") or []:
        for p, phrase in (PHRASES["roles"].get(r) or {}).items():
            out.setdefault(p, phrase)
    return out


def as_time(v, t):
    """a quoted time written for a TIME property is a time (section 7.2)"""
    kinds = checker.alts(t)
    if isinstance(v, str) and "TIME" in kinds and "TEXT" not in kinds:
        return time_of(v)
    return v


def time_of(text):
    """the time a text written as section 7.2 says stands for: YYYY-MM-DD
    HH:MM, or YYYY-MM-DD for 00:00 that day"""
    return datetime.datetime.fromisoformat(text)


def make_givens(given, workdir):
    """the givens by name; a with: value names another given only where its
    property's declared type is an entity or an actor; role names, choice
    values and text stay as written, a time becomes a time; a property left
    out takes its DEFAULT, [] or None, or is a binding.Unset (section 8)"""
    names = {g[next(k for k in g if k != "with")] for g in given}
    made, pending = {}, list(given)

    def refs(g):
        """the with: values of g that name a given, by property"""
        kind = next(k for k in g if k != "with")
        props = given_props(g, kind)
        return {k: v for k, v in (g.get("with") or {}).items() if holds_things(props.get(k))}

    def resolve(v):
        if isinstance(v, list):
            return [resolve(x) for x in v]
        return made[v] if isinstance(v, str) and v in made else v

    def waits(g):
        vals = [x for v in refs(g).values() for x in (v if isinstance(v, list) else [v])]
        return any(isinstance(x, str) and x in names and x not in made for x in vals)

    while pending:
        ready = [g for g in pending if not waits(g)]
        if not ready:
            raise EddaError("the givens name each other in a loop")
        for g in ready:
            kind = next(k for k in g if k != "with")
            props = given_props(g, kind)
            values = {k: as_time(v, props.get(k)) for k, v in (g.get("with") or {}).items()}
            values.update({k: resolve(v) for k, v in refs(g).items()})
            values = binding.Values(left_out(given_phrases(g, kind), values, g[kind]), **values)
            try:
                if kind == "actor":
                    made[g[kind]] = binding.make_actor(g[kind], values.pop("roles", []), values)
                else:
                    made[g[kind]] = binding.ENTITIES[kind](g[kind], values, workdir)
            except (binding.NotBound, EddaError):
                raise
            except binding.UnsetRead as u:  # the maker used an unset value
                raise UnsetFail(f"given {g[kind]} could not be made: {u}")
            except Exception as e:  # the binding's maker crashed
                raise Fail(f"given {g[kind]} could not be made: {type(e).__name__}: {e}")
            if isinstance(made[g[kind]], binding.Thing):
                vars(made[g[kind]])["_given"] = g[kind]     # show() names it
            pending.remove(g)
    return made


def judge(text, env):
    """None when the fact holds, else what was found"""
    try:
        n = ast.parse(text, mode="eval").body
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and not isinstance(n.ops[0], (ast.Is, ast.IsNot)):
            left = value(n.left, env)
            if compare(n.ops[0], left, value(n.comparators[0], env)):
                return None
            return f"{ast.unparse(n.left)} is {show(left)}"
        return None if value(n, env) else "it is false"
    except Fail as e:
        if UNSET_ENDS[0] and isinstance(e, UnsetFail):
            raise
        return str(e)
    except binding.UnsetRead as u:    # an unset value the runner was handed back, used
        if UNSET_ENDS[0]:
            raise
        return str(u)


def run_example(ex, where, source, path, workdir):
    """the failures of one example, each (file:line, then text, found), and
    what had no binding, or None; the example stops at the first thing with
    no binding, keeping the failures found before it. A given that cannot
    be made is one failure with no then text.
    ACTOR is the latest call's actor and RESULT its return, both kept
    across later steps without a call; after a refusal RESULT has none"""
    def line(at):
        return f"{os.path.relpath(path)}:{source.line(at)}"
    failures = []
    try:
        start_clock(ex)
    except OverflowError as e:
        return [(line(where), None, f"the clock cannot start: {e}")], None
    try:
        try:
            env = make_givens(ex.get("given") or [], workdir)
        except Fail as e:
            return [(line(where + ("given",)), None, str(e))], None
        GIVENS[:] = env.values()
        for i, step in enumerate(ex.get("steps") or []):
            if not run_step(step, i, env, where, line, failures):
                break
    except binding.NotBound as e:
        return failures, str(e)
    return failures, None


def start_clock(ex):
    """the clock of an example (section 8): stopped at its start, its
    starts_at: or the project's clock_start:, when it uses time; none
    otherwise. Nothing reads the machine's clock"""
    P = PROJECT[0]
    t = None
    if checker.time_uses(P, ex):
        text = checker.clock_start(P, ex)
        if text is None:
            raise EddaError("an example that uses time has no start; the checker refuses it (no_clock_start)")
        t = checker.resolved(checker.parse_time(text), ZONE[0])
    set_clock(t)


def move_clock(text, env):
    """the clock after a step's at: (section 8): a time, or NOW, the time
    before the step, moved by durations; raises Fail when it would go back"""
    t = checker.parse_time(text)
    try:
        t = checker.resolved(t, ZONE[0]) if t is not None else value(ast.parse(text, mode="eval").body, env)
    except OverflowError as e:
        raise Fail(f"at {text}: {e}")
    if moment(t) < moment(NOW[0]):
        raise Fail(checker.backwards(text, t, NOW[0]))
    set_clock(t)


def run_step(step, i, env, where, line, failures):
    """judge one step into failures; False when a wrong verdict, or an at:
    that would move the clock back, ends the example"""
    then = step.get("then") or []
    at = where + ("steps", i, "then")
    first = 0
    if "when" in step:
        when, first = step["when"], 1
        env["ACTOR"] = env[when["actor"]]
        env.pop("RESULT", None)
        if "at" in when:    # failures as the call's own: a Fail is found here, a broken rule its own
            try:
                move_clock(when["at"], env)
            except Fail as e:
                failures.append((line(where + ("steps", i, "when", "at")), None, str(e)))
                return False
            except RuleBroken as e:     # a read inside the at: broke a rule: the example ends here
                failures.extend(e.failures)
                return False
        call = ast.parse(when["call"], mode="eval").body
        try:
            args = [value(a, env) for a in call.args]
            kwargs = {k.arg: value(k.value, env) for k in call.keywords}
            env["RESULT"] = run_operation(call.func.id, env["ACTOR"], args, kwargs)
            got = "DONE"
        except Fail as e:           # an argument or a who-line condition has no value
            got = str(e)
        except binding.UnsetRead as u:  # the code used an unset value
            got = str(u)
        except binding.Refused as r:
            got = f"refused: {show(r.reason)}"
        except RuleBroken as e:     # the code broke a rule of the spec: the example ends here
            failures.extend(e.failures)
            return False
        except (EddaError, binding.NotBound):
            raise
        except Exception as e:      # the code under test crashed
            got = f"raised {type(e).__name__}: {e}"
        verdict = then[0] if then else "DONE"
        expected = "DONE" if verdict == "DONE" else f"refused: {show(verdict.get('refused'))}"
        if got != expected:
            failures.append((line(at + (0,)), expected, got))
            return False
    for j, text in enumerate(then[first:], first):
        try:
            found = judge(text, env)
        except RuleBroken as e:     # a read inside the fact broke a rule
            failures.extend(e.failures)
            continue
        if found is not None:
            failures.append((line(at + (j,)), text, found))
    return True


# --- the run -----------------------------------------------------------------

def run(folder, wanted=(), guard=None, clock=None):
    """the result of each story: (id, status, detail, [(title, failures)]);
    status is "examples passed", failing or not run; failures are
    (file:line, then text, found). A story with a failure is failing even
    when something after it had no binding; guard and clock as for
    load_project"""
    P, operations, stories = load_project(folder, guard, clock)
    PROJECT[0] = P
    FUNCTION_RESULTS.clear()
    ZONE[0] = P.zone
    OPERATIONS.clear()
    OPERATIONS.update(operations)
    STORIES.clear()
    STORIES.update((sid, st) for sid, st, _, _ in stories)
    STORY_FILES.clear()
    STORY_FILES.update((sid, path) for sid, _, _, path in stories)
    known = {sid for sid, *_ in stories}
    unknown = [s for s in wanted if s not in known]
    if unknown:
        raise UnknownStory(f"unknown story: {', '.join(unknown)}")
    out = []
    for sid, st, source, path in stories:
        if wanted and sid not in wanted:
            continue
        why = needs(st, P)
        if why:
            out.append((sid, "not run", why, []))
            continue
        results, unbound = [], []
        for title, ex in st["examples"].items():
            with tempfile.TemporaryDirectory() as workdir:
                failures, missing = run_example(ex, ("stories", sid, "examples", title), source, path, workdir)
            results.append((title, failures))
            if missing:
                unbound.append(f"no binding for {missing}")
        failed = [r for r in results if r[1]]
        if failed:
            detail = f"{len(failed)} of {len(results)} examples failed"
            out.append((sid, "failing", "; ".join([detail] + unbound[:1]), failed))
        elif unbound:
            out.append((sid, "not run", unbound[0], []))
        else:
            out.append((sid, "examples passed", f"all {len(results)}", []))
    return out


def main(argv, result=None):
    """the exit code; result, when given, a dict filled for edda run --json
    (reference section 13): stories, failures and counts"""
    ap = argparse.ArgumentParser(description="run the examples of Edda's stories through the binding")
    ap.add_argument("--root", help="the project: the folder holding edda.yaml and the spec folder "
                                   "(default Edda's own)")
    ap.add_argument("--project", help="the folder of .edda files (default the spec folder edda.yaml names, specs/)")
    ap.add_argument("--seed", type=int, help="the seed of the generated cases, to replay a run")
    ap.add_argument("stories", nargs="*", metavar="STORY")
    a = ap.parse_args(argv)
    usage = settings.not_there([a.root, a.project])
    if usage:
        print(usage)
        return 2
    project, code = settings.open_project(a.root, a.project)
    if project is None:
        return code
    if not os.path.isdir(project.folder):       # the spec folder edda.yaml names
        print(f"no such folder: {os.path.relpath(project.folder)}")
        return 1
    generated = project.generated
    if generated["on"]:
        try:
            import generate     # Hypothesis only now
        except ImportError as e:
            print(f"edda failed: generated cases need Hypothesis ({e}); "
                  "install it with python3 -m pip install -r tools/requirements.txt")
            return 3
        seed = a.seed if a.seed is not None else random.SystemRandom().randrange(1, 2 ** 31)
        again = [x for i, x in enumerate(argv)     # this command, its --seed this seed
                 if x != "--seed" and not x.startswith("--seed=") and (i == 0 or argv[i - 1] != "--seed")]
        replay = shlex.join(["python3", os.path.relpath(os.path.abspath(__file__)), *again, "--seed", str(seed)])
    PROJECT[0] = None       # run() sets it: the functions below are this project's
    try:
        out = run(project.folder, a.stories, project.guard, project.clock)
    except UnknownStory as e:
        print(f"edda failed: {e}")
        return 2
    except EddaError as e:
        print(f"edda failed: {e}")
        return 3
    except SpecRefused as e:
        print("the spec does not check; tools/check.py says:")
        for line in e.args[0]:
            print(f"    {line}")
        return 1
    bad = False
    at = []         # (rule, file, line, found by, message) of each failure, for the count line and the log
    shown = []      # each story's result, for --json, filled as it is run
    say = print if result is None else (lambda *_: None)     # with --json, the fields say it
    if result is not None:
        result["stories"] = shown
        result["functions"] = []
    reported = []   # the client functions whose rows were run against the real one and reported (section 9)

    def report_rows(names):
        """run and report the rows of each function of names not reported
        yet, in block order; a failing row fails the run"""
        nonlocal bad
        for kind, name in PROJECT[0].block_order:
            if kind != "function" or name not in names or name in reported:
                continue
            reported.append(name)
            status, detail, failures = function_rows(name)
            say(f"function {name}: {status}: {detail}")
            for line, _, found in failures:
                say(f"    {line}: {found}")
                at.append(("failing_function", *place_of(line), "example run", found))
            bad = bad or status == "failing"
            if result is not None:
                result["functions"].append({"name": name, "status": status, "detail": detail,
                                            "failures": [{"at": line, "found": found} for line, _, found in failures]})
    if PROJECT[0] is not None:      # first: every function, or every one the named stories reach
        report_rows(set(PROJECT[0].functions) if not a.stories else set().union(*(
            checker.story_functions(PROJECT[0], sid, STORIES[sid], PROJECT[0].stories[sid],
                                    checker.load(STORY_FILES[sid], project.guard)[0]) for sid in a.stories)))
    for sid, status, detail, failed in out:
        say(f"{sid}: {status}: {detail}")
        story = {"id": sid, "status": status, "detail": detail, "examples_failed": [], "generated": []}
        shown.append(story)
        for title, failures in failed:
            say(f"    example {show(title)} failed")
            story["examples_failed"].append({"title": title, "failures": []})
            for line, text, found in failures:
                said = f"then {text}: found {found}" if text else found
                say(f"        {line}: " + said)
                story["examples_failed"][-1]["failures"].append({"at": line, "then": text, "found": found})
                at.append(("failing_example", *place_of(line), "example run", said))
        if generated["on"]:
            try:
                lines, broke = generate.cases(sys.modules[__name__], sid, STORIES[sid], generated["runs"],
                                              generated["steps"], seed, replay)
            except EddaError as e:
                print(f"edda failed: {e}")
                return 3
            story["generated"] = lines
            say("\n".join(lines))
            bad = bad or broke
            if broke:
                rules = [(place_of(m.group(1)), m.string.strip()) for m in map(BROKEN_RULE.match, lines[1:])
                         if m and ": not judged: " not in m.string]
                at += [("failing_case", *p, "generated case", said)
                       for p, said in rules or [((STORY_FILES[sid], None), lines[0])]]
    if PROJECT[0] is not None:      # rows generated cases ran against the real function for any other reason
        report_rows(set(FUNCTION_RESULTS))
    problems = [watch.problem(rule, path, line, how, project.root, checker.load, project.guard)
                for rule, path, line, how, _ in at]
    counts = watch.count_line(problems)
    if counts:
        say(counts)
    if result is not None:
        result.update(counts=watch.counts(problems),
                      failures=[dict(p, message=said) for p, (*_, said) in zip(problems, at)])
    watch.log(problems, project.root, project.problem_log == "local")
    return 1 if bad or any(status == "failing" for _, status, _, _ in out) else 0


BROKEN_RULE = re.compile(r"    (\S[^:]*:\d+): ")     # a broken rule's line in a generated failure


def place_of(at):
    """(path, line) of a runner's file:line, the path from the working folder;
    no line when it names none"""
    path, _, n = at.rpartition(":")
    return (os.path.abspath(path), int(n)) if path and n.isdigit() else (os.path.abspath(at), None)


if __name__ == "__main__":
    import edda     # the one command: its exit codes, Edda failing exits 3
    sys.exit(edda.main(["run", *sys.argv[1:]]))
