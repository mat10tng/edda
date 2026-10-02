#!/usr/bin/env python3
"""Check every .edda and .edda.vc file through the source, shape and
meaning layers of reference section 11: the YAML 1.2 subset and the
quoting rule, both JSON Schemas mapped to rule names and source lines,
the type-phrase grammar, names resolved across the files of one folder
(entities, roles, operations, properties, choice values, givens), the
Python expression whitelist (7.1) with types from literals and
declarations, operation signatures, the style rule (7.2) under its
equivalences, and the operation key rules. A partial checker: the
history layer, the flags, not_ordered and the running of examples are
not here. Each folder (specs/, one fixture folder) is one project."""
import ast, glob, json, os, re, sys
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
    "stories/*/operations/*/who/#/role", "stories/*/operations/*/also_changes/#",
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
        self.src, self.style, self.marks, self.styles = [], [], {}, {}
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
             "number": "number", "boolean": "yes/no"}


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
    with a source line; a missing key is suppressed in a block that has
    an unknown key"""
    out, unknown_in = [], set()
    is_vc = validator is VC

    def add(rule, path, msg, key=True):
        out.append((rule, source.line(path, key), msg))

    def adapt(err, path):
        v = err.validator
        key = key_name(path)
        if v in ("anyOf", "oneOf"):
            branches = [resolve(b, root) for b in err.validator_value]
            kinds = [b.get("type") for b in branches]
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
                add("wrong_type", path, f"{key} must be a {KIND_WORD.get(inst, inst)} of the right shape", key=False)
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
        if v in ("const", "not"):
            add("wrong_type", path, f"{key} expects an expression, not DONE", key=False)
            return
        if v == "propertyNames":
            name = err.context[0].instance if err.context else "?"
            add("bad_name", path + (name,), f"not a name: {name}")
            return
        if v in ("pattern", "enum"):
            add("bad_name", path, f"not a name: {err.instance}", key=False)
            return
        if err.context:
            for c in err.context:
                adapt(c, path + tuple(c.relative_path))
        else:
            add("wrong_type", path, f"{key} must be a {KIND_WORD.get(yaml_kind(err.instance), 'value')} of the right shape", key=False)

    for err in validator.iter_errors(data):
        adapt(err, tuple(err.absolute_path))
    hidden = {source.line(u) for u in unknown_in}
    out = [p for p in out if not (p[0] == "missing_key" and p[1] in hidden)]
    return list(dict.fromkeys(out))


# --- types -----------------------------------------------------------------
# a type is "INTEGER", "NUMBER", "TEXT", "TIME", "YES_NO", "NONE",
# ("choice", values or None), ("list", element type), ("entity", name),
# or None when unknown

STR_LIT = r'"(?:[^"\\]|\\.)*"'
TYPE_RE = re.compile(
    rf"(?:DEFAULT (?:-?[0-9]+(?:\.[0-9]+)?|{STR_LIT}|True|False|(?P<dchoice>{NAME}(?: \| {NAME})+))(?:, DERIVED)?"
    rf"|(?:TEXT|NUMBER|INTEGER|TIME|YES_NO|(?P<choice>{NAME}(?: \| {NAME})+)|(?P<ref>{NAME})|MANY (?P<many>{NAME})(?:, IN ORDER)?)(?:, OPTIONAL)?(?:, DERIVED)?)")
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
        for x in vals:
            if x in PY_KEYWORDS:
                return [("bad_name", f"not a name: {x}")]
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
        return ("choice", tuple(m.group("dchoice").split(" | ")))
    if m.group("choice"):
        return ("choice", tuple(m.group("choice").split(" | ")))
    if m.group("many"):
        return ("list", ("entity", m.group("many")))
    if m.group("ref"):
        return ("entity", m.group("ref"))
    core = re.sub(r", (OPTIONAL|DERIVED)$", "", re.sub(r", (OPTIONAL|DERIVED)$", "", v))
    if core.startswith("DEFAULT "):
        lit = core[8:]
        if re.fullmatch(r"-?[0-9]+", lit):
            return "INTEGER"
        if re.fullmatch(r"-?[0-9]+\.[0-9]+", lit):
            return "NUMBER"
        if lit in ("True", "False"):
            return "YES_NO"
        return "TEXT"
    return core if core in SCALARS else None


def is_list(t):
    return isinstance(t, tuple) and t[0] == "list"


def is_entity(t):
    return isinstance(t, tuple) and t[0] == "entity"


def is_choice(t):
    return isinstance(t, tuple) and t[0] == "choice"


def unify(a, b):
    """the type of a value that is either a or b"""
    if a == b:
        return a
    if a is None or b is None:
        return None
    if a == "NONE":
        return b
    if b == "NONE":
        return a
    if {a, b} == {"INTEGER", "NUMBER"}:
        return "NUMBER"
    if is_list(a) and is_list(b):
        if a[1] is None:
            return b
        if b[1] is None:
            return a
        e = unify(a[1], b[1])
        return ("list", e) if e is not None else None
    if is_choice(a) and is_choice(b):
        return ("choice", None)
    return None


def compatible(given, expected):
    """may a value of type given stand where expected is declared"""
    if given is None or expected is None or given == "NONE":
        return True
    if given == expected:
        return True
    if given == "INTEGER" and expected == "NUMBER":
        return True
    if is_choice(given) and is_choice(expected):
        return True
    if is_list(given) and is_list(expected):
        return given[1] is None or compatible(given[1], expected[1])
    return False


def words(t):
    if t is None:
        return "a value"
    if t == "NONE":
        return "nothing"
    if isinstance(t, str):
        return ("an " if t[0] in "AEIOU" else "a ") + t
    if is_choice(t):
        return "a choice value"
    if is_list(t):
        return "MANY " + (t[1][1] if is_entity(t[1]) else str(t[1]))
    return ("an " if t[1][0] in "aeiou" else "a ") + t[1]


# --- the project: declarations across the files of one folder ---------------

class Project:
    def __init__(self, files):
        """files: list of (stem, data) for every .edda that passed the shape layer"""
        self.entities, self.roles, self.operations, self.epics, self.choices = {}, {}, {}, set(), set()
        self.actor = {"name": "TEXT", "roles": ("list", "TEXT")}
        for stem, data in files:
            for rname, role in (data.get("roles") or {}).items():
                has = {p: type_of_phrase(v) for p, v in (role.get("has") or {}).items()}
                self.roles[rname] = {"has": has, "includes": list(role.get("includes") or []), "file": stem}
                self.actor.update(has)
            for ename, ent in (data.get("entities") or {}).items():
                props, derived, computed = {}, set(), {}
                for p, v in (ent.get("properties") or {}).items():
                    if isinstance(v, dict):
                        props[p] = None
                        computed[p] = v.get("computed")
                    else:
                        props[p] = type_of_phrase(v)
                        if isinstance(v, str) and v.endswith(", DERIVED"):
                            derived.add(p)
                        if is_choice(props[p]):
                            self.choices.update(props[p][1])
                may = {}
                for key in ("may_create", "may_read", "may_update", "may_delete"):
                    may[key] = [w.get("role") for w in (ent.get(key) or []) if isinstance(w, dict)]
                self.entities[ename] = {"props": props, "derived": derived, "computed": computed, "may": may, "file": stem}
            self.epics.update((data.get("epics") or {}).keys())
            for sid, st in (data.get("stories") or {}).items():
                for oname, op in (st.get("operations") or {}).items():
                    inputs = []
                    for n, v in (op.get("inputs") or {}).items():
                        inputs.append((n, type_of_phrase(v), isinstance(v, str) and ", OPTIONAL" in v))
                    self.operations[oname] = {"inputs": inputs, "returns": op.get("returns"), "returns_type": None,
                                              "story": sid, "file": stem}
        for _ in range(4):      # computed properties, in dependency order
            changed = False
            for ename, ent in self.entities.items():
                for p, expr in ent["computed"].items():
                    if ent["props"][p] is None and isinstance(expr, str):
                        t = Expr(self, dict(ent["props"]), silent=True).run(expr)
                        if t is not None:
                            ent["props"][p] = t
                            changed = True
            if not changed:
                break
        for op in self.operations.values():
            if isinstance(op["returns"], str):
                op["returns_type"] = Expr(self, {n: t for n, t, _ in op["inputs"]}, silent=True).run(op["returns"])

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

    def role_cycles(self):
        out = set()
        for start in self.roles:
            seen, stack = set(), list(self.roles[start]["includes"])
            while stack:
                r = stack.pop()
                if r == start:
                    out.add(start)
                    break
                if r in seen or r not in self.roles:
                    continue
                seen.add(r)
                stack.extend(self.roles[r]["includes"])
        return out


# --- the expression checker ---------------------------------------------------

GEN_ONLY = {"sum", "min", "max", "any", "all"}
ONE_ARG = {"len", "OLD"}
OP_WORD = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


class Expr:
    """checks one expression and gives its type; problems as (rule, message)"""

    def __init__(self, project, scope, allow_old=False, in_fact=True, silent=False):
        self.P, self.scope, self.allow_old, self.in_fact, self.silent = project, scope, allow_old, in_fact, silent
        self.out, self.src = [], ""

    def problem(self, rule, msg):
        if not self.silent:
            self.out.append((rule, msg))

    def seg(self, n):
        return ast.get_source_segment(self.src, n) or "..."

    def second(self, new, old):
        text = ast.unparse(new)
        for c in ast.walk(new):      # Edda writes text literals with double quotes
            if isinstance(c, ast.Constant) and isinstance(c.value, str):
                text = text.replace(repr(c.value), '"' + c.value.replace('"', '\\"') + '"', 1)
        self.problem("second_way", f"write {text} (not {self.seg(old)})")

    def quiet(self, n, scope):
        """the type of a node without reporting, for a rewrite's guard"""
        silent = Expr(self.P, scope, self.allow_old, self.in_fact, silent=True)
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
        return self.visit(body, self.scope)

    def status(self, name, other, scope):
        """type a bare name compared with a value of type other"""
        if is_choice(other):
            if other[1] and name.id not in other[1]:
                self.problem("unknown_status", f"status not in its list: {name.id}")
            return ("choice", None)
        return self.visit(name, scope)

    def comprehension(self, generators, scope):
        inner = dict(scope)
        for g in generators:
            it = self.visit(g.iter, inner)
            if g.is_async:
                self.problem("not_an_expression", f"not an expression (async): {self.src}")
            if not isinstance(g.target, ast.Name):
                self.problem("not_an_expression", f"not an expression (a comprehension variable is a plain name): {self.src}")
                continue
            if it is not None and not is_list(it):
                self.problem("type_mismatch", f"for expects a list: {self.src}")
                inner[g.target.id] = None
            else:
                inner[g.target.id] = it[1] if it else None
            for c in g.ifs:
                self.visit(c, inner)
        return inner

    def visit(self, n, scope):
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
                return ("entity", "actor")
            if i in ("NOW", "TODAY"):
                return "TIME"
            if i == "RESULT":
                return scope.get("RESULT")
            if i in scope:
                return scope[i]
            if i in P.choices:
                return ("choice", None)
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
            if t == ("entity", "actor"):
                if n.attr not in P.actor:
                    self.problem("unknown_name", f"unknown name: {n.attr}")
                return P.actor.get(n.attr)
            if is_entity(t) and t[1] in P.entities:
                props = P.entities[t[1]]["props"]
                if n.attr not in props:
                    self.problem("unknown_name", f"unknown name: {n.attr}")
                return props.get(n.attr)
            return None
        if isinstance(n, ast.Subscript):
            t = self.visit(n.value, scope)
            s = n.slice
            if isinstance(s, ast.Slice):
                if s.step is not None:
                    self.problem("not_an_expression", f"not an expression (slice step): {src}")
                for b in (s.lower, s.upper):
                    if b is not None and self.visit(b, scope) not in (None, "INTEGER"):
                        self.problem("type_mismatch", f"a slice bound expects an INTEGER: {src}")
                if t is not None and not (is_list(t) or t == "TEXT"):
                    self.problem("type_mismatch", f"a slice expects a list or a text: {src}")
                return t if is_list(t) or t == "TEXT" else None
            st = self.visit(s, scope)
            if st not in (None, "INTEGER"):
                self.problem("type_mismatch", f"an index expects an INTEGER: {src}")
            elif isinstance(s, ast.BinOp) and isinstance(s.op, ast.Sub) and isinstance(s.left, ast.Call) \
                    and isinstance(s.left.func, ast.Name) and s.left.func.id == "len" and len(s.left.args) == 1 \
                    and isinstance(s.right, ast.Constant) and s.right.value == 1 and not isinstance(s.right.value, bool) \
                    and ast.dump(s.left.args[0]) == ast.dump(n.value):
                self.second(ast.Subscript(n.value, ast.UnaryOp(ast.USub(), ast.Constant(1)), ast.Load()), n)
            if is_list(t):
                return t[1]
            if t == "TEXT":
                return "TEXT"
            if t is not None:
                self.problem("type_mismatch", f"an index expects a list or a text: {src}")
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
            # a bare name beside a choice property is a status value: in its list or unknown_status
            def bare(b):
                return isinstance(b, ast.Name) and b.id not in scope and b.id not in P.operations \
                    and b.id not in ("RESULT", "ACTOR", "NOW", "TODAY") and re.fullmatch(NAME, b.id)
            if bare(right) and not bare(left):
                lt = self.visit(left, scope)
                rt = self.status(right, lt, scope)
            elif bare(left) and not bare(right):
                rt = self.visit(right, scope)
                lt = self.status(left, rt, scope)
            else:
                lt, rt = self.visit(left, scope), self.visit(right, scope)
            neg = isinstance(op, ast.NotEq)
            # len(x) == 0, len(x) != 0, len(x) > 0, only for a list
            if isinstance(left, ast.Call) and isinstance(left.func, ast.Name) and left.func.id == "len" \
                    and len(left.args) == 1 and isinstance(right, ast.Constant) and right.value == 0 \
                    and not isinstance(right.value, bool) and is_list(self.quiet(left.args[0], scope)):
                x = left.args[0]
                if isinstance(op, ast.Eq):
                    self.second(ast.Compare(x, [ast.Eq()], [ast.List([], ast.Load())]), n)
                elif isinstance(op, (ast.NotEq, ast.Gt)):
                    self.second(ast.Compare(x, [ast.NotEq()], [ast.List([], ast.Load())]), n)
            # x == None, None == x
            for a, b in ((left, right), (right, left)):
                if isinstance(b, ast.Constant) and b.value is None and isinstance(op, (ast.Eq, ast.NotEq)):
                    self.second(ast.Compare(a, [ast.IsNot() if neg else ast.Is()], [ast.Constant(None)]), n)
                    break
            # x == True / False, True == x, only for a yes/no
            for a, at, b in ((left, lt, right), (right, rt, left)):
                if isinstance(b, ast.Constant) and isinstance(b.value, bool) and isinstance(op, (ast.Eq, ast.NotEq)) \
                        and at == "YES_NO":
                    holds = b.value != neg
                    self.second(a if holds else ast.UnaryOp(ast.Not(), a), n)
                    break
            # x[:n] == "t" where "t" has n characters, x a text
            if isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Slice) and left.slice.lower is None \
                    and left.slice.step is None and isinstance(left.slice.upper, ast.Constant) \
                    and type(left.slice.upper.value) is int and isinstance(op, (ast.Eq, ast.NotEq)) \
                    and isinstance(right, ast.Constant) and isinstance(right.value, str) \
                    and len(right.value) == left.slice.upper.value and self.quiet(left.value, scope) == "TEXT":
                call = ast.Call(ast.Attribute(left.value, "startswith", ast.Load()), [right], [])
                self.second(ast.UnaryOp(ast.Not(), call) if neg else call, n)
            return "YES_NO"
        if isinstance(n, ast.BoolOp):
            t = None
            for i, v in enumerate(n.values):
                vt = self.visit(v, scope)
                t = vt if i == 0 else unify(t, vt)
            return t
        if isinstance(n, ast.UnaryOp):
            t = self.visit(n.operand, scope)
            if isinstance(n.op, ast.Not):
                if is_list(t):
                    self.second(ast.Compare(n.operand, [ast.Eq()], [ast.List([], ast.Load())]), n)
                return "YES_NO"
            if isinstance(n.op, ast.USub):
                if t not in (None, "INTEGER", "NUMBER"):
                    self.problem("type_mismatch", f"- expects a number: {src}")
                return t if t in ("INTEGER", "NUMBER") else None
            self.problem("not_an_expression", f"not an expression ({type(n.op).__name__}): {src}")
            return None
        if isinstance(n, ast.BinOp):
            lt, rt = self.visit(n.left, scope), self.visit(n.right, scope)
            if type(n.op) not in OP_WORD:
                self.problem("not_an_expression", f"not an expression ({type(n.op).__name__}): {src}")
                return None
            if isinstance(n.op, ast.Add) and (is_list(lt) or is_list(rt)):
                if lt is not None and rt is not None and not (is_list(lt) and is_list(rt)):
                    self.problem("type_mismatch", f"+ expects two lists or two numbers: {src}")
                    return None
                return unify(lt, rt) if (lt is not None and rt is not None) else (lt or rt)
            for t in (lt, rt):
                if t not in (None, "INTEGER", "NUMBER"):
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
            t = None
            for i, e in enumerate(n.elts):
                et = self.visit(e, scope)
                t = et if i == 0 else unify(t, et)
            return ("list", t)
        if isinstance(n, ast.ListComp):
            inner = self.comprehension(n.generators, scope)
            return ("list", self.visit(n.elt, inner))
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
                if rt not in (None, "TEXT") or at not in (None, "TEXT"):
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
                inner = self.comprehension(g.generators, scope)
                et = self.visit(g.elt, inner)
                if f.id == "sum" and isinstance(g.elt, ast.Constant) and g.elt.value == 1 and len(g.generators) == 1 \
                        and not g.generators[0].ifs:
                    self.second(ast.Call(ast.Name("len", ast.Load()), [g.generators[0].iter], []), n)
                if f.id in ("any", "all"):
                    return "YES_NO"
                if f.id == "sum" and et not in (None, "INTEGER", "NUMBER"):
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
                    if at is not None and not (is_list(at) or at == "TEXT"):
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
                    if not compatible(at, itype):
                        self.problem("type_mismatch", f"{f.id} input {iname} expects {words(itype)}: {src}")
                for a in n.args[len(req):]:
                    self.visit(a, scope)
                seen = set()
                for kw in n.keywords:
                    if kw.arg is None or kw.arg not in opt:
                        self.problem("type_mismatch", f"{f.id} has no optional input {kw.arg}: {src}")
                        self.visit(kw.value, scope)
                    elif kw.arg in seen:
                        self.problem("type_mismatch", f"{f.id} input {kw.arg} given twice: {src}")
                    else:
                        seen.add(kw.arg)
                        at = self.visit(kw.value, scope)
                        if not compatible(at, opt[kw.arg]):
                            self.problem("type_mismatch", f"{f.id} input {kw.arg} expects {words(opt[kw.arg])}: {src}")
                if self.in_fact and op["returns"] is None:
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
                yield "wrong_type", where, "a type phrase was expected, nothing was given"
                return
            for rule, p in type_phrase_problems(v):
                yield rule, where, p
            e = phrase_entity(v)
            if e and e not in P.entities:
                yield "unknown_name", where, f"unknown name: {e}"

    def ex(v, where, scope, allow_old=False, in_fact=True, call_slot=False):
        if isinstance(v, str):
            if v == "":
                yield "wrong_type", where, "an expression was expected, nothing was given"
                return
            c = Expr(P, scope, allow_old, in_fact)
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

    cycles = P.role_cycles()
    for rname, role in (data.get("roles") or {}).items():
        if rname in PY_KEYWORDS:
            yield "bad_name", ("roles", rname), f"not a name: {rname}"
        for p, v in (role.get("has") or {}).items():
            yield from tp(v, ("roles", rname, "has", p))
        for i, inc in enumerate(role.get("includes") or []):
            yield from role_ok(inc, ("roles", rname, "includes", i))
        if rname in cycles:
            yield "role_cycle", ("roles", rname, "includes"), f"role {rname} includes itself"
            cycles = set()      # the first role in file order only
    for ename, ent in (data.get("entities") or {}).items():
        props = P.entities.get(ename, {}).get("props", {})
        own = dict(props)
        if "part_of" in ent and ent["part_of"] not in P.entities:
            yield "unknown_name", ("entities", ename, "part_of"), f"unknown name: {ent['part_of']}"
        for p, v in (ent.get("properties") or {}).items():
            if p in PY_KEYWORDS:
                yield "bad_name", ("entities", ename, "properties", p), f"not a name: {p}"
            if isinstance(v, dict):
                yield from ex(v.get("computed"), ("entities", ename, "properties", p, "computed"), own)
            else:
                yield from tp(v, ("entities", ename, "properties", p))
        for p, arrows in (ent.get("may_change") or {}).items():
            where = ("entities", ename, "may_change", p)
            if p not in props:
                yield "unknown_name", where, f"unknown name: {p}"
                continue
            vals = props[p][1] if is_choice(props[p]) else None
            for frm, tos in (arrows or {}).items():
                if vals is not None and frm not in vals:
                    yield "unknown_status", where + (frm,), f"status not in its list: {frm}"
                for i, s in enumerate(tos or []):
                    if vals is not None and s not in vals:
                        yield "unknown_status", where + (frm, i), f"status not in its list: {s}"
        for p, per_value in (ent.get("wording") or {}).items():
            where = ("entities", ename, "wording", p)
            if p not in props:
                yield "unknown_name", where, f"unknown name: {p}"
                continue
            vals = props[p][1] if is_choice(props[p]) else None
            for val, per_role in (per_value or {}).items():
                if vals is not None and val not in vals:
                    yield "unknown_status", where + (val,), f"status not in its list: {val}"
                for r in (per_role or {}):
                    yield from role_ok(r, where + (val, r))
        for i, f in enumerate(ent.get("always") or []):
            yield from fact(f, ("entities", ename, "always", i), own)
        for i, w in enumerate(ent.get("while") or []):
            yield from ex(w.get("when"), ("entities", ename, "while", i, "when"), own)
            yield from fact(w.get("holds"), ("entities", ename, "while", i, "holds"), own)
        for key in ("may_create", "may_read", "may_update", "may_delete"):
            for i, w in enumerate(ent.get(key) or []):
                yield from role_ok(w.get("role"), ("entities", ename, key, i))
                if "when" in w:
                    yield from ex(w["when"], ("entities", ename, key, i, "when"), {ename: ("entity", ename)})
    for sid, st in (data.get("stories") or {}).items():
        about = st.get("about")
        if about not in P.entities:
            yield "unknown_name", ("stories", sid, "about"), f"unknown name: {about}"
        elif P.entities[about]["file"] != stem:
            yield "wrong_file", ("stories", sid), f"story {sid} is about {about} and belongs in {about}.edda"
        yield from role_ok(st.get("as_a"), ("stories", sid, "as_a"))
        if "epic" in st and st["epic"] not in P.epics:
            yield "unknown_name", ("stories", sid, "epic"), f"unknown name: {st['epic']}"
        admitted = P.admitted(about)
        for oname, op in (st.get("operations") or {}).items():
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
            for n, v in (op.get("inputs") or {}).items():
                if n in PY_KEYWORDS:
                    yield "bad_name", where + ("inputs", n), f"not a name: {n}"
                yield from tp(v, where + ("inputs", n))
                inputs[n] = type_of_phrase(v)
            for i, w in enumerate(op.get("who") or []):
                r = w.get("role")
                yield from role_ok(r, where + ("who", i))
                if admitted is not None and r in P.roles and r not in admitted:
                    yield "wider_than_entity", where + ("who", i), f"{oname} admits {r}, which {about} does not"
                if "when" in w:
                    yield from ex(w["when"], where + ("who", i, "when"), inputs)
            for i, r in enumerate(op.get("refuse") or []):
                yield from ex(r.get("when"), where + ("refuse", i, "when"), inputs)
            for i, f in enumerate(op.get("ensure") or []):
                yield from fact(f, where + ("ensure", i), inputs, allow_old=True)
            yield from ex(op.get("returns"), where + ("returns",), inputs)
            rt = P.operations.get(oname, {}).get("returns_type")
            item_scope = dict(inputs)
            if is_list(rt) and is_entity(rt[1]):
                item_scope[rt[1][1]] = rt[1]
            for i, o in enumerate(op.get("ordered_by") or []):
                yield from ex(o, where + ("ordered_by", i), item_scope)
            for i, p in enumerate(op.get("also_changes") or []):
                root = p.split(".")[0] if isinstance(p, str) else ""
                if root not in inputs:
                    yield "unknown_name", where + ("also_changes", i), f"unknown name: {root}"
        for title, exm in (st.get("examples") or {}).items():
            where = ("stories", sid, "examples", title)
            givens, names = {}, {}
            for i, g in enumerate(exm.get("given") or []):      # names first: givens are order-independent
                for k, v in g.items():
                    if k != "with" and isinstance(v, str):
                        if v in givens:
                            yield "declared_twice", where + ("given", i), f"declared twice: {v}"
                        givens[v] = ("entity", "actor") if k == "actor" else ("entity", k)
                        names[v] = k
            for i, g in enumerate(exm.get("given") or []):
                gw = where + ("given", i)
                kind = [k for k in g if k != "with"]
                if not kind:
                    continue
                k = kind[0]
                if k != "actor" and k not in P.entities:
                    yield "unknown_name", gw, f"unknown name: {k}"
                    continue
                props = P.actor if k == "actor" else P.entities[k]["props"]
                derived = set() if k == "actor" else P.entities[k]["derived"]
                for p, v in (g.get("with") or {}).items():
                    pw = gw + ("with", p)
                    if p == "fixture" and k != "actor":
                        if not os.path.isdir(f"{ROOT}/fixtures/{v}"):
                            yield "unknown_name", pw, f"unknown name: {v}"
                        continue
                    if p == "roles" and k == "actor":
                        for j, r in enumerate(v if isinstance(v, list) else [v]):
                            yield from role_ok(r, pw + ((j,) if isinstance(v, list) else ()))
                        continue
                    if p not in props:
                        yield "unknown_name", pw, f"unknown name: {p}"
                        continue
                    if p in derived:
                        yield "derived_in_given", pw, f"{p} is derived and cannot be given"
                        continue
                    yield from given_value(v, props[p], p, pw, givens, names, source)
            scope = dict(givens)
            for i, step in enumerate(exm.get("steps") or []):
                sw = where + ("steps", i)
                outcome_first = False
                if "when" in step and isinstance(step["when"], dict):
                    w = step["when"]
                    actor = w.get("actor")
                    if actor not in givens or names.get(actor) != "actor":
                        yield "unknown_name", sw + ("when", "actor"), f"unknown name: {actor}"
                    c = Expr(P, scope, in_fact=False)
                    rt = c.run(w["call"], call_slot=True) if isinstance(w.get("call"), str) else None
                    for rule, p in c.out:
                        yield rule, sw + ("when", "call"), p
                    outcome_first = True
                    then = step.get("then") or []
                    scope["RESULT"] = "NONE" if (then and isinstance(then[0], dict)) else rt
                for j, item in enumerate(step.get("then") or []):
                    if j == 0 and outcome_first:
                        continue
                    if isinstance(item, str) and item != "DONE":
                        yield from ex(item, sw + ("then", j), scope)


