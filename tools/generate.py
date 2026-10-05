"""Generated cases (reference section 9): random worlds and operation
sequences made from the glossary, every call held to its operation's
rules, a failure shrunk and printed as an example ready to paste.

tools/run.py imports this module only when the project's edda.yaml turns
generated cases on, so Hypothesis (tools/requirements.txt) is needed
only then. For each story: a starting world of one to three records of
every entity the binding can make, each value picked from its type and
favouring the numbers, texts and times the spec's own expressions name,
and one actor for each role a who-line of the story admits; a world
that breaks an always-rule is thrown away. Then up to `steps` steps:
one of the story's bound operations, an actor its who-lines name,
inputs from the records that exist, the givens and what their
properties reach at any depth; the call goes through the runner's
run_operation, the rule wrapping of section 6, the only oracle. Up to
`runs` runs, under one seed. An operation with no binding, that needs
the clock, with a required single-record input no record can fill, or
that no run called, and an entity no record can be made of, is skipped
and listed; a story none of whose runs called an operation is not run,
never passed. What the binding cannot give (no binding, an unset value)
never fails a run by itself: every rule that can be judged still is, and
a failure wins, the rules that could not be judged listed beside it.
With nothing failed, met in the starting world the story is not run, met
in a step the run ends there and the operation is skipped.
"""
import ast
import datetime
import json
import re
import sys
import tempfile

from hypothesis import HealthCheck, Phase, Verbosity, assume, seed as use_seed, settings as Settings, \
    strategies as st
from hypothesis.configuration import set_hypothesis_home_dir
from hypothesis.errors import Flaky, Unsatisfiable
from hypothesis.stateful import RuleBasedStateMachine, initialize, rule, run_state_machine_as_test

R = None    # the runner module, set by cases(): run.py may be __main__, not "run"


class Cannot(Exception):
    """the starting world needs what the binding cannot give; args[0] says what"""


class Record(tuple):
    """a record an input can point at, (thing, its path), shown as its
    path: Hypothesis shows what it draws, and the thing may hold an unset
    value, which cannot be read"""

    def __repr__(self):
        return self[1]


class Broken(Exception):
    """a run broke a rule: the givens and steps that led there, the
    verdict the spec expects of the last call, and what was found"""

    def __init__(self, given, steps, found):
        super().__init__("; ".join(found))
        self.given, self.steps, self.found = given, steps, found


# --- what the spec names, as edge values ------------------------------------------

def edges(P):
    """the numbers, texts and times the spec's expressions name: each number,
    read with its sign (-10, not 10), with its neighbours and its negation,
    0, 1 and -1 always"""
    nums, texts, times = {-1, 0, 1}, {""}, set()
    for text in expressions(P):
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            continue
        signed = {id(n.operand): -n.operand.value for n in ast.walk(tree)
                  if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and is_number(n.operand)}
        for n in ast.walk(tree):
            if is_number(n):
                v = signed.get(id(n), n.value)
                nums.update({v - 1, v, v + 1, -v})
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                (times if R.checker.time_text(n.value) else texts).add(n.value)
    key = (lambda v: (abs(v), v < 0, v))
    return sorted(nums, key=key), sorted(texts, key=lambda s: (len(s), s)), sorted(times)


def is_number(n):
    return isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)


def expressions(P):
    for op in R.OPERATIONS.values():
        for w in op.get("who") or []:
            if "when" in w:
                yield w["when"]
        if isinstance(op.get("returns"), str):
            yield op["returns"]
    for rules in R.RULES["operations"].values():
        yield from (when for when, _, _ in rules["refuse"])
        yield from (text for text, _ in rules["ensure"])
    for facts in R.RULES["always"].values():
        yield from (text for text, _ in facts)
    for ent in P.entities.values():
        yield from (e for e in ent["computed"].values() if isinstance(e, str))


# --- strategies -----------------------------------------------------------------

