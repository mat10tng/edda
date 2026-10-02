#!/usr/bin/env python3
"""Check every .edda and .edda.vc file through the layers of reference
section 11: the YAML 1.2 subset and the quoting rule (source), both
JSON Schemas mapped to rule names and source lines plus duplicate
names (shape), names resolved across the files of one folder, the
type-phrase grammar, the Python expression whitelist (7.1) with types
from literals and declarations, operation signatures, ordering, and the
style rule (7.2) under its equivalences (meaning), and the version
sequence, the pins and the snapshots of a .edda.vc (history). A
partial checker: the flags and the running of examples are not here.
Each folder (specs/, one fixture folder) is one project."""
import ast, copy, glob, json, os, re, sys
import yaml
from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = json.load(open(f"{ROOT}/language/schema.json"))
VC_SCHEMA = json.load(open(f"{ROOT}/language/vc-schema.json"))
Draft202012Validator.check_schema(SCHEMA)
Draft202012Validator.check_schema(VC_SCHEMA)
V = Draft202012Validator(SCHEMA)
VC = Draft202012Validator(VC_SCHEMA)

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

DUPLICATES = []   # (key, line) found by the last load, every one


def dup_mapping(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            DUPLICATES.append((key, k.start_mark.line + 1))
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


Core.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, dup_mapping)


# --- slots, by path pattern ------------------------------------------------

TEXT_PATHS = [
    "roles/*/is", "entities/*/is", "epics/*", "entities/*/wording/*/*/*",
    "stories/*/story", "stories/*/i_want", "stories/*/so_that",
    "stories/*/notes/#", "stories/*/questions/#",
    "stories/*/operations/*/is", "stories/*/operations/*/notes/#",
    "stories/*/operations/*/refuse/#/reason", "stories/*/operations/*/ensure/#/means",
    "entities/*/always/#/means", "entities/*/while/#/holds/means",
    "stories/*/examples/*/notes/#",
    "stories/*/examples/*/steps/#/then/#/refused",
    "stories/*/examples/*/steps/#/when/at",
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
    "stories/*/operations/*/also_changes/#",
    "stories/*/examples/*/steps/#/when/call",
    "stories/*/examples/*/steps/#/then/#",
]
TYPE_PATHS = ["roles/*/has/*", "entities/*/properties/*", "stories/*/operations/*/inputs/*"]
NAME_PATHS = [
    "stories/*/about", "stories/*/as_a", "stories/*/epic", "stories/*/tags/#",
    "roles/*/includes/#", "entities/*/part_of",
    "entities/*/may_create/#/role", "entities/*/may_read/#/role",
    "entities/*/may_update/#/role", "entities/*/may_delete/#/role",
    "entities/*/may_change/*/*/#",
    "stories/*/operations/*/who/#/role",
    "stories/*/examples/*/given/#/*",
    "stories/*/examples/*/given/#/with/roles/#", "stories/*/examples/*/given/#/with/fixture",
    "stories/*/examples/*/steps/#/when/actor",
]
TITLE_PATHS = ["stories/*/examples/*"]
VC_TEXT_PATHS = ["#/because", "#/approved_at"]
VC_NAME_PATHS = ["#/story", "#/entity", "#/role", "#/approved_by", "#/pins/#/entity", "#/pins/#/role"]


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


def mapping(x):
    return x if isinstance(x, dict) else {}


def listing(x):
    return x if isinstance(x, list) else []


# --- the source layer and the quoting rule ----------------------------------

def indentation_problems(text):
    out, prev = [], 0
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ind = len(line) - len(line.lstrip(" "))
        if ind % 2 or ind > prev + 2:
            out.append(("yaml_feature", n, "indentation must be even and at most two deeper than the line before"))
        rest = line.lstrip(" ")
        while rest.startswith("- "):      # a list dash counts as two for the next line
            ind += 2
            rest = rest[2:]
        prev = ind
    return out


class Source:
    """one file read at the source: source problems, the quoting rule's
    problems (shape layer), source marks per path, scalar styles per path"""

    def __init__(self, text, is_vc):
        self.src, self.style, self.marks, self.styles, self.raw = [], [], {}, {}, {}
        self.duplicates = []
        self.is_vc = is_vc
        if "\t" in text:
            self.src.append(("yaml_feature", text[:text.index("\t")].count("\n") + 1, "tabs are not allowed"))
        try:
            tokens = list(yaml.scan(text))
        except yaml.YAMLError as e:
            self.src.append(("not_yaml", getattr(getattr(e, "problem_mark", None), "line", 0) + 1,
                             f"not YAML: {str(e).splitlines()[0]}"))
            return
        for t in tokens:
            n = type(t).__name__
            line = t.start_mark.line + 1
            if n == "AnchorToken":
                self.src.append(("yaml_feature", line, "anchors and aliases are not allowed"))
            elif n == "TagToken":
                self.src.append(("yaml_feature", line, "tags are not allowed"))
            elif n == "DirectiveToken":
                self.src.append(("yaml_feature", line, "directives are not allowed"))
        try:
            docs = list(yaml.compose_all(text, Loader=Core))
        except yaml.YAMLError as e:
            self.src.append(("not_yaml", getattr(getattr(e, "problem_mark", None), "line", 0) + 1,
                             f"not YAML: {str(e).splitlines()[0]}"))
            return
        if len(docs) > 1:
            self.src.append(("yaml_feature", docs[1].start_mark.line + 1, "one document per file"))
        self.src += indentation_problems(text)
        self.seen = set()
        if docs:
            self.marks[()] = (1, 1)
            self.walk(docs[0], ())

    def walk(self, node, path):
        if id(node) in self.seen:       # an alias back to an anchor: reported once, at the anchor
            return
        self.seen.add(id(node))
        line = node.start_mark.line + 1
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                kline = k.start_mark.line + 1
                if not isinstance(k, yaml.ScalarNode):
                    self.src.append(("yaml_feature", kline, "a complex key is not allowed"))
                    continue
                if k.value == "<<":
                    self.src.append(("yaml_feature", kline, "the << key is not allowed"))
                kpath = path + (k.value,)
                self.marks[kpath] = (kline, v.start_mark.line + 1)
                is_title = not self.is_vc and any_match(kpath, TITLE_PATHS)
                if k.style == "'":
                    self.src.append(("yaml_feature", kline, "single quotes are not allowed; use double quotes"))
                elif k.style in ("|", ">"):
                    self.src.append(("yaml_feature", kline, "a key is one plain line"))
                elif is_title:
                    if k.style != '"':
                        self.style.append(("unquoted_text", kline, "quote the example title; an unquoted # drops the rest of the line"))
                    if k.end_mark.line > k.start_mark.line:
                        self.src.append(("yaml_feature", kline, "an example title is one line"))
                elif k.style == '"':
                    self.src.append(("yaml_feature", kline, "a key is plain, not quoted"))
                self.walk(v, kpath)
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                self.marks[path + (i,)] = (v.start_mark.line + 1, v.start_mark.line + 1)
                self.walk(v, path + (i,))
        elif isinstance(node, yaml.ScalarNode):
            self.styles[path] = node.style
            self.raw[path] = node.value          # as written, for messages
            key = path[-1] if path and isinstance(path[-1], str) else (path[-2] if len(path) > 1 else "")
            multiline = node.end_mark.line > node.start_mark.line
            if node.style == "'":
                self.src.append(("yaml_feature", line, "single quotes are not allowed; use double quotes"))
                return
            if node.style == ">":
                self.src.append(("yaml_feature", line, "folded scalars are not allowed"))
                return
            if node.style == "|":
                if not (self.is_vc and path[-1:] == ("text",)):
                    self.src.append(("yaml_feature", line, "block scalars are allowed only for text in .edda.vc"))
                return
            if self.is_vc:
                if node.style is None and any_match(path, VC_TEXT_PATHS):
                    self.style.append(("unquoted_text", line, f"quote the {key}; an unquoted # drops the rest of the line"))
                elif node.style == '"' and any_match(path, VC_NAME_PATHS):
                    self.style.append(("bad_name", line, f'not a name: "{node.value}" (a name is plain)'))
                return
            is_expr = any_match(path, EXPR_PATHS)
            is_type = any_match(path, TYPE_PATHS)
            is_text = any_match(path, TEXT_PATHS)
            is_name = any_match(path, NAME_PATHS) and path[-1] != "with"
            if is_expr and node.value == "DONE" and node.style is None:
                if not (len(path) >= 2 and path[-2] == "then" and path[-1] == 0):
                    self.src.append(("yaml_feature", line, "DONE is allowed only as the first then item"))
                return
            if is_expr and node.value == "DONE" and node.style == '"' and len(path) >= 2 and path[-2] == "then" and path[-1] == 0:
                self.style.append(("bad_name", line, 'not a name: "DONE" (a name is plain)'))
                return
            if (is_expr or is_text) and node.style is None:
                self.style.append(("unquoted_text", line, f"quote the {key}; an unquoted # drops the rest of the line"))
            if is_name and node.style == '"':
                self.style.append(("bad_name", line, f'not a name: "{node.value}" (a name is plain)'))
            if (is_expr or is_type) and multiline:
                self.src.append(("yaml_feature", line, "an expression or type phrase is one line"))

    def line(self, path, key=True):
        """the source line of a path: its key line, or its value line"""
        while path:
            if path in self.marks:
                return self.marks[path][0 if key else 1]
            path = path[:-1]
        return 1


# --- the shape layer: from the schema to a rule ------------------------------

ITEM = {"ensure": "fact", "always": "fact", "refuse": "refusal", "given": "given", "steps": "step",
        "then": "item", "notes": "note", "questions": "question", "who": "who-line",
        "may_create": "who-line", "may_read": "who-line", "may_update": "who-line", "may_delete": "who-line",
        "pins": "pin", "ordered_by": "expression", "also_changes": "path", "while": "rule",
        "tags": "tag", "includes": "role", "roles": "role"}
COLLECTION = {"roles": "role", "entities": "entity", "stories": "story", "operations": "operation",
              "examples": "example", "properties": "property", "inputs": "input", "has": "property"}
KIND_WORD = {"object": "mapping", "array": "list", "string": "text", "integer": "number",
             "number": "number", "boolean": "yes/no", "null": "value"}


