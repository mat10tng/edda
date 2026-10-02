#!/usr/bin/env python3
"""Validate every .edda and .edda.vc file through the source, shape and
meaning layers of reference section 11: the YAML 1.2 subset, the
quoting rule, both JSON Schemas mapped to rule names, the type-phrase
grammar, the Python expression whitelist (7.1) with types from literals
and declarations, the style rule (7.2) under its equivalences, and the
operation key rules. Reports which fixtures each layer catches. A
partial checker: name resolution across files, the history layer, the
flags and the examples themselves are not checked here."""
import ast, glob, json, os, re, sys
import yaml
from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
schema = json.load(open(f"{ROOT}/language/schema.json"))
vc_schema = json.load(open(f"{ROOT}/language/vc-schema.json"))
Draft202012Validator.check_schema(schema)
Draft202012Validator.check_schema(vc_schema)
V = Draft202012Validator(schema)
VC = Draft202012Validator(vc_schema)

NAME = r"[a-z][a-z0-9_]*"
PY_KEYWORDS = {"False", "None", "True", "and", "as", "assert", "async", "await", "break", "class",
               "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global",
               "if", "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise",
               "return", "try", "while", "with", "yield"}


# --- YAML 1.2 core schema loader (PyYAML is 1.1 by default) --------------

class Core(yaml.SafeLoader):
    pass


Core.yaml_implicit_resolvers = {}
for ch in "tT":
    Core.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(true|True|TRUE)$"), list(ch))
for ch in "fF":
    Core.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(false|False|FALSE)$"), list(ch))
Core.add_implicit_resolver("tag:yaml.org,2002:null", re.compile(r"^(null|Null|NULL|~|)$"), list("nN~") + [None])
Core.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^[-+]?[0-9]+$"), list("-+0123456789"))
Core.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^0o[0-7]+$|^0x[0-9a-fA-F]+$"), list("0"))
Core.add_implicit_resolver("tag:yaml.org,2002:float",
                           re.compile(r"^[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?$|^[-+]?\.(inf|Inf|INF)$|^\.(nan|NaN|NAN)$"),
                           list("-+.0123456789"))


def core_int(loader, node):
    v = loader.construct_scalar(node)
    if v.startswith("0o"):
        return int(v[2:], 8)
    if v.startswith("0x"):
        return int(v[2:], 16)
    return int(v, 10)


Core.add_constructor("tag:yaml.org,2002:int", core_int)

DUPLICATES = []   # (key, line) found by the last load


def dup_mapping(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            DUPLICATES.append((key, k.start_mark.line + 1))
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


Core.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, dup_mapping)


# --- the source layer and the quoting rule ----------------------------------

TEXT_PATHS = [
    "roles/*/is", "entities/*/is", "epics/*", "entities/*/wording/*/*/*",
    "stories/*/story", "stories/*/i_want", "stories/*/so_that",
    "stories/*/notes/#", "stories/*/questions/#",
    "stories/*/operations/*/is", "stories/*/operations/*/notes/#",
    "stories/*/operations/*/refuse/#/reason", "stories/*/operations/*/ensure/#/means",
    "entities/*/always/#/means", "entities/*/while/#/holds/means",
    "stories/*/examples/*/notes/#",
    "stories/*/examples/*/steps/#/then/#/refused",
]
EXPR_PATHS = [
    "entities/*/properties/*/computed",
    "entities/*/always/#", "entities/*/always/#/fact",
    "entities/*/while/#/when", "entities/*/while/#/holds", "entities/*/while/#/holds/fact",
    "entities/*/may_create/#/when", "entities/*/may_read/#/when",
    "entities/*/may_update/#/when", "entities/*/may_delete/#/when",
    "stories/*/operations/*/who/#/when",
    "stories/*/operations/*/refuse/#/when",
    "stories/*/operations/*/ensure/#", "stories/*/operations/*/ensure/#/fact",
    "stories/*/operations/*/returns", "stories/*/operations/*/ordered_by/#",
    "stories/*/examples/*/steps/#/when/call",
    "stories/*/examples/*/steps/#/then/#",
]
TYPE_PATHS = ["roles/*/has/*", "entities/*/properties/*", "stories/*/operations/*/inputs/*"]
TITLE_PATHS = ["stories/*/examples/*"]
VC_TEXT_PATHS = ["#/because"]