def scalar(t, E):
    """a strategy for a value of the scalar type t, or None"""
    nums, texts, times = E
    if t == "INTEGER":
        return st.one_of(st.sampled_from([v for v in nums if isinstance(v, int)]), st.integers(-1000, 1000))
    if t == "NUMBER":
        return st.one_of(st.sampled_from(nums), st.floats(-1000, 1000, allow_nan=False, allow_infinity=False))
    if t == "TEXT":
        return st.one_of(st.sampled_from(texts), st.text(alphabet="abc ", max_size=4))
    if t == "YES_NO":
        return st.booleans()
    if t == "TIME":
        made = st.datetimes(datetime.datetime(2026, 1, 1), datetime.datetime(2026, 12, 31)).map(
            lambda d: d.strftime("%Y-%m-%d %H:%M"))
        return st.one_of(st.sampled_from(times), made) if times else made
    if R.checker.is_choice(t):
        return st.sampled_from(list(t[1]))
    return None


def draw(data, t, E, pick):
    """a value of type t, MISSING for a property best left out (None for
    OPTIONAL, [] for MANY: the runner gives those) and for a reference
    with no record to point at; pick(kind) is the list of the records of
    that kind to pick from"""
    c = R.checker
    if c.is_either(t) and "NONE" in t[1]:
        if data.draw(st.booleans()):
            return draw(data, c.no_none(t), E, pick)
        return MISSING
    if c.is_entity(t):      # nothing to point at: left out, as an optional one may be
        found = pick(t[1])
        return data.draw(st.sampled_from(found)) if found else MISSING
    if c.is_list(t):
        found = pick(t[1][1])
        chosen = data.draw(st.lists(st.sampled_from(range(len(found))), unique=True, max_size=3)) if found else []
        return [found[i] for i in chosen] if chosen else MISSING
    return data.draw(scalar(t, E))


MISSING = object()


def generable(t, kinds):
    """can a value of type t be made, entities only from kinds"""
    c = R.checker
    if c.is_either(t) and "NONE" in t[1]:
        return True
    if c.is_list(t):
        return True
    if c.is_entity(t):
        return t[1] in kinds
    return t in R.checker.SCALARS or c.is_choice(t)


# --- the plan of one story ------------------------------------------------------------