def block_name(path, is_vc):
    if not path:
        return "file"
    last = path[-1]
    if isinstance(last, int):
        if len(path) == 1 and is_vc:
            return f"entry {last + 1}"
        return f"{ITEM.get(path[-2], path[-2])} {last + 1}"
    if len(path) >= 2 and path[-2] in COLLECTION:
        return f"{COLLECTION[path[-2]]} {last}"
    return last


def key_name(path):
    return path[-1] if path and isinstance(path[-1], str) else (path[-2] if len(path) > 1 else "file")


def resolve(frag, root):
    while isinstance(frag, dict) and "$ref" in frag:
        frag = root["$defs"][frag["$ref"].split("/")[-1]]
    return frag


def yaml_kind(v):
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "array"
    if isinstance(v, str):
        return "string"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    return "null"


def schema_problems(validator, root, data, source):
    """jsonschema errors mapped to the rules of reference section 11, each
    with a source line; a missing key is suppressed in the block that
    has an unknown key"""
    out, unknown_in = [], set()
    is_vc = validator is VC

    def add(rule, path, msg, key=True):
        out.append((rule, path, source.line(path, key), msg))

    def adapt(err, path):
        v = err.validator
        key = key_name(path)
        if "propertyNames" in err.schema_path:            # a key that is no name, whatever failed
            raw = next((k[-1] for k in source.marks if k[:-1] == path and str(k[-1]).lower() == str(err.instance).lower()), err.instance)
            add("bad_name", path + (raw,), f"not a name: {raw}")
            return
        if v in ("anyOf", "oneOf"):
            branches = [resolve(b, root) for b in err.validator_value]
            kinds = [b.get("type") or (yaml_kind(b["const"]) if "const" in b else None) for b in branches]
            if all(k is None for k in kinds):
                names = [", ".join(b.get("required", [])) for b in branches]
                add("wrong_type", path, f"{block_name(path, is_vc)} must name one of {' or '.join(names)}")
                return
            inst = yaml_kind(err.instance)
            idx = [i for i, k in enumerate(kinds) if k == inst or (k == "number" and inst == "integer")]
            if not idx:
                if kinds == ["string", "number", "boolean", "array"]:
                    add("wrong_type", path, f"{key} must be a number, text, yes/no, name or a flat list of those", key=False)
                else:
                    kind_words = [KIND_WORD.get(k, k) for k in kinds if k]
                    add("wrong_type", path, f"{key} must be a {' or a '.join(dict.fromkeys(kind_words))}", key=False)
                return
            found = False
            for c in err.context:
                if c.schema_path[0] in idx:
                    found = True
                    adapt(c, path + tuple(c.relative_path))
            if not found:
                add("wrong_type", path, f"{key} must be a {KIND_WORD.get(inst, inst)}", key=False)
            return
        if v == "additionalProperties":
            extras = [k for k in err.instance if k not in err.schema.get("properties", {})]
            unknown_in.add(path)
            for k in extras:
                add("unknown_key", path + (k,), f"unknown key: {k}")
            return
        if v == "required":
            m = re.match(r"'(.+)' is a required property", err.message)
            add("missing_key", path, f"{block_name(path, is_vc)} needs {m.group(1) if m else '?'}:")
            return
        if v == "type":
            if err.validator_value == "array":
                add("not_a_list", path, f"{key} must be a list, one {ITEM.get(key, 'item')} per line")
            else:
                add("wrong_type", path, f"{key} must be a {KIND_WORD.get(err.validator_value, err.validator_value)}", key=False)
            return
        if v == "minItems":
            add("wrong_type", path, f"{key} must be a list with at least one {ITEM.get(key, 'item')}")
            return
        if v in ("minProperties", "maxProperties"):
            add("wrong_type", path, "given must name exactly one thing besides with")
            return
        if v == "minLength":
            add("wrong_type", path, f"{key} expects a text, nothing was given", key=False)
            return
        if v == "const":
            if err.validator_value == "DONE":
                add("wrong_type", path, f"{key} must start with DONE or refused", key=False)
            else:
                add("wrong_type", path, f"{key} must be {err.validator_value}", key=False)
            return
        if v == "not":
            add("wrong_type", path, f"{key} expects an expression, not DONE", key=False)
            return
        if v == "propertyNames":
            name = err.context[0].instance if err.context else "?"
            add("bad_name", path + (name,), f"not a name: {name}")
            return
        if v in ("pattern", "enum"):
            if "propertyNames" in err.schema_path:        # a key failed the name pattern
                add("bad_name", path + (err.instance,), f"not a name: {err.instance}")
            else:
                add("bad_name", path, f"not a name: {err.instance}", key=False)
            return
        if err.context:
            for c in err.context:
                adapt(c, path + tuple(c.relative_path))
        else:
            add("wrong_type", path, f"{key} must be a {KIND_WORD.get(yaml_kind(err.instance), 'value')}", key=False)

    for err in validator.iter_errors(data):
        adapt(err, tuple(err.absolute_path))
    out = [p for p in out if not (p[0] == "missing_key" and p[1] in unknown_in)]
    return list(dict.fromkeys((rule, line, msg) for rule, _, line, msg in out))


def shape_extra(data, source=None):
    """shape-layer checks beside the schema: a given name used twice, has:
    redeclaring name or roles, a role-list item that is no name, a Python
    keyword as a choice value; yields (rule, path, message, at_key)"""
    out = []

    def phrase(v, path):
        if isinstance(v, str) and " | " in v:
            core = re.sub(r"^DEFAULT ", "", re.sub(r"(, (OPTIONAL|DERIVED))+$", "", v))
            for x in core.split(" | "):
                if x in PY_KEYWORDS:
                    out.append(("bad_name", path, f"not a name: {x}", False))

    for rname, role in mapping(mapping(data).get("roles")).items():
        for p, v in mapping(mapping(role).get("has")).items():
            if p in ("name", "roles"):
                out.append(("declared_twice", ("roles", rname, "has", p), f"declared twice: {p}", True))
            phrase(v, ("roles", rname, "has", p))
    for ename, ent in mapping(mapping(data).get("entities")).items():
        for p, v in mapping(mapping(ent).get("properties")).items():
            phrase(v, ("entities", ename, "properties", p))
    for sid, st in mapping(mapping(data).get("stories")).items():
        for oname, op in mapping(mapping(st).get("operations")).items():
            for n, v in mapping(mapping(op).get("inputs")).items():
                phrase(v, ("stories", sid, "operations", oname, "inputs", n))
        for title, exm in mapping(mapping(st).get("examples")).items():
            seen = set()
            for i, g in enumerate(listing(mapping(exm).get("given"))):
                if not isinstance(g, dict):
                    continue
                gw = ("stories", sid, "examples", title, "given", i)
                for k, v in g.items():
                    if k != "with" and isinstance(v, str):
                        if v in seen:
                            out.append(("declared_twice", gw, f"declared twice: {v}", True))
                        seen.add(v)
                if "actor" in g:
                    rs = mapping(g.get("with")).get("roles")
                    if rs is not None and not isinstance(rs, list):
                        out.append(("not_a_list", gw + ("with", "roles"), "roles must be a list, one role per line", True))
                    for j, r in enumerate(listing(rs)):
                        if not (isinstance(r, str) and re.fullmatch(NAME, r) and r not in PY_KEYWORDS):
                            raw = source.raw.get(gw + ("with", "roles", j), r) if source else r
                            out.append(("bad_name", gw + ("with", "roles", j), f"not a name: {raw}", False))
    return out


# --- types -----------------------------------------------------------------
# a type is "INTEGER", "NUMBER", "TEXT", "TIME", "YES_NO", "NONE", "ANY"
# (the element of an empty list), ("choice", values or None),
# ("list", element type, ordered), ("entity", name), ("actor", spec),
# ("either", alternatives), or None when unknown

STR_LIT = r'"(?:[^"\\]|\\.)*"'
TYPE_RE = re.compile(
    rf"(?:DEFAULT (?:-?[0-9]+(?:\.[0-9]+)?|{STR_LIT}|True|False|(?P<dchoice>{NAME}(?: \| {NAME})+))(?:, DERIVED)?"
    rf"|(?:TEXT|NUMBER|INTEGER|TIME|YES_NO|(?P<choice>{NAME}(?: \| {NAME})+)|(?P<ref>{NAME})|MANY (?P<many>{NAME})(?P<ordered>, IN ORDER)?)(?P<optional>, OPTIONAL)?(?:, DERIVED)?)")
SCALARS = ("TEXT", "NUMBER", "INTEGER", "TIME", "YES_NO")


def type_phrase_problems(v):
    m = TYPE_RE.fullmatch(v)
    if not m:
        return [("bad_type_phrase", f"not a type phrase: {v}")]
    choice = m.group("dchoice") or m.group("choice")
    if choice:
        vals = choice.split(" | ")
        if len(set(vals)) != len(vals):
            return [("bad_type_phrase", f"not a type phrase (repeated value): {v}")]
    return []


def phrase_entity(v):
    """the entity a type phrase refers to, or None"""
    m = TYPE_RE.fullmatch(v or "")
    return (m.group("ref") or m.group("many")) if m else None


def type_of_phrase(v):
    if not isinstance(v, str):
        return None
    m = TYPE_RE.fullmatch(v)
    if not m:
        return None
    if m.group("dchoice"):
        t = ("choice", tuple(m.group("dchoice").split(" | ")))
    elif m.group("choice"):
        t = ("choice", tuple(m.group("choice").split(" | ")))
    elif m.group("many"):
        t = ("list", ("entity", m.group("many")), bool(m.group("ordered")))
    elif m.group("ref"):
        t = ("entity", m.group("ref"))
    else:
        core = re.sub(r", (OPTIONAL|DERIVED)$", "", re.sub(r", (OPTIONAL|DERIVED)$", "", v))
        if core.startswith("DEFAULT "):
            lit = core[8:]
            if re.fullmatch(r"-?[0-9]+", lit):
                t = "INTEGER"
            elif re.fullmatch(r"-?[0-9]+\.[0-9]+", lit):
                t = "NUMBER"
            elif lit in ("True", "False"):
                t = "YES_NO"
            else:
                t = "TEXT"
        else:
            t = core if core in SCALARS else None
    if t is not None and m.group("optional"):
        return ("either", frozenset({t, "NONE"}))
    return t