def matches(path, pattern):
    parts = pattern.split("/")
    if len(parts) != len(path):
        return False
    for p, q in zip(parts, path):
        if p == "*" or (p == "#" and isinstance(q, int)) or p == q:
            continue
        return False
    return True


def any_match(path, patterns):
    return any(matches(path, p) for p in patterns)


def indentation_problems(text):
    out, prev = [], 0
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ind = len(line) - len(line.lstrip(" "))
        if ind % 2 or ind > prev + 2:
            out.append(f"indentation must be even and at most two deeper than the line before (line {n})")
        rest = line.lstrip(" ")
        while rest.startswith("- "):      # a list dash counts as two for the next line
            ind += 2
            rest = rest[2:]
        prev = ind
    return out


def source_problems(text, is_vc):
    """layer 1 (not_yaml, yaml_feature) and the quoting rule of layer 2;
    every independent problem is collected; returns (source, quoting)"""
    src, quoting = [], []
    if "\t" in text:
        src.append(f"tabs are not allowed (line {text[:text.index(chr(9))].count(chr(10)) + 1})")
    try:
        tokens = list(yaml.scan(text))
    except yaml.YAMLError as e:
        return [f"not YAML: {str(e).splitlines()[0]}"], []
    for t in tokens:
        n = type(t).__name__
        line = t.start_mark.line + 1
        if n == "AnchorToken":
            src.append(f"anchors and aliases are not allowed (line {line})")
        elif n == "TagToken":
            src.append(f"tags are not allowed (line {line})")
        elif n == "DirectiveToken":
            src.append(f"directives are not allowed (line {line})")
    try:
        docs = list(yaml.compose_all(text, Loader=Core))
    except yaml.YAMLError as e:
        return src + [f"not YAML: {str(e).splitlines()[0]}"], []
    if len(docs) > 1:
        src.append("one document per file")
    src += indentation_problems(text)
    root = docs[0] if docs else None

    def key_name(path):
        return path[-1] if path and isinstance(path[-1], str) else (path[-2] if len(path) > 1 else "")

    def walk(node, path):
        line = node.start_mark.line + 1
        multiline = node.end_mark.line > node.start_mark.line
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                kline = k.start_mark.line + 1
                if not isinstance(k, yaml.ScalarNode):
                    src.append(f"a complex key is not allowed (line {kline})")
                    continue
                if k.value == "<<":
                    src.append(f"the << key is not allowed (line {kline})")
                kpath = path + (k.value,)
                is_title = not is_vc and any_match(kpath, TITLE_PATHS)
                if k.style == "'":
                    src.append(f"single quotes are not allowed; use double quotes (line {kline})")
                elif k.style in ("|", ">"):
                    src.append(f"a key is one plain line (line {kline})")
                elif is_title:
                    if k.style != '"':
                        quoting.append(f"quote the example title; an unquoted # drops the rest of the line (line {kline})")
                    if k.end_mark.line > k.start_mark.line:
                        src.append(f"an example title is one line (line {kline})")
                elif k.style == '"':
                    src.append(f"a key is plain, not quoted (line {kline})")
                walk(v, kpath)
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                walk(v, path + (i,))
        elif isinstance(node, yaml.ScalarNode):
            key = key_name(path)
            if node.style == "'":
                src.append(f"single quotes are not allowed; use double quotes (line {line})")
                return
            if node.style == ">":
                src.append(f"folded scalars are not allowed (line {line})")
                return
            if node.style == "|":
                if not (is_vc and path[-1:] == ("text",)):
                    src.append(f"block scalars are allowed only for text in .edda.vc (line {line})")
                return
            if is_vc:
                if node.style is None and any_match(path, VC_TEXT_PATHS):
                    quoting.append(f"quote the {key}; an unquoted # drops the rest of the line (line {line})")
                return
            is_expr = any_match(path, EXPR_PATHS)
            is_type = any_match(path, TYPE_PATHS)
            is_text = any_match(path, TEXT_PATHS)
            if is_expr and node.value == "DONE" and node.style is None:
                if not (len(path) >= 2 and path[-2] == "then" and path[-1] == 0):
                    src.append(f"DONE is allowed only as the first then item (line {line})")
                return
            if (is_expr or is_text) and node.style is None:
                quoting.append(f"quote the {key}; an unquoted # drops the rest of the line (line {line})")
            if (is_expr or is_type) and multiline:
                src.append(f"an expression or type phrase is one line (line {line})")

    if root is not None:
        walk(root, ())
    return src, quoting