class Plan:
    """what generation can do for one story: the entities it makes (in an
    order where what a record needs is made first), the roles it gives an
    actor, the operations it calls and those it skips, and why"""

    def __init__(self, sid, story, P):
        b = R.binding
        self.P, self.sid, self.E = P, sid, edges(P)
        self.spaces = getattr(b, "VALUES", {})
        self.order, made = [], set()
        while True:     # a kind is made once every required reference it holds can be
            more = [k for k in sorted(P.entities) if k not in made and k in b.ENTITIES
                    and (k in self.spaces or all(generable(t, made) for p, t in self.fields(k).items()))]
            if not more:
                break
            self.order += more
            made.update(more)
        self.unmade = [(f"entity {k}", "nothing to fill its required " + ", ".join(
            p for p, t in self.fields(k).items() if not generable(t, made)))
            for k in sorted(P.entities) if k in b.ENTITIES and k not in made]
        self.reached = set()    # kinds found through a property of a made or reached record
        while True:
            more = {e for k in made | self.reached for t in P.entities[k]["props"].values()
                    for e in R.entity_kinds(t) if e in P.entities} - made - self.reached
            if not more:
                break
            self.reached |= more
        timed_ops, timed = R.clock_paths(P)
        world_clock = [f"{e}.always needs the clock, not built yet" for e in sorted(made | self.reached)
                       for text, _ in R.RULES["always"].get(e) or [] if clock(P, text, dict(P.entities[e]["props"]), timed, timed_ops, e)]
        self.roles = sorted(r for r, role in P.roles.items()      # an actor can be made for these
                            if all(generable(t, made) for t in role["properties"].values()))
        self.ops, self.skipped = [], list(self.unmade)
        for name in (story.get("operations") or {}):
            why = self.why_not(name, made, timed_ops, timed) or (world_clock[:1] or [None])[0]
            if why:
                self.skipped.append((name, why))
            else:
                self.ops.append(name)
        self.roles = [r for r in self.roles if any(w["role"] == r for o in self.ops for w in R.OPERATIONS[o]["who"])]
        self.inputs = {e for o in self.ops for _, t, _ in P.operations[o]["inputs"] for e in R.entity_kinds(t)}
        wanted = self.reached & self.inputs     # the kinds a run finds through properties
        self.leads = {k for k in P.entities if R.kinds_reached(P, {k}) & wanted}
        self.runs, self.calls, self.ready = 0, dict.fromkeys(self.ops, 0), set()

    def fields(self, kind):
        """the stored properties generation gives a record: those of the
        binding's value space when it has one, otherwise every stored one"""
        if kind in self.spaces:
            return {p: None for p in self.spaces[kind]}
        props = self.P.entities[kind]["props"]
        return {p: props[p] for p in R.stored(kind)}

    def why_not(self, name, made, timed_ops, timed):
        P, op = self.P, self.P.operations[name]
        if name not in R.binding.OPERATIONS:
            return f"no binding for {name}"
        if not any(w["role"] in self.roles for w in R.OPERATIONS[name]["who"]):
            return "no actor: each role it admits holds a reference no record fills"
        for _, t, opt in op["inputs"]:
            if opt or R.checker.is_list(t):     # left out, or empty, when no record fits
                continue
            for e in sorted(R.entity_kinds(t) - made - self.reached):
                return f"no {e} record can be made" if e in R.binding.ENTITIES else f"no binding for entity {e}"
        scope = {n: t for n, t, _ in op["inputs"]}
        scope["ACTOR"] = ("actor", ("one", frozenset(r for r in op.get("who") or [] if isinstance(r, str))))
        texts = [w["when"] for w in R.OPERATIONS[name].get("who") or [] if "when" in w]
        texts += [w for w, _, _ in R.RULES["operations"][name]["refuse"]]
        texts += [t for t, _ in R.RULES["operations"][name]["ensure"]]
        for text in texts:
            for n in ast.walk(ast.parse(text, mode="eval")):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in R.OPERATIONS \
                        and n.func.id not in R.binding.OPERATIONS:
                    return f"no binding for {n.func.id}"
        if name in timed_ops or any(clock(P, text, scope, timed, timed_ops) for text in texts):
            return "needs the clock, not built yet"
        return None


def clock(P, text, scope, timed, timed_ops, own=None):
    """does text read the clock: directly, through a computed property or
    through an operation it calls (run.py's clock_paths)"""
    reads, calls = R.walk(P, text, scope, own)
    return bool(R.uses_clock(text)) or bool(reads & timed) or bool(calls & timed_ops)


# --- the machine ------------------------------------------------------------------

