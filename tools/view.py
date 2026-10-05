#!/usr/bin/env python3
"""The read view (reference section 12): each story as plain sentences.

    python3 tools/view.py [--lines] [--root ROOT | DIR] [STORY ...]

DIR is the spec folder, else edda.yaml's. Every sentence is rendered from
the JSON model of section 9 (tools/check.py --model), never from the
YAML: one per line, in file order, a story's sentences together and a
blank line between stories; an entity's invariants come before the
stories of its file. A grey sentence (a note) starts with "~ ", a
warning (a question, a drifted pair) with "? ", a plain one with two
spaces; --lines puts "<file>:<line>: " before each. A project that does
not check prints its problems, as the checker does, and exits 1; a
STORY that is not in the project exits 1 too.

The renderer, story_sentences and version_sentences, is the one the
binding (tools/edda_binding.py) calls for view and view_at.
"""
import argparse
import ast
import os
import sys

import check as checker

FIXED = {"ACTOR": "the asker", "RESULT": "the result", "TODAY": "today", "NOW": "now"}
COMPARE = {ast.Eq: "is", ast.NotEq: "is not", ast.Gt: "is more than", ast.Lt: "is less than",
           ast.GtE: "is at least", ast.LtE: "is at most", ast.In: "is in", ast.NotIn: "is not in"}
ARITH = {ast.Add: "plus", ast.Sub: "minus", ast.Mult: "times", ast.Div: "divided by"}
SCALAR = {"TEXT": "text", "NUMBER": "number", "INTEGER": "integer", "TIME": "time", "YES_NO": "yes or no"}


# --- words ---------------------------------------------------------------------

def words(name):
    """a name as words: units_sent reads "units sent" """
    return name.replace("_", " ")


LETTER_VOWEL = "aefhilmnorsx"      # the letters whose names start with a vowel sound: an f, an s
VOWELS = "aeiou"
SILENT_H = ("hour", "honest", "honour")     # an h not said: an hour


def a(w):
    """w with "a" or "an" before it, by the sound it starts with (section
    12): a single letter by its name ("an s", "a p"); "an" before a silent
    h (hour, honest, honour); "an" before "un" (unable, uninstalled),
    except "uni" not followed by n or m, said "you" (unit, union); "a"
    before "eu" and before any other "u" then a consonant then a vowel,
    said "you" (user, usual); else "an" before a vowel and "a" before a
    consonant"""
    first = w.split(" ")[0].lower()
    if len(first) == 1 and first.isalpha():
        return ("an " if first in LETTER_VOWEL else "a ") + w
    if first.startswith(SILENT_H):
        return "an " + w
    if first.startswith("un"):
        return ("a " if first.startswith("uni") and not first.startswith(("unin", "unim")) else "an ") + w
    if first.startswith("eu") or (len(first) > 2 and first[0] == "u" and first[1].isalpha()
                                  and first[1] not in VOWELS and first[2] in VOWELS):
        return "a " + w
    return ("an " if first[:1] in VOWELS else "a ") + w


def quoted(text):
    """text in double quotes, a double quote or backslash inside it with a
    backslash before it, so a quote never ends it early (section 12)"""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def cap(text):
    return text[:1].upper() + text[1:]


def stop(text):
    """text ending with a full stop, unless it ends a sentence already"""
    return text if text.endswith((".", "?", "!")) else text + "."


def joined(items):
    """items joined with ", " and the last with ", and " (section 12, given)"""
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


class Unread(Exception):
    """a form the view has no reading for: a retired form a snapshot keeps
    (section 10), or any other; the expression is shown as written"""


RETIRED_CALLS = {"min", "max"}      # retired, kept in snapshots (section 10)


def rank(n):
    """how tightly a form binds, as Python's precedence: or 1, and 2, not 3,
    a comparison 4, + and - 5, * and / 6, a minus sign 7, anything else 9"""
    if isinstance(n, ast.BoolOp):
        return 1 if isinstance(n.op, ast.Or) else 2
    if isinstance(n, ast.UnaryOp):
        if isinstance(n.op, ast.Not):
            return 3
        return 9 if isinstance(n.operand, ast.Constant) else 7
    if isinstance(n, ast.Compare):
        return 4
    if isinstance(n, ast.BinOp):
        return 5 if isinstance(n.op, (ast.Add, ast.Sub)) else 6
    return 9


def is_or(n):
    return isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)


def open_end(n):
    """does n's reading end open, so that what follows it would be read
    into it: a list word or a comprehension ("... where c"), or an and or
    or whose last part does"""
    if isinstance(n, ast.ListComp):
        return True
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("sum", "any", "all"):
        return True
    return isinstance(n, ast.BoolOp) and open_end(n.values[-1])