# --- the shape layer: from the schema to a rule ------------------------------

KIND = {dict: "mapping", list: "list", str: "text", int: "number", float: "number", bool: "yes/no", type(None): "nothing"}


def schema_problems(validator, data):
    """jsonschema errors mapped to the rules of reference section 11; a
    missing key is suppressed in a block that has an unknown key"""
    out, unknown_in = [], set()

    def adapt(err, path):
        v = err.validator
        key = path[-1] if path and isinstance(path[-1], str) else (path[-2] if len(path) > 1 else "file")
        where = "/".join(map(str, path)) or "file"
        if v in ("anyOf", "oneOf"):
            kind = type(err.instance)
            branches = [c for c in err.context if c.schema.get("type") in (
                {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}.get(c.schema.get("type")) and None,) or True]
            matching = [c for c in err.context
                        if {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}.get(c.schema.get("type")) is kind
                        or (c.schema.get("type") == "number" and kind in (int, float))]
            if v == "oneOf" and not err.context:
                return [("wrong_type", where, f"{key} must be one of its kinds")]
            if not matching:
                return [("wrong_type", where, f"{key} must be a {'mapping' if dict in [c.schema.get('type') for c in err.context] else 'text'}")]
            res = []
            for c in matching:
                res += adapt(c, path + tuple(c.relative_path))
            return res
        if v == "additionalProperties":
            extras = [k for k in err.instance if k not in err.schema.get("properties", {})]
            unknown_in.add(where)
            return [("unknown_key", where, f"unknown key: {k}") for k in extras]
        if v == "required":
            m = re.match(r"'(.+)' is a required property", err.message)
            return [("missing_key", where, f"{key} needs {m.group(1) if m else '?'}:")]
        if v == "type":
            if err.validator_value == "array":
                return [("not_a_list", where, f"{key} must be a list, one item per line")]
            return [("wrong_type", where, f"{key} must be a {dict(object='mapping', string='text', integer='number', number='number', boolean='yes/no').get(err.validator_value, err.validator_value)}")]
        if v in ("minProperties", "maxProperties", "minItems", "minLength", "const", "not"):
            if v == "minLength" and err.instance == "":
                return [("wrong_type", where, f"{key} expects a text, nothing was given")]
            return [("wrong_type", where, f"{key} has the wrong shape")]
        if v in ("propertyNames", "pattern", "enum"):
            name = err.instance if isinstance(err.instance, str) else "?"
            if v == "propertyNames" and err.context:
                name = err.context[0].instance
            return [("bad_name", where, f"not a name: {name}")]
        if v in ("prefixItems", "items", "if", "then", "else"):
            res = []
            for c in err.context or []:
                res += adapt(c, path + tuple(c.relative_path))
            return res or [("wrong_type", where, f"{key} has the wrong shape")]
        return [("wrong_type", where, err.message[:80])]

    for err in validator.iter_errors(data):
        out += adapt(err, tuple(err.absolute_path))
    out = [p for p in out if not (p[0] == "missing_key" and p[1] in unknown_in)]
    seen, res = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            res.append(p)
    return [f"{where}: {msg}" for rule, where, msg in res]


# --- the meaning layer: type phrases, types and Python expressions ----------