def is_list(t):
    return isinstance(t, tuple) and t[0] == "list"


def int_lit(node):
    """the value of a signed whole-number literal (3, -1), or None"""
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) \
            and type(node.operand.value) is int:
        return -node.operand.value
    return None


LIT = ("lit", "TEXT")           # a text literal's position: it may stand for a time
LIT_NODE = ast.Constant("")     # the node such a position is given, so is_time_literal holds


def unlit(p):
    """a position's type as a plain type"""
    if p == LIT:
        return "TEXT"
    if is_either(p):
        alts_ = frozenset(unlit(a) for a in p[1])
        return next(iter(alts_)) if len(alts_) == 1 else ("either", alts_)
    return p


def positions_of(t):
    """the element types of a list by position, when known; a text literal's
    position is LIT"""
    return t[3] if is_list(t) and len(t) > 3 else None


def typed_positions(t):
    """positions_of as (node, type) leaves per position, for pair() and fits();
    a literal position keeps a literal node"""
    ps = positions_of(t)
    if ps is None:
        return None
    return [[(LIT_NODE if a == LIT else None, unlit(a)) for a in alts(x) if a != "NONE"] or [(None, "NONE")] for x in ps]


def ordered(t):
    return is_list(t) and len(t) > 2 and bool(t[2])


def is_entity(t):
    return isinstance(t, tuple) and t[0] == "entity"


def is_actor(t):
    return isinstance(t, tuple) and t[0] == "actor"


def is_choice(t):
    return isinstance(t, tuple) and t[0] == "choice"


def is_either(t):
    return isinstance(t, tuple) and t[0] == "either"


def choice_of(t):
    """the choice a value of type t is, NONE aside, or None"""
    rest = [a for a in alts(t) if a != "NONE"]
    return rest[0] if len(rest) == 1 and is_choice(rest[0]) else None


def no_none(t):
    """the type without its NONE alternative; None when nothing is left or known"""
    if t is None:
        return None
    rest = [a for a in alts(t) if a != "NONE"]
    return None if not rest else (rest[0] if len(rest) == 1 else ("either", frozenset(rest)))


def alts(t):
    """the alternatives a value of type t may be"""
    return list(t[1]) if is_either(t) else [t]


def all_alts(t, pred):
    """does every alternative satisfy pred; an unknown type does"""
    return t is None or all(a is None or pred(a) for a in alts(t))


def as_list(t):
    """the list type a value of type t certainly is, or None"""
    if is_list(t):
        return t
    if is_either(t) and all(is_list(a) for a in t[1]):
        e, o = None, True
        for i, a in enumerate(t[1]):
            e = a[1] if i == 0 else unify(e, a[1])
            o = o and ordered(a)
        return ("list", e, o)
    return None


def unify(a, b):
    """the type of a value that is either a or b"""
    if a == b:
        return a
    if a is None or b is None:
        return None
    if a == "ANY":
        return b
    if b == "ANY":
        return a
    if {a, b} == {"INTEGER", "NUMBER"}:
        return "NUMBER"
    if is_list(a) and is_list(b):
        o = ordered(a) and ordered(b)
        if a[1] is None or b[1] is None:
            return ("list", None, o) if a[1] is None and b[1] is None else None
        e = unify(a[1], b[1])
        if e == a[1] or e == b[1]:     # one element type covers the other
            pa, pb = positions_of(a), positions_of(b)
            if pa is not None and pb is not None and len(pa) == len(pb):
                ps = tuple(unify(x, y) for x, y in zip(pa, pb))
                if all(x is not None for x in ps):
                    return ("list", e, o, ps)
            return ("list", e, o)
        return ("either", frozenset({a, b}))
    if is_choice(a) and is_choice(b):
        if a[1] is None or b[1] is None:
            return ("choice", None)
        return ("choice", tuple(dict.fromkeys(a[1] + b[1])))
    out = set()
    for t in (a, b):
        out |= set(t[1]) if is_either(t) else {t}
    return ("either", frozenset(out))


def unify_all(types):
    t = None
    for i, x in enumerate(types):
        t = x if i == 0 else unify(t, x)
    return t


def unknowns(t):
    """how many unresolved parts a type has"""
    if t is None:
        return 1
    if is_list(t):
        return unknowns(t[1]) if t[1] != "ANY" else 0
    if is_either(t):
        return sum(unknowns(a) for a in t[1])
    return 0


def is_time_literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.IfExp):
        return is_time_literal(node.body) and is_time_literal(node.orelse)
    return False


def compatible(given, expected, optional=False, node=None):
    """may a value of type given stand where expected is declared"""
    if given is None or expected is None or given == "ANY":
        return True
    if given == "NONE":
        return optional or expected == "NONE"
    if is_either(expected):
        return any(compatible(given, e, optional or "NONE" in expected[1], node) for e in expected[1])
    if is_either(given):
        if expected == "TIME" and is_time_literal(node):
            return True
        return all(compatible(g, expected, optional) for g in given[1])
    if given == expected:
        return True
    if expected == "TIME" and is_time_literal(node):
        return True       # a time literal is read as a TIME where a TIME is expected
    if given == "INTEGER" and expected == "NUMBER":
        return True
    if is_choice(given) and is_choice(expected):
        return given[1] is None or expected[1] is None or set(given[1]) <= set(expected[1])
    if is_actor(given) and is_actor(expected):
        return True
    if is_list(given) and is_list(expected):
        if ordered(expected) and not ordered(given):
            return False
        return given[1] is None or compatible(given[1], expected[1])
    return False


def words(t):
    if t is None or t == "ANY":
        return "a value"
    if t == "NONE":
        return "nothing"
    if isinstance(t, str):
        return ("an " if t[0] in "AEIOU" else "a ") + t
    if is_choice(t):
        return "a choice value"
    if is_actor(t):
        return "an actor"
    if is_either(t):
        return " or ".join(sorted(words(a) for a in t[1]))
    if is_list(t):
        return ("MANY " + (t[1][1] if is_entity(t[1]) else str(t[1]))) + (", IN ORDER" if ordered(t) else "")
    return ("an " if t[1][0] in "aeiou" else "a ") + t[1]


# --- the project: declarations across the files of one folder ---------------

class Project:
    def __init__(self, files, histories=()):
        """files: list of (stem, data) for every .edda that passed the shape layer;
        histories: (stem, entries) of every .edda.vc that did"""
        self.entities, self.roles, self.operations, self.epics, self.stories = {}, {}, {}, set(), {}
        self.files = {stem for stem, _ in files}
        self.dups = {}            # stem -> [(path, name)]: a name declared twice across the project
        self.role_order = []
        for stem, data in sorted(files, key=lambda f: f[0]):
            for section, block in mapping(data).items():     # in source order, so the second is reported
                if section == "roles":
                    for rname, role in mapping(block).items():
                        if rname in self.roles or rname in self.entities:
                            self.dups.setdefault(stem, []).append((("roles", rname), rname))
                            continue
                        has = {p: type_of_phrase(v) for p, v in mapping(mapping(role).get("has")).items()}
                        self.roles[rname] = {"has": has, "includes": listing(mapping(role).get("includes")), "file": stem}
                        self.role_order.append(rname)
                elif section == "entities":
                    for ename, ent in mapping(block).items():
                        if ename in self.entities or ename in self.roles:
                            self.dups.setdefault(stem, []).append((("entities", ename), ename))
                            continue
                        props, derived, computed = {}, set(), {}
                        for p, v in mapping(mapping(ent).get("properties")).items():
                            if isinstance(v, dict):
                                props[p] = None
                                computed[p] = v.get("computed")
                            else:
                                props[p] = type_of_phrase(v)
                                if isinstance(v, str) and v.endswith(", DERIVED"):
                                    derived.add(p)
                        may = {}
                        for key in ("may_create", "may_read", "may_update", "may_delete"):
                            may[key] = [w.get("role") for w in listing(mapping(ent).get(key)) if isinstance(w, dict)]
                        self.entities[ename] = {"props": props, "derived": derived, "computed": computed, "may": may,
                                                "file": stem, "part_of": mapping(ent).get("part_of")}
                elif section == "epics":
                    self.epics.update(mapping(block).keys())
                elif section == "stories":
                    for sid, st in mapping(block).items():
                        if sid in self.stories:
                            self.dups.setdefault(stem, []).append((("stories", sid), sid))
                            continue
                        self.stories[sid] = stem
                        for oname, op in mapping(mapping(st).get("operations")).items():
                            if oname in self.operations:
                                self.dups.setdefault(stem, []).append((("stories", sid, "operations", oname), oname))
                                continue
                            inputs = []
                            for n, v in mapping(mapping(op).get("inputs")).items():
                                inputs.append((n, type_of_phrase(v), isinstance(v, str) and ", OPTIONAL" in v))
                            who = [w.get("role") for w in listing(mapping(op).get("who")) if isinstance(w, dict)]
                            self.operations[oname] = {"inputs": inputs, "returns": mapping(op).get("returns"), "returns_type": None,
                                                      "ordered_by": "ordered_by" in mapping(op), "who": who, "story": sid, "file": stem}
        while True:               # computed properties and returns, until no type gets more precise
            changed = False
            for ename, ent in self.entities.items():
                for p, expr in ent["computed"].items():
                    if isinstance(expr, str) and unknowns(ent["props"][p]):
                        t = Expr(self, dict(ent["props"]), silent=True).run(expr)
                        if t is not None and (ent["props"][p] is None or unknowns(t) < unknowns(ent["props"][p])):
                            ent["props"][p] = t
                            changed = True
            for op in self.operations.values():
                if isinstance(op["returns"], str) and unknowns(op["returns_type"]):
                    scope = {n: t for n, t, _ in op["inputs"]}
                    scope["ACTOR"] = ("actor", ("one", frozenset(r for r in op["who"] if isinstance(r, str))))
                    t = Expr(self, scope, silent=True).run(op["returns"])
                    if t is not None and (op["returns_type"] is None or unknowns(t) < unknowns(op["returns_type"])):
                        if op["ordered_by"] and is_list(t):
                            t = ("list", t[1], True)
                        op["returns_type"] = t
                        changed = True
            if not changed:
                break
        self.cycle_anchors = self.find_cycles()
        self.versions = {}        # (kind, name) -> the version numbers in the history beside the block's file
        for stem, entries in histories:
            for e in listing(entries):
                if isinstance(e, dict):
                    kind = "story" if "story" in e else "entity" if "entity" in e else "role"
                    if self.file_of(kind, e.get(kind)) == stem:
                        self.versions.setdefault((kind, e.get(kind)), set()).add(e.get("number"))

    def file_of(self, kind, name):
        """the stem of the file a block lives in, or None"""
        if kind == "story":
            return self.stories.get(name)
        block = (self.entities if kind == "entity" else self.roles).get(name)
        return block["file"] if block else None

    def find_cycles(self):
        """the first declared role of each cycle of includes, in file-name then file order"""
        reach = {}
        for r in self.roles:
            seen, stack = set(), list(self.roles[r]["includes"])
            while stack:
                x = stack.pop()
                if x in seen or x not in self.roles:
                    continue
                seen.add(x)
                stack.extend(self.roles[x]["includes"])
            reach[r] = seen
        anchors, reported = set(), set()
        for r in self.role_order:
            if r in reach[r] and r not in reported:
                component = {x for x in reach[r] if r in reach.get(x, ())} | {r}
                anchors.add(r)
                reported |= component
        return anchors

    def home(self, ename):
        """the file an entity lives in: its own name, or its owner's through part_of"""
        seen = set()
        while ename in self.entities and self.entities[ename]["part_of"] and ename not in seen:
            seen.add(ename)
            ename = self.entities[ename]["part_of"]
        return ename

    def closure(self, roles):
        """the roles plus every role they include, transitively"""
        out, stack = set(), list(roles)
        while stack:
            r = stack.pop()
            if r in out or r not in self.roles:
                continue
            out.add(r)
            stack.extend(self.roles[r]["includes"])
        return out

    def actor_props(self, spec):
        """the properties an actor has: name, roles, and the has: of its roles;
        spec ("all", roles) for a known actor, ("one", roles) for one of them;
        a property two roles declare differently may be either"""
        base = {"name": "TEXT", "roles": ("list", "TEXT", True)}
        if not spec or not spec[1]:
            return base
        kind, roles = spec
        sets = []
        for role in roles:
            s = {}
            for r in self.closure([role]):
                for p, t in self.roles[r]["has"].items():
                    s[p] = unify(s[p], t) if p in s else t
            sets.append(s)
        names = set.union(*[set(s) for s in sets]) if kind == "all" else set.intersection(*[set(s) for s in sets])
        out = {}
        for p in names:
            out[p] = unify_all([s[p] for s in sets if p in s])
        out.update(base)          # name and roles are fixed
        return out

    def admitted(self, ename):
        """the roles the entity's permission matrix admits, closed over includes"""
        ent = self.entities.get(ename)
        if not ent:
            return None
        roles = {r for rs in ent["may"].values() for r in rs if r}
        grown = True
        while grown:
            grown = False
            for rname, role in self.roles.items():
                if rname not in roles and any(i in roles for i in role["includes"]):
                    roles.add(rname)
                    grown = True
        return roles


