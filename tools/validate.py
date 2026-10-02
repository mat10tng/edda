#!/usr/bin/env python3
"""Validate every .edda and .edda.vc file: the YAML 1.2 subset at the
source, the quoting rule, the two JSON Schemas, the type-phrase grammar
and the Python expression whitelist of reference section 7. Reports
which fixtures these layers catch. A partial checker: names, statuses,
versions, flags and the examples themselves are not checked here."""
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


def no_dup(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", k.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


Core.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_dup)


# --- the source layer, from the token stream --------------------------------

# where free text or an expression lives, as path patterns over the tree;
# "*" is any key, "#" any list index
QUOTED = {
    "edda": [
        "roles/*/is", "entities/*/is", "epics/*",
        "entities/*/properties/*/computed",
        "entities/*/always/#", "entities/*/always/#/fact", "entities/*/always/#/means",
        "entities/*/while/#/when", "entities/*/while/#/holds",
        "entities/*/while/#/holds/fact", "entities/*/while/#/holds/means",
        "entities/*/may_create/#/when", "entities/*/may_read/#/when",
        "entities/*/may_update/#/when", "entities/*/may_delete/#/when",
        "stories/*/story", "stories/*/i_want", "stories/*/so_that",
        "stories/*/notes/#", "stories/*/questions/#",
        "stories/*/operations/*/is", "stories/*/operations/*/notes/#",
        "stories/*/operations/*/who/#/when",
        "stories/*/operations/*/refuse/#/when", "stories/*/operations/*/refuse/#/reason",
        "stories/*/operations/*/ensure/#", "stories/*/operations/*/ensure/#/fact",
        "stories/*/operations/*/ensure/#/means",
        "stories/*/operations/*/returns", "stories/*/operations/*/ordered_by/#",
        "stories/*/examples/*/notes/#",
        "stories/*/examples/*/steps/#/when/call",
        "stories/*/examples/*/steps/#/then/#", "stories/*/examples/*/steps/#/then/#/refused",
    ],
    "vc": ["#/because"],
}
PLAIN_OK = {"DONE"}


def matches(path, pattern):
    parts = pattern.split("/")
    if len(parts) != len(path):
        return False
    for p, q in zip(parts, path):
        if p == "*" or (p == "#" and isinstance(q, int)) or p == q:
            continue
        return False
    return True


def source_problems(text, is_vc):
    out = []
    if "\t" in text:
        out.append(f"tabs are not allowed (line {text[:text.index(chr(9))].count(chr(10)) + 1})")
    try:
        tokens = list(yaml.scan(text))
    except yaml.YAMLError as e:
        return [f"not YAML: {str(e).splitlines()[0]}"]
    docs = 0
    for t in tokens:
        n = type(t).__name__
        line = t.start_mark.line + 1
        if n == "AnchorToken":
            out.append(f"anchors and aliases are not allowed (line {line})")
        elif n == "TagToken":
            out.append(f"tags are not allowed (line {line})")
        elif n == "DirectiveToken":
            out.append(f"directives are not allowed (line {line})")
        elif n in ("DocumentStartToken", "DocumentEndToken"):
            docs += 1
            if docs > 1:
                out.append(f"one document per file (line {line})")
    if out:
        return out
    patterns = QUOTED["vc" if is_vc else "edda"]
    root = yaml.compose(text, Loader=Core)

    def walk(node, path):
        line = node.start_mark.line + 1
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                if k.value == "<<":
                    out.append(f"the << key is not allowed (line {k.start_mark.line + 1})")
                if not isinstance(k, yaml.ScalarNode):
                    out.append(f"a complex key is not allowed (line {k.start_mark.line + 1})")
                    continue
                walk(v, path + (k.value,))
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                walk(v, path + (i,))
        elif isinstance(node, yaml.ScalarNode):
            if node.style in ("|", ">"):
                if not (is_vc and path[-1:] == ("text",)):
                    out.append(f"block scalars are allowed only for text in .edda.vc (line {line})")
            elif node.style is None and node.value not in PLAIN_OK:
                if any(matches(path, p) for p in patterns):
                    out.append(f"quote the {path[-1] if isinstance(path[-1], str) else path[-2]}; an unquoted # drops the rest of the line (line {line})")

    if root is not None:
        walk(root, ())
    return out