STR_LIT = r'"(?:[^"\\]|\\.)*"'
TYPE_RE = re.compile(
    rf"(?:DEFAULT (?:-?[0-9]+(?:\.[0-9]+)?|{STR_LIT}|True|False|{NAME}(?: \| {NAME})+)(?:, DERIVED)?"
    rf"|(?:TEXT|NUMBER|INTEGER|TIME|YES_NO|{NAME}(?: \| {NAME})+|{NAME}|MANY {NAME}(?:, IN ORDER)?)(?:, OPTIONAL)?(?:, DERIVED)?)")


def type_phrase_problems(v):
    if not TYPE_RE.fullmatch(v):
        return [f"not a type phrase: {v}"]
    m = re.search(rf"({NAME}(?: \| {NAME})+)", v)
    if m:
        vals = m.group(1).split(" | ")
        if len(set(vals)) != len(vals):
            return [f"not a type phrase (repeated value): {v}"]
        for x in vals:
            if x in PY_KEYWORDS:
                return [f"not a name: {x}"]
    return []


def type_of_phrase(v):
    """the type a type phrase declares: INTEGER, NUMBER, TEXT, TIME, YES_NO,
    CHOICE, ('list', entity) or ('entity', name); None when unknown"""
    if not isinstance(v, str) or not TYPE_RE.fullmatch(v):
        return None
    core = re.sub(r", (OPTIONAL|DERIVED)", "", v)
    if core.startswith("DEFAULT "):
        lit = core[8:]
        if re.fullmatch(r"-?[0-9]+", lit):
            return "INTEGER"
        if re.fullmatch(r"-?[0-9]+\.[0-9]+", lit):
            return "NUMBER"
        if lit in ("True", "False"):
            return "YES_NO"
        if lit.startswith('"'):
            return "TEXT"
        return "CHOICE"
    if core in ("TEXT", "NUMBER", "INTEGER", "TIME", "YES_NO"):
        return core
    if " | " in core:
        return "CHOICE"
    if core.startswith("MANY "):
        return ("list", core[5:].split(",")[0])
    return ("entity", core)


ALLOWED_NODES = {
    "Expression", "Name", "Attribute", "Subscript", "Constant", "List", "Compare",
    "BoolOp", "And", "Or", "UnaryOp", "Not", "USub", "BinOp", "Add", "Sub", "Mult", "Div",
    "IfExp", "ListComp", "GeneratorExp", "comprehension", "Call", "keyword", "Load", "Store", "Slice",
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "In", "NotIn", "Is", "IsNot",
}
FIXED = {"OLD", "ACTOR", "RESULT", "NOW", "TODAY"}
ONE_ARG = {"len", "OLD"}
GEN_ONLY = {"sum", "min", "max", "any", "all"}
OPS = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=",
       ast.In: "in", ast.NotIn: "not in", ast.Is: "is", ast.IsNot: "is not"}


