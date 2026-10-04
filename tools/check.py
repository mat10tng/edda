#!/usr/bin/env python3
"""Check every .edda and .edda.vc file through the layers of reference
section 11: the YAML 1.2 subset and the quoting rule (source), both
JSON Schemas mapped to rule names and source lines plus duplicate
names (shape), names resolved across the files of one folder, the
type-phrase grammar, the Python expression whitelist (7.1) with types
from literals and declarations, operation signatures and ordering
(meaning), and the version
sequence, the pins and the snapshots of a .edda.vc (history), then the
flags of a .edda that passed them. A partial checker: the running of
examples is not here. Each folder (specs/, one fixture folder) is one project."""
import ast, copy, datetime, glob, json, os, re, sys
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
    "roles/*/is", "entities/*/is", "epics/*",
    "stories/*/story", "stories/*/i_want", "stories/*/so_that",
    "stories/*/rules/#/rule", "stories/*/rules/#/shown_by/#",
    "stories/*/notes/#", "stories/*/questions/#",
    "stories/*/operations/*/is", "stories/*/operations/*/notes/#",
    "stories/*/operations/*/refuse/#/reason", "stories/*/operations/*/ensure/#/means",
    "entities/*/always/#/means",
    "stories/*/examples/*/notes/#",
    "stories/*/examples/*/steps/#/then/#/refused",
    "stories/*/examples/*/steps/#/when/at",
]
EXPR_PATHS = [
    "entities/*/properties/*/computed",
    "entities/*/always/#", "entities/*/always/#/fact",
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
TYPE_PATHS = ["roles/*/properties/*", "entities/*/properties/*", "stories/*/operations/*/inputs/*"]
NAME_PATHS = [
    "stories/*/about", "stories/*/as_a", "stories/*/epic", "stories/*/tags/#",
    "entities/*/part_of",
    "entities/*/may_create/#/role", "entities/*/may_read/#/role",
    "entities/*/may_update/#/role", "entities/*/may_delete/#/role",
    "entities/*/may_change/*/*/#",
    "stories/*/operations/*/who/#/role",
    "stories/*/examples/*/given/#/*",
    "stories/*/examples/*/given/#/with/roles/#", "stories/*/examples/*/given/#/with/fixture",
    "stories/*/examples/*/steps/#/when/actor",
]
TITLE_PATHS = ["stories/*/examples/*"]
BLOCK_PATHS = ["roles", "entities", "stories", "roles/*", "entities/*", "stories/*",
               "stories/*/operations/*", "stories/*/examples/*"]     # written out, one key per line, never in flow form
TITLE_REF_PATHS = ["stories/*/rules/#/shown_by/#"]     # an example title as a value
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
        self.text = text
        if "\t" in text:
            self.src.append(("yaml_feature", text[:text.index("\t")].count("\n") + 1, "tabs are not allowed"))
        try:
            tokens = list(yaml.scan(text))
        except yaml.YAMLError as e:
            self.src.append(("not_yaml", getattr(getattr(e, "problem_mark", None), "line", 0) + 1,
                             f"not YAML: {str(e).splitlines()[0]}"))
            return
        self.explicit = set()           # where a key written after an explicit ? starts
        for t, nxt in zip(tokens, tokens[1:]):
            if isinstance(t, yaml.KeyToken) and text[t.start_mark.index:t.start_mark.index + 1] == "?":
                self.explicit.add(nxt.start_mark.index)
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

    def walk(self, node, path, in_flow=False):
        if id(node) in self.seen:       # an alias back to an anchor: reported once, at the anchor
            return
        self.seen.add(id(node))
        line = node.start_mark.line + 1
        if (not self.is_vc and not in_flow and getattr(node, "flow_style", False)
                and any_match(path, BLOCK_PATHS)):
            self.src.append(("yaml_feature", self.line(path), "a block is written one key per line, not in { } or [ ]"))
            in_flow = True              # once per block written in flow form, at its key
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                kline = k.start_mark.line + 1
                if not isinstance(k, yaml.ScalarNode):
                    self.src.append(("yaml_feature", kline, "a complex key is not allowed"))
                    continue
                if k.value == "<<":
                    self.src.append(("yaml_feature", kline, "the << key is not allowed"))
                if (k.start_mark.index in self.explicit
                        or self.text[k.end_mark.index:k.end_mark.index + 1] != ":"):
                    self.src.append(("yaml_feature", kline, "a key is written name: with no ? and no space before the colon"))
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
                self.walk(v, kpath, in_flow)
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                self.marks[path + (i,)] = (v.start_mark.line + 1, v.start_mark.line + 1)
                self.walk(v, path + (i,), in_flow)
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
                    self.src.append(("yaml_feature", line, "a | scalar is allowed only for text in .edda.vc"))
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
            if any_match(path, TITLE_REF_PATHS) and multiline:
                self.src.append(("yaml_feature", line, "an example title is one line"))

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
        "pins": "pin", "ordered_by": "expression", "also_changes": "path",
        "tags": "tag", "roles": "role", "rules": "rule", "shown_by": "example"}
COLLECTION = {"roles": "role", "entities": "entity", "stories": "story", "operations": "operation",
              "examples": "example", "properties": "property", "inputs": "input"}
KIND_WORD = {"object": "mapping", "array": "list", "string": "text", "integer": "number",
             "number": "number", "boolean": "yes/no", "null": "value"}


def block_name(path, is_vc):
    if not path:
        return "file"
    last = path[-1]
    if isinstance(last, int):
        if len(path) == 1 and is_vc:
            return f"version {last + 1}"
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
            add("wrong_type", path, f"{key} expects a text, no value was given", key=False)
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
    """shape-layer checks beside the schema: a given name used twice, an
    example named twice under rules, a role property named name or roles, a
    role-list item that is no name, a Python keyword as a choice value;
    yields (rule, path, message, at_key)"""
    out = []

    def phrase(v, path):
        if isinstance(v, str) and " | " in v:
            core = re.sub(r"^DEFAULT ", "", re.sub(r"(, (OPTIONAL|DERIVED))+$", "", v))
            for x in core.split(" | "):
                if x in PY_KEYWORDS:
                    out.append(("bad_name", path, f"not a name: {x}", False))

    for rname, role in mapping(mapping(data).get("roles")).items():
        for p, v in mapping(mapping(role).get("properties")).items():
            if p in ("name", "roles"):
                out.append(("declared_twice", ("roles", rname, "properties", p), f"declared twice: {p}", True))
            phrase(v, ("roles", rname, "properties", p))
    for ename, ent in mapping(mapping(data).get("entities")).items():
        for p, v in mapping(mapping(ent).get("properties")).items():
            phrase(v, ("entities", ename, "properties", p))
    for sid, st in mapping(mapping(data).get("stories")).items():
        for oname, op in mapping(mapping(st).get("operations")).items():
            for n, v in mapping(mapping(op).get("inputs")).items():
                phrase(v, ("stories", sid, "operations", oname, "inputs", n))
        named = set()
        for i, r in enumerate(listing(mapping(st).get("rules"))):
            for j, t in enumerate(listing(mapping(r).get("shown_by"))):
                if isinstance(t, str):
                    if t in named:
                        out.append(("declared_twice", ("stories", sid, "rules", i, "shown_by", j), f"declared twice: {t}", True))
                    named.add(t)
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

STR_LIT = r'"[^"]*"'     # text as written: a backslash is a character, no quote inside
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
            elif time_text(lit[1:-1]):
                t = "TIME"     # a quoted time of section 7.2
            else:
                t = "TEXT"
        else:
            t = core if core in SCALARS else None
    if t is not None and m.group("optional"):
        return ("either", frozenset({t, "NONE"}))
    return t


def is_list(t):
    return isinstance(t, tuple) and t[0] == "list"


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


def list_alts(t):
    """the list types a value of type t may be, when it is certainly a list; else None"""
    if is_list(t):
        return [t]
    if is_either(t) and all(is_list(a) for a in t[1]):
        return list(t[1])
    return None


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


