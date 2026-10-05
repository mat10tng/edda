"""The analyser (section 11, revision 66): four flags found by reading the
spec alone, before any code runs.

A condition is read as facts about single properties, when it has that
shape: `p == v`, `p != v`, `p in [..]`, `p not in [..]`, `p < n` and the
other orders, `p is None`, `p is not None`, a yes/no property on its own,
joined by `and`, `or` and `not`. A property is a dot path from a root in
scope (`f.status`, `number`). Its cases come from its type: the values of
a choice, True and False for a yes/no, ranges for a number (whole numbers
for an INTEGER), and only "no value" or "a value" for anything else;
`None` is one more case when the property is optional. Two different
paths are taken as independent. A condition outside that shape (a list
word, a sum, a call, two properties compared, OLD, ACTOR) is skipped for
the check that needs it, never guessed at. No solver.
"""
import ast
import copy
import math

INF = math.inf
LIMIT = 512          # boxes in one condition; above it the condition is skipped
NONE = None          # the case "no value"
SOME = "<a value>"   # the one case of a value that is no choice, yes/no or number


class Skip(Exception):
    """a condition outside the simple shape"""


# --- the type of a path -------------------------------------------------------

def _alts(t):
    return list(t[1]) if isinstance(t, tuple) and t[0] == "either" else [t]


def path_text(n):
    """the dot path a node is (`f.order.status`), or None"""
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        head = path_text(n.value)
        return head and f"{head}.{n.attr}"
    return None


def path_type(n, scope, P):
    """the declared type of a dot path, or None when unknown"""
    if isinstance(n, ast.Name):
        return scope.get(n.id)
    t = path_type(n.value, scope, P)
    rest = [a for a in _alts(t) if a != "NONE"]
    if len(rest) != 1 or not (isinstance(rest[0], tuple) and rest[0][0] == "entity"):
        return None
    ent = P.entities.get(rest[0][1])
    return ent and ent["props"].get(n.attr)


# --- the cases of one property ------------------------------------------------

class Finite:
    """a choice, a yes/no or a presence: a set of cases out of a few"""

    def __init__(self, cases):
        self.all = frozenset(cases)

    def full(self):
        return self.all

    def comp(self, s):
        return self.all - s

    def inter(self, a, b):
        return a & b

    def empty(self, s):
        return not s

    def point(self, v):
        if v not in self.all:
            raise Skip()
        return frozenset({v})


class Number:
    """a number: a tuple of intervals (lo, lo_closed, hi, hi_closed) and
    whether None is a case; an INTEGER keeps closed whole bounds"""

    def __init__(self, whole, optional):
        self.whole, self.optional = whole, optional

    def norm(self, ivs, none):
        out = []
        for lo, lc, hi, hc in ivs:
            if self.whole:
                if lo != -INF:
                    lo, lc = (math.ceil(lo) if lc else math.floor(lo) + 1), True
                if hi != INF:
                    hi, hc = (math.floor(hi) if hc else math.ceil(hi) - 1), True
            if lo < hi or (lo == hi and lc and hc):
                out.append((lo, lc, hi, hc))
        return (tuple(sorted(out)), none and self.optional)

    def full(self):
        return self.norm([(-INF, False, INF, False)], True)

    def inter(self, a, b):
        out = []
        for alo, alc, ahi, ahc in a[0]:
            for blo, blc, bhi, bhc in b[0]:
                lo, lc = max((alo, not alc), (blo, not blc))
                hi, hc = min((ahi, ahc), (bhi, bhc))
                out.append((lo, not lc, hi, hc))
        return self.norm(out, a[1] and b[1])

    def comp(self, s):
        rest = self.full()
        for lo, lc, hi, hc in s[0]:
            gaps = []
            if lo != -INF:
                gaps.append((-INF, False, lo, not lc))
            if hi != INF:
                gaps.append((hi, not hc, INF, False))
            rest = self.inter(rest, self.norm(gaps, True))
        return (rest[0], self.optional and not s[1])

    def empty(self, s):
        return not s[0] and not s[1]

    def point(self, v):
        if v is NONE:
            if not self.optional:
                raise Skip()
            return ((), True)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise Skip()
        return self.norm([(v, True, v, True)], False)

    def order(self, op, v):
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise Skip()
        iv = {ast.Lt: (-INF, False, v, False), ast.LtE: (-INF, False, v, True),
              ast.Gt: (v, False, INF, False), ast.GtE: (v, True, INF, False)}[op]
        return self.norm([iv], False)