def given_value(v, t, p, pw, givens, names, source):
    """problems of one with: value against its declared type"""
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
    """returns (source, shape, meaning): lists of (rule, line, message), each sorted"""
    stem = os.path.basename(path).split(".")[0]
    source, data = load(path)
    if source.src:
        return sorted(set(source.src), key=lambda p: (p[1], p[0])), [], []
    is_vc = path.endswith(".vc")
    shape = list(source.style) + [("declared_twice", ln, f"declared twice: {k}") for k, ln in source.duplicates]
    shape += schema_problems(VC if is_vc else V, VC_SCHEMA if is_vc else SCHEMA, data, source)
    shape = sorted(set(shape), key=lambda p: (p[1], p[0]))
    meaning = []
    if not is_vc and not shape:
        meaning = [(rule, source.line(where, key=rule in KEY_LINE_RULES), msg)
                   for rule, where, msg in walk_meaning(data, stem, P, source)]
        meaning = sorted(set(meaning), key=lambda p: (p[1], p[0]))
    return [], shape, meaning


def project_of(folder):
    files = []
    for path in sorted(glob.glob(f"{folder}/*.edda")):
        source, data = load(path)
        if isinstance(data, dict) and not schema_problems(V, SCHEMA, data, source):
            files.append((os.path.basename(path)[:-5], data))
    return Project(files)


if __name__ == "__main__":
    ok = True
    P = project_of(f"{ROOT}/specs")
    for path in sorted(glob.glob(f"{ROOT}/specs/*.edda") + glob.glob(f"{ROOT}/specs/*.edda.vc")):
        src, shape, meaning = check(path, P)
        problems = src + shape + meaning
        print(os.path.relpath(path, ROOT), "OK" if not problems else "")
        for rule, line, msg in problems:
            ok = False
            print(f"    {line}: {rule}: {msg}")

    print()
    print("fixtures: which the source, shape and meaning layers catch")
    for folder in sorted(os.listdir(f"{ROOT}/fixtures")):
        FP = project_of(f"{ROOT}/fixtures/{folder}")
        for path in sorted(glob.glob(f"{ROOT}/fixtures/{folder}/*")):
            src, shape, meaning = check(path, FP)
            layer = "source" if src else "shape" if shape else "meaning" if meaning else None
            print(f"  {folder}/{os.path.basename(path)}: {'caught by ' + layer if layer else 'passes'}")
            for rule, line, msg in src + shape + meaning:
                print(f"      {line}: {rule}: {msg}")
    sys.exit(0 if ok else 1)