def compatible(given, expected, optional=False):
    """may a value of type given stand where expected is declared"""
    if given is None or expected is None or given == "ANY":
        return True
    if given == "NONE":
        return optional or expected == "NONE"
    if is_either(expected):
        return any(compatible(given, e, optional or "NONE" in expected[1]) for e in expected[1])
    if is_either(given):
        return all(compatible(g, expected, optional) for g in given[1])
    if given == expected:
        return True
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
        return "no value"
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
        histories: (stem, versions) of every .edda.vc that did"""
        self.entities, self.roles, self.operations, self.epics, self.stories = {}, {}, {}, set(), {}
        self.files = {stem for stem, _ in files}
        self.dups = {}            # stem -> [(path, name)]: a name declared twice across the project
        self.role_order = []
        self.block_order = []     # (kind, name) of every role and entity block, by file name, then file order
        for stem, data in sorted(files, key=lambda f: f[0]):
            for section, block in mapping(data).items():     # in source order, so the second is reported
                if section == "roles":
                    for rname, role in mapping(block).items():
                        if rname in self.roles or rname in self.entities:
                            self.dups.setdefault(stem, []).append((("roles", rname), rname))
                            continue
                        props = {p: type_of_phrase(v) for p, v in mapping(mapping(role).get("properties")).items()}
                        self.roles[rname] = {"properties": props, "file": stem}
                        self.role_order.append(rname)
                        self.block_order.append(("role", rname))
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
                        self.block_order.append(("entity", ename))
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
                                                      "ordered_by": "ordered_by" in mapping(op), "who": who, "story": sid, "file": stem,
                                                      "order_exprs": listing(mapping(op).get("ordered_by")),
                                                      "refuse_when": [r.get("when") for r in listing(mapping(op).get("refuse")) if isinstance(r, dict)]}
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
                        if op["ordered_by"] and as_list(t):     # each alternative ordered
                            ts = [("list", a[1], True) for a in list_alts(t)]
                            t = ts[0] if len(ts) == 1 else ("either", frozenset(ts))
                        op["returns_type"] = t
                        changed = True
            if not changed:
                break
        self.computed_loops = self.find_computed_loops()
        self.versions = {}        # (kind, name) -> the version numbers in the history beside the block's file
        self.newest_version = {}    # (kind, name) -> the version with the highest number
        for stem, versions in histories:
            for e in listing(versions):
                if isinstance(e, dict):
                    kind = "story" if "story" in e else "entity" if "entity" in e else "role"
                    name = e.get(kind)
                    if self.file_of(kind, name) == stem:
                        n = e.get("number")
                        self.versions.setdefault((kind, name), set()).add(n)
                        if isinstance(n, int) and n > self.newest_version.get((kind, name), {}).get("number", 0):
                            self.newest_version[(kind, name)] = e

    def file_of(self, kind, name):
        """the stem of the file a block lives in, or None"""
        if kind == "story":
            return self.stories.get(name)
        block = (self.entities if kind == "entity" else self.roles).get(name)
        return block["file"] if block else None

    def find_computed_loops(self):
        """computed_cycle: (entity, property) of the first computed property of
        each group of computed properties that loop through one another, in
        file-name then file order, to its message: one shortest loop through
        that property. An edge runs to every computed property an expression
        reads: a bare one of its own entity, one through a path into another,
        or one in the summary of an operation the expression calls"""
        order = [(e, p) for k, e in self.block_order if k == "entity" for p in self.entities[e]["computed"]]
        summary = self.operation_reads()
        edges = {}
        for e, p in order:
            E = Expr(self, dict(self.entities[e]["props"]), silent=True)
            E.own, E.reads, E.calls = e, set(), set()
            if isinstance(self.entities[e]["computed"][p], str):
                E.run(self.entities[e]["computed"][p])
            for o in E.calls:
                E.reads |= summary[o]
            edges[(e, p)] = [q for q in order if q in E.reads]
        reach = {}
        for x in order:
            seen, stack = set(), list(edges[x])
            while stack:
                y = stack.pop()
                if y not in seen:
                    seen.add(y)
                    stack.extend(edges[y])
            reach[x] = seen
        loops, reported = {}, set()
        for start in order:
            if start in reported or start not in reach[start]:
                continue
            reported |= {x for x in reach[start] if start in reach[x]}     # the whole group, reported once here
            back, frontier = {}, [start]      # breadth first, so the loop shown is a shortest one
            while start not in back:
                nxt = []
                for x in frontier:
                    for y in edges[x]:
                        if y not in back:
                            back[y] = x
                            nxt.append(y)
                frontier = nxt
            path, x = [start], back[start]
            while x != start:
                path.append(x)
                x = back[x]
            path = [start] + path[:0:-1] + [start]
            one = len({e for e, _ in path}) == 1
            loops[start] = "computed properties loop: " + " -> ".join(p if one else f"{e}.{p}" for e, p in path)
        return loops

    def operation_reads(self):
        """computed_cycle: each operation with a text returns to its summary, the
        (entity, property) pairs a call can read: its refuse conditions and
        returns, each input typed by its declared type, and its ordered_by
        over one result item, plus the summary of every operation it calls;
        ("CLOCK", name) for NOW or TODAY read in any of them.
        who is left out: a call inside an expression has no actor and no
        permission check; ensure is left out: such a call is always a read.
        Each expression is walked once and the summaries grow to a fixed point"""
        own, calls = {}, {}
        for o, op in self.operations.items():
            if not isinstance(op["returns"], str):
                continue
            scope = {("var", n): True for n, _, _ in op["inputs"]}
            scope.update({n: t for n, t, _ in op["inputs"]})
            scope["ACTOR"] = ("actor", ("one", frozenset(r for r in op["who"] if isinstance(r, str))))
            item = {"ACTOR": scope["ACTOR"]}         # ordered_by's scope, as the meaning layer gives it
            rl = as_list(op["returns_type"])
            if rl and is_entity(rl[1]):
                item.update({("var", rl[1][1]): True, rl[1][1]: rl[1]})
            E = Expr(self, scope, silent=True)
            E.reads, E.calls = set(), set()
            for x in op["refuse_when"] + [op["returns"]]:
                if isinstance(x, str):
                    E.run(x)
            I = Expr(self, item, silent=True)
            I.reads, I.calls = E.reads, E.calls
            for x in op["order_exprs"]:
                if isinstance(x, str):
                    I.run(x)
            own[o], calls[o] = E.reads, E.calls
        callers = {o: set() for o in own}
        for o in own:
            for c in calls[o]:
                callers[c].add(o)
        summary = {o: set(own[o]) for o in own}
        work = list(own)
        while work:
            o = work.pop()
            new = summary[o].union(*(summary[c] for c in calls[o]))
            if new != summary[o]:
                summary[o] = new
                work.extend(callers[o])
        return summary

    def home(self, ename):
        """the file an entity lives in: its own name, or its owner's through part_of"""
        seen = set()
        while ename in self.entities and self.entities[ename]["part_of"] and ename not in seen:
            seen.add(ename)
            ename = self.entities[ename]["part_of"]
        return ename

    def actor_props(self, spec):
        """the properties an actor has: name, roles, and those of its roles;
        spec ("all", roles) for a known actor, ("one", roles) for one of them;
        a property two roles declare differently may be either"""
        base = {"name": "TEXT", "roles": ("list", "TEXT", True)}
        if not spec or not spec[1]:
            return base
        kind, roles = spec
        sets = [dict(self.roles[r]["properties"]) if r in self.roles else {} for r in roles]
        names = set.union(*[set(s) for s in sets]) if kind == "all" else set.intersection(*[set(s) for s in sets])
        out = {}
        for p in names:
            out[p] = unify_all([s[p] for s in sets if p in s])
        out.update(base)          # name and roles are fixed
        return out

    def admitted(self, ename):
        """the roles the entity's permission matrix admits"""
        ent = self.entities.get(ename)
        if not ent:
            return None
        return {r for rs in ent["may"].values() for r in rs if r}


# --- the expression checker ---------------------------------------------------

GEN_ONLY = {"sum", "any", "all"}
ONE_ARG = {"len", "OLD"}
OP_WORD = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}
CMP_WORD = {ast.Lt: "<", ast.Gt: ">", ast.LtE: "<=", ast.GtE: ">="}
FIXED = {"ACTOR", "RESULT", "NOW", "TODAY", "OLD", "TIME"}
TIME_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")     # section 7.2
REACHED = set()   # the entities a dot path has reached, the declared type of each step (story.blocks)


def time_text(v):
    """is v a time written as section 7.2 says"""
    for f in TIME_FORMATS:
        try:
            if datetime.datetime.strptime(v, f).strftime(f) == v:
                return True
        except ValueError:
            pass
    return False


def mentions_result(n):
    return any(isinstance(x, ast.Name) and x.id == "RESULT" for x in ast.walk(n))