def domain_of(t):
    """the cases of a property of type t"""
    alts = _alts(t)
    optional = "NONE" in alts
    rest = [a for a in alts if a != "NONE"]
    if len(rest) != 1 or rest[0] is None:
        raise Skip()
    t = rest[0]
    none = {NONE} if optional else set()
    if isinstance(t, tuple) and t[0] == "choice" and t[1]:
        return Finite(set(t[1]) | none)
    if t == "YES_NO":
        return Finite({True, False} | none)
    if t in ("INTEGER", "NUMBER"):
        return Number(t == "INTEGER", optional)
    return Finite({SOME} | none)


# --- a condition as boxes: each a property -> its cases, the rest any -------

class Reader:
    """reads conditions in one scope: name -> type, as the checker's"""

    def __init__(self, scope, P):
        self.scope, self.P = scope, P
        self.domains = {}     # path -> its cases

    def prop(self, n):
        p = path_text(n)
        if p is None or p.split(".")[0] not in self.scope:
            raise Skip()
        if p not in self.domains:
            self.domains[p] = domain_of(path_type(n, self.scope, self.P))
        return p, self.domains[p]

    def literal(self, n, d):
        """the value of a literal beside a property of cases d"""
        if isinstance(n, ast.Constant) and (n.value is None or isinstance(n.value, (bool, int, float))):
            return n.value
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant) \
                and isinstance(n.operand.value, (int, float)) and not isinstance(n.operand.value, bool):
            return -n.operand.value
        if isinstance(n, ast.Name) and n.id not in self.scope and isinstance(d, Finite) and n.id in d.all:
            return n.id      # a choice value of the compared property
        raise Skip()

    def atom(self, n):
        """(path, cases) for one fact about one property"""
        if isinstance(n, ast.Compare):
            if len(n.ops) != 1:
                raise Skip()
            op, left, right = n.ops[0], n.left, n.comparators[0]
            if path_text(left) is None:      # a literal on the left: turn it round
                flip = {ast.Lt: ast.Gt, ast.Gt: ast.Lt, ast.LtE: ast.GtE, ast.GtE: ast.LtE,
                        ast.Eq: ast.Eq, ast.NotEq: ast.NotEq}
                if type(op) not in flip:
                    raise Skip()
                op, left, right = flip[type(op)](), right, left
            p, d = self.prop(left)
            if isinstance(op, (ast.Eq, ast.Is)):
                if isinstance(op, ast.Is) and not (isinstance(right, ast.Constant) and right.value is None):
                    raise Skip()
                return p, d.point(self.literal(right, d))
            if isinstance(op, (ast.NotEq, ast.IsNot)):
                if isinstance(op, ast.IsNot) and not (isinstance(right, ast.Constant) and right.value is None):
                    raise Skip()
                return p, d.comp(d.point(self.literal(right, d)))
            if isinstance(op, (ast.In, ast.NotIn)):
                if not isinstance(right, ast.List):
                    raise Skip()
                s = d.comp(d.full())
                for e in right.elts:
                    one = d.point(self.literal(e, d))
                    s = d.comp(d.inter(d.comp(s), d.comp(one)))     # s or one
                return p, (s if isinstance(op, ast.In) else d.comp(s))
            if isinstance(d, Number) and type(op) in (ast.Lt, ast.LtE, ast.Gt, ast.GtE):
                return p, d.order(type(op), self.literal(right, d))
            raise Skip()
        p, d = self.prop(n)      # a yes/no property on its own
        if not (isinstance(d, Finite) and True in d.all):
            raise Skip()
        return p, d.point(True)

    def boxes(self, n, neg=False):
        """the condition, or its negation, as a list of boxes; [] when it
        has no case"""
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return self.boxes(n.operand, not neg)
        if isinstance(n, ast.BoolOp):
            parts = [self.boxes(v, neg) for v in n.values]
            if isinstance(n.op, ast.Or) != neg:
                return [b for part in parts for b in part]
            out = parts[0]
            for part in parts[1:]:
                out = self.both(out, part)
            return out
        p, s = self.atom(n)
        d = self.domains[p]
        s = d.comp(s) if neg else s
        return [] if d.empty(s) else [{p: s}]

    def both(self, xs, ys):
        """the cases two lists of boxes have in common"""
        out = []
        for x in xs:
            for y in ys:
                b = dict(x)
                for p, s in y.items():
                    b[p] = self.domains[p].inter(b[p], s) if p in b else s
                if not any(self.domains[p].empty(s) for p, s in b.items()):
                    out.append(b)
        if len(out) > LIMIT:
            raise Skip()
        return out

    def read(self, text, neg=False):
        """the boxes of a condition text, or None when it is skipped"""
        try:
            n = ast.parse(text, mode="eval").body
            return self.boxes(n, neg)
        except (Skip, SyntaxError, RecursionError):
            return None