def machine(plan):
    """a RuleBasedStateMachine over plan's operations"""
    P, b = plan.P, R.binding

    class Cases(RuleBasedStateMachine):
        def __init__(self):
            super().__init__()
            self.workdir = tempfile.TemporaryDirectory()
            self.given, self.steps, self.made, self.ok, self.stopped = [], [], {}, False, False
            self.calls = []     # the operations this run called

        def broken(self, found):
            return Broken([dict(g) for g in self.given], [list(s) for s in self.steps], found)

        @initialize(data=st.data())
        def world(self, data):
            names = {}
            for kind in plan.order:
                for i in range(1, data.draw(st.integers(1, 3)) + 1):
                    values = {}
                    for p, t in plan.fields(kind).items():
                        if t is None:       # the binding's value space
                            v = data.draw(st.sampled_from(plan.spaces[kind][p]))
                        else:
                            v = draw(data, t, plan.E, lambda e: names.get(e, []))
                        if v is not MISSING:
                            values[p] = v
                    self.given.append({kind: f"{kind}_{i}", "with": values})
                    names.setdefault(kind, []).append(f"{kind}_{i}")
            actors = []
            for role in plan.roles:
                values = {"roles": [role]}
                for p, t in P.roles[role]["properties"].items():
                    v = draw(data, t, plan.E, lambda e: names.get(e, []))
                    if v is not MISSING:
                        values[p] = v
                actors.append({"actor": f"{role}_1", "with": values})
            self.given[:0] = actors
            try:
                self.made = R.make_givens(self.given, self.workdir.name)
            except CANNOT as e:
                raise Cannot(cannot(e))
            except R.Fail as e:
                raise self.broken([str(e)])
            R.GIVENS[:] = self.made.values()
            R.ALWAYS[0] = True
            unjudged = []
            try:
                kept = all([R.judged(text, R.own_scope(thing, R.kind_of(thing)), at, text, unjudged) is None
                            for thing in R.reachable(list(self.made.values()))
                            for text, at in R.RULES["always"].get(R.kind_of(thing)) or []])
            except R.RuleBroken as e:
                raise self.broken(rule_lines(e))
            finally:
                R.ALWAYS[0] = False
            assume(kept)        # a world that breaks an always-rule is thrown away, judged or not
            if unjudged:
                raise Cannot(cannot(unjudged[0][2]))
            self.ok = True

        def existing(self):
            """kind to the records there now, each (thing, its path): the
            givens, then what their properties reach, at any depth, through
            the kinds that lead to an input the binding cannot make; each
            record once, so a loop ends"""
            out, seen = {}, set()
            queue = [(t, n) for n, t in self.made.items() if R.kind_of(t) != "actor"]
            while queue:
                thing, path = queue.pop(0)
                if id(thing) in seen:
                    continue
                seen.add(id(thing))
                kind = R.kind_of(thing)
                out.setdefault(kind, []).append(Record((thing, path)))
                if kind not in P.entities:
                    continue
                for p, t in P.entities[kind]["props"].items():
                    if not (R.entity_kinds(t) & plan.leads):
                        continue
                    try:
                        v = getattr(thing, p)
                    except (b.UnsetRead, Exception):
                        continue
                    if isinstance(v, b.Thing):
                        queue.append((v, f"{path}.{p}"))
                    elif type(v) is list:
                        queue += [(x, f"{path}.{p}[{i}]") for i, x in enumerate(v) if isinstance(x, b.Thing)]
            return out

        @rule(data=st.data())
        def step(self, data):
            if self.stopped:
                return
            there = self.existing()
            ready = [o for o in plan.ops if all(there.get(e) for _, t, opt in P.operations[o]["inputs"] if not opt
                                                and not R.checker.is_list(t) for e in R.entity_kinds(t))]
            if not ready:
                return
            plan.ready.update(ready)
            name = data.draw(st.sampled_from(ready))
            actor = data.draw(st.sampled_from(sorted({f"{w['role']}_1" for w in R.OPERATIONS[name]["who"]
                                                      if w["role"] in plan.roles})))
            args, kwargs, texts = [], {}, []
            for n, t, opt in P.operations[name]["inputs"]:
                if opt and not data.draw(st.booleans()):
                    continue
                v = draw(data, R.checker.no_none(t) if opt else t, plan.E, lambda e: there.get(e, []))
                if v is MISSING and not R.checker.is_list(R.checker.no_none(t)):
                    continue    # an optional input with no record to point at: left out
                if v is MISSING:
                    v = []      # an empty MANY input
                value, text = literal(v, R.checker.no_none(t))
                if opt:
                    kwargs[n] = value
                    texts.append(f"{n}={text}")
                else:
                    args.append(value)
                    texts.append(text)
            call = f"{name}({', '.join(texts)})"
            who = self.made[actor]
            expected = verdict(name, who, args, kwargs)
            self.steps.append([actor, call, expected])
            spec = "DONE" if expected in ("DONE", None) else f"refused: {json.dumps(expected)}"
            try:
                R.run_operation(name, who, args, kwargs)
                self.steps[-1][2] = "DONE"
                self.calls.append(name)
            except b.Refused as r:
                self.steps[-1][2] = r.reason
                self.calls.append(name)
            except R.RuleBroken as e:
                raise self.broken(rule_lines(e))
            except CANNOT as e:     # nothing failed; the run ends here; what came before stays
                plan.skipped.append((name, cannot(e)))
                self.steps.pop()
                self.stopped = True
            except R.Fail as e:
                raise self.broken([f"{call}: the spec cannot be judged: {e}"])
            except R.EddaError:
                raise
            except Exception as e:      # the code under test crashed
                raise self.broken([f"{call}: the spec gives {spec}, but it raised {type(e).__name__}: {e}"])

        def teardown(self):
            if self.ok and sys.exc_info()[0] is None:   # a run Hypothesis cut short is not counted
                plan.runs += 1
                for name in self.calls:
                    plan.calls[name] += 1
            self.workdir.cleanup()

    Cases.__name__ = f"Cases_{plan.sid.replace('-', '_')}"
    return Cases