def pair(a, b):
    """may two values of types a and b be compared for equality: one kind,
    two lists by their elements; None compares with anything"""
    if a is None or b is None or "ANY" in (a, b) or "NONE" in (a, b):
        return True
    if is_either(a) or is_either(b):
        return all(pair(x, y) for x in alts(a) for y in alts(b))
    if is_list(a) and is_list(b):
        return pair(a[1], b[1])
    if a == b or {a, b} == {"INTEGER", "NUMBER"}:
        return True
    if is_choice(a) and is_choice(b):
        return a[1] is None or b[1] is None or set(a[1]) <= set(b[1]) or set(b[1]) <= set(a[1])
    return is_actor(a) and is_actor(b)


def known(t):
    """the alternatives a value of type t may be, None aside"""
    return [a for a in alts(t) if a != "NONE"] if t is not None else [None]


class Expr:
    """checks one expression and gives its type; problems as (rule, message)"""

    def __init__(self, project, scope, allow_old=False, silent=False):
        self.P, self.scope, self.allow_old, self.silent = project, scope, allow_old, silent
        self.out, self.src, self.outer = [], "", None
        self.own, self.reads = None, None   # computed_cycle: the entity and the (entity, property) reads, ("CLOCK", name) for NOW or TODAY
        self.calls = None                   # computed_cycle: the operations with a text returns it calls

    def problem(self, rule, msg):
        if not self.silent:
            self.out.append((rule, msg))

    def seg(self, n):
        return ast.get_source_segment(self.src, n) or "..."

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

    def choice_value(self, name, other, node, scope):
        """type a bare name compared with node, a value of type other"""
        rest = [a for a in alts(other) if a != "NONE"]
        choices = [a for a in rest if is_choice(a)]
        if choices and len(choices) == len(rest):
            values = [v for c in choices for v in (c[1] or ())]
            if all(c[1] for c in choices) and name.id not in values:
                prop = node.attr if isinstance(node, ast.Attribute) else ast.unparse(node)
                self.problem("unknown_choice", f"not one of {prop}'s values: {name.id}")
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
            inner[("var", g.target.id)] = True      # a comprehension variable, never a property read
            if it is not None and lt is None:
                self.problem("type_mismatch", f"for expects a list: {self.src}")
                inner[g.target.id] = None
            else:
                inner[g.target.id] = (lt[1] if lt[1] != "ANY" else None) if lt else None
            ordered_all = ordered_all and ordered(lt)
            for c in g.ifs:
                self.visit(c, inner)
        return inner, ordered_all

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
                return scope.get("ACTOR", ("actor", None))
            if i in ("NOW", "TODAY"):     # TODAY is a day, a TIME at 00:00 (7.2)
                if self.reads is not None:
                    self.reads.add(("CLOCK", i))  # no entity is named CLOCK; the runner's clock check
                return "TIME"
            if i == "RESULT":
                if "RESULT" not in scope:
                    self.problem("not_an_expression", f"not an expression (RESULT only after a call): {src}")
                    return None
                return scope["RESULT"]
            if i in scope and i != "RESULT_OP":
                if self.reads is not None and ("var", i) not in scope:
                    self.reads.add((self.own, i))
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
                    if self.reads is not None:
                        self.reads.add((a[1], n.attr))
                    if n.attr not in props:
                        self.problem("unknown_name", f"unknown name: {n.attr}")
                    outs.append(props.get(n.attr))
                else:
                    self.problem("type_mismatch", f".{n.attr} expects an entity: {src}")
                    return None
            for a in alts(t) + [x for o in outs for x in alts(o)]:     # story.blocks: each step's declared type
                e = a[1] if is_list(a) else a
                if is_entity(e):
                    REACHED.add(e[1])
            return unify_all(outs)
        if isinstance(n, ast.Subscript):
            t = self.visit(n.value, scope)
            if isinstance(n.slice, ast.Slice):
                self.problem("not_an_expression", f"not an expression (slice): {src}")
                return None
            lt = as_list(t)
            if not all_alts(self.visit(n.slice, scope), lambda a: a == "INTEGER"):
                self.problem("type_mismatch", f"an index expects an INTEGER: {src}")
            if lt and not ordered(lt) and mentions_result(n.value):
                self.problem("not_ordered", f"{scope.get('RESULT_OP', 'the operation')} gives no order; RESULT[{self.seg(n.slice)}] needs ordered_by or IN ORDER")
            if lt:
                return lt[1] if lt[1] != "ANY" else None
            if t is not None:
                self.problem("type_mismatch", f"an index expects a list: {src}")
            return None
        if isinstance(n, ast.Compare):
            if len(n.ops) != 1:
                self.problem("not_an_expression", f"not an expression (one operator per comparison): {src}")
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
            # a bare name beside == or != is a choice value: in the property's list or unknown_choice
            if equality and bare(right) and not bare(left):
                lt = self.visit(left, scope)
                rt = self.choice_value(right, lt, left, scope)
            elif equality and bare(left) and not bare(right):
                rt = self.visit(right, scope)
                lt = self.choice_value(left, rt, right, scope)
            elif isinstance(op, (ast.In, ast.NotIn)) and isinstance(right, ast.List) and any(bare(e) for e in right.elts):
                lt = self.visit(left, scope)
                ets = [self.choice_value(e, lt, left, scope) if bare(e) else self.visit(e, scope) for e in right.elts]
                rt = ("list", unify_all(ets), True)      # a bare name in the list is a choice value of the compared property
            else:
                lt, rt = self.visit(left, scope), self.visit(right, scope)
            # the operands must compare: one kind for == and !=, an element for in, numbers, texts or times for <
            if isinstance(op, (ast.In, ast.NotIn)):
                R = known(rt)
                if not R:                                 # only None: neither a list nor a text
                    self.problem("type_mismatch", f"in expects a list or a text: {src}")
                for r in R:                               # each value the right side may be, on its own
                    if r is None:
                        continue
                    if is_list(r):
                        if not pair(lt, r[1]):
                            self.problem("type_mismatch", f"in expects an element of the list: {src}")
                    elif r == "TEXT":
                        if not known(lt) or not compatible(lt, "TEXT", True):
                            self.problem("type_mismatch", f"in expects a text in a text: {src}")
                    else:
                        self.problem("type_mismatch", f"in expects a list or a text: {src}")
            elif equality:
                if not pair(lt, rt):
                    self.problem("type_mismatch", f"{'!=' if isinstance(op, ast.NotEq) else '=='} expects two values of one kind: {src}")
            elif type(op) in CMP_WORD:
                L = known(lt) + known(rt)
                if L and not any(all(compatible(a, k, True) for a in L) for k in ("NUMBER", "TEXT", "TIME")):
                    self.problem("type_mismatch", f"{CMP_WORD[type(op)]} expects two numbers, two texts or two times: {src}")
            return "YES_NO"
        if isinstance(n, ast.BoolOp):
            return unify_all([self.visit(v, scope) for v in n.values])
        if isinstance(n, ast.UnaryOp):
            t = self.visit(n.operand, scope)
            if isinstance(n.op, ast.Not):
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
                    return ("list", unify(ll[1], rl[1]), ordered(ll) and ordered(rl))
                return None       # one side unresolved: the join waits for it
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
        if isinstance(n, ast.List):
            types = [self.visit(e, scope) for e in n.elts]
            return ("list", unify_all(types) if n.elts else "ANY", True)
        if isinstance(n, ast.ListComp):
            inner, o = self.comprehension(n.generators, scope)
            return ("list", self.visit(n.elt, inner), o)
        if isinstance(n, ast.GeneratorExp):
            self.problem("not_an_expression", f"not an expression (a generator only inside {', '.join(sorted(GEN_ONLY))}): {src}")
            return None
        if isinstance(n, ast.Call):
            f = n.func
            if not isinstance(f, ast.Name):
                self.problem("not_an_expression", f"not an expression (call form): {src}")
                return None
            if f.id == "TIME":
                a = n.args[0] if len(n.args) == 1 and not n.keywords else None
                if not (isinstance(a, ast.Constant) and isinstance(a.value, str) and time_text(a.value)):
                    for x in n.args + [kw.value for kw in n.keywords]:
                        if not isinstance(x, ast.Constant):
                            self.visit(x, scope)
                    self.problem("type_mismatch", f"TIME expects one quoted time, \"YYYY-MM-DD HH:MM\" or \"YYYY-MM-DD\": {src}")
                return "TIME"
            if f.id in GEN_ONLY:
                if not (len(n.args) == 1 and isinstance(n.args[0], ast.GeneratorExp) and not n.keywords):
                    self.problem("type_mismatch", f"{f.id} expects one generator: {src}")
                    for a in n.args:
                        self.visit(a, scope)
                    return None
                g = n.args[0]
                inner, _ = self.comprehension(g.generators, scope)
                et = self.visit(g.elt, inner)
                if f.id in ("any", "all"):
                    return "YES_NO"
                if not all_alts(et, lambda a: a in ("INTEGER", "NUMBER")):
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
                    if not compatible(self.visit(a, scope), itype):
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
                        if not compatible(self.visit(kw.value, scope), opt[kw.arg], True):
                            self.problem("type_mismatch", f"{f.id} input {kw.arg} expects {words(opt[kw.arg])}: {src}")
                if op["returns"] is None and n is not self.outer:
                    self.problem("not_an_expression", f"not an expression (a changing operation inside a fact): {src}")
                if self.calls is not None and isinstance(op["returns"], str):
                    self.calls.add(f.id)
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
                yield "wrong_type", where, f"{where[-1]} expects a text, no value was given"
                return
            for rule, p in type_phrase_problems(v):
                yield rule, where, p
            e = phrase_entity(v)
            if e and e not in P.entities:
                yield "unknown_name", where, f"unknown name: {e}"

    def ex(v, where, scope, allow_old=False, call_slot=False):
        if isinstance(v, str):
            if v == "":
                yield "wrong_type", where, f"{key_name(where)} expects a text, no value was given"
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
        for p, v in mapping(role.get("properties")).items():
            yield from tp(v, ("roles", rname, "properties", p))
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
                if P.entities.get(ename, {}).get("file") == stem and (ename, p) in P.computed_loops:
                    yield "computed_cycle", ("entities", ename, "properties", p), P.computed_loops[(ename, p)]
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
                    yield "unknown_choice", where + (frm,), f"not one of {p}'s values: {frm}"
                for i, s in enumerate(listing(tos)):
                    if vals is not None and s not in vals:
                        yield "unknown_choice", where + (frm, i), f"not one of {p}'s values: {s}"
        for i, f in enumerate(listing(ent.get("always"))):
            yield from fact(f, ("entities", ename, "always", i), own)
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
        if "rules" in st:          # every example under exactly one rule; twice is the shape layer's
            titles, named = mapping(st.get("examples")), set()
            for i, r in enumerate(listing(st.get("rules"))):
                for j, t in enumerate(listing(r.get("shown_by"))):
                    if t not in titles:
                        yield "unknown_name", ("stories", sid, "rules", i, "shown_by", j), f"unknown example: {t}"
                    named.add(t)
            for title in titles:
                if title not in named:
                    yield "no_rule", ("stories", sid, "examples", title), f'example "{title}" belongs to no rule'
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
            rl = as_list(rt)
            item_scope = {"ACTOR": body["ACTOR"]}
            if rl and is_entity(rl[1]):
                item_scope[rl[1][1]] = rl[1]
            if "ordered_by" in op and rt is not None and rl is None:
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
            givens, names = given_names(exm)
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
                verdict_first = False
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
                    verdict_first = True
                    then = listing(step.get("then"))
                    scope["RESULT"] = "NONE" if (then and isinstance(then[0], dict)) else rt
                    scope["RESULT_OP"] = c.outer.func.id if c.outer else "the operation"
                for j, item in enumerate(listing(step.get("then"))):
                    if j == 0 and verdict_first:
                        continue
                    if isinstance(item, str) and item != "DONE":
                        yield from ex(item, sw + ("then", j), scope)