def is_path(n):
    """a name or a property or item read on one"""
    return isinstance(n, (ast.Name, ast.Attribute, ast.Subscript))


def bracketed(n, above):
    """is n, read inside a larger expression, put in brackets: when it binds
    no tighter than above, its reading ends open, it is a list literal, or
    its reading holds an "and" or "or" of the view's own (section 12)"""
    return rank(n) <= above or open_end(n) or (isinstance(n, ast.List) and bool(n.elts)) or loose(n)


def loose(n):
    """does n's reading hold an "and" or "or" the view puts in, outside its
    own brackets, decided from the tree as Words.w reads it: a list literal
    or a call of two or more, an and or or, a comprehension, sum, any or
    all, at its top or on the path a property is read on. Every other part
    of a value is read in brackets when it holds one, so it does not count"""
    if isinstance(n, ast.List):
        return len(n.elts) > 1
    if isinstance(n, (ast.ListComp, ast.BoolOp)):
        return True
    if isinstance(n, ast.Attribute):
        return loose(n.value)           # "the <property> of <value>", the value without brackets
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        if n.func.id in ("len", "OLD", "TIME"):
            return False
        if n.func.id in ("sum", "any", "all"):
            return True
        return len(n.args) > 1
    return False


LIST_WORDS = ("len", "OLD", "TIME", "sum", "any", "all")


def value_form(n):
    """a value that reads "<value> is yes" when it stands as a condition and
    is proven yes or no (or OPTIONAL yes or no): a path, OLD of one, a
    call of a declared operation"""
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        if n.func.id == "OLD":
            return len(n.args) == 1 and value_form(n.args[0])
        return n.func.id not in LIST_WORDS
    return is_path(n)


YES_NO = "YES_NO"
MAYBE = "YES_NO, OPTIONAL"     # yes, no, or no value
YES_NOS = (YES_NO, MAYBE)


def prop_type(p):
    """a property's or an input's type as the view needs it, from the model:
    YES_NO, MAYBE (an OPTIONAL YES_NO), ("entity", name), ("list", item
    type), or None"""
    if p.get("many"):
        return ("list", ("entity", p["entity"]))
    if p.get("entity"):
        return ("entity", p["entity"])
    if p.get("type") == YES_NO:
        return MAYBE if p.get("optional") else YES_NO
    return None


def either(ts):
    """the one type a value of one of the types ts has: theirs when they
    agree; MAYBE when each is YES_NO or MAYBE and one is MAYBE; else None"""
    if ts and all(t in YES_NOS for t in ts):
        return MAYBE if MAYBE in ts else YES_NO
    return ts[0] if ts and all(t == ts[0] for t in ts) else None


class Types:
    """the types the view proves a value has (section 12), from the model:
    the entities' and roles' properties with their types, and the
    operations, whose returns give the type of a call. Only YES_NO, an
    entity and a list are told apart; anything else is not known"""

    def __init__(self, entities=(), roles=(), operations=()):
        self.entities = {e["name"]: {p["name"]: prop_type(p) for p in e["properties"]} for e in entities}
        self.roles = {r["name"]: {p["name"]: prop_type(p) for p in r["properties"]} for r in roles}
        self.operations = {o["name"]: o for o in operations}
        self.returned = {}

    def scope(self, op):
        """the names an operation's expressions read: its inputs, the asker
        as one of its roles, and its result"""
        out = {i["name"]: prop_type(i) for i in op["inputs"]}
        out["ACTOR"] = ("actor", "one", tuple(w["role"] for w in op["who"]))
        if op["returns"]:
            out["RESULT"] = self.returns(op["name"])
        return out

    def returns(self, name):
        """the type of a call of a declared operation; None while it is being
        found (a call back to itself)"""
        if name not in self.returned:
            self.returned[name] = None
            op = self.operations.get(name)
            if op and op["returns"]:
                self.returned[name] = self.of(checker.json_ast(op["returns"]["ast"]), self.scope(op))
        return self.returned[name]

    def actor(self, t, p):
        """the type of an actor's property: a role's, the same in every role
        that has it; for one of the roles ("one"), every role has it"""
        if p in ("name", "roles"):
            return None
        _, kind, roles = t
        found = [self.roles.get(r, {}).get(p, False) for r in roles]
        if kind == "one" and False in found:
            return None
        return either([x for x in found if x is not False])

    def of(self, n, scope):
        """n's type, scope giving the names in it"""
        if isinstance(n, ast.Name):
            return scope.get(n.id)
        if isinstance(n, ast.Constant):
            return YES_NO if isinstance(n.value, bool) else None
        if isinstance(n, ast.Attribute):
            t = self.of(n.value, scope)
            if isinstance(t, tuple) and t[0] == "entity":
                return self.entities.get(t[1], {}).get(n.attr)
            if isinstance(t, tuple) and t[0] == "actor":
                return self.actor(t, n.attr)
            return None
        if isinstance(n, ast.Subscript):
            t = self.of(n.value, scope)
            return t[1] if isinstance(t, tuple) and t[0] == "list" and not isinstance(n.slice, ast.Slice) else None
        if isinstance(n, ast.Compare) or (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)):
            return YES_NO
        if isinstance(n, ast.BoolOp):
            t = either([self.of(v, scope) for v in n.values])
            return t if t in YES_NOS else None
        if isinstance(n, ast.ListComp):
            return ("list", self.of(n.elt, self.bind(n.generators, scope)))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id not in scope:
            f = n.func.id
            if f == "OLD":
                return self.of(n.args[0], scope) if len(n.args) == 1 else None
            if f in ("any", "all"):
                return YES_NO
            if f in self.operations:
                return self.returns(f)
        return None

    def bind(self, gens, scope):
        """scope with the names a comprehension's generators bind"""
        scope = dict(scope)
        for g in gens:
            if isinstance(g.target, ast.Name):
                t = self.of(g.iter, scope)
                scope[g.target.id] = t[1] if isinstance(t, tuple) and t[0] == "list" else None
        return scope