# --- the expression checker ---------------------------------------------------

GEN_ONLY = {"sum", "min", "max", "any", "all"}
ONE_ARG = {"len", "OLD"}
OP_WORD = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
CMP_WORD = {ast.Lt: "<", ast.Gt: ">", ast.LtE: "<=", ast.GtE: ">="}
FIXED = {"ACTOR", "RESULT", "NOW", "TODAY", "OLD"}


def quoted(new):
    """unparse with Edda's double-quoted text literals"""
    tree = copy.deepcopy(new)
    literals = []
    for c in ast.walk(tree):
        if isinstance(c, ast.Constant) and isinstance(c.value, str):
            literals.append(c.value)
            c.value = f"__edda_text_{len(literals) - 1}__"
    text = ast.unparse(tree)
    for i, v in enumerate(literals):
        text = text.replace(f"'__edda_text_{i}__'", json.dumps(v, ensure_ascii=False))
    return text


def mentions_result(n):
    return any(isinstance(x, ast.Name) and x.id == "RESULT" for x in ast.walk(n))


class Expr:
    """checks one expression and gives its type; problems as (rule, message)"""

    def __init__(self, project, scope, allow_old=False, silent=False):
        self.P, self.scope, self.allow_old, self.silent = project, scope, allow_old, silent
        self.out, self.src, self.outer = [], "", None
        self.types = {}           # id(node) -> its type, for fits()

    def problem(self, rule, msg):
        if not self.silent:
            self.out.append((rule, msg))

    def seg(self, n):
        return ast.get_source_segment(self.src, n) or "..."

    def second(self, new, old):
        self.problem("second_way", f"write {quoted(new)} (not {self.seg(old)})")

    def quiet(self, n, scope):
        """the type of a node without reporting, for a rewrite's guard"""
        silent = Expr(self.P, scope, self.allow_old, silent=True)
        silent.src = self.src
        return silent.visit(n, scope)

    def run(self, text, call_slot=False):
        self.src = text
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            self.problem("not_an_expression", f"not an expression: {text}")
            return None
        body = tree.body
        if call_slot:
            if not (isinstance(body, ast.Call) and isinstance(body.func, ast.Name) and body.func.id in self.P.operations):
                if isinstance(body, ast.Call) and isinstance(body.func, ast.Name) and re.fullmatch(NAME, body.func.id) \
                        and body.func.id not in ONE_ARG and body.func.id not in GEN_ONLY:
                    self.problem("unknown_name", f"unknown name: {body.func.id}")
                else:
                    self.problem("not_an_expression", f"not an expression (a call of an operation was expected): {text}")
                return None
            self.outer = body        # the actor's request may be a changing operation
        return self.visit(body, self.scope)

    def status(self, name, other, scope):
        """type a bare name compared with a value of type other"""
        rest = [a for a in alts(other) if a != "NONE"]
        choices = [a for a in rest if is_choice(a)]
        if choices and len(choices) == len(rest):
            values = [v for c in choices for v in (c[1] or ())]
            if all(c[1] for c in choices) and name.id not in values:
                self.problem("unknown_status", f"status not in its list: {name.id}")
                return ("choice", None)
            return ("choice", (name.id,))
        return self.visit(name, scope)

    def comprehension(self, generators, scope):
        inner, ordered_all = dict(scope), True
        for g in generators:
            it = self.visit(g.iter, inner)
            lt = as_list(it)
            if g.is_async:
                self.problem("not_an_expression", f"not an expression (async): {self.src}")
            if not isinstance(g.target, ast.Name):
                self.problem("not_an_expression", f"not an expression (a comprehension variable is a plain name): {self.src}")
                continue
            if it is not None and lt is None:
                self.problem("type_mismatch", f"for expects a list: {self.src}")
                inner[g.target.id] = None
            else:
                inner[g.target.id] = (lt[1] if lt[1] != "ANY" else None) if lt else None
            ordered_all = ordered_all and ordered(lt)
            for c in g.ifs:
                self.visit(c, inner)
        return inner, ordered_all

    def fits(self, node, t, expected, optional=False):
        """may the value of node, of type t, stand where expected is declared;
        each branch of a conditional and each operand of and/or is checked on its
        own, and an element a constant index picks is checked as written"""
        L = self.index_leaf(node)
        if L is not None:
            if "NONE" in alts(t) and not compatible("NONE", expected, optional):
                return False
            return all(compatible(a, expected, optional, n) for n, a in L)
        if isinstance(node, ast.IfExp):
            return all(self.fits(b, self.types.get(id(b)), expected, optional) for b in (node.body, node.orelse))
        if isinstance(node, ast.BoolOp):
            return all(self.fits(v, self.types.get(id(v)), expected, optional) for v in node.values)
        return compatible(t, expected, optional, node)

    def lit_type(self, node, t):
        """a position's type: LIT for a text literal, each branch of a conditional
        and each operand of and/or on its own, else the type"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return LIT
        if isinstance(node, ast.IfExp):
            return unify(self.lit_type(node.body, self.types.get(id(node.body))),
                         self.lit_type(node.orelse, self.types.get(id(node.orelse))))
        if isinstance(node, ast.BoolOp):
            return unify_all([self.lit_type(v, self.types.get(id(v))) for v in node.values])
        return t

    def index_leaf(self, node):
        """the (node, type) pairs of the element a constant index picks out of a
        list with known positions, or None"""
        if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            i = int_lit(node.slice)
            P = self.positions(node.value)
            P = typed_positions(self.types.get(id(node.value))) if P is None else P
            if i is not None and P is not None and -len(P) <= i < len(P):
                return P[i]
        return None

    def leaves(self, node, t):
        """the (node, type) pairs a value may be: each branch of a conditional,
        each operand of and/or, each alternative, the element a constant index
        picks; None compares with anything"""
        L = self.index_leaf(node)
        if L is not None:
            return [(n, a) for n, x in L for a in alts(x) if a != "NONE"] if any(x is not None for _, x in L) else L
        if isinstance(node, ast.IfExp):
            return sum((self.leaves(b, self.types.get(id(b))) for b in (node.body, node.orelse)), [])
        if isinstance(node, ast.BoolOp):
            return sum((self.leaves(v, self.types.get(id(v))) for v in node.values), [])
        return [(node, a) for a in alts(t) if a != "NONE"] if t is not None else [(node, None)]

    def elts(self, node, t):
        """the (node, type) pairs a list's elements may be: each literal element,
        through a slice, a +, a comprehension's projection, OLD and alternatives;
        else the element type"""
        T = lambda n: self.types.get(id(n))
        if isinstance(node, ast.List):
            return sum((self.leaves(e, T(e)) for e in node.elts), [])
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            P = self.positions(node)
            return sum(P, []) if P is not None else self.elts(node.value, T(node.value))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.elts(node.left, T(node.left)) + self.elts(node.right, T(node.right))
        if isinstance(node, ast.ListComp):
            return self.leaves(node.elt, T(node.elt))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "OLD" and len(node.args) == 1:
            return self.elts(node.args[0], T(node.args[0]))
        if isinstance(node, ast.IfExp):
            return self.elts(node.body, T(node.body)) + self.elts(node.orelse, T(node.orelse))
        if isinstance(node, ast.BoolOp):
            return sum((self.elts(v, T(v)) for v in node.values), [])
        L = self.index_leaf(node)
        if L is not None and len(L) == 1 and L[0][0] is not None:
            return self.elts(L[0][0], T(L[0][0]))
        tp = typed_positions(t)                   # known positions, literals remembered
        if tp is not None:
            return sum(tp, [])
        return [(None, t[1] if is_list(t) else None)]

    def positions(self, node):
        """the elements of a written-out list by position, each the (node, type)
        pairs it may be, through a + and OLD; None when the positions are not known"""
        T = lambda n: self.types.get(id(n))
        if isinstance(node, ast.List):
            return [self.leaves(e, T(e)) for e in node.elts]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            A, B = self.positions(node.left), self.positions(node.right)
            return A + B if A is not None and B is not None else None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "OLD" and len(node.args) == 1:
            return self.positions(node.args[0])
        L = self.index_leaf(node)
        if L is not None and len(L) == 1 and L[0][0] is not None:
            return self.positions(L[0][0])
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            sl = node.slice
            if all(b is None or int_lit(b) is not None for b in (sl.lower, sl.upper)):
                P = self.positions(node.value)
                P = typed_positions(T(node.value)) if P is None else P
                if P is not None:
                    return P[int_lit(sl.lower) if sl.lower else None:int_lit(sl.upper) if sl.upper else None]
        return None

    def pair(self, a, an, b, bn):
        """may two single values be compared for equality: one kind, a time literal
        beside a TIME, two lists by their elements in any order"""
        if a is None or b is None or "ANY" in (a, b) or "NONE" in (a, b):
            return True
        if is_either(a) or is_either(b):
            return all(self.pair(x, an, y, bn) for x in alts(a) for y in alts(b))
        if is_list(a) and is_list(b):
            A, B = self.positions(an), self.positions(bn)
            A = typed_positions(a) if A is None else A
            B = typed_positions(b) if B is None else B
            if A is not None and B is not None:     # both with known positions: position by position
                return all(self.pair(x, xn, y, yn) for pa, pb in zip(A, B) for xn, x in pa for yn, y in pb)
            return all(self.pair(x, xn, y, yn) for xn, x in self.elts(an, a) for yn, y in self.elts(bn, b))
        if a == b or {a, b} == {"INTEGER", "NUMBER"}:
            return True
        if (a, b) == ("TIME", "TEXT") and is_time_literal(bn) or (a, b) == ("TEXT", "TIME") and is_time_literal(an):
            return True
        if is_choice(a) and is_choice(b):
            return a[1] is None or b[1] is None or set(a[1]) <= set(b[1]) or set(b[1]) <= set(a[1])
        if is_actor(a) and is_actor(b):
            return True
        return False

    def eq_ok(self, L, R):
        """every value one side may be compares with every value the other may be"""
        return not L or not R or all(self.pair(a, an, b, bn) for an, a in L for bn, b in R)

    def visit(self, n, scope):
        t = self.typed(n, scope)
        self.types[id(n)] = t
        return t

    def typed(self, n, scope):
        P, src = self.P, self.src
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
            if v is None:
                return "NONE"
            self.problem("not_an_expression", f"not an expression (constant): {src}")
            return None
        if isinstance(n, ast.Name):
            i = n.id
            if i == "ACTOR":
                return scope.get("ACTOR", ("actor", None))
            if i in ("NOW", "TODAY"):
                return "TIME"
            if i == "RESULT":
                if "RESULT" not in scope:
                    self.problem("not_an_expression", f"not an expression (RESULT only after a call): {src}")
                    return None
                return scope["RESULT"]
            if i in scope and i != "RESULT_OP":
                return scope[i]
            if i in ONE_ARG or i in GEN_ONLY or i in P.operations:
                self.problem("not_an_expression", f"not an expression (name {i}): {src}")
                return None
            if re.fullmatch(NAME, i):
                self.problem("unknown_name", f"unknown name: {i}")
                return None
            self.problem("not_an_expression", f"not an expression (name {i}): {src}")
            return None
        if isinstance(n, ast.Attribute):
            t = self.visit(n.value, scope)
            if t is None:
                return None
            outs = []
            for a in alts(t):
                if a is None:
                    outs.append(None)
                elif is_actor(a):
                    props = P.actor_props(a[1])
                    if n.attr not in props:
                        self.problem("unknown_name", f"unknown name: {n.attr}")
                    outs.append(props.get(n.attr))
                elif is_entity(a):
                    if a[1] not in P.entities:
                        outs.append(None)
                        continue
                    props = P.entities[a[1]]["props"]
                    if n.attr not in props:
                        self.problem("unknown_name", f"unknown name: {n.attr}")
                    outs.append(props.get(n.attr))
                else:
                    self.problem("type_mismatch", f".{n.attr} expects an entity: {src}")
                    return None
            return unify_all(outs)
        if isinstance(n, ast.Subscript):
            t = self.visit(n.value, scope)
            lt = as_list(t)
            s = n.slice
            if isinstance(s, ast.Slice):
                if s.step is not None:
                    self.problem("not_an_expression", f"not an expression (slice step): {src}")
                for b in (s.lower, s.upper):
                    if b is not None and not all_alts(self.visit(b, scope), lambda a: a == "INTEGER"):
                        self.problem("type_mismatch", f"a slice bound expects an INTEGER: {src}")
                if t is not None and lt is None:
                    self.problem("type_mismatch", f"a slice expects a list: {src}")
                if positions_of(lt) is not None and all(b is None or int_lit(b) is not None for b in (s.lower, s.upper)):
                    ps = lt[3][int_lit(s.lower) if s.lower else None:int_lit(s.upper) if s.upper else None]
                    return ("list", unify_all([unlit(x) for x in ps]) if ps else "ANY", ordered(lt), ps)
                return ("list", lt[1], ordered(lt)) if lt else None
            st = self.visit(s, scope)
            if not all_alts(st, lambda a: a == "INTEGER"):
                self.problem("type_mismatch", f"an index expects an INTEGER: {src}")
            elif isinstance(s, ast.BinOp) and isinstance(s.op, ast.Sub) and isinstance(s.left, ast.Call) \
                    and isinstance(s.left.func, ast.Name) and s.left.func.id == "len" and len(s.left.args) == 1 \
                    and isinstance(s.right, ast.Constant) and s.right.value == 1 and not isinstance(s.right.value, bool) \
                    and ast.dump(s.left.args[0]) == ast.dump(n.value):
                self.second(ast.Subscript(n.value, ast.UnaryOp(ast.USub(), ast.Constant(1)), ast.Load()), n)
            if lt and not ordered(lt) and mentions_result(n.value):
                self.problem("not_ordered", f"{scope.get('RESULT_OP', 'the operation')} gives no order; RESULT[{self.seg(s)}] needs ordered_by or IN ORDER")
            if lt:
                ps, i = positions_of(lt), int_lit(s)
                if ps is not None and i is not None and -len(ps) <= i < len(ps):
                    return unlit(ps[i])
                return lt[1] if lt[1] != "ANY" else None
            if t is not None:
                self.problem("type_mismatch", f"an index expects a list: {src}")
            return None
        if isinstance(n, ast.Compare):
            if len(n.ops) != 1:
                parts, left = [], n.left
                for op, c in zip(n.ops, n.comparators):
                    parts.append(ast.Compare(left, [op], [c]))
                    left = c
                self.second(ast.BoolOp(ast.And(), parts), n)
                for c in [n.left] + n.comparators:
                    self.visit(c, scope)
                return "YES_NO"
            left, right, op = n.left, n.comparators[0], n.ops[0]
            if isinstance(op, (ast.Is, ast.IsNot)) and not (isinstance(right, ast.Constant) and right.value is None):
                self.problem("not_an_expression", f"not an expression (is only against None): {src}")

            def bare(b):
                return isinstance(b, ast.Name) and b.id not in scope and b.id not in P.operations \
                    and b.id not in FIXED and re.fullmatch(NAME, b.id)

            equality = isinstance(op, (ast.Eq, ast.NotEq))
            # x[:n] == "t" where "t" has n characters, x a text: a second way, found before its slice is typed
            prefix = isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Slice) and left.slice.lower is None \
                and left.slice.step is None and isinstance(left.slice.upper, ast.Constant) \
                and type(left.slice.upper.value) is int and equality \
                and isinstance(right, ast.Constant) and isinstance(right.value, str) \
                and len(right.value) == left.slice.upper.value and self.quiet(left.value, scope) == "TEXT"
            # a bare name beside == or != is a status value: in the property's list or unknown_status
            if prefix:
                self.visit(left.value, scope)
                lt, rt = "TEXT", self.visit(right, scope)
            elif equality and bare(right) and not bare(left):
                lt = self.visit(left, scope)
                rt = self.status(right, lt, scope)
            elif equality and bare(left) and not bare(right):
                rt = self.visit(right, scope)
                lt = self.status(left, rt, scope)
            elif isinstance(op, (ast.In, ast.NotIn)) and isinstance(right, ast.List) and any(bare(e) for e in right.elts):
                lt = self.visit(left, scope)
                ets = []
                for e in right.elts:        # a bare name in the list is a status of the compared property
                    et = self.status(e, lt, scope) if bare(e) else self.visit(e, scope)
                    self.types[id(e)] = et
                    ets.append(et)
                rt = ("list", unify_all(ets), True)
            else:
                lt, rt = self.visit(left, scope), self.visit(right, scope)
            neg = isinstance(op, ast.NotEq)
            # the operands must compare: one kind for == and !=, an element for in, numbers, texts or times for <
            if isinstance(op, (ast.In, ast.NotIn)):
                L, R = self.leaves(left, lt), self.leaves(right, rt)
                if rt is not None and not R:              # only None: neither a list nor a text
                    self.problem("type_mismatch", f"in expects a list or a text: {src}")
                for rn, r in R:                           # each value the right side may be, on its own
                    if r is None:
                        continue
                    if is_list(r):
                        if not self.eq_ok(L, self.elts(rn, r)):
                            self.problem("type_mismatch", f"in expects an element of the list: {src}")
                    elif r == "TEXT":
                        if (lt is not None and not L) or not all(compatible(a, "TEXT", True, an) for an, a in L):
                            self.problem("type_mismatch", f"in expects a text in a text: {src}")
                    else:
                        self.problem("type_mismatch", f"in expects a list or a text: {src}")
            elif equality:
                if not self.eq_ok(self.leaves(left, lt), self.leaves(right, rt)):
                    self.problem("type_mismatch", f"{'!=' if neg else '=='} expects two values of one kind: {src}")
            elif type(op) in CMP_WORD:
                L = self.leaves(left, lt) + self.leaves(right, rt)
                if L and not any(all(compatible(a, k, True, an) for an, a in L) for k in ("NUMBER", "TEXT", "TIME")):
                    self.problem("type_mismatch", f"{CMP_WORD[type(op)]} expects two numbers, two texts or two times: {src}")
            # len(x) == 0, len(x) != 0, len(x) > 0, only for a list
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len" \
                    and len(left.args) == 1 and isinstance(right, ast.Constant) and right.value == 0 \
                    and not isinstance(right.value, bool) and as_list(self.quiet(left.args[0], scope)):
                x = left.args[0]
                if isinstance(op, ast.Eq):
                    self.second(ast.Compare(x, [ast.Eq()], [ast.List([], ast.Load())]), n)
                elif isinstance(op, (ast.NotEq, ast.Gt)):
                    self.second(ast.Compare(x, [ast.NotEq()], [ast.List([], ast.Load())]), n)
            # x == None, None == x
            for a, b in ((left, right), (right, left)):
                if isinstance(b, ast.Constant) and b.value is None and equality:
                    self.second(ast.Compare(a, [ast.IsNot() if neg else ast.Is()], [ast.Constant(None)]), n)
                    break
            # x == True / False, True == x, only for a yes/no
            for a, at, b in ((left, lt, right), (right, rt, left)):
                if isinstance(b, ast.Constant) and isinstance(b.value, bool) and equality and at == "YES_NO":
                    holds = b.value != neg
                    self.second(a if holds else ast.UnaryOp(ast.Not(), a), n)
                    break
            if prefix:
                call = ast.Call(ast.Attribute(left.value, "startswith", ast.Load()), [right], [])
                self.second(ast.UnaryOp(ast.Not(), call) if neg else call, n)
            return "YES_NO"
        if isinstance(n, ast.BoolOp):
            return unify_all([self.visit(v, scope) for v in n.values])
        if isinstance(n, ast.UnaryOp):
            t = self.visit(n.operand, scope)
            if isinstance(n.op, ast.Not):
                if as_list(t):
                    self.second(ast.Compare(n.operand, [ast.Eq()], [ast.List([], ast.Load())]), n)
                return "YES_NO"
            if isinstance(n.op, ast.USub):
                if not all_alts(t, lambda a: a in ("INTEGER", "NUMBER")):
                    self.problem("type_mismatch", f"- expects a number: {src}")
                    return None
                return t
            self.problem("not_an_expression", f"not an expression ({type(n.op).__name__}): {src}")
            return None
        if isinstance(n, ast.BinOp):
            lt, rt = self.visit(n.left, scope), self.visit(n.right, scope)
            if type(n.op) not in OP_WORD:
                self.problem("not_an_expression", f"not an expression ({type(n.op).__name__}): {src}")
                return None
            ll, rl = as_list(lt), as_list(rt)
            if isinstance(n.op, ast.Add) and (ll or rl):
                if lt is not None and rt is not None and not (ll and rl):
                    self.problem("type_mismatch", f"+ expects two lists or two numbers: {src}")
                    return None
                if ll and rl:
                    u = as_list(unify(ll, rl))
                    if u and positions_of(ll) is not None and positions_of(rl) is not None:
                        return ("list", u[1], ordered(u), ll[3] + rl[3])
                    return u
                return ll or rl
            for t in (lt, rt):
                if not all_alts(t, lambda a: a in ("INTEGER", "NUMBER")):
                    self.problem("type_mismatch", f"{OP_WORD[type(n.op)]} expects numbers: {src}")
                    return None
            if isinstance(n.op, ast.Div):
                return "NUMBER"
            if lt == "INTEGER" and rt == "INTEGER":
                return "INTEGER"
            if "NUMBER" in (lt, rt):
                return "NUMBER"
            return None
        if isinstance(n, ast.IfExp):
            self.visit(n.test, scope)
            return unify(self.visit(n.body, scope), self.visit(n.orelse, scope))
        if isinstance(n, ast.List):
            types = [self.visit(e, scope) for e in n.elts]
            ps = tuple(self.lit_type(e, t) for e, t in zip(n.elts, types))
            return ("list", unify_all(types) if n.elts else "ANY", True, ps)
        if isinstance(n, ast.ListComp):
            inner, o = self.comprehension(n.generators, scope)
            return ("list", self.visit(n.elt, inner), o)
        if isinstance(n, ast.GeneratorExp):
            self.problem("not_an_expression", f"not an expression (a generator only inside {', '.join(sorted(GEN_ONLY))}): {src}")
            return None
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                rt = self.visit(f.value, scope)
                if f.attr != "startswith":
                    self.problem("not_an_expression", f"not an expression (method {f.attr}): {src}")
                    return None
                if len(n.args) != 1 or n.keywords:
                    self.problem("type_mismatch", f"startswith expects one argument: {src}")
                    return "YES_NO"
                at = self.visit(n.args[0], scope)
                if not (all_alts(rt, lambda a: a == "TEXT") and all_alts(at, lambda a: a == "TEXT")):
                    self.problem("type_mismatch", f"startswith expects a text: {src}")
                return "YES_NO"
            if not isinstance(f, ast.Name):
                self.problem("not_an_expression", f"not an expression (call form): {src}")
                return None
            if f.id in GEN_ONLY:
                if not (len(n.args) == 1 and isinstance(n.args[0], ast.GeneratorExp) and not n.keywords):
                    self.problem("type_mismatch", f"{f.id} expects one generator: {src}")
                    for a in n.args:
                        self.visit(a, scope)
                    return None
                g = n.args[0]
                inner, _ = self.comprehension(g.generators, scope)
                et = self.visit(g.elt, inner)
                if f.id == "sum" and isinstance(g.elt, ast.Constant) and g.elt.value == 1 and len(g.generators) == 1 \
                        and not g.generators[0].ifs:
                    self.second(ast.Call(ast.Name("len", ast.Load()), [g.generators[0].iter], []), n)
                if f.id in ("any", "all"):
                    return "YES_NO"
                if f.id == "sum" and not all_alts(et, lambda a: a in ("INTEGER", "NUMBER")):
                    self.problem("type_mismatch", f"sum expects numbers: {src}")
                    return None
                return et
            if f.id in ONE_ARG:
                if len(n.args) != 1 or n.keywords:
                    self.problem("type_mismatch", f"{f.id} expects one argument: {src}")
                    for a in n.args:
                        self.visit(a, scope)
                    return "INTEGER" if f.id == "len" else None
                at = self.visit(n.args[0], scope)
                if f.id == "len":
                    if not all_alts(at, lambda a: is_list(a) or a == "TEXT"):
                        self.problem("type_mismatch", f"len expects a list or a text: {src}")
                    return "INTEGER"
                if not self.allow_old:
                    self.problem("not_an_expression", f"not an expression (OLD only under ensure): {src}")
                return at
            if f.id in P.operations:
                op = P.operations[f.id]
                req = [i for i in op["inputs"] if not i[2]]
                opt = {i[0]: i[1] for i in op["inputs"] if i[2]}
                if len(n.args) != len(req):
                    self.problem("type_mismatch", f"{f.id} expects {len(req)} input{'s' if len(req) != 1 else ''} by position: {src}")
                for a, (iname, itype, _) in zip(n.args, req):
                    at = self.visit(a, scope)
                    if not self.fits(a, at, itype):
                        self.problem("type_mismatch", f"{f.id} input {iname} expects {words(itype)}: {src}")
                for a in n.args[len(req):]:
                    self.visit(a, scope)
                seen = set()
                for kw in n.keywords:
                    if kw.arg is None or kw.arg not in opt:
                        self.problem("type_mismatch", f"{f.id} expects no input named {kw.arg}: {src}")
                        self.visit(kw.value, scope)
                    elif kw.arg in seen:
                        self.problem("type_mismatch", f"{f.id} expects {kw.arg} once: {src}")
                    else:
                        seen.add(kw.arg)
                        at = self.visit(kw.value, scope)
                        if not self.fits(kw.value, at, opt[kw.arg], True):
                            self.problem("type_mismatch", f"{f.id} input {kw.arg} expects {words(opt[kw.arg])}: {src}")
                if op["returns"] is None and n is not self.outer:
                    self.problem("not_an_expression", f"not an expression (a changing operation inside a fact): {src}")
                return op["returns_type"] if op["returns"] is not None else "NONE"
            for a in n.args:
                self.visit(a, scope)
            for kw in n.keywords:
                self.visit(kw.value, scope)
            if re.fullmatch(NAME, f.id):
                self.problem("unknown_name", f"unknown name: {f.id}")
            else:
                self.problem("not_an_expression", f"not an expression (call to {f.id}): {src}")
            return None
        self.problem("not_an_expression", f"not an expression ({type(n).__name__}): {src}")
        return None


# --- the meaning layer -------------------------------------------------------

def walk_meaning(data, stem, P, source):
    """yield (rule, path, message); the line comes from the path"""

    def tp(v, where):
        if isinstance(v, str):
            if v == "":
                yield "wrong_type", where, f"{where[-1]} expects a text, nothing was given"
                return
            for rule, p in type_phrase_problems(v):
                yield rule, where, p
            e = phrase_entity(v)
            if e and e not in P.entities:
                yield "unknown_name", where, f"unknown name: {e}"

    def ex(v, where, scope, allow_old=False, call_slot=False):
        if isinstance(v, str):
            if v == "":
                yield "wrong_type", where, f"{key_name(where)} expects a text, nothing was given"
                return
            c = Expr(P, scope, allow_old)
            c.run(v, call_slot=call_slot)
            for rule, p in c.out:
                yield rule, where, p

    def fact(v, where, scope, allow_old=False):
        if isinstance(v, dict):
            yield from ex(v.get("fact"), where + ("fact",), scope, allow_old)
        else:
            yield from ex(v, where, scope, allow_old)

    def role_ok(r, where):
        if isinstance(r, str) and r not in P.roles:
            yield "unknown_name", where, f"unknown name: {r}"

    def one_of(roles):
        return ("actor", ("one", frozenset(r for r in roles if isinstance(r, str))))

    for rname, role in mapping(data.get("roles")).items():
        for p, v in mapping(role.get("has")).items():
            yield from tp(v, ("roles", rname, "has", p))
        for i, inc in enumerate(listing(role.get("includes"))):
            yield from role_ok(inc, ("roles", rname, "includes", i))
        if rname in P.cycle_anchors:
            yield "role_cycle", ("roles", rname, "includes"), f"role {rname} includes itself"
    for ename, ent in mapping(data.get("entities")).items():
        props = P.entities.get(ename, {}).get("props", {})
        own = dict(props)
        if "part_of" in ent and ent["part_of"] not in P.entities:
            yield "unknown_name", ("entities", ename, "part_of"), f"unknown name: {ent['part_of']}"
        elif "part_of" in ent and ename in P.entities and P.home(ename) != stem:
            yield "wrong_file", ("entities", ename), f"entity {ename} is part of {ent['part_of']} and belongs in {P.home(ename)}.edda"
        for p, v in mapping(ent.get("properties")).items():
            if isinstance(v, dict):
                yield from ex(v.get("computed"), ("entities", ename, "properties", p, "computed"), own)
            else:
                yield from tp(v, ("entities", ename, "properties", p))
        for p, arrows in mapping(ent.get("may_change")).items():
            where = ("entities", ename, "may_change", p)
            if p not in props:
                yield "unknown_name", where, f"unknown name: {p}"
                continue
            c = choice_of(props[p])
            if c is None:
                if props[p] is not None:
                    yield "type_mismatch", where, f"may_change expects a choice property: {p}"
                continue
            vals = c[1]
            for frm, tos in mapping(arrows).items():
                if vals is not None and frm not in vals:
                    yield "unknown_status", where + (frm,), f"status not in its list: {frm}"
                for i, s in enumerate(listing(tos)):
                    if vals is not None and s not in vals:
                        yield "unknown_status", where + (frm, i), f"status not in its list: {s}"
        for p, per_value in mapping(ent.get("wording")).items():
            where = ("entities", ename, "wording", p)
            if p not in props:
                yield "unknown_name", where, f"unknown name: {p}"
                continue
            c = choice_of(props[p])
            if c is None:
                if props[p] is not None:
                    yield "type_mismatch", where, f"wording expects a choice property: {p}"
                continue
            vals = c[1]
            for val, per_role in mapping(per_value).items():
                if vals is not None and val not in vals:
                    yield "unknown_status", where + (val,), f"status not in its list: {val}"
                for r in mapping(per_role):
                    yield from role_ok(r, where + (val, r))
        for i, f in enumerate(listing(ent.get("always"))):
            yield from fact(f, ("entities", ename, "always", i), own)
        for i, w in enumerate(listing(ent.get("while"))):
            yield from ex(w.get("when"), ("entities", ename, "while", i, "when"), own)
            yield from fact(w.get("holds"), ("entities", ename, "while", i, "holds"), own)
        for key in ("may_create", "may_read", "may_update", "may_delete"):
            for i, w in enumerate(listing(ent.get(key))):
                yield from role_ok(w.get("role"), ("entities", ename, key, i, "role"))
                if "when" in w:
                    scope = {ename: ("entity", ename), "ACTOR": one_of([w.get("role")])}
                    yield from ex(w["when"], ("entities", ename, key, i, "when"), scope)
    for sid, st in mapping(data.get("stories")).items():
        about = st.get("about")
        if about not in P.entities:
            yield "unknown_name", ("stories", sid, "about"), f"unknown name: {about}"
        elif P.home(about) != stem:
            yield "wrong_file", ("stories", sid), f"story {sid} is about {about} and belongs in {P.home(about)}.edda"
        yield from role_ok(st.get("as_a"), ("stories", sid, "as_a"))
        if "epic" in st and st["epic"] not in P.epics:
            yield "unknown_name", ("stories", sid, "epic"), f"unknown name: {st['epic']}"
        admitted = P.admitted(about)
        for oname, op in mapping(st.get("operations")).items():
            where = ("stories", sid, "operations", oname)
            if "returns" in op and "ensure" in op:
                yield "returns_and_ensure", where, f"returns and ensure on one operation: {oname}"
            elif "returns" in op and "also_changes" in op:
                yield "returns_and_ensure", where, f"returns and also_changes on one operation: {oname}"
            if "ordered_by" in op and "returns" not in op:
                yield "returns_and_ensure", where, f"ordered_by needs returns: {oname}"
            if "also_changes" in op and "ensure" not in op:
                yield "returns_and_ensure", where, f"also_changes needs ensure: {oname}"
            inputs = {}
            for n, v in mapping(op.get("inputs")).items():
                yield from tp(v, where + ("inputs", n))
                inputs[n] = type_of_phrase(v)
            who_roles = [w.get("role") for w in listing(op.get("who")) if isinstance(w, dict)]
            body = dict(inputs, ACTOR=one_of(who_roles))
            for i, w in enumerate(listing(op.get("who"))):
                r = w.get("role")
                yield from role_ok(r, where + ("who", i, "role"))
                if admitted is not None and r in P.roles and r not in admitted:
                    yield "wider_than_entity", where + ("who", i), f"{oname} admits {r}, which {about} does not"
                if "when" in w:
                    yield from ex(w["when"], where + ("who", i, "when"), dict(inputs, ACTOR=one_of([r])))
            for i, r in enumerate(listing(op.get("refuse"))):
                yield from ex(r.get("when"), where + ("refuse", i, "when"), body)
            for i, f in enumerate(listing(op.get("ensure"))):
                yield from fact(f, where + ("ensure", i), body, allow_old=True)
            yield from ex(op.get("returns"), where + ("returns",), body)
            rt = P.operations.get(oname, {}).get("returns_type")
            item_scope = {"ACTOR": body["ACTOR"]}
            if is_list(rt) and is_entity(rt[1]):
                item_scope[rt[1][1]] = rt[1]
            if "ordered_by" in op and rt is not None and not is_list(rt):
                yield "type_mismatch", where + ("ordered_by",), f"ordered_by expects a list result: {op.get('returns')}"
            for i, o in enumerate(listing(op.get("ordered_by"))):
                yield from ex(o, where + ("ordered_by", i), item_scope)
            for i, p in enumerate(listing(op.get("also_changes"))):
                pw = where + ("also_changes", i)
                try:
                    node = ast.parse(p, mode="eval").body if isinstance(p, str) else None
                except SyntaxError:
                    node = None
                chain = node
                while isinstance(chain, ast.Attribute):
                    chain = chain.value
                if not (isinstance(node, ast.Attribute) and isinstance(chain, ast.Name)):
                    yield "not_an_expression", pw, f"not an expression (a property path was expected): {p}"
                else:
                    yield from ex(p, pw, inputs)
        for title, exm in mapping(st.get("examples")).items():
            where = ("stories", sid, "examples", title)
            givens, names = {}, {}
            for i, g in enumerate(listing(exm.get("given"))):      # names first: givens are order-independent
                for k, v in mapping(g).items():
                    if k != "with" and isinstance(v, str) and v not in givens:
                        roles = [r for r in listing(mapping(g.get("with")).get("roles")) if isinstance(r, str)] if k == "actor" else []
                        givens[v] = ("actor", ("all", frozenset(roles))) if k == "actor" else ("entity", k)
                        names[v] = k
            for i, g in enumerate(listing(exm.get("given"))):
                gw = where + ("given", i)
                kind = [k for k in mapping(g) if k != "with"]
                if not kind:
                    continue
                k = kind[0]
                if k != "actor" and k not in P.entities:
                    yield "unknown_name", gw, f"unknown name: {k}"
                    continue
                props = P.actor_props(givens.get(g[k], ("actor", None))[1]) if k == "actor" else P.entities[k]["props"]
                derived = set() if k == "actor" else P.entities[k]["derived"]
                computed = set() if k == "actor" else set(P.entities[k]["computed"])
                for p, v in mapping(g.get("with")).items():
                    pw = gw + ("with", p)
                    if p == "fixture" and k == "spec_file":
                        if not os.path.isdir(f"{ROOT}/fixtures/{v}"):
                            yield "unknown_name", pw, f"unknown name: {v}"
                        continue
                    if p == "roles" and k == "actor":
                        for j, r in enumerate(listing(v)):
                            yield from role_ok(r, pw + (j,))
                        continue
                    if p == "name" and k == "actor":
                        yield "derived_in_given", pw, "name is fixed and cannot be given"
                        continue
                    if p not in props:
                        yield "unknown_name", pw, f"unknown name: {p}"
                        continue
                    if p in derived:
                        yield "derived_in_given", pw, f"{p} is derived and cannot be given"
                        continue
                    if p in computed:
                        yield "derived_in_given", pw, f"{p} is computed and cannot be given"
                        continue
                    yield from given_value(v, props[p], p, pw, givens, names, source)
            scope = dict(givens)
            for i, step in enumerate(listing(exm.get("steps"))):
                sw = where + ("steps", i)
                outcome_first = False
                if "when" in step and isinstance(step["when"], dict):
                    w = step["when"]
                    actor = w.get("actor")
                    if actor not in givens or names.get(actor) != "actor":
                        yield "unknown_name", sw + ("when", "actor"), f"unknown name: {actor}"
                    else:
                        scope["ACTOR"] = givens[actor]
                    c = Expr(P, {k: v for k, v in scope.items() if k not in ("RESULT", "RESULT_OP")})
                    rt = c.run(w["call"], call_slot=True) if isinstance(w.get("call"), str) else None
                    for rule, p in c.out:
                        yield rule, sw + ("when", "call"), p
                    outcome_first = True
                    then = listing(step.get("then"))
                    scope["RESULT"] = "NONE" if (then and isinstance(then[0], dict)) else rt
                    scope["RESULT_OP"] = c.outer.func.id if c.outer else "the operation"
                for j, item in enumerate(listing(step.get("then"))):
                    if j == 0 and outcome_first:
                        continue
                    if isinstance(item, str) and item != "DONE":
                        yield from ex(item, sw + ("then", j), scope)


def given_value(v, t, p, pw, givens, names, source):
    """problems of one with: value against its declared type; a value that may
    be of several types must fit one of them, quoting and names included"""
    if is_either(t):
        rest = [a for a in t[1] if a != "NONE"]
        if len(rest) == 1:
            yield from given_value(v, rest[0], p, pw, givens, names, source)
        elif rest and all(list(given_value(v, a, p, pw, givens, names, source)) for a in rest):
            yield "type_mismatch", pw, f"{p} expects {words(('either', frozenset(rest)))}: {v}"
        return
    if t is None:
        return
    if isinstance(v, list):
        if not is_list(t):
            yield "type_mismatch", pw, f"{p} expects {words(t)}: {v}"
            return
        for j, e in enumerate(v):
            yield from given_value(e, t[1], p, pw + (j,), givens, names, source)
        return
    if is_list(t):
        yield "type_mismatch", pw, f"{p} expects {words(t)}: {v}"
        return
    if isinstance(v, bool):
        if t != "YES_NO":
            yield "type_mismatch", pw, f"{p} expects {words(t)}: {v}"
        return
    if isinstance(v, (int, float)):
        if not (t == "NUMBER" or (t == "INTEGER" and isinstance(v, int))):
            yield "type_mismatch", pw, f"{p} expects {words(t)}: {v}"
        return
    if isinstance(v, str):
        plain = source.styles.get(pw) is None
        if t in ("TEXT", "TIME"):
            if plain:
                yield "unquoted_text", pw, f"quote the {p}; an unquoted # drops the rest of the line"
            return
        if not plain:
            yield "type_mismatch", pw, f"{p} expects {words(t)}: \"{v}\""
            return
        if is_choice(t):
            if t[1] and v not in t[1]:
                yield "unknown_status", pw, f"status not in its list: {v}"
            return
        if is_entity(t):
            if v not in givens:
                yield "unknown_name", pw, f"unknown name: {v}"
            elif names.get(v) != t[1]:
                yield "type_mismatch", pw, f"{p} expects {words(t)}: {v}"
            return
        yield "type_mismatch", pw, f"{p} expects {words(t)}: {v}"


# --- the history layer ----------------------------------------------------------

def normalise(text):
    """a block's text normalised (section 10): from its key line to the last
    line indented deeper, comments, blank lines and trailing spaces removed
    outside quoted text, quoting tracked across wrapped lines, re-indented so
    the key line starts at column 0"""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return ""
    indent = len(lines[0]) - len(lines[0].lstrip(" "))
    out, q = [], False
    for n, s in enumerate(lines):
        if not q:
            if s.strip() == "" or s.lstrip().startswith("#"):
                continue
            if n > 0 and len(s) - len(s.lstrip(" ")) <= indent:
                break
        kept, close = [], -2
        for i, c in enumerate(s):
            if c == '"':
                k = i - 1
                while k >= 0 and s[k] == "\\":
                    k -= 1
                if (i - 1 - k) % 2 == 0:
                    q = not q
                    if not q:
                        close = i
            if c == "#" and not q and (i == 0 or s[i - 1] == " " or close == i - 1):
                break
            kept.append(c)
        t = "".join(kept) if q else "".join(kept).rstrip()
        out.append(t[indent:] if t.startswith(" " * indent) else t)
    return "\n".join(out) + "\n"


SECTION = {"entity": "entities", "role": "roles", "story": "stories"}


def snapshot_ok(text, kind, name):
    """is text a self-contained snapshot of the block (section 10): already
    normalised, named on its first line, in the subset of section 2 with no
    duplicate key, and one block under the entry's name"""
    norm = normalise(text)
    first = norm.split("\n")[0]
    if norm != text or not (first == f"{name}:" or first.startswith(f"{name}: ")):
        return False
    wrapped = SECTION[kind] + ":\n" + "".join("  " + l + "\n" for l in text.split("\n")[:-1])
    try:
        src = Source(wrapped, False)
        if src.src or src.style:
            return False
        DUPLICATES.clear()
        data = yaml.load(wrapped, Loader=Core)
        src.duplicates = list(DUPLICATES)
        if DUPLICATES or schema_problems(V, SCHEMA, data, src) or shape_extra(data):
            return False
    except Exception:
        return False
    block = mapping(data).get(SECTION[kind])
    return isinstance(block, dict) and list(block) == [name] and isinstance(block[name], dict)