def given_names(exm):
    """the givens of an example by name, with their types and kinds; names
    first, as givens are order-independent"""
    givens, names = {}, {}
    for g in listing(exm.get("given")):
        for k, v in mapping(g).items():
            if k != "with" and isinstance(v, str) and v not in givens:
                roles = [r for r in listing(mapping(g.get("with")).get("roles")) if isinstance(r, str)] if k == "actor" else []
                givens[v] = ("actor", ("all", frozenset(roles))) if k == "actor" else ("entity", k)
                names[v] = k
    return givens, names


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
                yield "unknown_choice", pw, f"not one of {p}'s values: {v}"
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
    line indented deeper, a flow mapping or list left open at a line's end
    keeping the block open until it closes; comments, blank lines and trailing
    spaces removed outside quoted text, quoting tracked across wrapped lines,
    re-indented so the key line starts at column 0"""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return ""
    indent = len(lines[0]) - len(lines[0].lstrip(" "))
    out, q, depth = [], False, 0       # depth: flow mappings and lists left open
    for n, s in enumerate(lines):
        if not q:
            if s.strip() == "" or s.lstrip().startswith("#"):
                continue
            if n > 0 and depth == 0 and len(s) - len(s.lstrip(" ")) <= indent:
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
            if not q and c in "[{":
                depth += 1
            elif not q and c in "]}" and depth:
                depth -= 1
            kept.append(c)
        t = "".join(kept) if q else "".join(kept).rstrip()
        out.append(t[indent:] if t.startswith(" " * indent) else t)
    return "\n".join(out) + "\n"


SECTION = {"entity": "entities", "role": "roles", "story": "stories"}

# the keys an earlier revision allowed in a block and a later one retired
# (section 10): a snapshot approved then may still hold them, with any value
# in the subset; a .edda may not
RETIRED_KEYS = {"roles": ("has", "includes"), "entities": ("wording", "while")}
HISTORY_SCHEMA = copy.deepcopy(SCHEMA)
for _section, _keys in RETIRED_KEYS.items():
    for _k in _keys:
        HISTORY_SCHEMA["properties"][_section]["additionalProperties"]["properties"][_k] = {}
HISTORY = Draft202012Validator(HISTORY_SCHEMA)


def snapshot_ok(text, kind, name):
    """is text a self-contained snapshot of the block (section 10): already
    normalised, named on its first line, in the subset of section 2 with no
    duplicate key, of a shape some revision allowed (RETIRED_KEYS), and one
    block under the version's name; never checked for meaning"""
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
        if DUPLICATES or schema_problems(HISTORY, HISTORY_SCHEMA, data, src) or shape_extra(data):
            return False
    except Exception:
        return False
    block = mapping(data).get(SECTION[kind])
    return isinstance(block, dict) and list(block) == [name] and isinstance(block[name], dict)


def history_problems(versions, P, source, stem):
    """the history layer of <stem>.edda.vc: bad_version (versions of the
    blocks of <stem>.edda only, numbered 1, 2, 3 per block, in file order),
    bad_pin (pins on a story version only, each to a version that exists, no
    block twice) and bad_snapshot (snapshot_ok)"""
    out, count = [], {}
    kinds = {"story": P.stories, "entity": P.entities, "role": P.roles}
    for i, e in enumerate(listing(versions)):
        if not isinstance(e, dict):
            continue
        kind = "story" if "story" in e else "entity" if "entity" in e else "role"
        name, n = e.get(kind), e.get("number")
        line = source.line((i, "number"))
        if name not in kinds[kind]:
            out.append(("bad_version", line, f"{kind} {name} v{n}: no such {kind}"))
            continue
        if P.file_of(kind, name) != stem:
            out.append(("bad_version", line, f"{kind} {name} v{n}: belongs in {P.file_of(kind, name)}.edda.vc"))
            continue
        expected = count.get((kind, name), 0) + 1
        if n != expected:
            out.append(("bad_version", line, f"{kind} {name} v{n} out of sequence; expected v{expected}"))
        count[(kind, name)] = n if isinstance(n, int) else expected
        pins = e.get("pins")
        if kind == "story":
            if not pins:
                out.append(("bad_pin", line, f"story {name} v{n}: no pins"))
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
            out.append(("bad_pin", source.line((i, "pins")), f"{kind} {name} v{n}: a block version has no pins"))
        text = e.get("text")
        if isinstance(text, str) and not snapshot_ok(text, kind, name):
            out.append(("bad_snapshot", line, f"text of {kind} {name} v{n} is not a normalised block"))
    return out


# --- run ---------------------------------------------------------------------

KEY_LINE_RULES = {"returns_and_ensure", "wrong_file", "computed_cycle", "wider_than_entity", "declared_twice", "no_rule"}

def block_text(text, line):
    """the normalised text (section 10) of the block whose key line is line
    (counted from 1) in a file's text"""
    return normalise("\n".join(text.split("\n")[line - 1:]))