# --- the meaning layer: type phrases and Python expressions ----------------

TYPE_RE = re.compile(
    r"^(DEFAULT (-?\d+(\.\d+)?|\"[^\"]*\"|True|False|[a-z][a-z0-9_]*( \| [a-z][a-z0-9_]*)+)"
    r"|TEXT|NUMBER|TIME|YES_NO|[a-z][a-z0-9_]*( \| [a-z][a-z0-9_]*)+|[a-z][a-z0-9_]*"
    r"|MANY [a-z][a-z0-9_]*(, IN ORDER)?)(, OPTIONAL)?(, DERIVED)?$")

ALLOWED_NODES = {
    "Expression", "Name", "Attribute", "Subscript", "Constant", "List", "Compare",
    "BoolOp", "And", "Or", "UnaryOp", "Not", "USub", "BinOp", "Add", "Sub", "Mult", "Div",
    "IfExp", "ListComp", "GeneratorExp", "comprehension", "Call", "keyword", "Load", "Store", "Slice",
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "In", "NotIn", "Is", "IsNot",
}
FIXED = {"OLD", "ACTOR", "RESULT", "NOW", "TODAY"}
BUILTINS = {"len", "sum", "min", "max", "any", "all", "OLD"}
GEN_ONLY = {"sum", "min", "max", "any", "all"}


def expression_problems(src):
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return [f"not an expression: {src}"]
    out = []
    for node in ast.walk(tree):
        kind = type(node).__name__
        if kind not in ALLOWED_NODES:
            out.append(f"not an expression ({kind}): {src}")
            continue
        if kind == "Compare":
            if len(node.ops) != 1:
                out.append(f"not an expression (comparison chain): {src}")
                continue
            left, right, op = node.left, node.comparators[0], node.ops[0]
            if isinstance(op, (ast.Is, ast.IsNot)) and not (isinstance(right, ast.Constant) and right.value is None):
                out.append(f"not an expression (is only against None): {src}")
            if (isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len"
                    and isinstance(right, ast.Constant) and right.value == 0 and isinstance(op, (ast.Eq, ast.NotEq))):
                out.append(f"write x == [] (not len(x) == 0): {src}")
            if isinstance(right, ast.Constant) and right.value is None and isinstance(op, (ast.Eq, ast.NotEq)):
                out.append(f"write x is None (not x == None): {src}")
            if isinstance(right, ast.Constant) and right.value is True and isinstance(op, ast.Eq):
                out.append(f"write x.approved (not x.approved == True): {src}")
        elif kind == "Call":
            f = node.func
            if isinstance(f, ast.Attribute):
                if f.attr != "startswith":
                    out.append(f"not an expression (method {f.attr}): {src}")
            elif isinstance(f, ast.Name):
                if f.id in GEN_ONLY:
                    if not (len(node.args) == 1 and isinstance(node.args[0], ast.GeneratorExp)):
                        out.append(f"not an expression ({f.id} takes one generator): {src}")
                elif f.id in BUILTINS:
                    pass
                elif not re.fullmatch(r"[a-z][a-z0-9_]*", f.id):
                    out.append(f"not an expression (call to {f.id}): {src}")
            else:
                out.append(f"not an expression (call form): {src}")
        elif kind == "Slice":
            if node.step is not None:
                out.append(f"not an expression (slice step): {src}")
            for b in (node.lower, node.upper):
                if b is not None and not (isinstance(b, ast.Constant) and isinstance(b.value, int)):
                    out.append(f"not an expression (slice bound): {src}")
        elif kind == "Subscript":
            s = node.slice
            if isinstance(s, ast.UnaryOp):
                s = s.operand
            if isinstance(s, ast.BinOp):
                continue   # number - 1: a whole-number expression
            if not (isinstance(s, ast.Slice) or (isinstance(s, ast.Constant) and isinstance(s.value, int))):
                out.append(f"not an expression (index must be a whole number): {src}")
        elif kind == "Constant":
            if not isinstance(node.value, (int, float, str, bool, type(None))):
                out.append(f"not an expression (constant): {src}")
        elif kind == "Name":
            if not (re.fullmatch(r"[a-z][a-z0-9_]*", node.id) or node.id in FIXED or node.id in BUILTINS):
                out.append(f"not an expression (name {node.id}): {src}")
    return out