class Types:
    """types from declarations: entities -> properties, roles -> has"""

    def __init__(self, data):
        self.entities = {}
        for ename, ent in (data.get("entities") or {}).items():
            props = {}
            for pn, pv in (ent.get("properties") or {}).items():
                props[pn] = None if isinstance(pv, dict) else type_of_phrase(pv)
            self.entities[ename] = props
        self.actor = {"name": "TEXT", "roles": ("list", "role")}
        for role in (data.get("roles") or {}).values():
            for pn, pv in (role.get("has") or {}).items():
                self.actor[pn] = type_of_phrase(pv)
        # computed properties: typed from their expressions, one pass
        for ename, ent in (data.get("entities") or {}).items():
            scope = dict(self.entities[ename])
            for pn, pv in (ent.get("properties") or {}).items():
                if isinstance(pv, dict) and isinstance(pv.get("computed"), str):
                    try:
                        tree = ast.parse(pv["computed"], mode="eval")
                        self.entities[ename][pn] = self.type_of(tree.body, scope)
                    except SyntaxError:
                        pass

    def prop(self, owner, name):
        if owner == ("entity", "actor"):
            return self.actor.get(name)
        if isinstance(owner, tuple) and owner[0] == "entity":
            return self.entities.get(owner[1], {}).get(name)
        return None

    def type_of(self, n, scope):
        if isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, bool):
                return "YES_NO"
            if isinstance(v, int):
                return "INTEGER"
            if isinstance(v, float):
                return "NUMBER"
            if isinstance(v, str):
                return "TEXT"
            return "NONE"
        if isinstance(n, (ast.List, ast.ListComp)):
            return ("list", None)
        if isinstance(n, ast.Name):
            if n.id == "ACTOR":
                return ("entity", "actor")
            return scope.get(n.id)
        if isinstance(n, ast.Attribute):
            return self.prop(self.type_of(n.value, scope), n.attr)
        if isinstance(n, ast.Subscript):
            t = self.type_of(n.value, scope)
            if isinstance(n.slice, ast.Slice):
                return t if isinstance(t, tuple) and t[0] == "list" else ("TEXT" if t == "TEXT" else None)
            if isinstance(t, tuple) and t[0] == "list":
                return ("entity", t[1]) if t[1] else None
            return None
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id == "len":
                return "INTEGER"
            if n.func.id in ("any", "all"):
                return "YES_NO"
            if n.func.id == "OLD" and n.args:
                return self.type_of(n.args[0], scope)
            return None
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "startswith":
            return "YES_NO"
        if isinstance(n, (ast.Compare, ast.BoolOp)):
            return "YES_NO"
        if isinstance(n, ast.UnaryOp):
            return "YES_NO" if isinstance(n.op, ast.Not) else self.type_of(n.operand, scope)
        if isinstance(n, ast.BinOp):
            lt, rt = self.type_of(n.left, scope), self.type_of(n.right, scope)
            if isinstance(lt, tuple) and lt[0] == "list":
                return lt
            if lt == "INTEGER" and rt == "INTEGER" and not isinstance(n.op, ast.Div):
                return "INTEGER"
            if lt in ("INTEGER", "NUMBER") or rt in ("INTEGER", "NUMBER"):
                return "NUMBER"
            return None
        return None


def is_list(t):
    return isinstance(t, tuple) and t[0] == "list"


def src_of(node, src):
    return ast.get_source_segment(src, node) or "..."