def _children(lines, lo, hi):
    """(start, end) of each child block in lines[lo:hi], all at one indent:
    a key line and the lines normalise keeps with it, and the list items
    written at the key's own indent under a key with no value"""
    def span(i):
        return max(len(normalise("\n".join(lines[i:hi]) + "\n").split("\n")) - 1, 1)
    i = lo
    while i < hi:
        j = i + span(i)
        if lines[i].endswith(":"):
            indent = len(lines[i]) - len(lines[i].lstrip(" "))
            while j < hi and lines[j].startswith(" " * indent + "-"):
                j += span(j)
        yield i, j
        i = j


def _key(line):
    m = re.match(r" *([a-z_]+):", line)
    return m.group(1) if m else None


BODY_KEYS = ("about", "as_a", "rules", "operations", "examples")


def body_text(text):
    """a story's body_text (section 10) from its normalised text: the key
    line, then only about:, as_a:, rules:, operations: and examples:, with
    every note under an operation or an example removed"""
    lines = text.split("\n")[:-1]
    if not lines:
        return ""
    out = [lines[0]]
    for lo, hi in _children(lines, 1, len(lines)):
        key = _key(lines[lo])
        if key not in BODY_KEYS:
            continue
        out.append(lines[lo])
        if key not in ("operations", "examples"):
            out += lines[lo + 1:hi]
            continue
        for ilo, ihi in _children(lines, lo + 1, hi):
            out.append(lines[ilo])
            for klo, khi in _children(lines, ilo + 1, ihi):
                if _key(lines[klo]) != "notes":
                    out += lines[klo:khi]
    return "\n".join(out) + "\n"


def _wording_drift_flags(sid, st, approved_st, source):
    """wording_drift for one draft story (section 10): a refusal's when and
    reason, a fact and its means, matched by position; yields (rule, line, msg)"""
    out = []
    for oname, op in mapping(mapping(st).get("operations", {})).items():
        app_op = mapping(mapping(approved_st).get("operations", {})).get(oname)
        if not isinstance(app_op, dict):
            continue
        curr_ref = listing(mapping(op).get("refuse", []))
        app_ref = listing(mapping(app_op).get("refuse", []))
        for i, (cr, ar) in enumerate(zip(curr_ref, app_ref)):
            if not isinstance(cr, dict) or not isinstance(ar, dict):
                continue
            cw, aw = cr.get("when"), ar.get("when")
            crr, arr = cr.get("reason"), ar.get("reason")
            if cw == aw and crr != arr:
                p = ("stories", sid, "operations", oname, "refuse", i, "reason")
                out.append(("wording_drift", source.line(p, key=False),
                    f"{sid} {oname}: reason changed, when did not"))
            elif cw != aw and crr == arr:
                p = ("stories", sid, "operations", oname, "refuse", i, "when")
                out.append(("wording_drift", source.line(p, key=False),
                    f"{sid} {oname}: when changed, reason did not"))
        curr_ens = listing(mapping(op).get("ensure", []))
        app_ens = listing(mapping(app_op).get("ensure", []))
        for i, (ce, ae) in enumerate(zip(curr_ens, app_ens)):
            cf = ce.get("fact") if isinstance(ce, dict) else ce
            af = ae.get("fact") if isinstance(ae, dict) else ae
            cm = ce.get("means") if isinstance(ce, dict) else None
            am = ae.get("means") if isinstance(ae, dict) else None
            if cf == af and cm != am and am is not None:
                p = ("stories", sid, "operations", oname, "ensure", i, "means")
                out.append(("wording_drift", source.line(p, key=False),
                    f"{sid} {oname}: means changed, fact did not"))
            elif cf != af and cm == am and am is not None:
                p = ("stories", sid, "operations", oname, "ensure", i, "fact")
                out.append(("wording_drift", source.line(p, key=False),
                    f"{sid} {oname}: fact changed, means did not"))
    return out


def flag_problems(data, stem, P, source):
    """the flags of the fourth layer, for a .edda file that passed the
    three before it"""
    out = []

    # unreachable_choice: a choice with DEFAULT, its first value the default
    for ename, ent in mapping(data.get("entities", {})).items():
        for prop, phrase in mapping(mapping(ent).get("properties", {})).items():
            if not isinstance(phrase, str):
                continue
            m = TYPE_RE.fullmatch(phrase)
            if not m or not m.group("dchoice"):
                continue
            vals = m.group("dchoice").split(" | ")
            default = vals[0]
            targets = {default}
            for frm, tos in mapping(mapping(mapping(ent).get("may_change", {})).get(prop, {})).items():
                for s in listing(tos):
                    if isinstance(s, str):
                        targets.add(s)
            for val in vals:
                if val not in targets:
                    path = ("entities", ename, "properties", prop)
                    out.append(("unreachable_choice", source.line(path),
                        f"no change reaches {prop}'s value: {val}"))

    # no_example
    for sid, st in mapping(data.get("stories", {})).items():
        if not mapping(st).get("examples"):
            out.append(("no_example", source.line(("stories", sid)),
                f"story {sid} has no example"))

    # flags that need history: approved when body_text equals the newest version's
    for sid, st in mapping(data.get("stories", {})).items():
        newest = P.newest_version.get(("story", sid))
        if not newest or not isinstance(newest.get("text"), str):
            continue
        current = block_text(source.text, source.line(("stories", sid)))
        is_approved = body_text(current) == body_text(newest["text"])

        # question_on_approved
        if is_approved and listing(mapping(st).get("questions", [])):
            out.append(("question_on_approved", source.line(("stories", sid)),
                f"story {sid} is approved and still has a question"))

        # wording_drift (only for drafts), over the parsed newest version
        if not is_approved:
            try:
                app_data = yaml.load(newest["text"], Loader=Core)
            except Exception:
                continue
            if isinstance(app_data, dict) and sid in app_data:
                out.extend(_wording_drift_flags(sid, st, app_data[sid], source))

    return sorted(set(out), key=lambda p: (p[1], p[0]))


def changes(old, new):
    """story.changes (section 11): the walk over the newest version's text
    and the current text; (kind, line, sentence), line counted from 1 at the
    key line of the current text"""
    a, b = old.split("\n")[:-1], new.split("\n")[:-1]
    lcs = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            lcs[i][j] = lcs[i + 1][j + 1] + 1 if a[i] == b[j] else max(lcs[i + 1][j], lcs[i][j + 1])
    out, i, j = [], 0, 0
    while i < len(a) or j < len(b):
        if i < len(a) and j < len(b) and a[i] == b[j]:
            i, j = i + 1, j + 1
        elif i < len(a) and (j == len(b) or lcs[i + 1][j] >= lcs[i][j + 1]):
            out.append(("removed", j + 1, a[i]))
            i += 1
        else:
            out.append(("added", j + 1, b[j]))
            j += 1
    return out


def pins_stale(version, P):
    """story.pins_stale (section 10): a pin of version, the newest one, older
    than its block's newest version"""
    def newest(kind, name):
        return max((n for n in P.versions.get((kind, name), ()) if isinstance(n, int)), default=0)
    pins = [p for p in listing(version.get("pins")) if isinstance(p, dict)]
    return any(isinstance(p.get("number"), int) and p["number"] < newest(k, p.get(k)) for p in pins
               for k in ["entity" if "entity" in p else "role"])


def approved(kind, current, newest):
    """block.approved, story.approved (section 10): current, the normalised
    text, against the newest version; False when there is none"""
    old = newest.get("text") if newest else None
    if not isinstance(old, str):
        return False
    return body_text(current) == body_text(old) if kind == "story" else current == old


def statuses(data, P, source):
    """(kind, name, section, approved, version, pins stale, changes) of every
    role, entity and story of a .edda, roles, then entities, then stories,
    each in file order (section 11); changes only under a story with a
    version, pins stale only on an approved story"""
    for section, kind in (("roles", "role"), ("entities", "entity"), ("stories", "story")):
        for name in mapping(data.get(section, {})):
            current = block_text(source.text, source.line((section, name)))
            newest = P.newest_version.get((kind, name))
            old = newest.get("text") if newest else None
            n = len(P.versions.get((kind, name), ()))     # block.version: len(versions)
            ok = isinstance(old, str) and approved(kind, current, newest)
            story = kind == "story" and isinstance(old, str)
            yield (kind, name, section, ok, n, story and ok and pins_stale(newest, P),
                   changes(old, current) if story else [])


