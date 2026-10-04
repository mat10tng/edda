#!/usr/bin/env python3
"""Run the examples of Edda's stories against real code, through the
binding (reference sections 8, 9 and 11).

    python3 tools/run.py [--project DIR] [STORY ...]

For each story (or each one named), each example: make the given things
through the binding, run each step's call as its actor, then judge each
then item: DONE, refused: "<reason>", or a fact, evaluated over the
parsed ast (the whitelist of section 7.1; never eval). The spec must
check first (tools/check.py). A story whose examples all pass is reported
"examples passed", never "done": done (reference section 11) needs more
than the runner computes. Exit 0 when no story failed, 1 when one failed
or the spec does not check, 3 when Edda itself failed.
"""
import argparse
import ast
import datetime
import glob
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as checker          # noqa: E402
import edda_binding as binding   # noqa: E402

CLOCK = {"NOW", "TODAY"}


class Fail(Exception):
    """the example fails here; the message says what was found"""


class EddaError(Exception):
    """Edda itself failed: a spec the checker should have refused"""


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


def compare(op, a, b):
    if isinstance(op, ast.Eq):
        return a == b
    if isinstance(op, ast.NotEq):
        return a != b
    if isinstance(op, (ast.Is, ast.IsNot)):
        return (a is None) == isinstance(op, ast.Is)
    if isinstance(op, (ast.In, ast.NotIn)):
        if not isinstance(b, (list, str)) or (isinstance(b, str) and not isinstance(a, str)):
            raise Fail(f"in of {show(a)} on {show(b)}")
        return (a in b) == isinstance(op, ast.In)
    if not ordered(a, b):
        raise Fail(f"a comparison of {show(a)} with {show(b)}")
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
            return env[n.id]
        if n.id == "RESULT":
            raise Fail("RESULT has no value after a refusal")
        if n.id == "ACTOR":
            raise Fail("ACTOR has no value before any call")
        if re.fullmatch(checker.NAME, n.id):
            return n.id                         # a choice value
        raise EddaError(f"{n.id} has no value here")
    if isinstance(n, ast.Attribute):
        obj = value(n.value, env)
        if not isinstance(obj, binding.Thing):
            raise Fail(f"{ast.unparse(n.value)} is no entity: {show(obj)}")
        try:
            v = getattr(obj, n.attr)
        except (binding.NotBound, EddaError):
            raise
        except binding.UnsetRead as u:
            if type(dict.get(object.__getattribute__(obj, "__dict__"), n.attr)) is binding.Unset:
                raise Fail(f"{ast.unparse(n)} is unset")    # this read itself
            raise Fail(str(u))          # the binding's property used an unset value
        except Exception as e:      # the binding's property crashed
            raise Fail(f"{ast.unparse(n)} raised {type(e).__name__}: {e}")
        if isinstance(v, binding.Unset):
            raise Fail(f"{ast.unparse(n)} is unset")
        return v
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
            return datetime.datetime.fromisoformat(args[0].value)
        if f in OPERATIONS:
            # a read inside a fact: as the checker itself, no actor, no permission (section 6)
            try:
                return run_operation(f, None, [value(a, env) for a in args],
                                     {k.arg: value(k.value, env) for k in n.keywords})
            except (Fail, EddaError, binding.NotBound):
                raise
            except binding.UnsetRead as u:
                raise Fail(str(u))
            except binding.Refused as r:
                raise Fail(f"{ast.unparse(n)} was refused: {show(r.reason)}")
            except Exception as e:      # the code under test crashed
                raise Fail(f"{ast.unparse(n)} raised {type(e).__name__}: {e}")
    raise EddaError(f"not an expression the runner knows: {ast.unparse(n)}")


# --- the spec ----------------------------------------------------------------

def load_project(folder):
    """the project (the checker's view of it), its operations as written and
    its stories as (id, story, source, path) in file-name, then file order;
    fills PHRASES"""
    P = checker.project_of(folder)
    refused = []
    for path in sorted(glob.glob(f"{folder}/*.edda") + glob.glob(f"{folder}/*.edda.vc")):
        src, shape, meaning, history, _ = checker.check(path, P)
        refused += [f"{os.path.relpath(path)}:{line}: {rule}: {msg}" for rule, line, msg in src + shape + meaning + history]
    if refused:
        raise SpecRefused(refused)
    operations, stories = {}, []
    PHRASES["entities"].clear()
    PHRASES["roles"].clear()
    for path in sorted(glob.glob(f"{folder}/*.edda")):
        source, data = checker.load(path)
        for section in ("entities", "roles"):
            for name, block in (data.get(section) or {}).items():
                PHRASES[section][name] = block.get("properties") or {}
        for sid, st in (data.get("stories") or {}).items():
            operations.update(st.get("operations") or {})
            stories.append((sid, st, source, path))
    return P, operations, stories