def expression_problems(src, types=None, scope=None, allow_old=False, call_slot=False):
    """problems of one expression: not_an_expression, second_way, type_mismatch"""
    scope = scope or {}
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return [f"not an expression: {src}"]
    out = []
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def t(n):
        return types.type_of(n, scope) if types else None

    def second(one, other):
        out.append(f"write {one} (not {other}): {src}")

    if call_slot:
        body = tree.body
        if not (isinstance(body, ast.Call) and isinstance(body.func, ast.Name)
                and body.func.id not in ONE_ARG and body.func.id not in GEN_ONLY):
            return [f"not an expression (a call of an operation was expected): {src}"]

    for node in ast.walk(tree):
        kind = type(node).__name__
        if kind not in ALLOWED_NODES:
            out.append(f"not an expression ({kind}): {src}")
            continue
        if kind == "Name" and node.id in PY_KEYWORDS:
            out.append(f"not a name: {node.id}")
        if kind == "Compare":
            if len(node.ops) != 1:
                parts = [src_of(node.left, src)]
                for op, c in zip(node.ops, node.comparators):
                    parts.append(f"{OPS[type(op)]} {src_of(c, src)}")
                pieces = []
                left = src_of(node.left, src)
                for op, c in zip(node.ops, node.comparators):
                    right = src_of(c, src)
                    pieces.append(f"{left} {OPS[type(op)]} {right}")
                    left = right
                second(" and ".join(pieces), src_of(node, src))
                continue
            left, right, op = node.left, node.comparators[0], node.ops[0]
            if isinstance(op, (ast.Is, ast.IsNot)) and not (isinstance(right, ast.Constant) and right.value is None):
                out.append(f"not an expression (is only against None): {src}")
            neg = isinstance(op, ast.NotEq)
            # len(x) == 0, len(x) != 0, len(x) > 0, only for a list
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len" and left.args \
                    and isinstance(right, ast.Constant) and right.value == 0 and not isinstance(right.value, bool) \
                    and is_list(t(left.args[0])):
                x = src_of(left.args[0], src)
                if isinstance(op, ast.Eq):
                    second(f"{x} == []", src_of(node, src))
                elif isinstance(op, (ast.NotEq, ast.Gt)):
                    second(f"{x} != []", src_of(node, src))
            # x == None, None == x
            for a, b in ((left, right), (right, left)):
                if isinstance(b, ast.Constant) and b.value is None and isinstance(op, (ast.Eq, ast.NotEq)):
                    second(f"{src_of(a, src)} is {'not ' if neg else ''}None", src_of(node, src))
                    break
            # x == True / False, True == x, only for a yes/no
            for a, b in ((left, right), (right, left)):
                if isinstance(b, ast.Constant) and isinstance(b.value, bool) and isinstance(op, (ast.Eq, ast.NotEq)) \
                        and t(a) == "YES_NO":
                    x = src_of(a, src)
                    holds = b.value != neg
                    second(x if holds else f"not {x}", src_of(node, src))
                    break
            # x[:n] == "t" where "t" has n characters
            if isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Slice) and left.slice.lower is None \
                    and isinstance(left.slice.upper, ast.Constant) and isinstance(left.slice.upper.value, int) \
                    and isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(right, ast.Constant) \
                    and isinstance(right.value, str) and len(right.value) == left.slice.upper.value:
                call = f"{src_of(left.value, src)}.startswith({src_of(right, src)})"
                second(f"not {call}" if neg else call, src_of(node, src))
        elif kind == "Call":
            f = node.func
            if isinstance(f, ast.Attribute):
                if f.attr != "startswith":
                    out.append(f"not an expression (method {f.attr}): {src}")
                elif len(node.args) != 1 or node.keywords:
                    out.append(f"startswith expects one argument: {src}")
                elif t(f.value) not in (None, "TEXT"):
                    out.append(f"startswith expects a text: {src}")
            elif isinstance(f, ast.Name):
                if f.id in GEN_ONLY:
                    if not (len(node.args) == 1 and isinstance(node.args[0], ast.GeneratorExp) and not node.keywords):
                        out.append(f"{f.id} expects one generator: {src}")
                    elif f.id == "sum" and isinstance(node.args[0].elt, ast.Constant) and node.args[0].elt.value == 1 \
                            and len(node.args[0].generators) == 1 and not node.args[0].generators[0].ifs:
                        second(f"len({src_of(node.args[0].generators[0].iter, src)})", src_of(node, src))
                elif f.id in ONE_ARG:
                    if len(node.args) != 1 or node.keywords:
                        out.append(f"{f.id} expects one argument: {src}")
                    elif f.id == "len":
                        at = t(node.args[0])
                        if at is not None and not (is_list(at) or at == "TEXT"):
                            out.append(f"len expects a list or a text: {src}")
                    if f.id == "OLD" and not allow_old:
                        out.append(f"not an expression (OLD only under ensure): {src}")
                elif not re.fullmatch(NAME, f.id):
                    out.append(f"not an expression (call to {f.id}): {src}")
            else:
                out.append(f"not an expression (call form): {src}")
        elif kind == "GeneratorExp":
            p = parents.get(node)
            if not (isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in GEN_ONLY):
                out.append(f"not an expression (a generator only inside {', '.join(sorted(GEN_ONLY))}): {src}")
        elif kind == "comprehension":
            if not isinstance(node.target, ast.Name):
                out.append(f"not an expression (a comprehension variable is a plain name): {src}")
            if node.is_async:
                out.append(f"not an expression (async): {src}")
            it = t(node.iter)
            if it is not None and not is_list(it):
                out.append(f"for expects a list: {src}")
            elif isinstance(node.target, ast.Name) and is_list(it) and it[1]:
                scope = dict(scope, **{node.target.id: ("entity", it[1])})
        elif kind == "Slice":
            if node.step is not None:
                out.append(f"not an expression (slice step): {src}")
            for b in (node.lower, node.upper):
                if b is not None and t(b) not in (None, "INTEGER"):
                    out.append(f"a slice bound expects an INTEGER: {src}")
        elif kind == "Subscript":
            s = node.slice
            if isinstance(s, ast.Slice):
                pass
            elif t(s) not in (None, "INTEGER"):
                out.append(f"an index expects an INTEGER: {src}")
            elif isinstance(s, ast.BinOp) and isinstance(s.op, ast.Sub) and isinstance(s.left, ast.Call) \
                    and isinstance(s.left.func, ast.Name) and s.left.func.id == "len" and s.left.args \
                    and isinstance(s.right, ast.Constant) and s.right.value == 1 \
                    and src_of(s.left.args[0], src) == src_of(node.value, src):
                second(f"{src_of(node.value, src)}[-1]", src_of(node, src))
        elif kind == "UnaryOp" and isinstance(node.op, ast.Not):
            if is_list(t(node.operand)):
                second(f"{src_of(node.operand, src)} == []", src_of(node, src))
        elif kind == "BinOp":
            lt, rt = t(node.left), t(node.right)
            if isinstance(node.op, ast.Add) and (is_list(lt) != is_list(rt)) and lt is not None and rt is not None:
                out.append(f"+ expects two lists or two numbers: {src}")
            elif not isinstance(node.op, ast.Add) and (is_list(lt) or is_list(rt)):
                out.append(f"{type(node.op).__name__} expects numbers: {src}")
        elif kind == "Constant":
            if not isinstance(node.value, (int, float, str, bool, type(None))):
                out.append(f"not an expression (constant): {src}")
        elif kind == "Name":
            if not (re.fullmatch(NAME, node.id) or node.id in FIXED or node.id in ONE_ARG or node.id in GEN_ONLY):
                out.append(f"not an expression (name {node.id}): {src}")
    return out