CANNOT = ()     # what the binding cannot give, set by cases(): no binding, an unset value read


def rule_lines(e):
    """the lines of a RuleBroken: each broken rule, then each rule of the
    call that could not be judged"""
    return [f"{at}: {m}" for at, _, m in e.failures] + \
        [f"{at}: not judged: {what}: {cannot(x)}" for at, what, x in e.unjudged]


def cannot(e):
    """why a CANNOT exception means nothing can be run there"""
    return f"no binding for {e}" if isinstance(e, R.binding.NotBound) else str(e)


def literal(v, t):
    """(the value a call gets, its text in the call)"""
    c = R.checker
    if isinstance(v, tuple):        # a record: (thing, path)
        return v
    if type(v) is list:
        parts = [literal(x, t[1] if c.is_list(t) else None) for x in v]
        return [p[0] for p in parts], "[" + ", ".join(p[1] for p in parts) + "]"
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return v, repr(v)
    if t == "TIME":
        return R.time_of(v), f'TIME("{v}")'
    if c.is_choice(t):
        return v, v
    return v, json.dumps(v)


def verdict(name, actor, args, kwargs):
    """the verdict the spec gives the call before it runs: the permission
    refusal, the first refuse condition that holds, past any that cannot be
    judged, or DONE; None when it cannot be judged (the call itself then
    fails, or is not judged)"""
    try:
        if not R.permitted(name, actor, args, kwargs):
            return f"{name} is not allowed for {', '.join(actor.roles)}"
        required, optionals = R.inputs_of(name, args, kwargs)
        scope = dict(required, **optionals, ACTOR=actor)
        unknown = False
        for when, reason, _ in R.RULES["operations"][name]["refuse"]:
            try:
                if R.evaluate(when, scope):
                    return reason
            except CANNOT:
                unknown = True
        return None if unknown else "DONE"
    except (Exception, R.binding.UnsetRead):
        return None


# --- the run and its report ---------------------------------------------------------