def uses_clock(text):
    """the clock names text reads directly"""
    return [n.id for n in ast.walk(ast.parse(text, mode="eval")) if isinstance(n, ast.Name) and n.id in CLOCK]


def walk(P, text, scope):
    """what text reads, typed as the checker types it: its (entity,
    property) pairs, ("CLOCK", name) for NOW or TODAY, and the operations
    with a text returns it calls"""
    E = checker.Expr(P, scope, silent=True)
    E.reads, E.calls = set(), set()
    E.run(text)
    return E.reads, E.calls


def on_clock(reads, timed):
    return any(e == "CLOCK" for e, _ in reads) or bool(reads & timed)


def clock_paths(P):
    """the operations and the computed properties that read the clock. An
    operation's summary is the checker's (operation_reads: its returns,
    refuse conditions and ordered_by, and those of every operation it
    calls, nested calls included); a computed property reads its own
    expression and the summaries of the operations it calls. Either reads
    the clock directly or through a computed property that does; that
    grows to a fixed point (the checker refuses loops of computed
    properties)"""
    summary = P.operation_reads()
    reads = {}
    for e, ent in P.entities.items():
        for p, expr in ent["computed"].items():
            if isinstance(expr, str):
                E = checker.Expr(P, dict(ent["props"]), silent=True)
                E.own, E.reads, E.calls = e, set(), set()
                E.run(expr)
                reads[(e, p)] = E.reads.union(*(summary[o] for o in E.calls))
    timed = set()
    while True:
        more = {x for x, r in reads.items() if on_clock(r, timed)} - timed
        if not more:
            return {o for o, r in summary.items() if on_clock(r, timed)}, timed
        timed |= more


def needs(story, operations, P):
    """why a story cannot run yet, or None: a missing binding first, then
    the clock; read in the call, the then facts, and the who-line and
    refuse conditions of the called operation, all the runner evaluates or
    the code decides, in the computed properties they read and in the
    operations they call (clock_paths)"""
    examples = story.get("examples") or {}
    if not examples:
        return "no examples"
    unbound, clock = [], []
    timed_ops, timed = clock_paths(P)

    def scan(text, scope):
        for name in uses_clock(text):
            clock.append(f"{name} needs the clock, not built yet")
        reads, calls = walk(P, text, scope)
        for e, p in sorted(reads & timed):
            clock.append(f"{e}.{p} needs the clock, not built yet")
        for o in sorted(calls & timed_ops):
            clock.append(f"{o} needs the clock, not built yet")
        for n in ast.walk(ast.parse(text, mode="eval")):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in operations \
                    and n.func.id not in binding.OPERATIONS:
                unbound.append(f"no binding for {n.func.id}")

    for ex in examples.values():
        scope = {}
        for g in ex.get("given") or []:
            entity = next(k for k in g if k != "with")
            if entity == "actor":
                scope[g[entity]] = ("actor", ("all", frozenset((g.get("with") or {}).get("roles") or [])))
            else:
                scope[g[entity]] = ("entity", entity)
                if entity not in binding.ENTITIES:
                    unbound.append(f"no binding for entity {entity}")
        for step in ex.get("steps") or []:
            when = step.get("when") or {}
            then = step.get("then") or []
            if "at" in when:
                clock.append("at: needs the clock, not built yet")
            if "call" in when:
                scope["ACTOR"] = scope.get(when.get("actor"))
                scope.pop("RESULT", None)
                scan(when["call"], scope)
                name = ast.parse(when["call"], mode="eval").body.func.id
                rt = checker.Expr(P, scope, silent=True).run(when["call"], call_slot=True)
                scope["RESULT"] = "NONE" if then and isinstance(then[0], dict) else rt
                op = P.operations.get(name) or {}
                inputs = {n: t for n, t, _ in op.get("inputs") or []}
                inputs["ACTOR"] = ("actor", ("one", frozenset(r for r in op.get("who") or [] if isinstance(r, str))))
                for w in operations.get(name, {}).get("who") or []:
                    if "when" in w:
                        scan(w["when"], inputs)
                for x in op.get("refuse_when") or []:
                    if isinstance(x, str):
                        scan(x, inputs)
            for text in then:
                if isinstance(text, str) and text != "DONE":
                    scan(text, scope)
    return (unbound + clock or [None])[0]