def walk_meaning(data):
    """yield (path, problem) for type phrases, expressions and operation keys"""
    types = Types(data)

    def tp(v, where):
        if isinstance(v, str):
            if v == "":
                yield where, "a type phrase was expected, nothing was given"
                return
            for p in type_phrase_problems(v):
                yield where, p

    def ex(v, where, scope, allow_old=False, call_slot=False):
        if isinstance(v, str):
            if v == "":
                yield where, "an expression was expected, nothing was given"
                return
            for p in expression_problems(v, types, scope, allow_old, call_slot):
                yield where, p

    def fact(v, where, scope, allow_old=False):
        if isinstance(v, dict):
            yield from ex(v.get("fact"), where + ("fact",), scope, allow_old)
        else:
            yield from ex(v, where, scope, allow_old)

    for rname, role in (data.get("roles") or {}).items():
        if rname in PY_KEYWORDS:
            yield ("roles", rname), f"not a name: {rname}"
        for pn, pv in (role.get("has") or {}).items():
            yield from tp(pv, ("roles", rname, "has", pn))
    for ename, ent in (data.get("entities") or {}).items():
        own = dict(types.entities.get(ename, {}))
        for pn, pv in (ent.get("properties") or {}).items():
            if pn in PY_KEYWORDS:
                yield ("entities", ename, pn), f"not a name: {pn}"
            if isinstance(pv, dict):
                yield from ex(pv.get("computed"), ("entities", ename, pn, "computed"), own)
            else:
                yield from tp(pv, ("entities", ename, pn))
        for i, f in enumerate(ent.get("always") or []):
            yield from fact(f, ("entities", ename, "always", i), own)
        for i, w in enumerate(ent.get("while") or []):
            yield from ex(w.get("when"), ("entities", ename, "while", i, "when"), own)
            yield from fact(w.get("holds"), ("entities", ename, "while", i, "holds"), own)
        for key in ("may_create", "may_read", "may_update", "may_delete"):
            for i, w in enumerate(ent.get(key) or []):
                if "when" in w:
                    yield from ex(w["when"], ("entities", ename, key, i), {ename: ("entity", ename)})
    for sid, st in (data.get("stories") or {}).items():
        for oname, op in (st.get("operations") or {}).items():
            where = ("stories", sid, oname)
            if "returns" in op and "ensure" in op:
                yield where, f"returns and ensure on one operation: {oname}"
            elif "returns" in op and "also_changes" in op:
                yield where, f"returns and also_changes on one operation: {oname}"
            if "ordered_by" in op and "returns" not in op:
                yield where, f"ordered_by needs returns: {oname}"
            if "also_changes" in op and "ensure" not in op:
                yield where, f"also_changes needs ensure: {oname}"
            inputs = {}
            for pn, pv in (op.get("inputs") or {}).items():
                yield from tp(pv, where + ("inputs", pn))
                inputs[pn] = type_of_phrase(pv) if isinstance(pv, str) else None
            for i, w in enumerate(op.get("who") or []):
                if "when" in w:
                    yield from ex(w["when"], where + ("who", i), inputs)
            for i, r in enumerate(op.get("refuse") or []):
                yield from ex(r.get("when"), where + ("refuse", i), inputs)
            for i, f in enumerate(op.get("ensure") or []):
                yield from fact(f, where + ("ensure", i), inputs, allow_old=True)
            yield from ex(op.get("returns"), where + ("returns",), inputs)
            rt = None
            if isinstance(op.get("returns"), str):
                try:
                    rt = types.type_of(ast.parse(op["returns"], mode="eval").body, inputs)
                except SyntaxError:
                    pass
            item_scope = dict(inputs)
            if is_list(rt) and rt[1]:
                item_scope[rt[1]] = ("entity", rt[1])
            for i, o in enumerate(op.get("ordered_by") or []):
                yield from ex(o, where + ("ordered_by", i), item_scope)
        for title, exm in (st.get("examples") or {}).items():
            givens = {}
            for g in exm.get("given") or []:
                for k, v in g.items():
                    if k != "with" and isinstance(v, str):
                        givens[v] = ("entity", "actor") if k == "actor" else ("entity", k)
            for i, step in enumerate(exm.get("steps") or []):
                where = ("stories", sid, title, i)
                if "when" in step:
                    yield from ex(step["when"].get("call"), where + ("call",), givens, call_slot=True)
                for j, item in enumerate(step.get("then") or []):
                    if isinstance(item, str) and item != "DONE":
                        yield from ex(item, where + ("then", j), givens)