def cases(runner, sid, story, runs, steps, seed, replay):
    """the lines that report the generated cases of one story, and whether
    they failed; replay is the command that runs them again"""
    global R, CANNOT
    R = runner
    CANNOT = R.cannot_judge()
    plan = Plan(sid, story, R.PROJECT[0])
    if not plan.ops:
        return [f"{sid}: generated cases: not run: " + (skips(plan)[2:] or "no operations")], False
    Cases = use_seed(seed)(machine(plan))
    home = tempfile.TemporaryDirectory()    # Hypothesis's caches, never in the project
    set_hypothesis_home_dir(home.name)
    R.UNSET_ENDS[0] = True
    try:
        run_state_machine_as_test(Cases, settings=Settings(
            max_examples=runs, stateful_step_count=steps + 1, database=None, deadline=None,
            derandomize=False, print_blob=False, report_multiple_bugs=False, verbosity=Verbosity.quiet,
            phases=[Phase.generate, Phase.shrink], suppress_health_check=list(HealthCheck)))
    except Broken as e:
        return failure(sid, story, e, seed, replay, skips(plan)), True
    except Cannot as e:
        return [f"{sid}: generated cases: not run: {e}{skips(plan)}"], False
    except Unsatisfiable:
        return [f"{sid}: generated cases: not run: no starting world keeps every always-rule" + skips(plan)], False
    except Flaky as e:
        return [f"{sid}: generated cases: failed once, and not again on replay (seed {seed}){skips(plan)}: {e}"], True
    finally:
        R.UNSET_ENDS[0] = False
        set_hypothesis_home_dir(None)
        home.cleanup()
    if not any(plan.calls.values()):
        why = [f"{o} never had a record for each input" for o in plan.ops if o not in plan.ready]
        return [f"{sid}: generated cases: not run: no call ran in {plan.runs} runs"
                + "".join(f"; {w}" for w in why) + skips(plan)], False
    plan.skipped += [(o, "never had a record for each input" if o not in plan.ready else f"not called in {plan.runs} runs")
                     for o in plan.ops if not plan.calls[o] and o not in dict(plan.skipped)]
    calls = ", ".join(f"{o} {n}" for o, n in plan.calls.items() if n)
    return [f"{sid}: generated cases: {plan.runs} runs passed; calls: {calls}" + skips(plan)], False


def skips(plan):
    """"; skipped <what>: <why>" for each thing skipped, once, with the first why"""
    first = {}
    for o, why in plan.skipped:
        first.setdefault(o, why)
    return "".join(f"; skipped {o}: {why}" for o, why in first.items())


def failure(sid, story, e, seed, replay, skipped):
    """a shrunk failure: the seed, what was skipped, the command that
    replays it, the broken rule, and
    the run as an example ready to paste under the story's examples:,
    with, for a story with rules:, the line its rule's shown_by: needs"""
    name = re.match(r"[a-z_0-9]+", e.steps[-1][1]).group() if e.steps else "the starting world"
    title = f"generated: {name} breaks a rule"
    out = [f"{sid}: generated cases: failed (seed {seed}){skipped}", f"    replay: {replay}"]
    out += [f"    {f}" for f in e.found]
    out.append("    as an example:")
    out.append(f"      {json.dumps(title)}:")
    out.append("        given:")
    for g in e.given:
        kind = next(k for k in g if k != "with")
        out.append(f"          - {kind}: {g[kind]}")
        if g["with"]:
            out.append("            with: {" + ", ".join(f"{p}: {shown(v, prop_type(g, kind, p))}"
                                                        for p, v in g["with"].items()) + "}")
    if e.steps:
        out.append("        steps:")
        for actor, call, then in e.steps:
            out.append(f"          - when: {{actor: {actor}, call: {json.dumps(call)}}}")
            if then in ("DONE", None):
                out.append("            then: [DONE]")
            else:
                out += ["            then:", f"              - refused: {json.dumps(then)}"]
    rules = story.get("rules") or []
    if rules:
        which = f"the rule {json.dumps(rules[0].get('rule'))}" if len(rules) == 1 else "the rule it shows"
        out.append(f"    and under the shown_by: of {which}:")
        out.append(f"          - {json.dumps(title)}")
    return out


def prop_type(g, kind, p):
    if p == "roles":
        return ("list", "role")
    if kind == "actor":
        return R.PROJECT[0].actor_props(("all", frozenset(g["with"]["roles"]))).get(p)
    return R.PROJECT[0].entities[kind]["props"].get(p)


def shown(v, t):
    """a with: value as an example writes it"""
    c = R.checker
    if type(v) is list:
        return "[" + ", ".join(shown(x, t[1] if c.is_list(t) else None) for x in v) + "]"
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return repr(v)
    kinds = c.alts(t) if t is not None else []
    if "TEXT" in kinds or "TIME" in kinds or not re.fullmatch(c.NAME, v):
        return json.dumps(v)
    return v