def status_lines(data, P, source):
    """the status of every role, entity and story of a .edda that checks,
    its history included (section 11): approved or draft with its version,
    pins stale on an approved story, and under a story with a version its
    changes"""
    out = []
    for kind, name, _, ok, n, stale, ch in statuses(data, P, source):
        out.append(f"{kind} {name}: {'approved' if ok else 'draft'} v{n}" + (", pins stale" if stale else ""))
        out += [f"  {'-' if k == 'removed' else '+'} {line}: {s}" for k, line, s in ch]
    return out


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
    """returns (source, shape, meaning, history, flags): lists of (rule,
    line, message); history and flags are the fourth layer of section 11,
    history for a .edda.vc and flags for a .edda"""
    stem = os.path.basename(path).split(".")[0]
    source, data = load(path)
    if source.src:
        return sorted(set(source.src), key=lambda p: (p[1], p[0])), [], [], [], []
    is_vc = path.endswith(".vc")
    shape = list(source.style) + [("declared_twice", ln, f"declared twice: {k}") for k, ln in source.duplicates]
    shape += schema_problems(VC if is_vc else V, VC_SCHEMA if is_vc else SCHEMA, data, source)
    if not is_vc:
        shape += [(rule, source.line(where, at_key), msg) for rule, where, msg, at_key in shape_extra(data, source)]
        shape += [("declared_twice", source.line(where), f"declared twice: {name}") for where, name in P.dups.get(stem, [])]
    shape = sorted(set(shape), key=lambda p: (p[1], p[0]))
    meaning, history, flags = [], [], []
    if shape:
        return [], shape, [], [], []
    if is_vc:
        history = sorted(set(history_problems(data, P, source, stem)), key=lambda p: (p[1], p[0]))
    else:
        meaning = [(rule, source.line(where, key=rule in KEY_LINE_RULES), msg)
                   for rule, where, msg in walk_meaning(data, stem, P, source)]
        meaning = sorted(set(meaning), key=lambda p: (p[1], p[0]))
        if not meaning:
            flags = flag_problems(data, stem, P, source)
    return [], shape, meaning, history, flags


def history_refused(path, P):
    """whether the .edda.vc beside a .edda has a refusal"""
    vc = path + ".vc"
    return os.path.exists(vc) and any(check(vc, P)[:4])


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


# --- the JSON model (section 9) ------------------------------------------------

MODEL_VERSION = 1     # the model's own version, edda_model
REVISION = 63         # the language revision the model follows


def ast_json(n):
    """a Python ast node as JSON: {"node": <class>, <field>: ...} for every
    field in _fields order, no positions; constants as JSON values"""
    if isinstance(n, ast.AST):
        out = {"node": type(n).__name__}
        for f in n._fields:
            out[f] = ast_json(getattr(n, f, None))
        return out
    if isinstance(n, list):
        return [ast_json(x) for x in n]
    return n


def json_ast(d):
    """the ast node of ast_json's output, for a stack that reads it back"""
    if isinstance(d, dict) and "node" in d:
        return getattr(ast, d["node"])(**{k: json_ast(v) for k, v in d.items() if k != "node"})
    if isinstance(d, list):
        return [json_ast(x) for x in d]
    return d


def default_value(v):
    """the value a DEFAULT type phrase gives, by the grammar of section 4: a
    choice's first value, a number (so 01 is 1), True or False, or the text
    between the quotes exactly as written; None for any other phrase"""
    m = TYPE_RE.fullmatch(v) if isinstance(v, str) else None
    if not (m and v.startswith("DEFAULT ")):
        return None
    if m.group("dchoice"):
        return m.group("dchoice").split(" | ")[0]
    lit = re.sub(r", DERIVED$", "", v)[8:]
    if re.fullmatch(r"-?[0-9]+", lit):
        return int(lit)
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", lit):
        return float(lit)
    if lit in ("True", "False"):
        return lit == "True"
    return lit[1:-1]


def phrase_json(v):
    """a type phrase as written, parsed by the grammar of section 4"""
    m = TYPE_RE.fullmatch(v)
    choice = m.group("dchoice") or m.group("choice")
    default = default_value(v)
    if choice:
        t = "choice"
    elif m.group("ref") or m.group("many"):
        t = "entity"
    else:
        t = no_none(type_of_phrase(v))     # a scalar word, or the type a DEFAULT literal fixes
    return {"phrase": v, "type": t, "values": choice.split(" | ") if choice else None,
            "entity": m.group("ref") or m.group("many"), "many": bool(m.group("many")),
            "in_order": bool(m.group("ordered")), "default": default,
            "optional": bool(m.group("optional")), "derived": v.endswith(", DERIVED"), "computed": None}


def resolved_json(t):
    """the type and values the checker resolved a computed property to: a
    choice with its values, a scalar word, or neither"""
    c = choice_of(t)
    if c is not None:
        return {"type": "choice", "values": list(c[1]) if c[1] else None}
    t = no_none(t)
    return {"type": t if t in SCALARS else None, "values": None}


def with_json(v, t, pw, givens, names, source):
    """a with: value with the kind the checker resolved it to (section 9):
    of a value that may be of several types, the one it fits, a given
    before a choice value as the runner reads it; kind null where the
    property's type is not known"""
    if is_either(t):
        rest = sorted((a for a in t[1] if a != "NONE"), key=lambda a: (not is_entity(a), not is_choice(a), repr(a)))
        t = next((a for a in rest if not list(given_value(v, a, "", pw, givens, names, source))), None)
    if isinstance(v, list):
        return {"kind": "list", "value": [with_json(e, t[1] if is_list(t) else None, pw + (j,), givens, names, source)
                                          for j, e in enumerate(v)]}
    if isinstance(v, bool):
        kind = "yes_no"
    elif isinstance(v, (int, float)):
        kind = "integer" if t == "INTEGER" else "number"
    elif t in ("TEXT", "TIME"):
        kind = t.lower()
    elif is_choice(t):
        kind = "choice"
    elif is_entity(t):
        kind = "given"
    else:
        kind = None
    return {"kind": kind, "value": v}


class ModelParts:
    """the model's pieces read from one source (section 9): a path's line,
    less shift (a version's lines count from its key line), and the
    expressions, facts and who-lines at a path; drift, the lines the
    wording_drift flags give"""

    def __init__(self, source, shift=0, drift=()):
        self.source, self.shift, self.drift = source, shift, set(drift)

    def line(self, p, key=True):
        return self.source.line(p, key) - self.shift

    def expr(self, text, p):
        return {"text": text, "line": self.line(p, False), "ast": ast_json(ast.parse(text, mode="eval").body)}

    def fact(self, f, p):
        if isinstance(f, dict):
            drift = bool({self.line(p + ("fact",), False), self.line(p + ("means",), False)} & self.drift)
            return {"fact": self.expr(f["fact"], p + ("fact",)), "means": f.get("means"), "drift": drift, "line": self.line(p)}
        return {"fact": self.expr(f, p), "means": None, "drift": False, "line": self.line(p)}

    def who(self, ws, p):
        return [{"role": w["role"], "when": self.expr(w["when"], p + (i, "when")) if "when" in w else None,
                 "line": self.line(p + (i,))} for i, w in enumerate(listing(ws))]

    def props(self, ps, p, types):
        """the properties at p, each with its type: as written, or as the
        checker resolved a computed one from types"""
        out = []
        for n, v in mapping(ps).items():
            if isinstance(v, dict):
                t = dict({"phrase": None}, **resolved_json(types.get(n)), entity=None, many=False,
                         in_order=False, default=None, optional=False, derived=False,
                         computed=self.expr(v["computed"], p + (n, "computed")))
            else:
                t = phrase_json(v)
            out.append(dict({"name": n}, **t, line=self.line(p + (n,))))
        return out

    def text_lines(self, xs, p):
        """the line of each text of a list (notes, questions)"""
        return [self.line(p + (i,), False) for i, _ in enumerate(listing(xs))]


