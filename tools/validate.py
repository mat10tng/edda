#!/usr/bin/env python3
"""Validate every .edda and .edda.vc file through the source, shape and
meaning layers of reference section 11: the YAML 1.2 subset, the
quoting rule, both JSON Schemas, the type-phrase grammar, the Python
expression whitelist (7.1), the style rule (7.2) and the operation key
rules. Reports which fixtures each layer catches. A partial checker:
names, statuses, the history layer, flags and the examples themselves
are not checked here."""
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


def core_int(loader, node):
    v = loader.construct_scalar(node)
    if v.startswith("0o"):
        return int(v[2:], 8)
    if v.startswith("0x"):
        return int(v[2:], 16)
    return int(v, 10)


Core.add_constructor("tag:yaml.org,2002:int", core_int)


def no_dup(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", k.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


Core.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_dup)


# --- the source and quoting layers, from the token stream and the tree ------

# where free text or an expression lives, as path patterns over the tree;
# "*" is any key, "#" any list index
TEXT_PATHS = [
    "roles/*/is", "entities/*/is", "epics/*",
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
    returns (source, quoting)"""
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
    if src:
        return src, []
    root = docs[0] if docs else None

    def walk(node, path):
        line = node.start_mark.line + 1
        multiline = node.end_mark.line > node.start_mark.line
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                if not isinstance(k, yaml.ScalarNode):
                    src.append(f"a complex key is not allowed (line {k.start_mark.line + 1})")
                    continue
                if k.value == "<<":
                    src.append(f"the << key is not allowed (line {k.start_mark.line + 1})")
                kpath = path + (k.value,)
                if not is_vc and any_match(kpath, TITLE_PATHS):
                    if k.style != '"':
                        if k.style == "'":
                            src.append(f"single quotes are not allowed; use double quotes (line {k.start_mark.line + 1})")
                        else:
                            quoting.append(f"quote the example title; an unquoted # drops the rest of the line (line {k.start_mark.line + 1})")
                    if k.end_mark.line > k.start_mark.line:
                        src.append(f"an example title is one line (line {k.start_mark.line + 1})")
                walk(v, kpath)
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                walk(v, path + (i,))
        elif isinstance(node, yaml.ScalarNode):
            key = path[-1] if path and isinstance(path[-1], str) else (path[-2] if len(path) > 1 else "")
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


# --- the meaning layer: type phrases and Python expressions ----------------

NAME = r"[a-z][a-z0-9_]*"
TYPE_RE = re.compile(
    rf"^(?:DEFAULT (?:-?\d+(?:\.\d+)?|\"[^\"]*\"|True|False|{NAME}(?: \| {NAME})+)(?:, DERIVED)?"
    rf"|(?:TEXT|NUMBER|INTEGER|TIME|YES_NO|{NAME}(?: \| {NAME})+|{NAME}|MANY {NAME}(?:, IN ORDER)?)(?:, OPTIONAL)?(?:, DERIVED)?)$")


def type_phrase_problems(v):
    if not TYPE_RE.match(v):
        return [f"not a type phrase: {v}"]
    m = re.search(rf"({NAME}(?: \| {NAME})+)", v)
    if m:
        vals = m.group(1).split(" | ")
        if len(set(vals)) != len(vals):
            return [f"not a type phrase (repeated value): {v}"]
    return []


ALLOWED_NODES = {
    "Expression", "Name", "Attribute", "Subscript", "Constant", "List", "Compare",
    "BoolOp", "And", "Or", "UnaryOp", "Not", "USub", "BinOp", "Add", "Sub", "Mult", "Div",
    "IfExp", "ListComp", "GeneratorExp", "comprehension", "Call", "keyword", "Load", "Store", "Slice",
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "In", "NotIn", "Is", "IsNot",
}
FIXED = {"OLD", "ACTOR", "RESULT", "NOW", "TODAY"}
ONE_ARG = {"len", "OLD"}
GEN_ONLY = {"sum", "min", "max", "any", "all"}


def is_integer_valued(n):
    """an INTEGER-valued expression: a whole-number constant, a name, a
    path, an index, or those with + - * (section 7.1)"""
    if isinstance(n, ast.Constant):
        return isinstance(n.value, int) and not isinstance(n.value, bool)
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
        return is_integer_valued(n.operand)
    if isinstance(n, (ast.Name, ast.Attribute, ast.Subscript)):
        return True
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "len":
        return True
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult)):
        return is_integer_valued(n.left) and is_integer_valued(n.right)
    return False


def src_of(node, src):
    return ast.get_source_segment(src, node) or "..."


def expression_problems(src, allow_old=False):
    """problems of one expression: not_an_expression, second_way, type_mismatch"""
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return [f"not an expression: {src}"]
    out = []
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def second(one, other):
        out.append(f"write {one} (not {other}): {src}")

    for node in ast.walk(tree):
        kind = type(node).__name__
        if kind not in ALLOWED_NODES:
            out.append(f"not an expression ({kind}): {src}")
            continue
        if kind == "Compare":
            if len(node.ops) != 1:
                second("a <= x and x <= b", "a comparison chain")
                continue
            left, right, op = node.left, node.comparators[0], node.ops[0]
            if isinstance(op, (ast.Is, ast.IsNot)) and not (isinstance(right, ast.Constant) and right.value is None):
                out.append(f"not an expression (is only against None): {src}")
            neg = isinstance(op, ast.NotEq)
            # len(x) == 0, len(x) != 0, len(x) > 0
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len" \
                    and isinstance(right, ast.Constant) and right.value == 0 and not isinstance(right.value, bool):
                x = src_of(left.args[0], src) if left.args else "x"
                if isinstance(op, ast.Eq):
                    second(f"{x} == []", f"len({x}) == 0")
                elif isinstance(op, (ast.NotEq, ast.Gt)):
                    second(f"{x} != []", src_of(node, src))
            # x == None, None == x
            for a, b in ((left, right), (right, left)):
                if isinstance(b, ast.Constant) and b.value is None and isinstance(op, (ast.Eq, ast.NotEq)):
                    x = src_of(a, src)
                    second(f"{x} is {'not ' if neg else ''}None", src_of(node, src))
                    break
            # x == True / False, True == x
            for a, b in ((left, right), (right, left)):
                if isinstance(b, ast.Constant) and isinstance(b.value, bool) and isinstance(op, (ast.Eq, ast.NotEq)):
                    x = src_of(a, src)
                    holds = b.value != neg
                    second(x if holds else f"not {x}", src_of(node, src))
                    break
            # x[:n] == t
            if isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Slice) and left.slice.lower is None \
                    and isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(right, ast.Constant) and isinstance(right.value, str):
                second(f"{src_of(left.value, src)}.startswith({src_of(right, src)})", src_of(node, src))
        elif kind == "Call":
            f = node.func
            if isinstance(f, ast.Attribute):
                if f.attr != "startswith":
                    out.append(f"not an expression (method {f.attr}): {src}")
                elif len(node.args) != 1 or node.keywords:
                    out.append(f"startswith expects one argument: {src}")
            elif isinstance(f, ast.Name):
                if f.id in GEN_ONLY:
                    if not (len(node.args) == 1 and isinstance(node.args[0], ast.GeneratorExp) and not node.keywords):
                        out.append(f"{f.id} expects one generator: {src}")
                    elif f.id == "sum" and isinstance(node.args[0].elt, ast.Constant) and node.args[0].elt.value == 1:
                        second("len(x)", "sum(1 for ...)")
                elif f.id in ONE_ARG:
                    if len(node.args) != 1 or node.keywords:
                        out.append(f"{f.id} expects one argument: {src}")
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
        elif kind == "Slice":
            if node.step is not None:
                out.append(f"not an expression (slice step): {src}")
            for b in (node.lower, node.upper):
                if b is not None and not is_integer_valued(b):
                    out.append(f"a slice bound expects an INTEGER: {src}")
        elif kind == "Subscript":
            s = node.slice
            if isinstance(s, ast.Slice):
                pass
            elif not is_integer_valued(s):
                out.append(f"an index expects an INTEGER: {src}")
            elif isinstance(s, ast.BinOp) and isinstance(s.op, ast.Sub) and isinstance(s.left, ast.Call) \
                    and isinstance(s.left.func, ast.Name) and s.left.func.id == "len" \
                    and isinstance(s.right, ast.Constant) and s.right.value == 1:
                second(f"{src_of(node.value, src)}[-1]", src_of(node, src))
        elif kind == "Constant":
            if not isinstance(node.value, (int, float, str, bool, type(None))):
                out.append(f"not an expression (constant): {src}")
        elif kind == "Name":
            if not (re.fullmatch(NAME, node.id) or node.id in FIXED or node.id in ONE_ARG or node.id in GEN_ONLY):
                out.append(f"not an expression (name {node.id}): {src}")
    return out


def walk_meaning(data):
    """yield (path, problem) for type phrases, expressions and operation keys"""
    def tp(v, where):
        if isinstance(v, str):
            for p in type_phrase_problems(v):
                yield where, p

    def ex(v, where, allow_old=False):
        if isinstance(v, str):
            if v == "":
                yield where, "an expression was expected, nothing was given"
                return
            for p in expression_problems(v, allow_old):
                yield where, p

    def fact(v, where, allow_old=False):
        if isinstance(v, dict):
            yield from ex(v.get("fact"), where + ("fact",), allow_old)
        else:
            yield from ex(v, where, allow_old)

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
            if "returns" in op and "ensure" in op:
                yield where, f"returns and ensure on one operation: {oname}"
            elif "returns" in op and "also_changes" in op:
                yield where, f"returns and also_changes on one operation: {oname}"
            if "ordered_by" in op and "returns" not in op:
                yield where, f"ordered_by needs returns: {oname}"
            if "also_changes" in op and "ensure" not in op:
                yield where, f"also_changes needs ensure: {oname}"
            for pn, pv in (op.get("inputs") or {}).items():
                yield from tp(pv, where + ("inputs", pn))
            for i, w in enumerate(op.get("who") or []):
                if "when" in w:
                    yield from ex(w["when"], where + ("who", i))
            for i, r in enumerate(op.get("refuse") or []):
                yield from ex(r.get("when"), where + ("refuse", i))
            for i, f in enumerate(op.get("ensure") or []):
                yield from fact(f, where + ("ensure", i), allow_old=True)
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
    """returns (source, shape, meaning) problem lists"""
    text = open(path).read()
    is_vc = path.endswith(".vc")
    src, quoting = source_problems(text, is_vc)
    if src:
        return src, [], []
    try:
        data = yaml.load(text, Loader=Core)
    except Exception as e:
        return [], [f"yaml: {str(e).splitlines()[0]}"], []
    v = VC if is_vc else V
    errs = sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path))
    shape = quoting + [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:90]}" for e in errs]
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