# --- run ---------------------------------------------------------------------

def check(path):
    """returns (source, shape, meaning) problem lists"""
    text = open(path).read()
    is_vc = path.endswith(".vc")
    src, quoting = source_problems(text, is_vc)
    if src:
        return src, [], []
    DUPLICATES.clear()
    try:
        data = yaml.load(text, Loader=Core)
    except Exception as e:
        return [], [f"yaml: {str(e).splitlines()[0]}"], []
    shape = quoting + [f"declared twice: {k} (line {ln})" for k, ln in DUPLICATES]
    shape += schema_problems(VC if is_vc else V, data)
    meaning = []
    if not is_vc and not shape:
        meaning = [f"{'/'.join(map(str, w))}: {p}" for w, p in walk_meaning(data)]
    return [], shape, meaning


if __name__ == "__main__":
    ok = True
    for path in sorted(glob.glob(f"{ROOT}/specs/*.edda") + glob.glob(f"{ROOT}/specs/*.edda.vc")):
        src, shape, meaning = check(path)
        problems = src + shape + meaning
        print(os.path.relpath(path, ROOT), "OK" if not problems else "")
        for e in problems:
            ok = False
            print("   ", e)

    print()
    print("fixtures: which the source, shape and meaning layers catch")
    for folder in sorted(os.listdir(f"{ROOT}/fixtures")):
        for path in sorted(glob.glob(f"{ROOT}/fixtures/{folder}/*")):
            src, shape, meaning = check(path)
            layer = "source" if src else "shape" if shape else "meaning" if meaning else None
            print(f"  {folder}/{os.path.basename(path)}: {'caught by ' + layer if layer else 'passes'}")
            for e in src + shape + meaning:
                print("     ", e)
    sys.exit(0 if ok else 1)