def story_json(sid, st, fname, P, M, pins):
    """one story of the model and its operations (section 9), from its
    parsed YAML at ("stories", sid) of M's source; P gives the types of
    its givens' values, pins are the story's (kind, name, version)"""
    at = ("stories", sid)
    examples = []
    for title, x in mapping(st.get("examples")).items():
        xa = at + ("examples", title)
        givens, names = given_names(x)
        given = []
        for i, g in enumerate(listing(x.get("given"))):
            kind = next(k for k in g if k != "with")
            ga = xa + ("given", i)
            types = P.actor_props(givens[g[kind]][1]) if kind == "actor" else P.entities.get(kind, {}).get("props", {})
            values = {}
            for p, v in mapping(g.get("with")).items():
                if kind == "actor" and p == "roles":
                    values[p] = {"kind": "list", "value": [{"kind": "role", "value": r} for r in listing(v)]}
                elif kind == "spec_file" and p == "fixture":
                    values[p] = {"kind": "fixture", "value": v}
                else:
                    values[p] = with_json(v, types.get(p), ga + ("with", p), givens, names, M.source)
            given.append({"kind": kind, "name": g[kind], "with": values, "line": M.line(ga)})
        steps = []
        for i, s in enumerate(listing(x.get("steps"))):
            sa = xa + ("steps", i)
            then = listing(s.get("then"))
            when, verdict = None, None
            if "when" in s:
                w = s["when"]
                when = {"actor": w["actor"], "call": M.expr(w["call"], sa + ("when", "call")),
                        "at": w.get("at"), "line": M.line(sa + ("when",))}
                verdict = {"kind": "DONE" if then[0] == "DONE" else "refused",
                           "reason": None if then[0] == "DONE" else then[0]["refused"], "line": M.line(sa + ("then", 0))}
                then = then[1:]
            skip = 1 if when else 0
            steps.append({"when": when, "verdict": verdict,
                          "then": [M.expr(t, sa + ("then", j + skip)) for j, t in enumerate(then)],
                          "then_line": M.line(sa + ("then",)) if "then" in s else None, "line": M.line(sa)})
        examples.append({"title": title, "given": given,
                         "given_line": M.line(xa + ("given",)) if "given" in x else None, "steps": steps,
                         "notes": listing(x.get("notes")), "note_lines": M.text_lines(x.get("notes"), xa + ("notes",)),
                         "line": M.line(xa)})
    operations = []
    for oname, op in mapping(st.get("operations")).items():
        oa = at + ("operations", oname)
        operations.append({
            "name": oname, "story": sid, "is": op["is"],
            "inputs": [dict({"name": n}, **phrase_json(v), line=M.line(oa + ("inputs", n)))
                       for n, v in mapping(op.get("inputs")).items()],
            "who": M.who(op.get("who"), oa + ("who",)),
            "refuse": [{"when": M.expr(r["when"], oa + ("refuse", i, "when")), "reason": r["reason"],
                        "drift": bool({M.line(oa + ("refuse", i, k), False) for k in ("when", "reason")} & M.drift),
                        "line": M.line(oa + ("refuse", i))}
                       for i, r in enumerate(listing(op.get("refuse")))],
            "ensure": [M.fact(f, oa + ("ensure", i)) for i, f in enumerate(listing(op.get("ensure")))],
            "returns": M.expr(op["returns"], oa + ("returns",)) if "returns" in op else None,
            "ordered_by": [M.expr(o, oa + ("ordered_by", i)) for i, o in enumerate(listing(op.get("ordered_by")))],
            "also_changes": [M.expr(o, oa + ("also_changes", i)) for i, o in enumerate(listing(op.get("also_changes")))],
            "notes": listing(op.get("notes")), "note_lines": M.text_lines(op.get("notes"), oa + ("notes",)),
            "file": fname, "line": M.line(oa)})
    story = {
        "id": sid, "sentence": st["story"], "about": st["about"], "as_a": st["as_a"],
        "i_want": st["i_want"], "so_that": st["so_that"], "epic": st.get("epic"), "tags": listing(st.get("tags")),
        "notes": listing(st.get("notes")), "note_lines": M.text_lines(st.get("notes"), at + ("notes",)),
        "questions": listing(st.get("questions")), "question_lines": M.text_lines(st.get("questions"), at + ("questions",)),
        "rules": [{"rule": r["rule"], "shown_by": listing(r.get("shown_by")), "line": M.line(at + ("rules", i, "rule"))}
                  for i, r in enumerate(listing(st.get("rules")))],
        "operations": list(mapping(st.get("operations"))), "examples": examples,
        "pins": [{"kind": k, "name": n, "version": v} for k, n, v in pins]}
    return story, operations


def pins_of(version):
    """a version's pins as (kind, name, number)"""
    return [("entity" if "entity" in p else "role", p.get("entity", p.get("role")), p["number"])
            for p in listing(version.get("pins")) if isinstance(p, dict)]


def snapshot_data(text, kind):
    """(source, data) of a snapshot's text read as one block under its
    section, its key line on line 2 (section 10)"""
    wrapped = SECTION[kind] + ":\n" + "".join("  " + l + "\n" for l in text.split("\n")[:-1])
    DUPLICATES.clear()
    return Source(wrapped, False), yaml.load(wrapped, Loader=Core)


def versions_json(sid, fname, entries, snapshots):
    """the approved versions of a story, oldest first (section 9): each
    with its own record and its snapshot modelled as the story is, its
    lines counted from its key line, read against the blocks it pins at
    their pinned versions (section 12), whose properties it holds with
    their types, each line counted from its snapshot's key line"""
    out = []
    for e, line in entries:
        source, data = snapshot_data(e["text"], "story")
        st = data["stories"][sid]
        pins = pins_of(e)
        pinned = {"roles": {}, "entities": {}}
        sources = {}
        for k, n, v in pins:
            sources[(k, n)], block = snapshots.get((k, n, v), (None, None))
            pinned[SECTION[k]][n] = mapping(block)
        VP = Project([(fname[:-5], dict(pinned, stories={sid: st}))])
        blocks = {}
        for k, n, v in pins:
            ps = mapping(pinned[SECTION[k]][n].get("properties"))
            types = VP.entities[n]["props"] if k == "entity" else VP.roles[n]["properties"]
            at = (SECTION[k], n, "properties")
            found = ModelParts(sources[(k, n)], shift=1).props(ps, at, types) if sources[(k, n)] else []
            blocks.setdefault(SECTION[k], []).append({"name": n, "properties": found})
        M = ModelParts(source, shift=1)
        story, operations = story_json(sid, st, fname, VP, M, pins)
        out.append({"number": e["number"], "approved_at": e["approved_at"], "approved_by": e["approved_by"],
                    "because": e.get("because"), "pins": story["pins"],
                    "story": dict(story, file=fname, line=M.line(("stories", sid))),
                    "operations": operations, "entities": blocks.get("entities", []),
                    "roles": blocks.get("roles", []), "line": line})
    return out


def model_of(folder):
    """the model of a project that checks (section 9): every declaration with
    its file and line, every expression with its ast, and the graphs"""
    P = project_of(folder)
    files, epics, roles, entities, stories, operations = [], [], [], [], [], []
    story_versions, snapshots = {}, {}    # (sid) -> [(version, line)]; (kind, name, number) -> (source, block)
    for path in sorted(glob.glob(f"{folder}/*.edda.vc")):
        source, data = load(path)
        stem = os.path.basename(path)[:-8]
        for i, e in enumerate(listing(data)):
            kind = "story" if "story" in e else "entity" if "entity" in e else "role"
            if P.file_of(kind, e[kind]) != stem:
                continue
            if kind == "story":
                story_versions.setdefault(e[kind], []).append((e, source.line((i,))))
            else:
                source, block = snapshot_data(e["text"], kind)
                snapshots[(kind, e[kind], e["number"])] = (source, block[SECTION[kind]][e[kind]])
    for path in sorted(glob.glob(f"{folder}/*.edda")):
        source, data = load(path)
        fname = os.path.basename(path)
        stem = fname[:-5]
        drift = [line for rule, line, _ in flag_problems(data, stem, P, source) if rule == "wording_drift"]
        M = ModelParts(source, drift=drift)
        line = M.line

        props = M.props

        files.append({"name": fname, "history": fname + ".vc" if os.path.exists(path + ".vc") else None,
                      "blocks": [{"kind": k, "name": n, "line": line((s, n)), "status": "approved" if ok else "draft",
                                  "version": v, "pins_stale": stale}
                                 for k, n, s, ok, v, stale, _ in statuses(data, P, source)]})
        for eid, text in mapping(data.get("epics")).items():
            epics.append({"id": eid, "text": text, "file": fname, "line": line(("epics", eid))})
        for rname, r in mapping(data.get("roles")).items():
            roles.append({"name": rname, "is": r["is"], "properties": props(r.get("properties"), ("roles", rname, "properties"), P.roles[rname]["properties"]),
                          "file": fname, "line": line(("roles", rname))})
        for ename, e in mapping(data.get("entities")).items():
            at = ("entities", ename)
            changes = [{"property": p, "line": line(at + ("may_change", p)),
                        "arrows": [{"from": frm, "to": list(tos), "line": line(at + ("may_change", p, frm))}
                                   for frm, tos in mapping(a).items()]}
                       for p, a in mapping(e.get("may_change")).items()]
            ent = {"name": ename, "is": e["is"], "part_of": e.get("part_of"),
                   "part_of_line": line(at + ("part_of",)) if "part_of" in e else None,
                   "properties": props(e.get("properties"), at + ("properties",), P.entities[ename]["props"]),
                   "may_change": changes,
                   "always": [M.fact(f, at + ("always", i)) for i, f in enumerate(listing(e.get("always")))]}
            for key in ("may_create", "may_read", "may_update", "may_delete"):
                ent[key] = M.who(e.get(key), at + (key,))
            entities.append(dict(ent, file=fname, line=line(at)))
        for sid, st in mapping(data.get("stories")).items():
            story, ops = story_json(sid, st, fname, P, M, pins_of(P.newest_version.get(("story", sid)) or {}))
            versions = versions_json(sid, fname, sorted(story_versions.get(sid, []), key=lambda v: v[0]["number"]), snapshots)
            stories.append(dict(story, versions=versions, file=fname, line=line(("stories", sid))))
            operations += ops
    return {"edda_model": MODEL_VERSION, "revision": REVISION, "files": files, "epics": epics, "roles": roles,
            "entities": entities, "stories": stories, "operations": operations,
            "graphs": graphs_of(roles, entities, stories, operations)}