def keys(boxes):
    return {p for b in boxes for p in b}


# --- the four flags -------------------------------------------------------------

def _listing(x):
    return x if isinstance(x, list) else []


def _mapping(x):
    return x if isinstance(x, dict) else {}


def _fact(f):
    return f.get("fact") if isinstance(f, dict) else f


def _rooted(text, prefix, props):
    """an always fact of an entity, its bare property names put under
    prefix (`quantity > 0` under `f` is `f.quantity > 0`)"""
    tree = ast.parse(text, mode="eval")
    base = ast.parse(prefix, mode="eval").body

    class Root(ast.NodeTransformer):
        def visit_Name(self, n):
            return ast.Attribute(value=copy.deepcopy(base), attr=n.id, ctx=ast.Load()) if n.id in props else n

        def visit_comprehension(self, n):
            raise Skip()

    try:
        return ast.unparse(Root().visit(tree))
    except Skip:
        return None


def _entity(prefix, scope, P):
    """the one entity a dot path holds, or None"""
    t = path_type(ast.parse(prefix, mode="eval").body, scope, P)
    ents = [a[1] for a in _alts(t) if isinstance(a, tuple) and a[0] == "entity"]
    return ents[0] if len(ents) == 1 and ents[0] in P.entities else None


def _ents(t):
    """every entity a type names, at any depth (a list, an either)"""
    if isinstance(t, tuple) and len(t) == 2 and t[0] == "entity":
        return {t[1]}
    if isinstance(t, (tuple, list, set, frozenset)):
        return set().union(*(_ents(x) for x in t))
    return set()


def _prefixes(path):
    """the dot paths a path goes through: f.order.status -> f, f.order"""
    steps = path.split(".")
    return [".".join(steps[:k]) for k in range(1, len(steps))]


def _free(path, scope, P):
    """whether every step of a path is a declared property that is neither
    computed nor DERIVED, so its value is free beside the others"""
    for head, step in zip(_prefixes(path), path.split(".")[1:]):
        e = _entity(head, scope, P)
        ent = e and P.entities[e]
        if not ent or step not in ent["props"] or step in ent["computed"] or step in ent["derived"]:
            return False
    return True


THINGS = 16      # things whose always facts a start state takes in; above it the check is skipped


def _reaches(ename, target, P):
    """whether an always fact of entity ename reads a path that reaches the
    target's entity; True when that cannot be shown (a fact that is no text,
    does not parse, or walks a list with a comprehension or a lambda)"""
    props = P.entities[ename]["props"]
    for rule in _listing(P.entities[ename].get("always")):
        rule = _fact(rule)
        try:
            tree = ast.parse(rule, mode="eval") if isinstance(rule, str) else None
        except SyntaxError:
            tree = None
        if tree is None:
            return True
        for n in ast.walk(tree):
            if isinstance(n, (ast.comprehension, ast.Lambda)):
                return True
            q = path_text(n) if isinstance(n, (ast.Name, ast.Attribute)) else None
            if q and q.split(".")[0] in props:
                t = path_type(n, props, P)
                if t is None or target in _ents(t):
                    return True
    return False