def history_problems(entries, P, source, stem):
    """the history layer of <stem>.edda.vc: bad_version (entries of the
    blocks of <stem>.edda only, numbered 1, 2, 3 per block, in file order),
    bad_pin (pins on a story entry only, each to a version that exists, no
    block twice) and bad_snapshot (snapshot_ok)"""
    out, count = [], {}
    kinds = {"story": P.stories, "entity": P.entities, "role": P.roles}
    for i, e in enumerate(listing(entries)):
        if not isinstance(e, dict):
            continue
        kind = "story" if "story" in e else "entity" if "entity" in e else "role"
        name, n = e.get(kind), e.get("number")
        line = source.line((i, "number"))
        if name not in kinds[kind]:
            out.append(("bad_version", line, f"{kind} {name} version {n}: no such {kind}"))
            continue
        if P.file_of(kind, name) != stem:
            out.append(("bad_version", line, f"{kind} {name} version {n}: belongs in {P.file_of(kind, name)}.edda.vc"))
            continue
        expected = count.get((kind, name), 0) + 1
        if n != expected:
            out.append(("bad_version", line, f"{kind} {name} version {n} out of sequence; expected {expected}"))
        count[(kind, name)] = n if isinstance(n, int) else expected
        pins = e.get("pins")
        if kind == "story":
            if not pins:
                out.append(("bad_pin", line, f"story {name} version {n}: no pins"))
            seen = set()
            for j, pin in enumerate(listing(pins)):
                if not isinstance(pin, dict):
                    continue
                pk = "entity" if "entity" in pin else "role"
                pname, pn = pin.get(pk), pin.get("number")
                pl = source.line((i, "pins", j), key=False)
                if pname not in kinds[pk]:
                    out.append(("bad_pin", pl, f"pin {pk} {pname} v{pn}: no such {pk}"))
                elif pn not in P.versions.get((pk, pname), ()):
                    out.append(("bad_pin", pl, f"pin {pk} {pname} v{pn}: no such version"))
                if (pk, pname) in seen:
                    out.append(("bad_pin", pl, f"pin {pk} {pname} v{pn}: pinned twice"))
                seen.add((pk, pname))
        elif "pins" in e:
            out.append(("bad_pin", source.line((i, "pins")), f"{kind} {name} version {n}: a block entry has no pins"))
        text = e.get("text")
        if isinstance(text, str) and not snapshot_ok(text, kind, name):
            out.append(("bad_snapshot", line, f"text of {kind} {name} v{n} is not a normalised block"))
    return out