# --- one example ---------------------------------------------------------------

OPERATIONS = {}     # the project's operations as written, set by run()
PROJECT = [None]    # the checker's view of the project, set by run()
PHRASES = {"entities": {}, "roles": {}}     # property type phrases as written, set by load_project()


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
    inside a fact, with no permission check"""
    if actor is not None and not permitted(name, actor, args, kwargs):
        raise binding.Refused(f"{name} is not allowed for {', '.join(actor.roles)}")
    return binding.OPERATIONS[name](actor, *args, **inputs_of(name, args, kwargs)[1])


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
    """section 8: a stored property the given leaves out takes its DEFAULT,
    [] for MANY, None for OPTIONAL; any other is a binding.Unset named
    after the given and the property"""
    out = {}
    for p, phrase in phrases.items():
        m = checker.TYPE_RE.fullmatch(phrase) if isinstance(phrase, str) else None
        if p in values or not m or phrase.endswith(", DERIVED"):
            continue
        if phrase.startswith("DEFAULT "):
            out[p] = m.group("dchoice").split(" | ")[0] if m.group("dchoice") else ast.literal_eval(phrase[len("DEFAULT "):])
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
        return datetime.datetime.fromisoformat(v)
    return v


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
                raise Fail(f"given {g[kind]} could not be made: {u}")
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
        return str(e)
    except binding.UnsetRead as u:    # an unset value the runner was handed back, used
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
        try:
            env = make_givens(ex.get("given") or [], workdir)
        except Fail as e:
            return [(line(where + ("given",)), None, str(e))], None
        for i, step in enumerate(ex.get("steps") or []):
            if not run_step(step, i, env, where, line, failures):
                break
    except binding.NotBound as e:
        return failures, str(e)
    return failures, None


def run_step(step, i, env, where, line, failures):
    """judge one step into failures; False when a wrong verdict ends the example"""
    then = step.get("then") or []
    at = where + ("steps", i, "then")
    first = 0
    if "when" in step:
        when, first = step["when"], 1
        env["ACTOR"] = env[when["actor"]]
        env.pop("RESULT", None)
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
        found = judge(text, env)
        if found is not None:
            failures.append((line(at + (j,)), text, found))
    return True


# --- the run -----------------------------------------------------------------

def run(folder, wanted=()):
    """the result of each story: (id, status, detail, [(title, failures)]);
    status is "examples passed", failing or not run; failures are
    (file:line, then text, found). A story with a failure is failing even
    when something after it had no binding"""
    P, operations, stories = load_project(folder)
    PROJECT[0] = P
    OPERATIONS.clear()
    OPERATIONS.update(operations)
    known = {sid for sid, *_ in stories}
    unknown = [s for s in wanted if s not in known]
    if unknown:
        raise EddaError(f"unknown story: {', '.join(unknown)}")
    out = []
    for sid, st, source, path in stories:
        if wanted and sid not in wanted:
            continue
        why = needs(st, operations, P)
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


def main(argv):
    ap = argparse.ArgumentParser(description="run the examples of Edda's stories through the binding")
    ap.add_argument("--project", default=os.path.join(checker.ROOT, "specs"), help="the folder of .edda files (default specs/)")
    ap.add_argument("stories", nargs="*", metavar="STORY")
    a = ap.parse_args(argv)
    try:
        out = run(a.project, a.stories)
    except EddaError as e:
        print(f"edda failed: {e}")
        return 3
    except SpecRefused as e:
        print("the spec does not check; tools/check.py says:")
        for line in e.args[0]:
            print(f"    {line}")
        return 1
    for sid, status, detail, failed in out:
        print(f"{sid}: {status}: {detail}")
        for title, failures in failed:
            print(f"    example {show(title)} failed")
            for line, text, found in failures:
                print(f"        {line}: " + (f"then {text}: found {found}" if text else found))
    return 1 if any(status == "failing" for _, status, _, _ in out) else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:          # Edda itself failed
        print(f"edda failed: {type(e).__name__}: {e}")
        sys.exit(3)