def _start_states(R, op, refuse, p, scope, P):
    """the start states an operation leaves open for an ensure on path p, as
    boxes: every refusal passed, a who-line met and every always fact of the
    things read held, all at once; None when one of them cannot be read in
    the simple shape, reads a computed or DERIVED property, or there are
    too many things"""
    parts = []

    def readable(text, neg=False):
        b = R.read(text, neg) if isinstance(text, str) else None
        if b is None or not all(_free(k, scope, P) for k in keys(b)):
            raise Skip()
        return b

    try:
        for w in refuse:
            parts.append(readable(w, neg=True))
        whens = [x.get("when") if isinstance(x, dict) else None for x in _listing(op.get("who"))]
        admitted = [readable(x) for x in whens if x is not None]
        if whens and all(x is not None for x in whens):      # a who-line with no when admits any start
            parts.append([box for b in admitted for box in b])
        # the always facts of every thing read, and of the things those read
        todo, seen = [p.rsplit(".", 1)[0]] + [q for b in parts for k in keys(b) for q in _prefixes(k)], set()
        while todo:
            x = todo.pop()
            e = _entity(x, scope, P)
            if x in seen or not e:
                continue
            seen.add(x)
            if len(seen) > THINGS:
                return None
            for rule in _listing(P.entities[e].get("always")):
                rule = _fact(rule)
                b = readable(isinstance(rule, str) and _rooted(rule, x, P.entities[e]["props"]) or None)
                parts.append(b)
                todo += [q for k in keys(b) for q in _prefixes(k)]
    except Skip:
        return None
    # a path that leads to a read property holds a thing, not None
    read = {k for b in parts for k in keys(b)} | {p}
    for k in {q for r in read for q in _prefixes(r)} & set(R.domains):
        d = R.domains[k]
        if isinstance(d, Finite) and NONE in d.all:
            parts.append([{k: d.comp(d.point(NONE))}])
    opens = [{}]
    for b in parts:
        opens = _meet_or_none(R, opens, b)
        if opens is None:
            return None
    return opens


def _numbers(xs):
    xs = sorted(xs)
    return ", ".join(str(x) for x in xs[:-1]) + " and " + str(xs[-1]) if len(xs) > 1 else str(xs[0])


def _meet_or_none(R, a, b):
    try:
        return R.both(a, b)
    except Skip:
        return None


def _meets(R, a, b):
    """whether two conditions share a case; True when too large to tell"""
    try:
        return bool(R.both(a, b))
    except Skip:
        return True