# --- run ---------------------------------------------------------------------

KEY_LINE_RULES = {"returns_and_ensure", "wrong_file", "role_cycle", "wider_than_entity", "declared_twice"}


def load(path):
    """(source, data or None); data only when the file is YAML"""
    text = open(path).read()
    source = Source(text, path.endswith(".vc"))
    if source.src:
        return source, None
    DUPLICATES.clear()
    try:
        data = yaml.load(text, Loader=Core)
    except Exception as e:
        source.src.append(("not_yaml", 1, f"not YAML: {str(e).splitlines()[0]}"))
        return source, None
    source.duplicates = list(DUPLICATES)
    return source, data


def check(path, P):
    """returns (source, shape, meaning, history): lists of (rule, line, message), each sorted"""
    stem = os.path.basename(path).split(".")[0]
    source, data = load(path)
    if source.src:
        return sorted(set(source.src), key=lambda p: (p[1], p[0])), [], [], []
    is_vc = path.endswith(".vc")
    shape = list(source.style) + [("declared_twice", ln, f"declared twice: {k}") for k, ln in source.duplicates]
    shape += schema_problems(VC if is_vc else V, VC_SCHEMA if is_vc else SCHEMA, data, source)
    if not is_vc:
        shape += [(rule, source.line(where, at_key), msg) for rule, where, msg, at_key in shape_extra(data, source)]
        shape += [("declared_twice", source.line(where), f"declared twice: {name}") for where, name in P.dups.get(stem, [])]
    shape = sorted(set(shape), key=lambda p: (p[1], p[0]))
    meaning, history = [], []
    if shape:
        return [], shape, [], []
    if is_vc:
        history = sorted(set(history_problems(data, P, source, stem)), key=lambda p: (p[1], p[0]))
    else:
        meaning = [(rule, source.line(where, key=rule in KEY_LINE_RULES), msg)
                   for rule, where, msg in walk_meaning(data, stem, P, source)]
        meaning = sorted(set(meaning), key=lambda p: (p[1], p[0]))
    return [], shape, meaning, history