class Words:
    """an expression in words (section 12), from its ast as JSON. kept are
    the roots that keep their name (inputs, givens; a comprehension's
    names are kept too); the, the roots that read "the <entity>" instead
    (an input named for its entity type, an ordered_by item). unread is
    set when an expression was shown as written; the caller shades its
    sentence a warning and clears it. types and scope prove which values
    are yes or no: a value is read "is yes" only then. A comprehension's
    names hold only inside it: scope is put back after each"""

    def __init__(self, kept=(), the=(), types=None, scope=None):
        self.the = set(the)
        self.kept = set(kept) - self.the
        self.types = types or Types()
        self.scope = dict(scope or {})
        self.unread = False

    def yes_no(self, n):
        """n's type when it is a value that reads "is yes" as a condition: of
        that form and proven yes or no, YES_NO or MAYBE; else None"""
        t = self.types.of(n, self.scope) if value_form(n) else None
        return t if t in YES_NOS else None

    def inside(self, read):
        """read(), a comprehension's reading, its names bound in a copy of
        the scope, which is put back after"""
        outer = self.scope
        self.scope = dict(outer)
        try:
            return read()
        finally:
            self.scope = outer

    def of(self, e, condition=False):
        """an expression of the model, {"text", "line", "ast"}, as a value or
        as a condition; one the view cannot read, as written in its quotes"""
        try:
            n = checker.json_ast(e["ast"])
            return self.c(n) if condition else self.w(n)
        except Unread:
            return self.as_written(e)

    def as_written(self, e):
        self.unread = True
        return quoted(e["text"])

    # values

    def w(self, n, bound=frozenset(), drop=None):
        """n as a value; drop, a root read away (a refusal's input, ACTOR)"""
        if isinstance(n, ast.Name):
            if n.id in FIXED:
                return FIXED[n.id]
            if n.id in bound or n.id in self.kept:
                return n.id
            if n.id in self.the:
                return "the " + words(n.id)
            return words(n.id)              # a choice value, or an entity's own property
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool):
                return "yes" if n.value else "no"
            if n.value is None:
                return "no value"
            if isinstance(n.value, str):
                return quoted(n.value)
            if isinstance(n.value, (int, float)):
                return str(n.value)
            raise Unread
        if isinstance(n, ast.Attribute):
            if isinstance(n.value, ast.Name) and n.value.id == drop:
                return words(n.attr)
            if isinstance(n.value, ast.Name) or self.dropped_root(n.value, drop):
                return f"{self.w(n.value, bound, drop)}'s {words(n.attr)}"
            return f"the {words(n.attr)} of {self.w(n.value, bound, drop)}"
        if isinstance(n, ast.Subscript):
            return self.index(n.slice, self.atom(n.value, bound, drop), bound)
        if isinstance(n, ast.Compare):
            return self.compare(n, bound, drop)
        if is_or(n):                        # a value: the first that is not empty, zero, no or no value
            return ", or else ".join(self.side(v, 1, bound, drop) for v in n.values)
        if isinstance(n, ast.BoolOp):
            raise Unread                    # and as a value gives one of its parts; no reading
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return self.c(n, bound, drop)   # yes or no either way
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            if isinstance(n.operand, ast.Constant) and type(n.operand.value) in (int, float):
                return "-" + self.w(n.operand, bound)
            return "minus " + self.side(n.operand, 7, bound, drop)
        if isinstance(n, ast.BinOp) and type(n.op) in ARITH:
            p = rank(n)
            return (f"{self.side(n.left, p - 1, bound, drop)} {ARITH[type(n.op)]} "
                    f"{self.side(n.right, p, bound, drop)}")
        if isinstance(n, ast.List):
            if not n.elts:
                return "empty"
            return "the list of " + " and ".join(self.item(e, bound) for e in n.elts)
        if isinstance(n, ast.ListComp):
            return self.inside(lambda: self.comprehension(n, bound))
        if isinstance(n, ast.Call):
            return self.call(n, bound)
        raise Unread                        # no form of 7.1: a retired one, or any other

    def comprehension(self, n, bound):
        gens, inner = self.generators(n.generators, bound)
        elt = n.elt
        if isinstance(elt, ast.Name) and len(n.generators) == 1 and elt.id == n.generators[0].target.id:
            return "every " + gens
        return f"{self.side(elt, 1, inner)} for every {gens}"

    def dropped_root(self, n, drop):
        """is n a property read on the dropped root, which reads as a name"""
        return isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == drop

    def side(self, n, above, bound, drop=None):
        """n in words, in brackets when bracketed(n, above) or its reading
        holds an "or" of the view's own (own_or)"""
        text = self.w(n, bound, drop)
        return f"({text})" if bracketed(n, above) or self.own_or(n) else text

    def own_or(self, n):
        """does n's reading as a condition hold an "or" the view puts in, not
        one written: not over a value that may have no value, "<value> is no
        or has no value"; decided from the tree and the types, never the
        text"""
        return isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not) and self.yes_no(n.operand) == MAYBE

    def part(self, n, bound, drop=None, leaf=None):
        """n as a condition inside a larger one, in brackets when own_or(n)"""
        text = self.c(n, bound, drop, leaf)
        return f"({text})" if self.own_or(n) else text

    def item(self, n, bound):
        """n as one of a list joined with "and" (a list literal's elements, a
        call's arguments and keyword values): in brackets as side(n, 2) says
        (section 12), as the tree shows, never the text"""
        return self.side(n, 2, bound)

    def atom(self, n, bound, drop=None):
        """n as the thing a property, an item or a word is read on"""
        return self.side(n, 8, bound, drop)

    def index(self, i, of, bound):
        """l[0], l[-1], l[n] in words, l read already"""
        if isinstance(i, ast.Slice):
            raise Unread
        if isinstance(i, ast.Constant) and i.value == 0:
            return f"the first of {of}"
        if isinstance(i, ast.UnaryOp) and isinstance(i.op, ast.USub) and getattr(i.operand, "value", None) == 1:
            return f"the last of {of}"
        return f"item {self.side(i, 1, bound)} of {of}"

    def compare(self, n, bound, drop=None, left=None):
        """a comparison; left, its left side read already (a "whose" part)"""
        if len(n.ops) != 1:
            raise Unread                    # a chain
        op, right = type(n.ops[0]), n.comparators[0]
        left = left if left is not None else self.side(n.left, 4, bound, drop)
        if op in (ast.Is, ast.IsNot):
            if not (isinstance(right, ast.Constant) and right.value is None):
                raise Unread
            return f"{left} {'has no value' if op is ast.Is else 'has a value'}"
        if op not in COMPARE:
            raise Unread
        return f"{left} {COMPARE[op]} {self.side(right, 4, bound)}"

    def generators(self, gens, bound):
        """the generators in order, "x in l where c", and the names they
        bind, their types in self.scope, which the caller put back after"""
        parts = []
        for g in gens:
            if not isinstance(g.target, ast.Name) or g.is_async:
                raise Unread
            it = self.side(g.iter, 0, bound)
            t = self.types.of(g.iter, self.scope)
            self.scope[g.target.id] = t[1] if isinstance(t, tuple) and t[0] == "list" else None
            bound = bound | {g.target.id}
            part = f"{g.target.id} in {it}"
            if g.ifs:
                part += " where " + self.conj(g.ifs, bound, whole=False)
            parts.append(part)
        return ", and every ".join(parts), bound

    def call(self, n, bound):
        if not isinstance(n.func, ast.Name) or n.func.id in RETIRED_CALLS:
            raise Unread                    # a method (startswith), min, max
        f = n.func.id
        if f in ("len", "OLD"):
            if len(n.args) != 1 or n.keywords:
                raise Unread
            x = self.atom(n.args[0], bound)
            return "the number of " + x if f == "len" else x + " before"
        if f == "TIME":
            if not (len(n.args) == 1 and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                raise Unread
            return "the time " + n.args[0].value
        if f in ("sum", "any", "all"):
            if len(n.args) != 1 or n.keywords or not isinstance(n.args[0], ast.GeneratorExp):
                raise Unread
            if len(n.args[0].generators) != 1:
                raise Unread
            return self.inside(lambda: self.over(f, n.args[0], bound))
        return f"the {words(f)} of {self.arguments(n, bound)}"

    def over(self, f, g, bound):
        """sum, any or all over the generator g"""
        x = g.generators[0]
        if f == "sum":
            gens, inner = self.generators(g.generators, bound)
            return f"the sum of {self.side(g.elt, 1, inner)} over every {gens}"
        gens, inner = self.generators([ast.comprehension(target=x.target, iter=x.iter, ifs=[], is_async=0)], bound)
        if f == "any":
            return f"there is {a(gens)} where {self.conj(x.ifs + [g.elt], inner, whole=False)}"
        where = f" where {self.conj(x.ifs, inner, whole=False)}" if x.ifs else ""
        return f"for every {gens}{where}, {self.part(g.elt, inner)}"

    def arguments(self, n, bound=frozenset()):
        """a call's arguments: by position joined with "and", then ", <keyword> <value>" """
        if any(isinstance(x, ast.Starred) for x in n.args) or any(k.arg is None for k in n.keywords):
            raise Unread
        out = " and ".join(self.item(x, bound) for x in n.args)
        for k in n.keywords:
            out += f", {words(k.arg)} {self.item(k.value, bound)}"
        return out

    # conditions

    def c(self, n, bound=frozenset(), drop=None, leaf=None):
        """n as a condition: a value proven yes or no on its own reads
        "<value> is yes", any other value has no reading; leaf reads a
        comparison when it is not read whole. Under not, an OPTIONAL one
        reads "<value> is no or has no value", as not holds for both, in
        brackets inside a larger condition (part); a value whose reading
        holds an "and" of the view's own is in brackets before "is yes" """
        if isinstance(n, ast.BoolOp):
            if isinstance(n.op, ast.And):
                return self.conj(n.values, bound, drop, leaf)
            last = len(n.values) - 1
            return " or ".join(self.part(v, bound, drop, leaf) if k == last or not open_end(v)
                               else f"({self.c(v, bound, drop, leaf)})" for k, v in enumerate(n.values))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            x = n.operand
            t = self.yes_no(x)
            if t:
                return self.subject(x, bound, drop) + (" is no or has no value" if t == MAYBE else " is no")
            if value_form(x):
                raise Unread                # not proven yes or no
            if isinstance(x, ast.Compare):
                return "not " + self.c(x, bound, drop, leaf)
            return f"not ({self.c(x, bound, drop, leaf)})"
        if isinstance(n, ast.Compare):
            return leaf(n) if leaf else self.compare(n, bound, drop)
        if self.yes_no(n):
            return self.subject(n, bound, drop) + " is yes"
        if (isinstance(n, ast.Constant) and isinstance(n.value, bool)) or (
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("any", "all")):
            return self.w(n, bound, drop)
        raise Unread                        # a value not proven yes or no (a text, a number, a list) as a condition

    def subject(self, n, bound, drop=None):
        """a value before "is yes" or "is no", in brackets when its reading
        holds an "and" of the view's own (the f of a and b)"""
        text = self.w(n, bound, drop)
        return f"({text})" if loose(n) else text

    def conj(self, parts, bound, drop=None, leaf=None, texts=None, whole=True):
        """conditions joined with "and": an or among them reads "either ...
        or"; it, and a part whose reading ends open, is in brackets unless it
        is the last; a part whose reading holds an "or" of the view's own
        (own_or) is in brackets wherever it stands, unless it is the whole
        condition; whole is False when the and joins more than parts (after
        "it is done and", "is asked and", "where"); texts, the parts read
        already"""
        out = []
        for k, v in enumerate(parts):
            t = texts[k] if texts else self.c(v, bound, drop, leaf)
            if is_or(v):
                t = "either " + t
            if ((is_or(v) or open_end(v)) and k < len(parts) - 1) or (
                    self.own_or(v) and (len(parts) > 1 or not whole)):
                t = f"({t})"
            out.append(t)
        return " and ".join(out)

    def condition(self, n, root):
        """a condition whose left sides start with root, each read without it"""
        return self.c(n, leaf=lambda x: self.compare(x, frozenset(), left=self.w(x.left, drop=root)))


def lefts(n):
    """the left sides of a condition's comparisons, through and, or and
    not; None when a part is no comparison (a bare yes/no path included)"""
    if isinstance(n, ast.BoolOp):
        out = []
        for v in n.values:
            found = lefts(v)
            if found is None:
                return None
            out += found
        return out
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
        return lefts(n.operand)
    if isinstance(n, ast.Compare):
        return [n.left]
    return None


def root_of(n):
    """the name a path starts with, when a property is read on it directly
    (order.status, order.lines[0]; not lines[0].status), else None"""
    while isinstance(n, (ast.Attribute, ast.Subscript)):
        if isinstance(n.value, ast.Name):
            return n.value.id if isinstance(n, ast.Attribute) else None
        n = n.value
    return None


def mentions(n, name):
    return any(isinstance(x, ast.Name) and x.id == name for x in ast.walk(n))


def type_words(i):
    """an input's type in words, with "a" or "an" """
    if i["many"]:
        w = ("ordered " if i["in_order"] else "") + words(i["entity"]) + " list"
    elif i["entity"]:
        w = words(i["entity"])
    elif i["type"] == "choice":
        vs = [words(v) for v in i["values"]]
        w = "choice of " + (", ".join(vs[:-1]) + " or " + vs[-1] if len(vs) > 1 else vs[0])
    else:
        w = SCALAR.get(i["type"], "value")
    return a(("optional " if i["optional"] else "") + w)


def apposed(i):
    """is an input read with its type after its name: any whose name is not its type"""
    return not (i["entity"] == i["name"] and not i["many"])


def input_words(i):
    """an input as its type when its name is its type (an order), else
    "<name>, a <type>" """
    return f"{i['name']}, {type_words(i)}" if apposed(i) else type_words(i)


def value_words(v):
    """a with: value by the kind the checker resolved it to"""
    k, x = v["kind"], v["value"]
    if k == "list":
        return " and ".join(value_words(e) for e in x)
    if k == "text":
        return quoted(x)
    if k == "time":
        return "the time " + x
    if k == "yes_no":
        return "yes" if x else "no"
    if k in ("choice", "role"):
        return words(x)
    return str(x)       # a given keeps its name; a number, a fixture folder as written


# --- sentences -----------------------------------------------------------------

def sentence(kind, text, line, shade="plain"):
    return {"kind": kind, "text": text, "line": line, "shade": shade}


def shaded(W, shade="plain"):
    """a sentence's shade: a warning when W showed an expression as written
    (section 12), which clears it"""
    if W.unread:
        W.unread = False
        return "warning"
    return shade


def notes(xs, lines, kind="note"):
    return [sentence(kind, x, ln, "grey" if kind == "note" else "warning") for x, ln in zip(xs, lines)]


def operation_sentences(op, entities, types):
    """the operation, its permissions, refusals, outcomes and read in file
    order, then its notes"""
    name = words(op["name"])
    inputs = {i["name"]: i for i in op["inputs"]}
    W = Words(kept=inputs, the={n for n, i in inputs.items() if i["entity"] == n and not i["many"]} & entities,
              types=types, scope=types.scope(op))
    parts = []
    for w in op["who"]:
        whose, during, other = "", "", ""
        if w["when"]:
            c = checker.json_ast(w["when"]["ast"])
            try:
                mine, rest, others = [], [], []     # (part, its text)
                for part in c.values if isinstance(c, ast.BoolOp) and isinstance(c.op, ast.And) else [c]:
                    if not mentions(part, "ACTOR"):
                        rest.append((part, W.c(part)))
                    elif isinstance(part, ast.Compare) and root_of(part.left) == "ACTOR":
                        mine.append((part, W.condition(part, "ACTOR")))
                    else:                   # reads unnaturally after "whose": at the end, after "if"
                        others.append((part, W.c(part)))
                whose, during, other = [W.conj([p for p, _ in g], frozenset(), texts=[t for _, t in g]) if g else ""
                                        for g in (mine, rest, others)]
            except Unread:                  # shown whole, where its top would stand
                if mentions(c, "ACTOR"):
                    other = W.as_written(w["when"])
                else:
                    during = W.as_written(w["when"])
        text = a(words(w["role"])) + (" whose " + whose if whose else "")
        text += f" may {name}" + (" " + joined([input_words(i) for i in op["inputs"]]) if op["inputs"] else "")
        if during:      # an apposition at the end closes with a comma
            text += ("," if op["inputs"] and apposed(op["inputs"][-1]) else "") + " while " + during
        if other:
            text += ", if " + other
        parts.append(sentence("permission", stop(cap(text)), w["line"], shaded(W)))
    for r in op["refuse"]:
        c = checker.json_ast(r["when"]["ast"])
        found = lefts(c)
        roots = {root_of(x) for x in found} if found else {None}
        root = roots.pop() if len(roots) == 1 else None
        try:
            if root in inputs:
                i = inputs[root]
                who = input_words(i) + ("," if apposed(i) else "")
                cond = f"for {who} whose {W.condition(c, root)}"
            else:
                cond = "and " + W.conj([c], frozenset(), whole=False)
        except Unread:
            cond = "and " + W.as_written(r["when"])
        text = f"If {name} is asked {cond}, then the system shall refuse it: {r['reason']}"
        shade = shaded(W, "warning" if r["drift"] else "plain")
        parts.append(sentence("refusal", stop(text), r["when"]["line"], shade))
    for f in op["ensure"]:
        text = f"When {name} succeeds, {f['means'] or W.of(f['fact'], condition=True)}"
        parts.append(sentence("outcome", stop(text), f["line"], shaded(W, "warning" if f["drift"] else "plain")))
    if op["returns"]:
        R = Words(kept=inputs, the=W.the | ({o["text"].split(".")[0] for o in op["ordered_by"]} & entities),
                  types=types, scope=W.scope)
        text = f"{cap(name)} gives {W.of(op['returns'])}"
        if op["ordered_by"]:
            text += ", ordered by " + " and ".join(R.of(o) for o in op["ordered_by"])
        W.unread |= R.unread
        R.unread = False
        parts.append(sentence("read", stop(text), op["returns"]["line"], shaded(W)))
    parts.sort(key=lambda s: s["line"])
    return ([sentence("operation", stop(cap(f"{name} {op['is']}")), op["line"])] + parts
            + notes(op["notes"], op["note_lines"]))


def example_sentences(x, types):
    """the example, its givens in one sentence, each step's when and then,
    in file order, then its notes"""
    scope = {g["name"]: ("actor", "all", tuple(r["value"] for r in g["with"].get("roles", {"value": []})["value"]))
             if g["kind"] == "actor" else ("entity", g["kind"]) for g in x["given"]}
    W = Words(kept=scope, types=types, scope=scope)     # a bare name that is no given is a choice value
    parts = []
    if x["given"]:
        items = []
        for g in x["given"]:
            values = dict(g["with"])
            if g["kind"] == "actor":
                roles = values.pop("roles", {"value": []})["value"]
                item = f"{g['name']}, " + " and ".join(a(words(r["value"])) for r in roles)
            else:
                item = f"{g['name']}, {a(words(g['kind']))}"
            if values:
                item += " with " + " and ".join(f"{words(p)} {value_words(v)}" for p, v in values.items())
            items.append(item)
        parts.append((x["given_line"], [sentence("given", stop(f"Given {joined(items)}"), x["given_line"])]))
    for s in x["steps"]:
        out = []
        facts = W.conj([checker.json_ast(t["ast"]) for t in s["then"]], frozenset(),
                       texts=[W.of(t, condition=True) for t in s["then"]],     # the facts of one then are one and
                       whole=not s["when"])                                    # after "it is done and" too
        then_shade = shaded(W)
        if s["when"]:
            call = checker.json_ast(s["when"]["call"]["ast"])
            try:
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                    raise Unread
                args = W.arguments(call)
                text = f"When {s['when']['actor']} asks to {words(call.func.id)}" + (" " + args if args else "")
            except Unread:
                text = f"When {s['when']['actor']} asks {W.as_written(s['when']['call'])}"
            out.append(sentence("when", stop(text), s["when"]["line"], shaded(W)))
            v = s["verdict"]
            said = "it is done" if v["kind"] == "DONE" else f"it is refused: {v['reason']}"
            then = f"Then {said}" + ((" and " if v["kind"] == "DONE" else ", and ") + facts if facts else "")
        else:
            then = f"Then {facts}"
        out.append(sentence("then", stop(then), s["then_line"], then_shade))
        parts.append((s["line"], out))
    parts.sort(key=lambda p: p[0])
    return ([sentence("example", stop(f"Example: {x['title']}"), x["line"])]
            + [s for _, ss in parts for s in ss] + notes(x["notes"], x["note_lines"]))


# EDDA-007@0
def story_sentences(story, operations, entities, roles):
    """a story of the model as sentences (section 12): the story, its notes,
    its questions, then its operations and its examples in file order,
    the examples grouped under their rules when it has rules. operations,
    the model's operations (only the story's are read as sentences, any
    gives the type of a call); entities and roles, the model's, which it
    is read against, their properties with their types"""
    types = Types(entities, roles, operations)
    entities = {e["name"] for e in entities}
    out = [sentence("story", f"{stop(cap(story['sentence']))} As {a(words(story['as_a']))}, "
                             f"I want {story['i_want']}, so that {stop(story['so_that'])}", story["line"])]
    out += notes(story["notes"], story["note_lines"]) + notes(story["questions"], story["question_lines"], "question")
    ops = {o["name"]: o for o in operations if o["story"] == story["id"]}
    groups = [(ops[n]["line"], operation_sentences(ops[n], entities, types)) for n in story["operations"]]
    by_title = {x["title"]: x for x in story["examples"]}
    if story["rules"]:
        ex = []
        for r in story["rules"]:
            ex.append(sentence("rule", stop(f"Rule: {r['rule']}"), r["line"]))
            for t in r["shown_by"]:
                if t in by_title:       # a snapshot is never checked for meaning
                    ex += example_sentences(by_title[t], types)
        where = story["examples"][0]["line"] if story["examples"] else story["rules"][0]["line"]
        groups.append((where, ex))      # the rules come where the examples stood
    elif story["examples"]:
        groups.append((story["examples"][0]["line"],
                       [s for x in story["examples"] for s in example_sentences(x, types)]))
    groups.sort(key=lambda g: g[0])
    return out + [s for _, ss in groups for s in ss]


def version_sentences(version):
    """an approved version of a story as sentences, from its snapshot as the
    model holds it, read against the blocks it pins (sections 10, 12); a
    line counts from the version's key line"""
    return story_sentences(version["story"], version["operations"], version["entities"], version["roles"])


def invariant_sentences(entity, types=None):
    """an entity's always facts: "Always, <fact>." , its own properties
    read by their bare names"""
    types = types or Types([entity])
    W = Words(types=types, scope=types.entities[entity["name"]])
    return [sentence("invariant", stop(f"Always, {W.of(f['fact'], condition=True)}"), f["line"], shaded(W))
            for f in entity["always"]]


# --- the command ---------------------------------------------------------------

MARK = {"plain": "  ", "grey": "~ ", "warning": "? "}


def main(argv):
    ap = argparse.ArgumentParser(description="print each story as plain sentences (reference section 12)")
    ap.add_argument("--lines", action="store_true", help="put <file>:<line>: before each sentence")
    ap.add_argument("--root", help="the project: the folder holding edda.yaml and the spec folder; "
                                   "then every name after the options is a STORY")
    ap.add_argument("folder", nargs="?", metavar="DIR")
    ap.add_argument("stories", nargs="*", metavar="STORY")
    a = ap.parse_args(argv)
    if a.root is not None and a.folder is not None:
        a.folder, a.stories = None, [a.folder] + a.stories
    if a.folder is not None and not os.path.isdir(a.folder):
        print(f"no such folder: {a.folder}")
        return 1
    import settings     # edda.yaml: the spec folder and the pin (section 9)
    project, code = settings.open_project(a.root, a.folder)
    if project is None:
        return code
    folder = project.folder
    if not os.path.isdir(folder):
        print(f"no such folder: {os.path.relpath(folder)}")
        return 1
    if checker.refused(folder, project.guard):
        checker.report(folder, project.root if a.root else checker.ROOT, guard=project.guard)
        return 1
    model = checker.model_of(folder, project.guard)
    unknown = [s for s in a.stories if s not in {st["id"] for st in model["stories"]}]
    if unknown:
        print(f"no such story: {', '.join(unknown)}")
        return 1
    types = Types(model["entities"], model["roles"], model["operations"])
    blocks = []         # (file, sentences): invariants before the stories of each file
    for f in model["files"]:
        if not a.stories:
            blocks += [(f["name"], ss) for e in model["entities"] if e["file"] == f["name"]
                       for ss in [invariant_sentences(e, types)] if ss]
        blocks += [(f["name"], story_sentences(st, model["operations"], model["entities"], model["roles"]))
                   for st in model["stories"]
                   if st["file"] == f["name"] and (not a.stories or st["id"] in a.stories)]
    for n, (fname, ss) in enumerate(blocks):
        if n:
            print()
        for s in ss:
            print(MARK[s["shade"]] + (f"{fname}:{s['line']}: " if a.lines else "") + s["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