def walk_meaning(data):
    """yield (path, problem) for type phrases and expressions in a parsed file"""
    def tp(v, where):
        if isinstance(v, str) and not TYPE_RE.match(v):
            yield where, f"not a type phrase: {v}"

    def ex(v, where):
        if isinstance(v, str):
            for p in expression_problems(v):
                yield where, p

    def fact(v, where):
        if isinstance(v, dict):
            yield from ex(v.get("fact"), where + ("fact",))
        else:
            yield from ex(v, where)

    for rname, role in (data.get("roles") or {}).items():
        for pn, pv in (role.get("has") or {}).items():
            yield from tp(pv, ("roles", rname, "has", pn))
    for ename, ent in (data.get("entities") or {}).items():
        for pn, pv in (ent.get("properties") or {}).items():
            if isinstance(pv, dict):
                yield from ex(pv.get("computed"), ("entities", ename, pn, "computed"))
            else:
                yield from tp(pv, ("entities", ename, pn))
        for i, f in enumerate(ent.get("always") or []):
            yield from fact(f, ("entities", ename, "always", i))
        for i, w in enumerate(ent.get("while") or []):
            yield from ex(w.get("when"), ("entities", ename, "while", i, "when"))
            yield from fact(w.get("holds"), ("entities", ename, "while", i, "holds"))
        for key in ("may_create", "may_read", "may_update", "may_delete"):
            for i, w in enumerate(ent.get(key) or []):
                if "when" in w:
                    yield from ex(w["when"], ("entities", ename, key, i))
    for sid, st in (data.get("stories") or {}).items():
        for oname, op in (st.get("operations") or {}).items():
            where = ("stories", sid, oname)
            if "returns" in op and ("ensure" in op or "also_changes" in op):
                yield where, f"returns and ensure on one operation: {oname}"
            if "ordered_by" in op and "returns" not in op:
                yield where, f"ordered_by without returns: {oname}"
            for pn, pv in (op.get("inputs") or {}).items():
                yield from tp(pv, where + ("inputs", pn))
            for i, w in enumerate(op.get("who") or []):
                if "when" in w:
                    yield from ex(w["when"], where + ("who", i))
            for i, r in enumerate(op.get("refuse") or []):
                yield from ex(r.get("when"), where + ("refuse", i))
            for i, f in enumerate(op.get("ensure") or []):
                yield from fact(f, where + ("ensure", i))
            yield from ex(op.get("returns"), where + ("returns",))
            for i, o in enumerate(op.get("ordered_by") or []):
                yield from ex(o, where + ("ordered_by", i))
        for title, exm in (st.get("examples") or {}).items():
            for i, step in enumerate(exm.get("steps") or []):
                where = ("stories", sid, title, i)
                if "when" in step:
                    yield from ex(step["when"].get("call"), where + ("call",))
                for j, item in enumerate(step.get("then") or []):
                    if isinstance(item, str) and item != "DONE":
                        yield from ex(item, where + ("then", j))


# --- run ---------------------------------------------------------------------

def check(path):
    text = open(path).read()
    is_vc = path.endswith(".vc")
    src = source_problems(text, is_vc)
    try:
        data = yaml.load(text, Loader=Core)
    except Exception as e:
        return src, [f"yaml: {str(e).splitlines()[0]}"], []
    v = VC if is_vc else V
    errs = sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))
    shape = [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:90]}" for e in errs]
    meaning = []
    if not is_vc and not shape and not src:
        meaning = [f"{'/'.join(map(str, w))}: {p}" for w, p in walk_meaning(data)]
    return src, shape, meaning


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