def project_of(folder):
    files, histories = [], []
    for path in sorted(glob.glob(f"{folder}/*.edda")):
        source, data = load(path)
        if isinstance(data, dict) and not schema_problems(V, SCHEMA, data, source) and not shape_extra(data):
            files.append((os.path.basename(path)[:-5], data))
    for path in sorted(glob.glob(f"{folder}/*.edda.vc")):
        source, data = load(path)
        if isinstance(data, list) and not schema_problems(VC, VC_SCHEMA, data, source):
            histories.append((os.path.basename(path)[:-8], data))
    return Project(files, histories)


if __name__ == "__main__":
    ok = True
    P = project_of(f"{ROOT}/specs")
    for path in sorted(glob.glob(f"{ROOT}/specs/*.edda") + glob.glob(f"{ROOT}/specs/*.edda.vc")):
        problems = sum(check(path, P), [])
        print(os.path.relpath(path, ROOT), "OK" if not problems else "")
        for rule, line, msg in problems:
            ok = False
            print(f"    {line}: {rule}: {msg}")

    print()
    print("fixtures: which layer catches each file")
    LAYERS = ("source", "shape", "meaning", "history")
    for folder in sorted(os.listdir(f"{ROOT}/fixtures")):
        FP = project_of(f"{ROOT}/fixtures/{folder}")
        for path in sorted(glob.glob(f"{ROOT}/fixtures/{folder}/*")):
            layers = check(path, FP)
            caught = [name for name, found in zip(LAYERS, layers) if found]
            print(f"  {folder}/{os.path.basename(path)}: {'caught by ' + caught[0] if caught else 'passes'}")
            for rule, line, msg in sum(layers, []):
                print(f"      {line}: {rule}: {msg}")
    sys.exit(0 if ok else 1)