def graphs_of(roles, entities, stories, operations):
    """the four graphs of decision N (Q7) as nodes and edges, each with its
    file and line, from the model's own lists"""
    status = []
    for e in entities:
        for p in e["properties"]:
            c = next((c for c in e["may_change"] if c["property"] == p["name"]), None)
            if c is None:
                continue
            arrows = c["arrows"]      # none for an empty may_change: every value, no arrows
            reached = {p["default"]} | {t for a in arrows for t in a["to"]}
            status.append({
                "entity": e["name"], "property": p["name"], "file": e["file"], "line": p["line"],
                "nodes": [{"value": v, "default": v == p["default"],
                           "unreached": p["default"] is not None and v not in reached, "file": e["file"], "line": p["line"]}
                          for v in p["values"] or []],
                "edges": [{"from": a["from"], "to": t, "file": e["file"], "line": a["line"]} for a in arrows for t in a["to"]]})
    emap = {"nodes": [{"entity": e["name"], "file": e["file"], "line": e["line"]} for e in entities], "edges": []}
    for e in entities:
        for p in e["properties"]:
            if p["entity"]:
                emap["edges"].append({"from": e["name"], "to": p["entity"], "kind": "many" if p["many"] else "reference",
                                      "property": p["name"], "in_order": p["in_order"], "file": e["file"], "line": p["line"]})
        if e["part_of"]:
            emap["edges"].append({"from": e["name"], "to": e["part_of"], "kind": "part_of", "property": None,
                                  "in_order": False, "file": e["file"], "line": e["part_of_line"]})
    about = {s["id"]: s for s in stories}
    who = {"nodes": [{"kind": "role", "name": r["name"], "file": r["file"], "line": r["line"]} for r in roles]
           + [{"kind": "operation", "name": o["name"], "story": o["story"], "file": o["file"], "line": o["line"]} for o in operations]
           + [{"kind": "entity", "name": e["name"], "file": e["file"], "line": e["line"]} for e in entities], "edges": []}
    for o in operations:
        for w in o["who"]:
            who["edges"].append({"from": w["role"], "to": o["name"], "kind": "asks",
                                 "when": w["when"]["text"] if w["when"] else None, "file": o["file"], "line": w["line"]})
        s = about[o["story"]]
        who["edges"].append({"from": o["name"], "to": s["about"], "kind": "about", "when": None,
                             "file": s["file"], "line": s["line"]})
    return {"status_life": status, "entity_map": emap,
            "role_inclusion": {"nodes": [{"role": r["name"], "file": r["file"], "line": r["line"]} for r in roles], "edges": []},
            "who_may": who}


def status_text(g):
    """a status life graph as text, one line per value in declared order"""
    out = []
    for n in g["nodes"]:
        s = n["value"] + (" (default)" if n["default"] else "") + (" (unreached)" if n["unreached"] else "")
        tos = [e["to"] for e in g["edges"] if e["from"] == n["value"]]
        out.append(s + (" -> " + ", ".join(tos) if tos else ""))
    return out


def report(folder):
    """print each file of folder with its problems, flags and status, as the
    checker's own run does for specs/; whether nothing was refused"""
    ok = True
    P = project_of(folder)
    for path in sorted(glob.glob(f"{folder}/*.edda") + glob.glob(f"{folder}/*.edda.vc")):
        src, shape, meaning, history, flags = check(path, P)
        problems = src + shape + meaning + history
        print(os.path.relpath(path, ROOT), "OK" if not problems else "")
        for rule, line, msg in problems:
            ok = False
            print(f"    {line}: {rule}: {msg}")
        for rule, line, msg in flags:
            print(f"    {line}: flagged: {rule}: {msg}")
        if not problems and not path.endswith(".vc") and not history_refused(path, P):
            source, data = load(path)
            for s in status_lines(data, P, source):
                print(f"    {s}")
    return ok


def refused(folder):
    """whether any file of folder has a refusal"""
    P = project_of(folder)
    return any(any(check(path, P)[:4]) for path in sorted(glob.glob(f"{folder}/*.edda") + glob.glob(f"{folder}/*.edda.vc")))


def model_main(args):
    """--model [DIR] and --graph ENTITY.PROPERTY [DIR]; the exit code"""
    folder = os.path.abspath(args[-1] if len(args) == (2 if args[0] == "--model" else 3) else f"{ROOT}/specs")
    if not os.path.isdir(folder):
        print(f"no such folder: {args[-1]}")
        return 1
    if refused(folder):
        report(folder)
        return 1
    model = model_of(folder)
    if args[0] == "--model":
        try:
            print(json.dumps(model, indent=2), flush=True)
        except BrokenPipeError:     # the reader stopped early (| head); the model was whole
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    ename, _, prop = args[1].partition(".")
    g = next((g for g in model["graphs"]["status_life"] if (g["entity"], g["property"]) == (ename, prop)), None)
    if g is None:
        has = any(e["name"] == ename and any(p["name"] == prop for p in e["properties"]) for e in model["entities"])
        print(f"{args[1]} has no may_change" if has else f"no such property: {args[1]}")
        return 1
    if not g["nodes"]:
        print(f"{args[1]} has no known values")
        return 1
    for s in status_text(g):
        print(s)
    return 0


USAGE = "usage: check.py [--model [DIR] | --graph ENTITY.PROPERTY [DIR]]"

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--model"] and len(args) <= 2 or args[:1] == ["--graph"] and 2 <= len(args) <= 3:
        sys.exit(model_main(args))
    if args:
        print(USAGE)
        sys.exit(2)
    ok = report(f"{ROOT}/specs")

    print()
    print("fixtures: which layer catches each file")
    LAYERS = ("source", "shape", "meaning", "history")      # the fourth layer's refusals; its flags are "flagged"
    for folder in sorted(os.listdir(f"{ROOT}/fixtures")):
        FP = project_of(f"{ROOT}/fixtures/{folder}")
        for path in sorted(glob.glob(f"{ROOT}/fixtures/{folder}/*")):
            src, shape, meaning, history, flags = check(path, FP)
            refusals = src + shape + meaning + history
            caught = next((name for name, found in zip(LAYERS, (src, shape, meaning, history)) if found), None)
            label = ("caught by " + caught) if caught else ("flagged" if flags else "passes")
            print(f"  {folder}/{os.path.basename(path)}: {label}")
            for rule, line, msg in refusals:
                print(f"      {line}: {rule}: {msg}")
            for rule, line, msg in flags:
                print(f"      {line}: flagged: {rule}: {msg}")
            if not refusals and not path.endswith(".vc") and not history_refused(path, FP):
                source, data = load(path)
                for s in status_lines(data, FP, source):
                    print(f"      {s}")
    sys.exit(0 if ok else 1)