def operation_flags(sid, oname, op, P, line):
    """the four flags of one operation; line(path) is the line of a slot"""
    out = []
    at = ("stories", sid, "operations", oname)
    info = P.operations.get(oname)
    if not info or info.get("story") != sid:
        return out
    scope = {n: t for n, t, _ in info["inputs"]}
    R = Reader(scope, P)
    refuse = [r.get("when") if isinstance(r, dict) else None for r in _listing(op.get("refuse"))]
    ensure = [_fact(f) for f in _listing(op.get("ensure"))]

    def fact_line(i):
        f = op["ensure"][i]
        return line(at + ("ensure", i) + (("fact",) if isinstance(f, dict) else ()))

    # dead_refusal: refusal n covers no case refusals 1 to n-1 leave open
    read = [R.read(w) if isinstance(w, str) else None for w in refuse]
    for n in range(1, len(read)):
        if not read[n]:
            continue                          # skipped, or no case at all
        left, sharing = read[n], []
        try:
            for k in range(n):
                other = R.read(refuse[k], neg=True) if read[k] is not None else None
                if other is None or not R.both(read[n], read[k]):
                    continue
                sharing.append(k + 1)
                left = R.both(left, other)
            if sharing and not left:      # name only the refusals needed to cover it
                for k in list(sharing):
                    rest = read[n]
                    for m in sharing:
                        if m != k:
                            rest = R.both(rest, R.read(refuse[m - 1], neg=True))
                    if not rest:
                        sharing.remove(k)
        except Skip:
            continue
        if sharing and not left:
            word = "refusal" if len(sharing) == 1 else "refusals"
            out.append(("dead_refusal", line(at + ("refuse", n, "when")),
                f"{oname}: refusal {n + 1} can never be given; {word} {_numbers(sharing)} "
                f"{'covers' if len(sharing) == 1 else 'cover'} it"))

    # empty_ensure: both sides the same expression, or a call of its own operation
    for i, f in enumerate(ensure):
        if not isinstance(f, str):
            continue
        try:
            n = ast.parse(f, mode="eval").body
        except SyntaxError:
            continue
        same = isinstance(n, ast.Compare) and len(n.ops) == 1 and isinstance(n.ops[0], (ast.Eq, ast.GtE, ast.LtE)) \
            and ast.dump(n.left) == ast.dump(n.comparators[0])
        own = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == oname for c in ast.walk(n))
        if same or own:
            why = "both sides are the same" if same else f"it calls {oname} itself"
            out.append(("empty_ensure", fact_line(i), f"{oname}: ensure {i + 1} cannot fail; {why}: {f}"))

    # conflicting_ensure: two ensures, or an ensure and an always fact, with no case in common
    facts = [R.read(f) if isinstance(f, str) else None for f in ensure]
    for j, b in enumerate(facts):
        if not b:
            continue
        for i in range(j):
            a = facts[i]
            if a and keys(a) & keys(b) and not _meets(R, a, b):
                out.append(("conflicting_ensure", fact_line(j),
                    f"{oname}: ensure {i + 1} and ensure {j + 1} cannot both hold"))
    for i, b in enumerate(facts):
        if not b:
            continue
        prefixes = sorted({p.rsplit(".", 1)[0] for p in keys(b) if "." in p})
        for prefix in prefixes:
            t = path_type(ast.parse(prefix, mode="eval").body, scope, P)
            ents = [a[1] for a in _alts(t) if isinstance(a, tuple) and a[0] == "entity"]
            if len(ents) != 1 or ents[0] not in P.entities:
                continue
            ename = ents[0]
            for k, rule in enumerate(_listing(P.entities[ename].get("always"))):
                rule = _fact(rule)
                text = isinstance(rule, str) and _rooted(rule, prefix, P.entities[ename]["props"])
                c = text and R.read(text)
                if c and keys(c) & keys(b) and not _meets(R, b, c):
                    out.append(("conflicting_ensure", fact_line(i),
                        f"{oname}: ensure {i + 1} cannot hold with always {k + 1} of {ename}: {rule}"))

    # forbidden_change: an ensure sets the choice of an input to a value
    # may_change does not allow from a start the operation leaves open; only
    # where that is provable (section 11): the input's own property, neither
    # computed nor DERIVED, every condition read, no always fact of another
    # entity reaching the target's
    for i, b in enumerate(facts):
        if not b or len(b) != 1 or len(b[0]) != 1:
            continue
        (p, s), = b[0].items()
        d = R.domains[p]
        if not isinstance(d, Finite) or len(s) != 1 or "." not in p:
            continue
        target, = s
        prefix, prop = p.rsplit(".", 1)
        ename = prefix in scope and _entity(prefix, scope, P)     # an input, not a path through a reference
        if not ename:
            continue
        ent = P.entities[ename]
        if prop in ent["computed"] or prop in ent["derived"]:     # its value follows from others, not set
            continue
        arrows = _mapping(_mapping(ent.get("may_change")).get(prop))
        if target in (NONE, SOME, True, False) or prop not in _mapping(ent.get("may_change")):
            continue
        if any(_reaches(e, ename, P) for e in P.entities if e != ename):
            continue
        opens = _start_states(R, op, refuse, p, scope, P)
        if opens is None:
            continue
        values = [v for a in _alts(path_type(ast.parse(p, mode="eval").body, scope, P))
                  if isinstance(a, tuple) and a[0] == "choice" for v in a[1]]     # in declared order
        if prop in ent.get("defaults", {}):     # a DEFAULT choice starts at its default or a value a change reaches
            reached = {ent["defaults"][prop]} | {v for tos in arrows.values() for v in _listing(tos)}
            values = [v for v in values if v in reached]
        starts = [v for v in values
                  if v != target and target not in _listing(arrows.get(v)) and _meet_or_none(R, opens, [{p: frozenset({v})}])]
        if starts:
            out.append(("forbidden_change", fact_line(i),
                f"{oname} sets {prop} to {target} from {' or '.join(starts)}, which may_change does not allow"))
    return out


def flags(data, P, line):
    """the analyser's flags of one .edda file: (rule, line, message)"""
    out = []
    for sid, st in _mapping(data.get("stories")).items():
        for oname, op in _mapping(_mapping(st).get("operations")).items():
            out += operation_flags(sid, oname, _mapping(op), P, line)
    return out
